# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from odoo.fields import Domain
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

    cashdro_deposit_levels_json = fields.Text(
        string='Configuración fianza (última enviada)',
        help='JSON de la última configuración enviada con Configurar fianza (setDepositLevels). '
             'Se usa para mostrar Estado de fianza: Nivel fianza, reciclador y faltante.'
    )

    # ========================
    # TERMINAL POS: use_payment_terminal = 'cashdro' / 'cashdro_refund'
    # ========================
    # Para que la caja registradora use el interface de pago CashDro al pulsar
    # el método (ej. Efectivisimo), debe aparecer en la selección y asignarse al marcar cashdro_enabled.
    # Añadimos 'cashdro_refund' como terminal opcional para reembolsos, sin alterar el comportamiento de 'cashdro'.
    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [
            ('cashdro', 'CashDro'),
            ('cashdro_refund', 'CashDro (Reembolso)'),
        ]

    @api.onchange('cashdro_enabled')
    def _onchange_cashdro_enabled(self):
        if self.cashdro_enabled:
            if self.use_payment_terminal != 'cashdro_refund':
                self.use_payment_terminal = 'cashdro'
            self.payment_method_type = 'terminal'

    # ========================
    # CARGA POS (caja): enviar use_payment_terminal = 'cashdro' si cashdro_enabled
    # ========================
    # Así el front siempre recibe el terminal aunque la sesión se abrió antes de guardar el método.
    @api.model
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        if 'cashdro_enabled' not in fields:
            fields = list(fields) + ['cashdro_enabled']
        return fields

    @api.model
    def _load_pos_data_read(self, records, config):
        result = super()._load_pos_data_read(records, config)
        # Construir mapa id -> record para saber cuáles tienen cashdro_enabled
        id_to_record = {r.id: r for r in records}
        for row in result:
            rec = id_to_record.get(row.get('id'))
            # Si cashdro habilitado: cobro usa 'cashdro', reembolso usa 'cashdro_refund' (no sobrescribir).
            if rec and getattr(rec, 'cashdro_enabled', False):
                terminal = getattr(rec, 'use_payment_terminal', None) or row.get('use_payment_terminal')
                row['use_payment_terminal'] = 'cashdro_refund' if terminal == 'cashdro_refund' else 'cashdro'
                row['payment_method_type'] = 'terminal'
                row['cashdro_enabled'] = True
        return result

    # ========================
    # is_cash_count: no contar como efectivo en quiosco
    # ========================
    # El core pos_self_order bloquea métodos con is_cash_count en modo quiosco.
    # Para "Efectivo cashdro" no hay casilla en la UI (is_cash_count es computado por type=='cash').
    # Override: si cashdro_enabled, is_cash_count=False para que el constraint no bloquee.
    @api.depends('type', 'cashdro_enabled')
    def _compute_is_cash_count(self):
        for pm in self:
            if getattr(pm, 'cashdro_enabled', False):
                pm.is_cash_count = False
            else:
                pm.is_cash_count = pm.type == 'cash'

    # ========================
    # CARGA DE DATOS EN QUIOSCO (pos_self_order)
    # ========================
    # El core pos_self_order devuelve dominio vacío [('id', '=', False)] para métodos de pago,
    # así el kiosk no recibe ninguno y la orden se confirma sin pasar por caja. Aquí enviamos
    # explícitamente TODOS los métodos de pago del POS en modo quiosco (incluido Efectivo cashdro),
    # y dejamos el dominio original para el resto de modos (móvil, consulta).
    @api.model
    def _load_pos_self_data_domain(self, data, config):
        if config.self_ordering_mode == "kiosk":
            # En kiosk: devolver exactamente los métodos de pago configurados en el POS.
            return [("id", "in", config.payment_method_ids.ids)]
        # Otros modos: respetar el comportamiento estándar de pos_self_order.
        return super()._load_pos_self_data_domain(data, config)

    @api.model
    def _load_pos_self_data_fields(self, config):
        fields = super()._load_pos_self_data_fields(config)
        if config.self_ordering_mode == "kiosk":
            if "cashdro_enabled" not in fields:
                fields = list(fields) + ["cashdro_enabled"]
        return fields

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
        # Si el método de pago tiene URL, usarla; si no, usar la configuración global
        url = None
        
        if self.cashdro_gateway_url and self.cashdro_gateway_url != 'http://localhost:5000':
            url = self.cashdro_gateway_url
        else:
            # Obtener de configuración global
            config = self.env['res.config.settings'].sudo().get_cashdro_config()
            url = config.get('gateway_url') if config else None
        
        # Si no hay nada, usar default
        if not url:
            url = 'https://10.0.1.140'  # Default a la máquina Cashdrop real
        
        # Asegurar que la URL tenga protocolo
        if url and not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        return url
    
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
        Si es un método CashDro: inicia el pago y devuelve status 'pending' (no tramitar orden aún).
        Si es otro método: devuelve success para flujo normal.
        """
        # No es CashDro (no está habilitado): flujo normal
        if not getattr(self, "cashdro_enabled", False):
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
