# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

from odoo import models, api
from odoo.exceptions import ValidationError
from odoo import _


class PosConfig(models.Model):
    _inherit = "pos.config"

    @api.constrains("payment_method_ids", "self_ordering_mode")
    def _check_kiosk_payment_methods(self):
        """
        Override de la validación de pos_self_order que bloquea cash en kiosk.
        Permitimos Cashdrop en kiosk porque es una máquina automática que maneja el dinero.
        """
        for record in self:
            if record.self_ordering_mode == "kiosk":
                # Permitimos Cashdrop (es un terminal automático, no cash manual)
                cash_methods = record.payment_method_ids.filtered(
                    lambda pm: pm.is_cash_count
                    and not (pm.journal_id and pm.journal_id.name == "Cashdrop")
                )
                if cash_methods:
                    raise ValidationError(
                        _(
                            "No puede agregar métodos de pago en efectivo al modo de quiosco, excepto Cashdrop."
                        )
                    )
