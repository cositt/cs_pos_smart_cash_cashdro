# -*- coding: utf-8 -*-
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CashdroConfigWizard(models.TransientModel):
    """Wizard simple de configuración Cashdrop.

    Nota: Este wizard existe principalmente por compatibilidad con despliegues
    que referencian `wizard/cashdro_config_wizard_views.xml`.

    Persiste en ir.config_parameter (igual que res.config.settings).
    """

    _name = 'cashdro.config.wizard'
    _description = 'Cashdrop Config Wizard'

    cashdro_enabled = fields.Boolean(string='Habilitar Cashdrop')
    cashdro_default_gateway_url = fields.Char(string='URL Gateway por Defecto')
    cashdro_connection_timeout = fields.Integer(string='Timeout Conexión (s)', default=10)
    cashdro_polling_timeout = fields.Integer(string='Timeout Polling (s)', default=60)
    cashdro_polling_interval = fields.Integer(string='Intervalo Polling (ms)', default=500)
    cashdro_verify_ssl = fields.Boolean(string='Verificar SSL', default=False)
    cashdro_max_retries = fields.Integer(string='Máx. Reintentos', default=3)
    cashdro_retry_delay = fields.Integer(string='Delay Reintentos (s)', default=2)
    cashdro_auto_confirm_payments = fields.Boolean(string='Auto-confirmar pagos', default=True)
    cashdro_log_level = fields.Selection(
        selection=[
            ('DEBUG', 'Debug'),
            ('INFO', 'Info'),
            ('WARNING', 'Warning'),
            ('ERROR', 'Error'),
            ('CRITICAL', 'Critical'),
        ],
        string='Nivel de Log',
        default='INFO'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        icp = self.env['ir.config_parameter'].sudo()
        
        def _get_bool(key, default=False):
            v = icp.get_param(key)
            if v is None:
                return default
            return str(v).lower() in ('1', 'true', 'yes', 'y', 'on')

        def _get_int(key, default=0):
            v = icp.get_param(key)
            try:
                return int(v) if v is not None else default
            except Exception:
                return default

        def _get_str(key, default=''):
            v = icp.get_param(key)
            return v if v is not None else default

        mapping = {
            'cashdro_enabled': ('cs_pos_smart_cash_cashdro.cashdro_enabled', _get_bool, False),
            'cashdro_default_gateway_url': ('cs_pos_smart_cash_cashdro.cashdro_default_gateway_url', _get_str, ''),
            'cashdro_connection_timeout': ('cs_pos_smart_cash_cashdro.cashdro_connection_timeout', _get_int, 10),
            'cashdro_polling_timeout': ('cs_pos_smart_cash_cashdro.cashdro_polling_timeout', _get_int, 60),
            'cashdro_polling_interval': ('cs_pos_smart_cash_cashdro.cashdro_polling_interval', _get_int, 500),
            'cashdro_verify_ssl': ('cs_pos_smart_cash_cashdro.cashdro_verify_ssl', _get_bool, False),
            'cashdro_max_retries': ('cs_pos_smart_cash_cashdro.cashdro_max_retries', _get_int, 3),
            'cashdro_retry_delay': ('cs_pos_smart_cash_cashdro.cashdro_retry_delay', _get_int, 2),
            'cashdro_auto_confirm_payments': ('cs_pos_smart_cash_cashdro.cashdro_auto_confirm_payments', _get_bool, True),
            'cashdro_log_level': ('cs_pos_smart_cash_cashdro.cashdro_log_level', _get_str, 'INFO'),
        }

        for field_name, (param, getter, default) in mapping.items():
            if field_name in fields_list:
                res[field_name] = getter(param, default)

        return res

    @api.constrains('cashdro_connection_timeout', 'cashdro_polling_timeout', 'cashdro_polling_interval')
    def _check_timeouts(self):
        for r in self:
            if r.cashdro_connection_timeout <= 0:
                raise ValidationError(_('El timeout de conexión debe ser mayor a 0'))
            if r.cashdro_polling_timeout <= 0:
                raise ValidationError(_('El timeout de polling debe ser mayor a 0'))
            if r.cashdro_polling_interval <= 0:
                raise ValidationError(_('El intervalo de polling debe ser mayor a 0'))

    def action_apply(self):
        """Persistir parámetros en ir.config_parameter."""
        self.ensure_one()
        icp = self.env['ir.config_parameter'].sudo()

        def _set(key, val):
            icp.set_param(key, val)

        _set('cs_pos_smart_cash_cashdro.cashdro_enabled', '1' if self.cashdro_enabled else '0')
        _set('cs_pos_smart_cash_cashdro.cashdro_default_gateway_url', self.cashdro_default_gateway_url or '')
        _set('cs_pos_smart_cash_cashdro.cashdro_connection_timeout', int(self.cashdro_connection_timeout))
        _set('cs_pos_smart_cash_cashdro.cashdro_polling_timeout', int(self.cashdro_polling_timeout))
        _set('cs_pos_smart_cash_cashdro.cashdro_polling_interval', int(self.cashdro_polling_interval))
        _set('cs_pos_smart_cash_cashdro.cashdro_verify_ssl', '1' if self.cashdro_verify_ssl else '0')
        _set('cs_pos_smart_cash_cashdro.cashdro_max_retries', int(self.cashdro_max_retries))
        _set('cs_pos_smart_cash_cashdro.cashdro_retry_delay', int(self.cashdro_retry_delay))
        _set('cs_pos_smart_cash_cashdro.cashdro_auto_confirm_payments', '1' if self.cashdro_auto_confirm_payments else '0')
        _set('cs_pos_smart_cash_cashdro.cashdro_log_level', self.cashdro_log_level or 'INFO')

        _logger.info('Cashdrop config wizard: parámetros aplicados')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Configuración guardada'),
                'message': _('Los parámetros de Cashdrop se han guardado correctamente.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
