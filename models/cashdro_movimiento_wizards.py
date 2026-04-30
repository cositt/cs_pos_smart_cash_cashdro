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
    _description = 'Wizard Venta CashDro'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)
    amount = fields.Float(string='Importe (EUR)', required=True, digits=(16, 2))

    def name_get(self):
        return [(r.id, _('Venta')) for r in self]

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
        """Ejecuta venta desde JavaScript (cashdro_gateway_service.js)."""
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_('El importe debe ser mayor que 0.'))
        if not self.payment_method_id or not self.payment_method_id.cashdro_enabled:
            raise UserError(_('Método de pago CashDro no válido o no habilitado.'))
        return True


class CashdroMovimientoDevolucionWizard(models.TransientModel):
    _name = 'cashdro.movimiento.devolucion.wizard'
    _description = 'Wizard Pago CashDro'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)
    amount = fields.Float(string='Importe a devolver (EUR)', required=True, digits=(16, 2))

    def name_get(self):
        return [(r.id, _('Pago')) for r in self]

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
        """Ejecuta pago/devolución desde JavaScript (cashdro_gateway_service.js)."""
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_('El importe debe ser mayor que 0.'))
        if not self.payment_method_id or not self.payment_method_id.cashdro_enabled:
            raise UserError(_('Método de pago CashDro no válido o no habilitado.'))
        return True


class CashdroMovimientoCargaWizard(models.TransientModel):
    _name = 'cashdro.movimiento.carga.wizard'
    _description = 'Wizard Ingresar CashDro'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)

    def name_get(self):
        return [(r.id, _('Ingresar')) for r in self]

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
        """Ejecuta carga desde JavaScript (cashdro_gateway_service.js)."""
        self.ensure_one()
        if not self.payment_method_id or not self.payment_method_id.cashdro_enabled:
            raise UserError(_('Método de pago CashDro no válido o no habilitado.'))
        return True


class CashdroMovimientoIngresoImporteWizard(models.TransientModel):
    """Ingreso por importe (doc 5.6): startOperation type=17 con parameters={"amount": "<amount>"}."""
    _name = 'cashdro.movimiento.ingreso.importe.wizard'
    _description = 'Wizard Ingresar por importe CashDro'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)
    amount = fields.Float(string='Importe a ingresar (EUR)', required=True, digits=(16, 2))

    def name_get(self):
        return [(r.id, _('Ingresar por importe')) for r in self]

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
        """Ejecuta ingreso por importe desde JavaScript (cashdro_gateway_service.js)."""
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_('El importe debe ser mayor que 0.'))
        if not self.payment_method_id or not self.payment_method_id.cashdro_enabled:
            raise UserError(_('Método de pago CashDro no válido o no habilitado.'))
        return True


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
        """Ejecuta inicializar niveles desde JavaScript (cashdro_gateway_service.js)."""
        self.ensure_one()
        if not self.payment_method_id or not self.payment_method_id.cashdro_enabled:
            raise UserError(_('Método de pago CashDro no válido o no habilitado.'))
        return True


class CashdroMovimientoCargaOperacionWizard(models.TransientModel):
    """
    Carga (doc 5.7): type=1. Iniciar carga → máquina en pantalla de carga. Aceptar desde la máquina.
    """
    _name = 'cashdro.movimiento.carga.operacion.wizard'
    _description = 'Wizard Carga CashDro (type=1)'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)

    def name_get(self):
        return [(r.id, _('Carga')) for r in self]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_payment_method_id'):
            res['payment_method_id'] = self.env.context['default_payment_method_id']
        return res

    def action_iniciar_carga(self):
        """Ejecuta carga desde JavaScript (cashdro_gateway_service.js)."""
        self.ensure_one()
        if not self.payment_method_id or not self.payment_method_id.cashdro_enabled:
            raise UserError(_('Método de pago CashDro no válido o no habilitado.'))
        return True


class CashdroMovimientoRetiradaWizard(models.TransientModel):
    """
    Retirada (doc 5.8): type=2. Iniciar retirada → completar el proceso en la máquina y aceptar.
    """
    _name = 'cashdro.movimiento.retirada.wizard'
    _description = 'Wizard Retirada CashDro (type=2)'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)

    def name_get(self):
        return [(r.id, _('Retirada')) for r in self]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_payment_method_id'):
            res['payment_method_id'] = self.env.context['default_payment_method_id']
        return res

    def action_iniciar_retirada(self):
        """Ejecuta retirada desde JavaScript (cashdro_gateway_service.js)."""
        self.ensure_one()
        if not self.payment_method_id or not self.payment_method_id.cashdro_enabled:
            raise UserError(_('Método de pago CashDro no válido o no habilitado.'))
        return True


class CashdroMovimientoRetiradaCaseteMonedasWizard(models.TransientModel):
    """
    Retirada casete de monedas (doc 5.13): type=11. Iniciar → completar en la máquina y aceptar.
    """
    _name = 'cashdro.movimiento.retirada.casete.monedas.wizard'
    _description = 'Wizard Retirada casete de monedas CashDro (type=11)'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)

    def name_get(self):
        return [(r.id, _('Retirada de casete de monedas')) for r in self]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_payment_method_id'):
            res['payment_method_id'] = self.env.context['default_payment_method_id']
        return res

    def action_iniciar(self):
        """Ejecuta retirada de casete de monedas desde JavaScript (cashdro_gateway_service.js)."""
        self.ensure_one()
        if not self.payment_method_id or not self.payment_method_id.cashdro_enabled:
            raise UserError(_('Método de pago CashDro no válido o no habilitado.'))
        return True


class CashdroMovimientoRetiradaCaseteBilletesWizard(models.TransientModel):
    """
    Retirada casete de billetes (doc 5.12): type=10. Iniciar → completar en la máquina y aceptar.
    """
    _name = 'cashdro.movimiento.retirada.casete.billetes.wizard'
    _description = 'Wizard Retirada casete de billetes CashDro (type=10)'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)

    def name_get(self):
        return [(r.id, _('Retirada de casete de billetes')) for r in self]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_payment_method_id'):
            res['payment_method_id'] = self.env.context['default_payment_method_id']
        return res

    def action_iniciar(self):
        """Ejecuta retirada de casete de billetes desde JavaScript (cashdro_gateway_service.js)."""
        self.ensure_one()
        if not self.payment_method_id or not self.payment_method_id.cashdro_enabled:
            raise UserError(_('Método de pago CashDro no válido o no habilitado.'))
        return True


class CashdroMovimientoCambioWizard(models.TransientModel):
    """
    Cambio (doc 5.4): type=18.
    Iniciar la transacción de cambio y abrir la interfaz web de CashDro (pantalla splash) para gestionarla.
    """
    _name = 'cashdro.movimiento.cambio.wizard'
    _description = 'Wizard Cambio CashDro (type=18)'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)

    def name_get(self):
        return [(r.id, _('Cambio')) for r in self]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_payment_method_id'):
            res['payment_method_id'] = self.env.context['default_payment_method_id']
        return res

    def action_iniciar(self):
        """Ejecuta cambio desde JavaScript (cashdro_gateway_service.js)."""
        self.ensure_one()
        if not self.payment_method_id or not self.payment_method_id.cashdro_enabled:
            raise UserError(_('Método de pago CashDro no válido o no habilitado.'))
        return True
