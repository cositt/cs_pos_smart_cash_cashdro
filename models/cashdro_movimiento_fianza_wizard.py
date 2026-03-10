# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..gateway_integration import CashdropGatewayIntegration


def _fianza_get_gateway(env, payment_method_id):
    """Helper para obtener gateway; no depende de otros wizards."""
    if not payment_method_id or not env['pos.payment.method'].browse(payment_method_id).cashdro_enabled:
        raise UserError(_('Método de pago CashDro no válido o no habilitado.'))
    config = env['res.config.settings'].sudo().get_cashdro_config()
    pm = env['pos.payment.method'].sudo().browse(payment_method_id)
    return CashdropGatewayIntegration(
        gateway_url=pm.get_gateway_url(),
        timeout=config.get('connection_timeout', 10),
        verify_ssl=config.get('verify_ssl', False),
        log_level=config.get('log_level', 'INFO'),
        user=pm.cashdro_user,
        password=pm.cashdro_password,
    )


class CashdroMovimientoFianzaWizard(models.TransientModel):
    _name = 'cashdro.movimiento.fianza.wizard'
    _description = 'Wizard Configurar fianza CashDro'

    payment_method_id = fields.Many2one('pos.payment.method', string='Método de pago', required=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id,
        help='Solo para mostrar totales en la vista.'
    )
    levels_json = fields.Text(
        string='Configuración fianza (JSON)',
        help='JSON con limitRecyclerCheck y config (lista de DepositLevel por denominación). Ej: {"limitRecyclerCheck": 0, "config": [{"CurrencyId": "EUR", "DepositLevel": "1", "Value": "10", "Type": "3"}, ...]}'
    )
    limit_recycler_check = fields.Boolean(
        string='Activar límites de recicladores',
        default=False,
        help='Si está activo, CashDro comprobará los límites de reciclador (limitRecyclerCheck=1).'
    )
    deposit_bill_5 = fields.Integer(string='5 €', default=0)
    deposit_bill_10 = fields.Integer(string='10 €', default=0)
    deposit_bill_20 = fields.Integer(string='20 €', default=0)
    deposit_bill_50 = fields.Integer(string='50 €', default=0)
    deposit_bill_100 = fields.Integer(string='100 €', default=0)
    deposit_bill_200 = fields.Integer(string='200 €', default=0)
    deposit_coin_005 = fields.Integer(string='0,05 €', default=0)
    deposit_coin_010 = fields.Integer(string='0,10 €', default=0)
    deposit_coin_020 = fields.Integer(string='0,20 €', default=0)
    deposit_coin_050 = fields.Integer(string='0,50 €', default=0)
    deposit_coin_1 = fields.Integer(string='1 €', default=0)
    deposit_coin_2 = fields.Integer(string='2 €', default=0)

    # Totales por fila (Valor × Fianza) para mostrar en la tabla
    total_coin_005 = fields.Float(string='Total 0,05', compute='_compute_totals', readonly=True)
    total_coin_010 = fields.Float(string='Total 0,10', compute='_compute_totals', readonly=True)
    total_coin_020 = fields.Float(string='Total 0,20', compute='_compute_totals', readonly=True)
    total_coin_050 = fields.Float(string='Total 0,50', compute='_compute_totals', readonly=True)
    total_coin_1 = fields.Float(string='Total 1 €', compute='_compute_totals', readonly=True)
    total_coin_2 = fields.Float(string='Total 2 €', compute='_compute_totals', readonly=True)
    total_bill_5 = fields.Float(string='Total 5 €', compute='_compute_totals', readonly=True)
    total_bill_10 = fields.Float(string='Total 10 €', compute='_compute_totals', readonly=True)
    total_bill_20 = fields.Float(string='Total 20 €', compute='_compute_totals', readonly=True)
    total_bill_50 = fields.Float(string='Total 50 €', compute='_compute_totals', readonly=True)
    total_bill_100 = fields.Float(string='Total 100 €', compute='_compute_totals', readonly=True)
    total_bill_200 = fields.Float(string='Total 200 €', compute='_compute_totals', readonly=True)
    # Resúmenes
    monedas_units = fields.Integer(string='Unidades monedas', compute='_compute_totals', readonly=True)
    monedas_total_eur = fields.Float(string='Total monedas (€)', compute='_compute_totals', readonly=True)
    billetes_units = fields.Integer(string='Unidades billetes', compute='_compute_totals', readonly=True)
    billetes_total_eur = fields.Float(string='Total billetes (€)', compute='_compute_totals', readonly=True)
    grand_total_eur = fields.Float(string='Total (€)', compute='_compute_totals', readonly=True)

    @api.depends(
        'deposit_coin_005', 'deposit_coin_010', 'deposit_coin_020', 'deposit_coin_050', 'deposit_coin_1', 'deposit_coin_2',
        'deposit_bill_5', 'deposit_bill_10', 'deposit_bill_20', 'deposit_bill_50', 'deposit_bill_100', 'deposit_bill_200',
    )
    def _compute_totals(self):
        for r in self:
            r.total_coin_005 = r.deposit_coin_005 * 0.05
            r.total_coin_010 = r.deposit_coin_010 * 0.10
            r.total_coin_020 = r.deposit_coin_020 * 0.20
            r.total_coin_050 = r.deposit_coin_050 * 0.50
            r.total_coin_1 = r.deposit_coin_1 * 1.0
            r.total_coin_2 = r.deposit_coin_2 * 2.0
            r.total_bill_5 = r.deposit_bill_5 * 5.0
            r.total_bill_10 = r.deposit_bill_10 * 10.0
            r.total_bill_20 = r.deposit_bill_20 * 20.0
            r.total_bill_50 = r.deposit_bill_50 * 50.0
            r.total_bill_100 = r.deposit_bill_100 * 100.0
            r.total_bill_200 = r.deposit_bill_200 * 200.0
            r.monedas_units = (r.deposit_coin_005 + r.deposit_coin_010 + r.deposit_coin_020 +
                               r.deposit_coin_050 + r.deposit_coin_1 + r.deposit_coin_2)
            r.monedas_total_eur = (r.total_coin_005 + r.total_coin_010 + r.total_coin_020 +
                                   r.total_coin_050 + r.total_coin_1 + r.total_coin_2)
            r.billetes_units = (r.deposit_bill_5 + r.deposit_bill_10 + r.deposit_bill_20 +
                                r.deposit_bill_50 + r.deposit_bill_100 + r.deposit_bill_200)
            r.billetes_total_eur = (r.total_bill_5 + r.total_bill_10 + r.total_bill_20 +
                                    r.total_bill_50 + r.total_bill_100 + r.total_bill_200)
            r.grand_total_eur = r.monedas_total_eur + r.billetes_total_eur

    @api.model
    def default_get(self, fields_list):
        """Cargar fianza actual con la misma lógica que Estado de la caja (getPiecesCurrency + fallback config)."""
        res = super().default_get(fields_list)
        pid = self.env.context.get('default_payment_method_id')
        if not pid:
            return res

        res['payment_method_id'] = pid
        method = self.env['pos.payment.method'].sudo().browse(pid)

        # 1) limitRecyclerCheck desde la última config guardada
        if method.cashdro_deposit_levels_json:
            try:
                last_config = json.loads(method.cashdro_deposit_levels_json) or {}
                res['limit_recycler_check'] = bool(int(last_config.get('limitRecyclerCheck', 0) or 0))
            except (TypeError, json.JSONDecodeError, ValueError):
                pass

        # 2) Misma lógica que "Estado de la caja" → getPiecesCurrency + parseo unificado (helper en caja)
        try:
            gateway = _fianza_get_gateway(self.env, pid)
            pieces_resp = gateway.get_pieces_currency()
        except Exception:
            pieces_resp = {'code': 0}
        niveles = self.env['cashdro.caja.movimientos'].get_fianza_niveles_from_pieces(
            pieces_resp,
            config_json=method.cashdro_deposit_levels_json,
            full_denom=True,
        )

        # 3) Volcar en los campos del wizard
        res['deposit_bill_200'] = niveles.get(200, 0)
        res['deposit_bill_100'] = niveles.get(100, 0)
        res['deposit_bill_50'] = niveles.get(50, 0)
        res['deposit_bill_20'] = niveles.get(20, 0)
        res['deposit_bill_10'] = niveles.get(10, 0)
        res['deposit_bill_5'] = niveles.get(5, 0)
        res['deposit_coin_2'] = niveles.get(2.0, 0)
        res['deposit_coin_1'] = niveles.get(1.0, 0)
        res['deposit_coin_050'] = niveles.get(0.5, 0)
        res['deposit_coin_020'] = niveles.get(0.2, 0)
        res['deposit_coin_010'] = niveles.get(0.1, 0)
        res['deposit_coin_005'] = niveles.get(0.05, 0)

        return res

    def _notify_and_close(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Movimiento CashDro'), 'message': message, 'type': 'success', 'sticky': False},
            'next': {'type': 'ir.actions.act_window_close'},
        }

    def _build_levels_config(self):
        config = []
        for value_eur, level in [
            (5, self.deposit_bill_5),
            (10, self.deposit_bill_10),
            (20, self.deposit_bill_20),
            (50, self.deposit_bill_50),
            (100, self.deposit_bill_100),
            (200, self.deposit_bill_200),
        ]:
            if level and level > 0:
                config.append({
                    'CurrencyId': 'EUR',
                    'DepositLevel': str(level),
                    'Value': str(value_eur),
                    'Type': '3',
                })
        for value_cents, level in [
            (5, self.deposit_coin_005),
            (10, self.deposit_coin_010),
            (20, self.deposit_coin_020),
            (50, self.deposit_coin_050),
            (100, self.deposit_coin_1),
            (200, self.deposit_coin_2),
        ]:
            if level and level > 0:
                config.append({
                    'CurrencyId': 'EUR',
                    'DepositLevel': str(level),
                    'Value': str(value_cents),
                    'Type': '2',
                })
        return {
            'limitRecyclerCheck': 1 if self.limit_recycler_check else 0,
            'config': config,
        }

    def action_execute(self):
        self.ensure_one()
        levels_config = self._build_levels_config()
        if not levels_config.get('config'):
            raise UserError(_('Indique al menos un nivel de fianza (unidades) para alguna denominación.'))
        gateway = _fianza_get_gateway(self.env, self.payment_method_id.id)
        gateway.set_deposit_levels(levels_config)
        self.payment_method_id.sudo().write({
            'cashdro_deposit_levels_json': json.dumps(levels_config),
        })
        return self._notify_and_close(_('Fianza configurada correctamente.'))
