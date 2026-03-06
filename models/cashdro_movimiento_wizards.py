# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

import json
import logging
from odoo import fields, models, api, _
from odoo.exceptions import UserError

from ..gateway_integration import CashdropGatewayIntegration

_logger = logging.getLogger(__name__)


def _get_gateway_from_method(env, payment_method_id):
    if not payment_method_id or not env['pos.payment.method'].browse(payment_method_id).cashdro_enabled:
        raise UserError(_('Método de pago CashDro no válido o no habilitado.'))
    config = env['res.config.settings'].sudo().get_cashdro_config()
    pm = env['pos.payment.method'].sudo().browse(payment_method_id)
    url = pm.get_gateway_url()
    _logger.info("CashDro wizard: gateway_url=%s (método=%s)", url, pm.name)
    return CashdropGatewayIntegration(
        gateway_url=url,
        timeout=config.get('connection_timeout', 10),
        verify_ssl=config.get('verify_ssl', False),
        log_level=config.get('log_level', 'INFO'),
        user=pm.cashdro_user,
        password=pm.cashdro_password,
    )


class CashdroMovimientoPagoWizard(models.TransientModel):
    _name = 'cashdro.movimiento.pago.wizard'
    _description = 'Wizard Pago (cobro) CashDro'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)
    amount = fields.Float(string='Importe (EUR)', required=True, digits=(16, 2))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_payment_method_id'):
            res['payment_method_id'] = self.env.context['default_payment_method_id']
        return res

    def _notify_and_close(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Movimiento CashDro'),
                'message': message,
                'type': 'success',
                'sticky': False,
            },
            'next': {'type': 'ir.actions.act_window_close'},
        }

    def action_execute(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_('El importe debe ser mayor que 0.'))
        gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
        gateway.start_operation(self.amount, operation_type=3)
        return self._notify_and_close(_('Pago iniciado: %.2f €. Inserte dinero en la máquina.') % self.amount)


class CashdroMovimientoDevolucionWizard(models.TransientModel):
    _name = 'cashdro.movimiento.devolucion.wizard'
    _description = 'Wizard Devolución CashDro'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)
    amount = fields.Float(string='Importe a devolver (EUR)', required=True, digits=(16, 2))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_payment_method_id'):
            res['payment_method_id'] = self.env.context['default_payment_method_id']
        return res

    def _notify_and_close(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Movimiento CashDro'), 'message': message, 'type': 'success', 'sticky': False},
            'next': {'type': 'ir.actions.act_window_close'},
        }

    def action_execute(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_('El importe debe ser mayor que 0.'))
        gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
        gateway.start_operation(self.amount, operation_type=3)
        return self._notify_and_close(_('Devolución iniciada: %.2f €. La máquina dispensará.') % self.amount)


class CashdroMovimientoCargaWizard(models.TransientModel):
    _name = 'cashdro.movimiento.carga.wizard'
    _description = 'Wizard Carga de dinero CashDro'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_payment_method_id'):
            res['payment_method_id'] = self.env.context['default_payment_method_id']
        return res

    def _notify_and_close(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Movimiento CashDro'), 'message': message, 'type': 'success', 'sticky': False},
            'next': {'type': 'ir.actions.act_window_close'},
        }

    def action_execute(self):
        self.ensure_one()
        gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
        # type=16 = INGRESAR genérico (movimientos_funcionan/ingresar_generico.py). index.php, aliasId="", isManual="0"
        gateway.start_operation_admin(operation_type=16, alias_id='', is_manual='0', parameters='')
        return self._notify_and_close(_('Carga iniciada. Inserte dinero en la máquina (ingreso genérico).'))


class CashdroMovimientoInicializarWizard(models.TransientModel):
    _name = 'cashdro.movimiento.inicializar.wizard'
    _description = 'Wizard Inicializar niveles CashDro'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_payment_method_id'):
            res['payment_method_id'] = self.env.context['default_payment_method_id']
        return res

    def _notify_and_close(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Movimiento CashDro'), 'message': message, 'type': 'success', 'sticky': False},
            'next': {'type': 'ir.actions.act_window_close'},
        }

    def action_execute(self):
        self.ensure_one()
        gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
        gateway.start_operation_admin(operation_type=12, alias_id='', is_manual='0', parameters='')
        return self._notify_and_close(_('Inicializar niveles iniciado. Compruebe el estado en la máquina.'))


class CashdroMovimientoFianzaWizard(models.TransientModel):
    _name = 'cashdro.movimiento.fianza.wizard'
    _description = 'Wizard Configurar fianza CashDro'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)
    levels_json = fields.Text(
        string='Configuración fianza (JSON)',
        help='JSON con limitRecyclerCheck y config (lista de DepositLevel por denominación). Ver documentación.'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_payment_method_id'):
            res['payment_method_id'] = self.env.context['default_payment_method_id']
        return res

    def _notify_and_close(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Movimiento CashDro'), 'message': message, 'type': 'success', 'sticky': False},
            'next': {'type': 'ir.actions.act_window_close'},
        }

    def action_execute(self):
        self.ensure_one()
        if not self.levels_json or not self.levels_json.strip():
            raise UserError(_('Indique la configuración JSON de fianza.'))
        try:
            levels_config = json.loads(self.levels_json)
        except json.JSONDecodeError as e:
            raise UserError(_('JSON inválido: %s') % str(e))
        gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
        gateway.set_deposit_levels(levels_config)
        self.payment_method_id.sudo().write({
            'cashdro_deposit_levels_json': self.levels_json.strip(),
        })
        return self._notify_and_close(_('Fianza configurada correctamente.'))
