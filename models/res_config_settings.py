# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    """Modelo para configuración global de Cashdrop"""
    
    _inherit = 'res.config.settings'
    
    # ========================
    # CONFIGURACIÓN GENERAL
    # ========================
    
    cashdro_enabled = fields.Boolean(
        string='Habilitar Cashdrop',
        config_parameter='cs_pos_smart_cash_cashdro.cashdro_enabled',
        help='Activar integración con máquinas Cashdrop'
    )
    
    cashdro_default_gateway_url = fields.Char(
        string='URL Gateway por Defecto',
        config_parameter='cs_pos_smart_cash_cashdro.cashdro_default_gateway_url',
        help='URL del gateway Cashdrop por defecto (ej: https://10.0.1.140)'
    )
    
    # ========================
    # CONFIGURACIÓN DE COMUNICACIÓN
    # ========================
    
    cashdro_connection_timeout = fields.Integer(
        string='Timeout de Conexión (segundos)',
        config_parameter='cs_pos_smart_cash_cashdro.cashdro_connection_timeout',
        default=10,
        help='Tiempo máximo de espera para conexión a Cashdrop'
    )
    
    cashdro_polling_timeout = fields.Integer(
        string='Timeout de Polling (segundos)',
        config_parameter='cs_pos_smart_cash_cashdro.cashdro_polling_timeout',
        default=60,
        help='Tiempo máximo de espera en polling de operaciones'
    )
    
    cashdro_polling_interval = fields.Integer(
        string='Intervalo de Polling (milisegundos)',
        config_parameter='cs_pos_smart_cash_cashdro.cashdro_polling_interval',
        default=500,
        help='Intervalo entre intentos de polling'
    )
    
    cashdro_verify_ssl = fields.Boolean(
        string='Verificar Certificado SSL',
        config_parameter='cs_pos_smart_cash_cashdro.cashdro_verify_ssl',
        default=False,
        help='Verificar certificado SSL en conexiones HTTPS (False para desarrollo)'
    )
    
    # ========================
    # CONFIGURACIÓN DE REINTENTOS
    # ========================
    
    cashdro_max_retries = fields.Integer(
        string='Máximo de Reintentos',
        config_parameter='cs_pos_smart_cash_cashdro.cashdro_max_retries',
        default=3,
        help='Número máximo de reintentos en caso de error'
    )
    
    cashdro_retry_delay = fields.Integer(
        string='Delay entre Reintentos (segundos)',
        config_parameter='cs_pos_smart_cash_cashdro.cashdro_retry_delay',
        default=2,
        help='Tiempo de espera entre reintentos'
    )
    
    # ========================
    # CONFIGURACIÓN DE OPERACIONES
    # ========================
    
    cashdro_auto_confirm_payments = fields.Boolean(
        string='Confirmar Pagos Automáticamente',
        config_parameter='cs_pos_smart_cash_cashdro.cashdro_auto_confirm_payments',
        default=True,
        help='Confirmar transacciones automáticamente cuando se complete el pago'
    )
    
    cashdro_log_level = fields.Selection(
        selection=[
            ('DEBUG', 'Debug'),
            ('INFO', 'Info'),
            ('WARNING', 'Advertencia'),
            ('ERROR', 'Error'),
            ('CRITICAL', 'Crítico')
        ],
        string='Nivel de Log',
        config_parameter='cs_pos_smart_cash_cashdro.cashdro_log_level',
        default='INFO',
        help='Nivel de detalle de logs para Cashdrop'
    )
    
    # ========================
    # CONFIGURACIÓN AVANZADA
    # ========================
    
    cashdro_enable_test_mode = fields.Boolean(
        string='Modo de Prueba',
        config_parameter='cs_pos_smart_cash_cashdro.cashdro_enable_test_mode',
        default=False,
        help='Activar modo de prueba con logs detallados'
    )
    
    cashdro_keep_transaction_logs = fields.Boolean(
        string='Guardar Logs de Transacciones',
        config_parameter='cs_pos_smart_cash_cashdro.cashdro_keep_transaction_logs',
        default=True,
        help='Guardar logs completos de respuestas de Cashdrop'
    )
    
    cashdro_transaction_retention_days = fields.Integer(
        string='Retención de Transacciones (días)',
        config_parameter='cs_pos_smart_cash_cashdro.cashdro_transaction_retention_days',
        default=90,
        help='Días para mantener registros de transacciones (0 = indefinido)'
    )
    
    # ========================
    # VALIDACIONES
    # ========================
    
    @api.constrains('cashdro_connection_timeout')
    def _check_connection_timeout(self):
        """Validar timeout de conexión"""
        for record in self:
            if record.cashdro_connection_timeout <= 0:
                raise ValidationError(
                    _('El timeout de conexión debe ser mayor a 0 segundos')
                )
    
    @api.constrains('cashdro_polling_timeout')
    def _check_polling_timeout(self):
        """Validar timeout de polling"""
        for record in self:
            if record.cashdro_polling_timeout <= 0:
                raise ValidationError(
                    _('El timeout de polling debe ser mayor a 0 segundos')
                )
    
    @api.constrains('cashdro_polling_interval')
    def _check_polling_interval(self):
        """Validar intervalo de polling"""
        for record in self:
            if record.cashdro_polling_interval <= 0:
                raise ValidationError(
                    _('El intervalo de polling debe ser mayor a 0 ms')
                )
    
    @api.constrains('cashdro_max_retries')
    def _check_max_retries(self):
        """Validar máximo de reintentos"""
        for record in self:
            if record.cashdro_max_retries < 0:
                raise ValidationError(
                    _('El máximo de reintentos no puede ser negativo')
                )
    
    @api.constrains('cashdro_retry_delay')
    def _check_retry_delay(self):
        """Validar delay entre reintentos"""
        for record in self:
            if record.cashdro_retry_delay < 0:
                raise ValidationError(
                    _('El delay entre reintentos no puede ser negativo')
                )
    
    @api.constrains('cashdro_transaction_retention_days')
    def _check_transaction_retention_days(self):
        """Validar días de retención"""
        for record in self:
            if record.cashdro_transaction_retention_days < 0:
                raise ValidationError(
                    _('Los días de retención no pueden ser negativos')
                )
    
    # ========================
    # MÉTODOS DE VALIDACIÓN
    # ========================
    
    def test_cashdro_connection(self):
        """
        Probar conexión con Cashdrop usando URL por defecto
        
        Returns:
            dict: Resultado de prueba {'success': bool, 'message': str}
        """
        try:
            import requests
            
            url = self.cashdro_default_gateway_url
            if not url:
                return {
                    'success': False,
                    'message': _('No hay URL de gateway configurada')
                }
            
            # Construir URL de login
            login_url = f"{url}/Cashdro3WS/index.php?operation=login"
            
            response = requests.get(
                login_url,
                timeout=self.cashdro_connection_timeout,
                verify=self.cashdro_verify_ssl
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': _('Conexión exitosa a Cashdrop')
                }
            else:
                return {
                    'success': False,
                    'message': _('Cashdrop respondió con código %d') % response.status_code
                }
        
        except Exception as e:
            _logger.error(f"Error probando conexión a Cashdrop: {e}")
            return {
                'success': False,
                'message': _('Error de conexión: %s') % str(e)
            }
    
    def action_test_connection(self):
        """Acción para probar conexión desde UI"""
        result = self.test_cashdro_connection()
        message = result.get('message', '')
        
        if result.get('success'):
            _logger.info(f"Prueba de conexión exitosa: {message}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Éxito'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            _logger.warning(f"Prueba de conexión fallida: {message}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': message,
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    # ========================
    # GETTERS PARA CONFIGURACIÓN
    # ========================
    
    @api.model
    def get_cashdro_config(self):
        """
        Obtener toda la configuración de Cashdrop
        
        Returns:
            dict: Configuración actual
        """
        settings = self.search([], limit=1)
        if not settings:
            settings = self.create({})
        
        return {
            'enabled': settings.cashdro_enabled,
            'gateway_url': settings.cashdro_default_gateway_url,
            'connection_timeout': settings.cashdro_connection_timeout,
            'polling_timeout': settings.cashdro_polling_timeout,
            'polling_interval': settings.cashdro_polling_interval,
            'verify_ssl': settings.cashdro_verify_ssl,
            'max_retries': settings.cashdro_max_retries,
            'retry_delay': settings.cashdro_retry_delay,
            'auto_confirm': settings.cashdro_auto_confirm_payments,
            'log_level': settings.cashdro_log_level,
            'test_mode': settings.cashdro_enable_test_mode,
            'keep_logs': settings.cashdro_keep_transaction_logs,
            'retention_days': settings.cashdro_transaction_retention_days,
        }
    
    @api.model
    def is_cashdro_enabled(self):
        """¿Está habilitado Cashdrop globalmente?"""
        config = self.get_cashdro_config()
        return config.get('enabled', False)
