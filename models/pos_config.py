# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

from odoo import models, api, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    @api.constrains("payment_method_ids", "self_ordering_mode")
    def _onchange_payment_method_ids(self):
        """
        Sustituye la validación de pos_self_order que bloquea TODO efectivo en kiosk.
        Aquí solo bloqueamos métodos de efectivo que NO estén marcados como CashDro
        (cashdro_enabled=True). Es decir:
        - Efectivo normal: prohibido en kiosk.
        - Efectivo CashDro: permitido en kiosk.
        """
        for record in self:
            if record.self_ordering_mode == "kiosk":
                cash_methods = record.payment_method_ids.filtered(
                    lambda pm: pm.is_cash_count and not getattr(pm, "cashdro_enabled", False)
                )
                if cash_methods:
                    # Traducción alineada con la original, añadiendo la excepción Cashdrop.
                    raise ValidationError(
                        _(
                            "No puede agregar métodos de pago en efectivo al modo de quiosco, excepto Cashdrop."
                        )
                    )
