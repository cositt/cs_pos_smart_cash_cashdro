# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

import json
import logging
from odoo import fields, models, api, _
from odoo.exceptions import UserError

from ..gateway_integration import CashdropGatewayIntegration

_logger = logging.getLogger(__name__)


class CashdroCajaMovimientos(models.TransientModel):
    _name = 'cashdro.caja.movimientos'
    _description = 'Vista Movimientos CashDro - Estado caja y operaciones'

    payment_method_id = fields.Many2one(
        'pos.payment.method',
        string='Método de pago / Caja',
        required=True,
        domain=[('cashdro_enabled', '=', True)],
        help='Selecciona el método de pago CashDro para consultar y operar'
    )
    last_refresh = fields.Datetime(string='Última actualización', readonly=True)
    state_display = fields.Html(string='Estado de la caja', readonly=True, sanitize=False)
    state_fianza = fields.Html(
        string='ESTADO DE FIANZA',
        readonly=True,
        sanitize=False,
        default='<p>Pulsa <strong>Actualizar estado</strong> para cargar el estado de fianza (getPiecesCurrency).</p>',
    )
    state_raw = fields.Text(string='Datos crudos (debug)', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        method = self.env['pos.payment.method'].sudo().search(
            [('cashdro_enabled', '=', True)], limit=1
        )
        if method:
            res['payment_method_id'] = method.id
        return res

    def _get_gateway(self):
        self.ensure_one()
        if not self.payment_method_id or not self.payment_method_id.cashdro_enabled:
            raise UserError(_('Selecciona un método de pago CashDro habilitado.'))
        config = self.env['res.config.settings'].sudo().get_cashdro_config()
        url = self.payment_method_id.get_gateway_url()
        _logger.info("CashDro Movimientos: usando gateway_url=%s (método=%s)", url, self.payment_method_id.name)
        return CashdropGatewayIntegration(
            gateway_url=url,
            timeout=config.get('connection_timeout', 10),
            verify_ssl=config.get('verify_ssl', False),
            log_level=config.get('log_level', 'INFO'),
            user=self.payment_method_id.cashdro_user,
            password=self.payment_method_id.cashdro_password,
        )

    def action_refresh(self):
        """Actualiza estado de la caja: consulta de niveles (monedas/billetes) como en interfaz CashDro."""
        self.ensure_one()
        gateway = self._get_gateway()
        raw = {}

        levels = {'moneda': [], 'billete': []}
        levels_debug = {}
        try:
            levels, levels_debug = gateway.get_consult_levels()
            raw['levels'] = levels
            raw['levels_debug'] = levels_debug
        except Exception as e:
            raw['levels_error'] = str(e)
            moneda_denom = [2.0, 1.0, 0.5, 0.2, 0.1, 0.05]
            billete_denom = [100, 50, 20, 10, 5]
            levels = {
                'moneda': [(v, 0, 0.0, 0, 0.0) for v in moneda_denom],
                'billete': [(v, 0, 0.0, 0, 0.0) for v in billete_denom],
            }

        def row_moneda(val_eur, nivel_rec, total_rec, nivel_cas, total_cas):
            css = 'background-color: #f8d7da;' if (nivel_rec == 0 and nivel_cas == 0) else ''
            return '<tr style="%s"><td>%.2f €</td><td>%s</td><td>%.2f €</td><td>%s</td><td>%.2f €</td></tr>' % (
                css, val_eur, nivel_rec, total_rec, nivel_cas, total_cas
            )

        def row_billete(val_eur, nivel_rec, total_rec, nivel_cas, total_cas):
            css = 'background-color: #f8d7da;' if (nivel_rec == 0 and nivel_cas == 0) else ''
            return '<tr style="%s"><td>%s €</td><td>%s</td><td>%s €</td><td>%s</td><td>%s €</td></tr>' % (
                css, val_eur, nivel_rec, total_rec if total_rec else '0 €', nivel_cas, total_cas if total_cas else '0 €'
            )

        moneda_rows = ''.join(row_moneda(v, nr, tr, nc, tc) for v, nr, tr, nc, tc in levels['moneda'])
        billete_rows = ''.join(row_billete(v, nr, tr, nc, tc) for v, nr, tr, nc, tc in levels['billete'])

        sum_moneda_rec = sum(nr for _, nr, _, _, _ in levels['moneda'])
        sum_moneda_cas = sum(nc for _, _, _, nc, _ in levels['moneda'])
        total_rec_moneda = sum(tr for _, _, tr, _, _ in levels['moneda'])
        total_cas_moneda = sum(tc for _, _, _, _, tc in levels['moneda'])
        total_moneda = total_rec_moneda + total_cas_moneda

        sum_billete_rec = sum(nr for _, nr, _, _, _ in levels['billete'])
        sum_billete_cas = sum(nc for _, _, _, nc, _ in levels['billete'])
        total_rec_billete = sum(tr for _, _, tr, _, _ in levels['billete'])
        total_cas_billete = sum(tc for _, _, _, _, tc in levels['billete'])
        total_billete = total_rec_billete + total_cas_billete
        total_general = total_moneda + total_billete

        state_html = '''
        <div style="width:100%%; max-width:100%%; box-sizing:border-box;">
            <table class="table table-sm table-bordered" style="width:100%%; table-layout:fixed; margin-bottom:1.5rem;">
                <caption style="text-align:left; font-weight:bold;">Moneda</caption>
                <thead><tr>
                    <th style="width:12%%">Valor</th>
                    <th style="width:22%%">Niv. reciclador</th>
                    <th style="width:22%%">Total reciclador</th>
                    <th style="width:22%%">Niv. casete</th>
                    <th style="width:22%%">Total casete</th>
                </tr></thead>
                <tbody>%s</tbody>
                <tfoot><tr style="font-weight:bold;"><td>Total</td><td>%s</td><td>%.2f €</td><td>%s</td><td>%.2f €</td></tr></tfoot>
            </table>
            <table class="table table-sm table-bordered" style="width:100%%; table-layout:fixed; margin-bottom:1.5rem;">
                <caption style="text-align:left; font-weight:bold;">Billete</caption>
                <thead><tr>
                    <th style="width:12%%">Valor</th>
                    <th style="width:22%%">Niv. reciclador</th>
                    <th style="width:22%%">Total reciclador</th>
                    <th style="width:22%%">Niv. casete</th>
                    <th style="width:22%%">Total casete</th>
                </tr></thead>
                <tbody>%s</tbody>
                <tfoot><tr style="font-weight:bold;"><td>Total</td><td>%s</td><td>%.2f €</td><td>%s</td><td>%.2f €</td></tr></tfoot>
            </table>
            <p style="margin:0.5rem 0;"><strong>Total monedas:</strong> %.2f € &nbsp;|&nbsp; <strong>Total billetes:</strong> %.2f € &nbsp;|&nbsp; <strong>Total:</strong> %.2f €</p>
        </div>
        ''' % (
            moneda_rows,
            sum_moneda_rec, total_rec_moneda, sum_moneda_cas, total_cas_moneda,
            billete_rows,
            sum_billete_rec, total_rec_billete, sum_billete_cas, total_cas_billete,
            total_moneda, total_billete, total_general,
        )

        try:
            pieces_resp = gateway.get_pieces_currency(currency_id='EUR', include_images='0', include_levels='1')
            raw['getPiecesCurrency'] = pieces_resp
        except Exception as e:
            raw['getPiecesCurrency_error'] = str(e)
            pieces_resp = {}
        fianza_html = self._build_estado_fianza_from_pieces(pieces_resp, levels)

        try:
            dev = gateway.get_info_devices()
            raw['getInfoDevices'] = dev
        except Exception as e:
            raw['getInfoDevices_error'] = str(e)

        self.write({
            'state_display': state_html,
            'state_fianza': fianza_html,
            'state_raw': json.dumps(raw, indent=2, default=str)[:5000],
            'last_refresh': fields.Datetime.now(),
        })
        return True

    @api.model
    def get_fianza_niveles_from_pieces(self, pieces_resp, config_json=None, full_denom=False):
        """
        Extrae nivel de fianza (DepositLevel) por denominación a partir de getPiecesCurrency.

        Basado en la respuesta REAL observada:
        - Monedas: Type = \"1\", Value en céntimos → 1,2,5,10,20,50,100,200 (0.01..2.00 €)
        - Billetes: Type = \"2\", Value en céntimos → 500,1000,2000,5000,10000,20000,50000 (5..500 €)

        Para ambos casos solo consideramos denominaciones activas (RecyclerLimit > 0).
        Si la máquina no devuelve ningún nivel, usamos config_json (setDepositLevels) como fallback.
        """
        order_caja = [20, 10, 5, 2.0, 1.0, 0.5, 0.2, 0.1, 0.05]
        order_denom = [200, 100, 50, 20, 10, 5, 2.0, 1.0, 0.5, 0.2, 0.1, 0.05] if full_denom else order_caja
        rows_by_val = {v: 0 for v in order_denom}

        if pieces_resp and pieces_resp.get('code') == 1:
            data = pieces_resp.get('data')
            if data is None:
                resp = pieces_resp.get('response') or {}
                data = resp.get('data') if isinstance(resp, dict) else None
            if data is not None:
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except Exception:
                        data = []
                if not isinstance(data, list):
                    data = [data] if isinstance(data, dict) else []
                for p in data:
                    if not isinstance(p, dict):
                        continue
                    try:
                        val_raw = p.get('value') or p.get('Value') or 0
                        typ = str(p.get('Type') or p.get('type') or '')
                        dep = int(float(p.get('DepositLevel') or p.get('depositLevel') or 0))
                        rec_limit = int(float(p.get('RecyclerLimit') or 0))
                        val_int = int(float(val_raw))
                    except (TypeError, ValueError):
                        continue

                    if not rec_limit:
                        # Denominación no operativa: la doc y las respuestas reales muestran RecyclerLimit=0
                        # para monedas/billetes que la máquina no usa.
                        continue

                    if typ == '1':
                        # Monedas: céntimos → euros
                        val_eur = round(val_int / 100.0, 2)
                        if val_eur in rows_by_val:
                            rows_by_val[val_eur] = dep
                    elif typ == '2':
                        # Billetes: céntimos → euros (500→5€, 1000→10€, ...)
                        val_eur = float(val_int) / 100.0
                        if val_eur in rows_by_val:
                            rows_by_val[val_eur] = dep

        # Fallback: si TODO está a 0 pero tenemos config_json, usamos esa configuración
        if config_json and not any(rows_by_val.values()):
            try:
                config_data = json.loads(config_json) if isinstance(config_json, str) else (config_json or {})
                for item in (config_data.get('config') or []):
                    try:
                        val_raw = item.get('Value') or item.get('value') or 0
                        val_int = int(float(val_raw))
                        typ = str(item.get('Type') or item.get('type') or '1')
                        dep = int(float(item.get('DepositLevel') or item.get('depositLevel') or 0))
                    except (TypeError, ValueError):
                        continue
                    if typ in ('1', '3') and val_int in (5, 10, 20, 50, 100, 200) and val_int in rows_by_val:
                        rows_by_val[val_int] = dep
                    elif typ == '2':
                        v = round(val_int / 100.0, 2)
                        if v in rows_by_val:
                            rows_by_val[v] = dep
            except (TypeError, json.JSONDecodeError):
                pass

        return {v: rows_by_val[v] for v in order_denom}

    def _build_estado_fianza_from_pieces(self, pieces_resp, levels=None):
        """
        ESTADO DE FIANZA exactamente como en CashDro (primera imagen): Moneda, Nivel fianza, Total Fianza,
        Niv. reciclador, Total reciclador, Niv. faltante, Total faltante.
        - Nivel fianza: DepositLevel de getPiecesCurrency o de config guardada (setDepositLevels).
        - Nivel reciclador: real desde levels (consulta type=12) para que coincida con la máquina.
        - Orden: 20€, 10€, 5€, 2.00€, 1.00€, 0.50€, 0.20€, 0.10€, 0.05€. Celdas Niv. reciclador=0 en rojo.
        """
        default_msg = (
            '<p>Pulsa <strong>Actualizar estado</strong> para cargar el estado de fianza (getPiecesCurrency).</p>'
        )
        order_denom = [20, 10, 5, 2.0, 1.0, 0.5, 0.2, 0.1, 0.05]
        rows_by_val = {v: (0, 0) for v in order_denom}
        if pieces_resp and pieces_resp.get('code') == 1:
            data = pieces_resp.get('data')
            if data is None:
                resp = pieces_resp.get('response') or {}
                data = resp.get('data') if isinstance(resp, dict) else None
            if data is not None:
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except Exception:
                        data = []
                if not isinstance(data, list):
                    data = [data] if isinstance(data, dict) else []
                for p in data:
                    if not isinstance(p, dict):
                        continue
                    try:
                        val_raw = p.get('value') or p.get('Value') or 0
                        val_num = float(val_raw)
                        typ = str(p.get('Type') or p.get('type') or '')
                        nf = int(float(p.get('DepositLevel') or p.get('depositLevel') or 0))
                        nr = int(float(p.get('unitsInRecycler') or p.get('unitsinrecycler') or p.get('finishlevelrecycler') or p.get('FinishLevelRecycler') or 0))
                    except (TypeError, ValueError):
                        continue
                    val_eur = None
                    if val_num <= 200:
                        if val_num in (5, 10, 20, 50, 100, 200):
                            val_eur = round(val_num / 100.0, 2)
                            if val_eur in (2.0, 1.0, 0.5, 0.2, 0.1, 0.05):
                                rows_by_val[val_eur] = (nf, nr)
                    elif val_num >= 500:
                        val_eur = val_num / 100.0
                        if val_eur in (5.0, 10.0, 20.0, 50.0, 100.0):
                            rows_by_val[val_eur] = (nf, nr)
        if levels:
            for v in order_denom:
                nf, _ = rows_by_val.get(v, (0, 0))
                rec_data = next((x for x in levels.get('billete', []) if abs(x[0] - v) < 0.01), None)
                if rec_data is None:
                    rec_data = next((x for x in levels.get('moneda', []) if abs(x[0] - v) < 0.01), None)
                nr = rec_data[1] if rec_data else 0
                rows_by_val[v] = (nf, nr)
        method = self.payment_method_id
        if method and method.cashdro_deposit_levels_json and not any(rows_by_val[v][0] for v in order_denom):
            try:
                config_data = json.loads(method.cashdro_deposit_levels_json)
                for item in (config_data.get('config') or []):
                    try:
                        val_raw = item.get('Value') or item.get('value') or 0
                        val_int = int(float(val_raw))
                        typ = str(item.get('Type') or item.get('type') or '1')
                        dep = int(float(item.get('DepositLevel') or item.get('depositLevel') or 0))
                    except (TypeError, ValueError):
                        continue
                    if typ in ('1', '3') and val_int in (100, 50, 20, 10, 5):
                        if val_int in rows_by_val:
                            nr = rows_by_val[val_int][1]
                            rows_by_val[val_int] = (dep, nr)
                    elif typ == '2':
                        v = round(val_int / 100.0, 2)
                        if v in (2.0, 1.0, 0.5, 0.2, 0.1, 0.05) and v in rows_by_val:
                            nr = rows_by_val[v][1]
                            rows_by_val[v] = (dep, nr)
            except (TypeError, json.JSONDecodeError):
                pass
        rows = []
        total_fianza = total_rec = total_faltante = 0.0
        for v in order_denom:
            nf, nr = rows_by_val.get(v, (0, 0))
            tr = nr * v
            faltante = max(0, nf - nr)
            tf = nf * v
            tfalt = faltante * v
            total_fianza += tf
            total_rec += tr
            total_faltante += tfalt
            css = 'background-color: #f8d7da;' if nr == 0 else ''
            if v >= 1:
                rows.append(
                    '<tr style="%s"><td>%s €</td><td>%s</td><td>%.2f €</td><td>%s</td><td>%.2f €</td><td>%s</td><td>%.2f €</td></tr>'
                    % (css, int(v), nf, tf, nr, tr, faltante, tfalt)
                )
            else:
                rows.append(
                    '<tr style="%s"><td>%.2f €</td><td>%s</td><td>%.2f €</td><td>%s</td><td>%.2f €</td><td>%s</td><td>%.2f €</td></tr>'
                    % (css, v, nf, tf, nr, tr, faltante, tfalt)
                )
        if not rows:
            return default_msg
        return '''
        <p style="margin-bottom:0.5rem;">Estado de fianza (getPiecesCurrency).</p>
        <table class="table table-sm table-bordered" style="width:100%%; table-layout:fixed;">
            <thead><tr>
                <th>Moneda</th>
                <th>Nivel fianza</th>
                <th>Total Fianza</th>
                <th>Niv. reciclador</th>
                <th>Total reciclador</th>
                <th>Niv. faltante</th>
                <th>Total faltante</th>
            </tr></thead>
            <tbody>%s</tbody>
            <tfoot><tr style="font-weight:bold;">
                <td>Total</td>
                <td></td>
                <td>%.2f €</td>
                <td></td>
                <td>%.2f €</td>
                <td></td>
                <td>%.2f €</td>
            </tr></tfoot>
        </table>
        ''' % (''.join(rows), total_fianza, total_rec, total_faltante)

    def _build_estado_fianza_html(self, levels):
        """
        Construye la tabla Estado de fianza: Nivel fianza, Total Fianza, Nivel reciclador,
        Total reciclador, Nivel faltante, Total faltante.
        levels = {'moneda': [(v, nr, tr, nc, tc), ...], 'billete': [...]}
        Nivel fianza se obtiene de payment_method_id.cashdro_deposit_levels_json (setDepositLevels).
        """
        self.ensure_one()
        method = self.payment_method_id
        if not method or not method.cashdro_deposit_levels_json:
            return None
        try:
            config_data = json.loads(method.cashdro_deposit_levels_json)
        except (TypeError, json.JSONDecodeError):
            return None
        config_list = config_data.get('config') or []
        fianza_by_eur = {}
        for item in config_list:
            try:
                val_raw = item.get('Value') or item.get('value') or 0
                val_int = int(float(val_raw))
                typ = str(item.get('Type') or item.get('type') or '1')
                dep = int(float(item.get('DepositLevel') or item.get('depositLevel') or 0))
            except (TypeError, ValueError):
                continue
            if typ in ('1', '3'):
                valor_eur = val_int
                if valor_eur in (100, 50, 20, 10, 5):
                    fianza_by_eur[valor_eur] = dep
            elif typ == '2':
                valor_eur = round(val_int / 100.0, 2)
                if valor_eur in (2.0, 1.0, 0.5, 0.2, 0.1, 0.05):
                    fianza_by_eur[valor_eur] = dep
        billete_denom = [100, 50, 20, 10, 5]
        moneda_denom = [2.0, 1.0, 0.5, 0.2, 0.1, 0.05]
        rows = []
        total_fianza = 0.0
        total_rec = 0.0
        total_faltante = 0.0
        for v in billete_denom:
            nf = fianza_by_eur.get(v, 0)
            rec_data = next((x for x in levels['billete'] if abs(x[0] - v) < 0.01), None)
            nr = rec_data[1] if rec_data else 0
            tr = rec_data[2] if rec_data else 0.0
            faltante = max(0, nf - nr)
            tf = nf * v
            tfalt = faltante * v
            total_fianza += tf
            total_rec += tr
            total_faltante += tfalt
            css = 'background-color: #f8d7da;' if nr == 0 else ''
            rows.append(
                '<tr style="%s"><td>%s €</td><td>%s</td><td>%.2f €</td><td>%s</td><td>%.2f €</td><td>%s</td><td>%.2f €</td></tr>'
                % (css, v, nf, tf, nr, tr, faltante, tfalt)
            )
        for v in moneda_denom:
            nf = fianza_by_eur.get(v, 0)
            rec_data = next((x for x in levels['moneda'] if abs(x[0] - v) < 0.01), None)
            nr = rec_data[1] if rec_data else 0
            tr = rec_data[2] if rec_data else 0.0
            faltante = max(0, nf - nr)
            tf = nf * v
            tfalt = faltante * v
            total_fianza += tf
            total_rec += tr
            total_faltante += tfalt
            css = 'background-color: #f8d7da;' if nr == 0 else ''
            rows.append(
                '<tr style="%s"><td>%.2f €</td><td>%s</td><td>%.2f €</td><td>%s</td><td>%.2f €</td><td>%s</td><td>%.2f €</td></tr>'
                % (css, v, nf, tf, nr, tr, faltante, tfalt)
            )
        if not rows:
            return None
        html = '''
        <p style="margin-bottom:0.5rem;"><strong>Estado de fianza</strong> (Nivel fianza configurado, reciclador actual y faltante).</p>
        <table class="table table-sm table-bordered" style="width:100%%; table-layout:fixed;">
            <thead><tr>
                <th>Moneda</th>
                <th>Nivel fianza</th>
                <th>Total Fianza</th>
                <th>Niv. reciclador</th>
                <th>Total reciclador</th>
                <th>Niv. faltante</th>
                <th>Total faltante</th>
            </tr></thead>
            <tbody>%s</tbody>
            <tfoot><tr style="font-weight:bold;">
                <td>Total</td>
                <td></td>
                <td>%.2f €</td>
                <td></td>
                <td>%.2f €</td>
                <td></td>
                <td>%.2f €</td>
            </tr></tfoot>
        </table>
        ''' % (''.join(rows), total_fianza, total_rec, total_faltante)
        return html

    def action_pago(self):
        """Abre wizard de pago (cobro)."""
        return self._open_wizard('cashdro.movimiento.pago.wizard', _('Pago (cobro)'))

    def action_devolucion(self):
        """Abre wizard de devolución."""
        return self._open_wizard('cashdro.movimiento.devolucion.wizard', _('Devolución'))

    def action_carga(self):
        """Abre wizard de carga de dinero."""
        return self._open_wizard('cashdro.movimiento.carga.wizard', _('Carga de dinero'))

    def action_inicializar_niveles(self):
        """Abre wizard de inicializar niveles."""
        return self._open_wizard('cashdro.movimiento.inicializar.wizard', _('Inicializar niveles'))

    def action_configurar_fianza(self):
        """Abre wizard de configurar fianza."""
        return self._open_wizard('cashdro.movimiento.fianza.wizard', _('Configurar fianza'))

    def action_open_form(self):
        """Abre el formulario de este registro (usado por la acción del menú)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Movimientos'),
            'res_model': 'cashdro.caja.movimientos',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _open_wizard(self, model_name, title):
        self.ensure_one()
        return {
            'name': title,
            'type': 'ir.actions.act_window',
            'res_model': model_name,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payment_method_id': self.payment_method_id.id,
            },
        }
