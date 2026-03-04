# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import requests
import logging

from .payment_method_integration import PaymentMethodIntegration

_logger = logging.getLogger(__name__)


class PosPaymentMethod(models.Model):
    """Extensión de pos.payment.method para soportar Cashdrop"""
    
    _inherit = 'pos.payment.method'
    
    # ========================
    # CAMPOS DE CONFIGURACIÓN
    # ========================
    
    cashdro_enabled = fields.Boolean(
        string='Habilitar Cashdrop',
        default=False,
        help='Activar este método de pago como terminal Cashdrop'
    )
    
    cashdro_host = fields.Char(
        string='Host/IP de Cashdrop',
        help='IP o hostname de la máquina Cashdrop (ej: 10.0.1.140)'
    )
    
    cashdro_user = fields.Char(
        string='Usuario Cashdrop',
        help='Usuario para autenticación en Cashdrop (ej: admin)'
    )
    
    cashdro_password = fields.Char(
        string='Contraseña Cashdrop',
        help='Contraseña para autenticación en Cashdrop'
    )
    
    cashdro_gateway_url = fields.Char(
        string='URL del Gateway',
        default='http://localhost:5000',
        help='URL del gateway Flask (ej: http://localhost:5000)'
    )
    
    cashdro_connection_status = fields.Selection(
        selection=[
            ('not_tested', 'No probado'),
            ('connected', 'Conectado'),
            ('disconnected', 'Desconectado'),
            ('error', 'Error')
        ],
        default='not_tested',
        readonly=True,
        help='Estado de la conexión con Cashdrop'
    )
    
    cashdro_last_check = fields.Datetime(
        string='Último chequeo',
        readonly=True,
        help='Timestamp del último test de conexión'
    )
    
    cashdro_error_message = fields.Text(
        string='Mensaje de error',
        readonly=True,
        help='Detalle del último error de conexión'
    )
    
    # ========================
    # VALIDACIONES
    # ========================
    
    @api.constrains('cashdro_enabled', 'cashdro_host', 'cashdro_user', 'cashdro_password')
    def _check_cashdro_config(self):
        """Validar configuración de Cashdrop si está habilitado"""
        for record in self:
            if record.cashdro_enabled:
                if not record.cashdro_host:
                    raise ValidationError(
                        _('El Host/IP de Cashdrop es requerido cuando Cashdrop está habilitado')
                    )
                if not record.cashdro_user:
                    raise ValidationError(
                        _('El Usuario de Cashdrop es requerido cuando Cashdrop está habilitado')
                    )
                if not record.cashdro_password:
                    raise ValidationError(
                        _('La Contraseña de Cashdrop es requerida cuando Cashdrop está habilitado')
                    )
    
    # ========================
    # MÉTODOS DE INTEGRACIÓN
    # ========================
    
    def validate_connection(self):
        """
        Valida la conexión con Cashdrop
        Prueba conectividad con la máquina real
        """
        self.ensure_one()
        
        if not self.cashdro_enabled:
            raise ValidationError(_('Cashdrop no está habilitado para este método de pago'))
        
        try:
            _logger.info(f"Validando conexión con Cashdrop en {self.cashdro_host}")
            
            # Construir URL de prueba
            url = f"https://{self.cashdro_host}/Cashdro3WS/index.php"
            params = {
                'name': self.cashdro_user,
                'password': self.cashdro_password,
                'operation': 'login'
            }
            
            # Realizar petición
            response = requests.get(
                url,
                params=params,
                timeout=5,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verificar respuesta
                if data.get('code') == 1:
                    self.cashdro_connection_status = 'connected'
                    self.cashdro_error_message = False
                    _logger.info("✅ Conexión con Cashdrop exitosa")
                    return True
                else:
                    self.cashdro_connection_status = 'error'
                    self.cashdro_error_message = f"Respuesta inválida: code={data.get('code')}"
                    _logger.warning(self.cashdro_error_message)
                    raise ValidationError(
                        _('Respuesta inválida de Cashdrop: %s') % self.cashdro_error_message
                    )
            else:
                self.cashdro_connection_status = 'error'
                self.cashdro_error_message = f"HTTP {response.status_code}"
                raise ValidationError(
                    _('Error HTTP %s al conectar con Cashdrop') % response.status_code
                )
        
        except requests.Timeout:
            self.cashdro_connection_status = 'error'
            self.cashdro_error_message = "Timeout - Cashdrop no responde"
            _logger.error(self.cashdro_error_message)
            raise ValidationError(_('Timeout: Cashdrop no responde. Verifica IP y conectividad'))
        
        except requests.ConnectionError as e:
            self.cashdro_connection_status = 'disconnected'
            self.cashdro_error_message = f"Conexión rechazada: {str(e)}"
            _logger.error(self.cashdro_error_message)
            raise ValidationError(
                _('No se puede conectar a Cashdrop en %s. Verifica que el host sea correcto') % self.cashdro_host
            )
        
        except Exception as e:
            self.cashdro_connection_status = 'error'
            self.cashdro_error_message = str(e)
            _logger.error(f"Error validando conexión: {e}")
            raise ValidationError(_('Error al validar conexión: %s') % str(e))
    
    def get_gateway_url(self):
        """Retorna la URL del gateway"""
        self.ensure_one()
        return self.cashdro_gateway_url or 'http://localhost:5000'
    
    def is_cashdrop_enabled(self):
        """Verifica si Cashdrop está habilitado"""
        return self.cashdro_enabled and self.cashdro_connection_status == 'connected'
    
    # ========================
    # ACCIONES
    # ========================
    
    def action_test_connection(self):
        """Acción para probar conexión desde UI"""
        self.validate_connection()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Éxito'),
                'message': _('Conexión con Cashdrop validada correctamente'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _payment_request_from_kiosk(self, order):
        """
        Override: Procesar pago Cashdrop en kiosk.
        Si es Cashdrop: inicia el pago y devuelve status 'pending' (no tramitar orden aún).
        Si es otro método: devuelve success para flujo normal.
        """
        # No es Cashdrop: flujo normal
        if self.name != 'Cashdrop' or not self.journal_id or self.journal_id.name != 'Cashdrop':
            return {
                'payment_method': self.name,
                'status': 'success',
                'is_cashdrop': False,
                'message': _('Esperando pago en %s') % self.name,
            }

        try:
            integration = PaymentMethodIntegration(self.env, payment_method_id=self.id)
            validation = integration.validate_configuration()
            if not validation['valid']:
                msg = '; '.join(validation['errors'])
                return {
                    'payment_method': self.name,
                    'status': 'error',
                    'is_cashdrop': True,
                    'message': _('Error de configuración: %s') % msg,
                }

            transaction = integration.create_transaction(
                amount=order.amount_total,
                user_id=self.env.user.id,
                pos_session_id=order.session_id.id if order.session_id else None,
                pos_order_id=order.id,
            )
            result = integration.start_payment(transaction, user_credentials=None)

            if not result.get('success'):
                return {
                    'payment_method': self.name,
                    'status': 'error',
                    'is_cashdrop': True,
                    'message': result.get('error', _('Error al iniciar pago en Cashdrop')),
                }

            return {
                'payment_method': self.name,
                'status': 'pending',
                'is_cashdrop': True,
                'transaction_id': transaction.transaction_id,
                'operation_id': result.get('operation_id'),
                'message': _('Esperando confirmación de pago en Cashdrop...'),
            }
        except Exception as e:
            _logger.exception("Kiosk Cashdrop payment error")
            return {
                'payment_method': self.name,
                'status': 'error',
                'is_cashdrop': True,
                'message': str(e),
            }

    def action_get_payment_info(self):
        """Obtiene información de disponibilidad de piezas de Cashdrop"""
        self.ensure_one()
        
        if not self.is_cashdrop_enabled():
            raise ValidationError(_('Cashdrop no está disponible o no conectado'))
        
        try:
            url = f"https://{self.cashdro_host}/Cashdro3WS/index.php"
            params = {
                'name': self.cashdro_user,
                'password': self.cashdro_password,
                'operation': 'getPiecesCurrency',
                'currencyId': 'EUR',
                'includeImages': '0',
                'includeLevels': '1'
            }
            
            response = requests.get(url, params=params, timeout=5, verify=False)
            response.raise_for_status()
            
            data = response.json()
            _logger.info(f"Información de piezas obtenida: {len(data.get('data', []))} piezas")
            
            return data
        
        except Exception as e:
            _logger.error(f"Error obteniendo información de piezas: {e}")
            raise ValidationError(_('Error obteniendo información: %s') % str(e))
