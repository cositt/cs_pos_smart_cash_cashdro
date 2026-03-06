# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

import logging
import uuid
from datetime import datetime
from odoo import _
from odoo.exceptions import UserError

from ..gateway_integration import CashdropGatewayIntegration

_logger = logging.getLogger(__name__)


class PaymentMethodIntegration:
    """
    Clase para manejar integración de métodos de pago Cashdrop.
    Ubicada en models para que pos.payment.method pueda importarla en _payment_request_from_kiosk.
    """

    def __init__(self, env, payment_method_id=None):
        self.env = env
        self.payment_method_id = payment_method_id
        self.payment_method = None
        self.gateway = None
        # Usar sudo para acceso a modelos sin restricciones de permiso
        self.transaction_model = env['cashdro.transaction'].sudo()
        self.config_model = env['res.config.settings'].sudo()

        if payment_method_id:
            self.load_payment_method(payment_method_id)

    def load_payment_method(self, payment_method_id):
        # Usar sudo para evitar problemas de permisos en endpoints publicos
        payment_method_model = self.env['pos.payment.method'].sudo()
        payment_method = payment_method_model.browse(payment_method_id)
        if not payment_method.exists():
            raise UserError(_('Método de pago no encontrado'))
        if not payment_method.cashdro_enabled:
            raise UserError(_('Cashdrop no habilitado para este método de pago'))
        self.payment_method = payment_method
        self._initialize_gateway()

    def _initialize_gateway(self):
        if not self.payment_method:
            raise UserError(_('Método de pago no configurado'))
        gateway_url = self.payment_method.get_gateway_url()
        timeout = self.config_model.get_cashdro_config().get('connection_timeout', 10)
        verify_ssl = self.config_model.get_cashdro_config().get('verify_ssl', False)
        log_level = self.config_model.get_cashdro_config().get('log_level', 'INFO')
        # Pasar credenciales al gateway para que las incluya en cada request
        user = self.payment_method.cashdro_user
        password = self.payment_method.cashdro_password
        self.gateway = CashdropGatewayIntegration(
            gateway_url=gateway_url,
            timeout=timeout,
            verify_ssl=verify_ssl,
            log_level=log_level,
            user=user,
            password=password
        )

    def create_transaction(self, order_id=None, amount=None, user_id=None, pos_session_id=None, pos_order_id=None):
        """
        Crear registro de transacción.
        Debe indicarse order_id (sale.order) o pos_order_id (pos.order).
        """
        if amount is None or amount <= 0:
            raise UserError(_('El monto debe ser positivo'))
        if not order_id and not pos_order_id:
            raise UserError(_('Debe indicar order_id o pos_order_id'))
        if user_id is None:
            user_id = self.env.user.id

        transaction_id = str(uuid.uuid4())
        vals = {
            'transaction_id': transaction_id,
            'payment_method_id': self.payment_method.id,
            'amount': amount,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'processing',
            'user_id': user_id,
            'pos_session_id': pos_session_id,
        }
        if pos_order_id:
            vals['pos_order_id'] = pos_order_id
        if order_id:
            vals['order_id'] = order_id

        try:
            transaction = self.transaction_model.create(vals)
            _logger.info("Transacción creada: %s (ID=%s)", transaction.name, transaction_id)
            return transaction
        except Exception as e:
            _logger.error("Error creando transacción: %s", e)
            raise UserError(_('Error creando transacción: %s') % str(e))

    def start_payment(self, transaction, user_credentials=None):
        if not self.gateway:
            self._initialize_gateway()
        try:
            # Las credenciales ya se envían con cada request del gateway
            # Monto en EUR: el gateway envía amount en céntimos vía parameters (API 3WS)
            response = self.gateway.start_operation(transaction.amount)
            # El gateway retorna {code, data, operation_id} donde operation_id se extrajo de data
            operation_id = response.get('operation_id')
            transaction.write({'operation_id': operation_id, 'response_data': response})
            _logger.info("Pago iniciado: %s, operation_id=%s", transaction.name, operation_id)
            return {
                'success': True,
                'operation_id': operation_id,
                'transaction_id': transaction.transaction_id,
                'message': _('Pago iniciado, esperando inserción de dinero')
            }
        except Exception as e:
            transaction.mark_error(str(e))
            raise UserError(_('Error iniciando pago: %s') % str(e))

    def confirm_payment(self, transaction):
        if not transaction.operation_id:
            raise UserError(_('No hay operación en progreso'))
        if not self.gateway:
            self._initialize_gateway()
        try:
            self.gateway.acknowledge_operation_id(transaction.operation_id)
            polling_config = self.config_model.get_cashdro_config()
            response = self.gateway.ask_operation_with_polling(
                transaction.operation_id,
                polling_timeout=polling_config.get('polling_timeout', 60),
                polling_interval=polling_config.get('polling_interval', 500),
                max_retries=polling_config.get('max_retries', 3)
            )
            transaction.update_from_gateway_response(response)
            if transaction.is_confirmed():
                transaction.action_confirm()
            _logger.info("Pago confirmado: %s", transaction.name)
            return {
                'success': True,
                'transaction_id': transaction.transaction_id,
                'amount_received': transaction.amount_received,
                'message': _('Pago confirmado')
            }
        except Exception as e:
            transaction.mark_error(str(e))
            raise UserError(_('Error confirmando pago: %s') % str(e))

    def cancel_payment(self, transaction):
        if not transaction.operation_id:
            raise UserError(_('No hay operación en progreso'))
        if transaction.status not in ['processing', 'error']:
            raise UserError(_('Solo se pueden cancelar pagos en proceso'))
        if not self.gateway:
            self._initialize_gateway()
        try:
            response = self.gateway.finish_operation(transaction.operation_id)
            transaction.update_from_gateway_response(response)
            transaction.action_cancel()
            _logger.info("Pago cancelado: %s", transaction.name)
            return {
                'success': True,
                'transaction_id': transaction.transaction_id,
                'message': _('Pago cancelado')
            }
        except Exception as e:
            raise UserError(_('Error cancelando pago: %s') % str(e))

    def get_payment_status(self, transaction):
        if not transaction.operation_id:
            return {'status': transaction.status, 'message': _('Sin operación en progreso')}
        if not self.gateway:
            self._initialize_gateway()
        try:
            response = self.gateway.ask_operation(transaction.operation_id)
            state = None
            amount_received = None
            if 'data' in response:
                import json
                data = response['data']
                if isinstance(data, str):
                    data = json.loads(data)
                if isinstance(data, dict) and 'operation' in data:
                    op = data['operation']
                    state = op.get('state')
                    amount_received = op.get('totalin', 0) / 100
            return {
                'status': transaction.status,
                'operation_id': transaction.operation_id,
                'state': state,
                'amount_received': amount_received,
                'message': _('Estado obtenido')
            }
        except Exception as e:
            raise UserError(_('Error obteniendo estado: %s') % str(e))

    def validate_configuration(self):
        errors = []
        if not self.payment_method:
            return {'valid': False, 'errors': [_('Método de pago no configurado')]}
        if not self.payment_method.cashdro_enabled:
            errors.append(_('Cashdrop no habilitado'))
        if not self.payment_method.cashdro_host:
            errors.append(_('Host de Cashdrop no configurado'))
        if not self.payment_method.cashdro_user:
            errors.append(_('Usuario de Cashdrop no configurado'))
        if not self.payment_method.cashdro_password:
            errors.append(_('Contraseña de Cashdrop no configurada'))
        return {'valid': len(errors) == 0, 'errors': errors}

    def test_gateway_connection(self):
        try:
            if not self.gateway:
                self._initialize_gateway()
            return self.gateway.get_connection_status()
        except Exception as e:
            return {'connected': False, 'message': str(e), 'timestamp': datetime.now().isoformat()}
