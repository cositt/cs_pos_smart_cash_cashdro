# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

import logging
import uuid
from datetime import datetime
from odoo import _
from odoo.exceptions import UserError, ValidationError
from .gateway_integration import CashdropGatewayIntegration

_logger = logging.getLogger(__name__)


class PaymentMethodIntegration:
    """
    Clase para manejar integración de métodos de pago Cashdrop
    
    Coordina entre modelos Odoo y gateway Cashdrop.
    """
    
    def __init__(self, env, payment_method_id=None):
        """
        Inicializar integración de método de pago
        
        Args:
            env: Entorno Odoo
            payment_method_id: ID del método de pago (opcional)
        """
        self.env = env
        self.payment_method_id = payment_method_id
        self.payment_method = None
        self.gateway = None
        self.transaction_model = env['cashdro.transaction']
        self.config_model = env['res.config.settings']
        
        if payment_method_id:
            self.load_payment_method(payment_method_id)
    
    # ========================
    # CARGA Y CONFIGURACIÓN
    # ========================
    
    def load_payment_method(self, payment_method_id):
        """
        Cargar método de pago y validar configuración
        
        Args:
            payment_method_id: ID del método de pago
            
        Raises:
            UserError: Si el método no existe o no está configurado
        """
        payment_method = self.env['pos.payment.method'].browse(payment_method_id)
        
        if not payment_method.exists():
            raise UserError(_('Método de pago no encontrado'))
        
        if not payment_method.cashdro_enabled:
            raise UserError(_('Cashdrop no habilitado para este método de pago'))
        
        self.payment_method = payment_method
        self._initialize_gateway()
    
    def _initialize_gateway(self):
        """Inicializar cliente del gateway con configuración del método"""
        if not self.payment_method:
            raise UserError(_('Método de pago no configurado'))
        
        gateway_url = self.payment_method.get_gateway_url()
        timeout = self.config_model.get_cashdro_config().get('connection_timeout', 10)
        verify_ssl = self.config_model.get_cashdro_config().get('verify_ssl', False)
        log_level = self.config_model.get_cashdro_config().get('log_level', 'INFO')
        
        self.gateway = CashdropGatewayIntegration(
            gateway_url=gateway_url,
            timeout=timeout,
            verify_ssl=verify_ssl,
            log_level=log_level
        )
    
    # ========================
    # TRANSACCIONES
    # ========================
    
    def create_transaction(self, order_id, amount, user_id=None, pos_session_id=None):
        """
        Crear registro de transacción
        
        Args:
            order_id: ID de orden de venta
            amount (float): Monto en EUR
            user_id: ID de usuario (opcional, usa usuario actual)
            pos_session_id: ID de sesión POS (opcional)
            
        Returns:
            cashdro.transaction: Modelo de transacción creado
            
        Raises:
            UserError: Si hay error en validación
        """
        if amount <= 0:
            raise UserError(_('El monto debe ser positivo'))
        
        if not user_id:
            user_id = self.env.user.id
        
        transaction_id = str(uuid.uuid4())
        
        try:
            transaction = self.transaction_model.create({
                'transaction_id': transaction_id,
                'order_id': order_id,
                'payment_method_id': self.payment_method.id,
                'amount': amount,
                'currency_id': self.env.ref('base.EUR').id,
                'status': 'processing',
                'user_id': user_id,
                'pos_session_id': pos_session_id
            })
            
            _logger.info(f"Transacción creada: {transaction.name} (ID={transaction_id})")
            return transaction
        
        except Exception as e:
            msg = _('Error creando transacción: %s') % str(e)
            _logger.error(msg)
            raise UserError(msg)
    
    def start_payment(self, transaction, user_credentials=None):
        """
        Iniciar pago en Cashdrop
        
        Args:
            transaction: Modelo cashdro.transaction
            user_credentials (dict): {'user': '', 'password': ''} (opcional)
            
        Returns:
            dict: {'success': bool, 'operation_id': str, 'message': str}
            
        Raises:
            UserError: Si falla la operación
        """
        if not self.gateway:
            self._initialize_gateway()
        
        try:
            # Validar credenciales si se proporcionan
            if user_credentials:
                self.gateway.login(
                    user_credentials.get('user'),
                    user_credentials.get('password')
                )
            
            # Iniciar operación (amount en centavos)
            amount_centavos = int(transaction.amount * 100)
            response = self.gateway.start_operation(amount_centavos)
            operation_id = response.get('operation_id')
            
            # Guardar operation_id en transacción
            transaction.write({
                'operation_id': operation_id,
                'response_data': response
            })
            
            _logger.info(f"Pago iniciado: {transaction.name}, operation_id={operation_id}")
            
            return {
                'success': True,
                'operation_id': operation_id,
                'transaction_id': transaction.transaction_id,
                'message': _('Pago iniciado, esperando inserción de dinero')
            }
        
        except Exception as e:
            transaction.mark_error(str(e))
            msg = _('Error iniciando pago: %s') % str(e)
            _logger.error(msg)
            raise UserError(msg)
    
    def confirm_payment(self, transaction):
        """
        Confirmar pago en Cashdrop y en Odoo
        
        Args:
            transaction: Modelo cashdro.transaction
            
        Returns:
            dict: Respuesta de confirmación
            
        Raises:
            UserError: Si falla
        """
        if not transaction.operation_id:
            raise UserError(_('No hay operación en progreso'))
        
        if not self.gateway:
            self._initialize_gateway()
        
        try:
            # Reconocer operación
            self.gateway.acknowledge_operation_id(transaction.operation_id)
            
            # Polling hasta completar
            polling_config = self.config_model.get_cashdro_config()
            response = self.gateway.ask_operation_with_polling(
                transaction.operation_id,
                polling_timeout=polling_config.get('polling_timeout', 60),
                polling_interval=polling_config.get('polling_interval', 500),
                max_retries=polling_config.get('max_retries', 3)
            )
            
            # Actualizar transacción con respuesta
            transaction.update_from_gateway_response(response)
            
            # Confirmar en Odoo
            if transaction.is_confirmed():
                transaction.action_confirm()
            
            _logger.info(f"Pago confirmado: {transaction.name}")
            
            return {
                'success': True,
                'transaction_id': transaction.transaction_id,
                'amount_received': transaction.amount_received,
                'message': _('Pago confirmado')
            }
        
        except Exception as e:
            transaction.mark_error(str(e))
            msg = _('Error confirmando pago: %s') % str(e)
            _logger.error(msg)
            raise UserError(msg)
    
    def cancel_payment(self, transaction):
        """
        Cancelar pago en Cashdrop y en Odoo
        
        Args:
            transaction: Modelo cashdro.transaction
            
        Returns:
            dict: Respuesta de cancelación
            
        Raises:
            UserError: Si falla
        """
        if not transaction.operation_id:
            raise UserError(_('No hay operación en progreso'))
        
        if transaction.status not in ['processing', 'error']:
            raise UserError(_('Solo se pueden cancelar pagos en proceso'))
        
        if not self.gateway:
            self._initialize_gateway()
        
        try:
            # Finalizar operación en Cashdrop
            response = self.gateway.finish_operation(transaction.operation_id)
            
            # Actualizar transacción
            transaction.update_from_gateway_response(response)
            transaction.action_cancel()
            
            _logger.info(f"Pago cancelado: {transaction.name}")
            
            return {
                'success': True,
                'transaction_id': transaction.transaction_id,
                'message': _('Pago cancelado')
            }
        
        except Exception as e:
            msg = _('Error cancelando pago: %s') % str(e)
            _logger.error(msg)
            raise UserError(msg)
    
    def get_payment_status(self, transaction):
        """
        Obtener estado actual del pago
        
        Args:
            transaction: Modelo cashdro.transaction
            
        Returns:
            dict: Estado del pago
            
        Raises:
            UserError: Si falla
        """
        if not transaction.operation_id:
            return {
                'status': transaction.status,
                'message': _('Sin operación en progreso')
            }
        
        if not self.gateway:
            self._initialize_gateway()
        
        try:
            response = self.gateway.ask_operation(transaction.operation_id)
            
            # Parsear estado
            state = None
            amount_received = None
            
            if 'data' in response:
                import json
                data = response['data']
                if isinstance(data, str):
                    data = json.loads(data)
                
                if isinstance(data, dict) and 'operation' in data:
                    operation = data['operation']
                    state = operation.get('state')
                    amount_received = operation.get('totalin', 0) / 100
            
            return {
                'status': transaction.status,
                'operation_id': transaction.operation_id,
                'state': state,
                'amount_received': amount_received,
                'message': _('Estado obtenido')
            }
        
        except Exception as e:
            msg = _('Error obteniendo estado: %s') % str(e)
            _logger.error(msg)
            raise UserError(msg)
    
    # ========================
    # VALIDACIONES
    # ========================
    
    def validate_configuration(self):
        """
        Validar configuración del método de pago
        
        Returns:
            dict: {'valid': bool, 'errors': [str]}
        """
        errors = []
        
        if not self.payment_method:
            errors.append(_('Método de pago no configurado'))
            return {'valid': False, 'errors': errors}
        
        if not self.payment_method.cashdro_enabled:
            errors.append(_('Cashdrop no habilitado'))
        
        if not self.payment_method.cashdro_host:
            errors.append(_('Host de Cashdrop no configurado'))
        
        if not self.payment_method.cashdro_user:
            errors.append(_('Usuario de Cashdrop no configurado'))
        
        if not self.payment_method.cashdro_password:
            errors.append(_('Contraseña de Cashdrop no configurada'))
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def test_gateway_connection(self):
        """
        Probar conexión con gateway
        
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            if not self.gateway:
                self._initialize_gateway()
            
            status = self.gateway.get_connection_status()
            return status
        
        except Exception as e:
            return {
                'connected': False,
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
