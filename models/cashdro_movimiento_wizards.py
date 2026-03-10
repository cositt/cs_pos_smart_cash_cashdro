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
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_('El importe debe ser mayor que 0.'))
        try:
            gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
            # type=4 = VENTA/COBRO (cobro_20centimos_FUNCIONA.py). index3.php + acknowledge.
            gateway.start_operation(self.amount, operation_type=4)
            return self._notify_and_close(_('Venta iniciada: %.2f €. Inserte dinero en la máquina.') % self.amount)
        except Exception as e:
            _logger.exception("CashDro Venta falló")
            msg = str(e)
            if not msg:
                msg = _('Error desconocido. Revisa logs de Odoo.')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error CashDro'),
                    'message': msg,
                    'type': 'danger',
                    'sticky': True,
                },
            }


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
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_('El importe debe ser mayor que 0.'))
        gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
        # type=3 = DEVOLUCIÓN/DISPENSA (payOutProgress). La máquina dispensará el importe.
        gateway.start_operation(self.amount, operation_type=3)
        return self._notify_and_close(_('Pago iniciado: %.2f €. La máquina dispensará.') % self.amount)


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
        self.ensure_one()
        gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
        # type=16 = INGRESAR genérico (movimientos_funcionan/ingresar_generico.py).
        # startLoadMoney: startOperation(type=16) + acknowledgeOperationId → máquina entra en modo "cargando".
        gateway.start_load_money(alias_id='', is_manual='0', parameters='')
        return self._notify_and_close(_('Carga iniciada. Inserte dinero en la máquina (ingreso genérico, type=16).'))


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
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_('El importe debe ser mayor que 0.'))
        gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
        # type=17 = Ingreso por importe (doc 5.6). parameters={"amount": "<amount>"} con amount en céntimos.
        gateway.start_operation(self.amount, operation_type=17)
        return self._notify_and_close(_('Ingreso por importe iniciado: %.2f €. Inserte dinero en la máquina.') % self.amount)


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
        # Usa el flujo completo de inicialización de niveles (type=12) probado contra la máquina:
        # startOperation → acknowledge → askOperation → finishOperation.
        gateway.initialize_levels()
        return self._notify_and_close(_('Inicializar niveles ejecutado. Consulte Estado de la caja para ver los nuevos niveles.'))


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
        self.ensure_one()
        gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
        gateway.start_carga(alias_id='')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Carga'),
                'message': _('Aceptar desde la máquina para finalizar la carga.'),
                'type': 'info',
                'sticky': False,
            },
            'next': {'type': 'ir.actions.act_window_close'},
        }


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
        self.ensure_one()
        gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
        res = gateway.start_retirada(alias_id='')
        operation_id = res.get('operation_id')
        if not operation_id:
            raise UserError(_('No se recibió operation_id al iniciar la retirada.'))
        # Doc 5.8.3: es obligatorio acceder a la interfaz web para indicar las piezas a retirar.
        # Sin abrir esta URL la máquina se queda en "Retirando..." sin pantalla para elegir.
        url = gateway.get_retirada_web_url(operation_id)
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
            'name': _('Retirada - Indicar piezas en la web'),
        }


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
        self.ensure_one()
        gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
        gateway.start_retirada_casete_monedas(alias_id='')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Retirada de casete de monedas'),
                'message': _('Completar el proceso en la máquina y aceptar.'),
                'type': 'info',
                'sticky': False,
            },
            'next': {'type': 'ir.actions.act_window_close'},
        }


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
        self.ensure_one()
        gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
        gateway.start_retirada_casete_billetes(alias_id='')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Retirada de casete de billetes'),
                'message': _('Completar el proceso en la máquina y aceptar.'),
                'type': 'info',
                'sticky': False,
            },
            'next': {'type': 'ir.actions.act_window_close'},
        }


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
        """
        Doc 5.4: envía la orden a la máquina (startOperation type=18 + acknowledge).
        No se abre ninguna ventana; la operación se gestiona en la propia máquina.
        """
        self.ensure_one()
        gateway = _get_gateway_from_method(self.env, self.payment_method_id.id)
        gateway.start_cambio(alias_id='')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cambio'),
                'message': _('Orden enviada a la máquina. Complete el cambio en CashDro.'),
                'type': 'info',
                'sticky': False,
            },
            'next': {'type': 'ir.actions.act_window_close'},
        }
