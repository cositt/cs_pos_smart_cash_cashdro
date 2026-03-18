# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

from odoo import models, api, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    @api.constrains("payment_method_ids")
    def _check_payment_method_ids_journal(self):
        """
        El core exige que un método de pago con diario tipo 'cash' solo esté en un PdV.
        Para métodos CashDro (cashdro_enabled) permitimos usarlos en varios PdV:
        es un terminal compartido, no caja física por PdV.
        """
        for config in self:
            cash_methods = config.payment_method_ids.filtered(
                lambda m: m.journal_id and m.journal_id.type == "cash"
            )
            for cash_method in cash_methods:
                if getattr(cash_method, "cashdro_enabled", False):
                    continue
                if self.env["pos.config"].search_count(
                    [
                        ("id", "!=", config.id),
                        ("payment_method_ids", "in", cash_method.ids),
                    ],
                    limit=1,
                ):
                    raise ValidationError(
                        _(
                            "This cash payment method is already used in another Point of Sale.\n"
                            "A new cash payment method should be created for this Point of Sale."
                        )
                    )
                if len(cash_method.journal_id.pos_payment_method_ids) > 1:
                    raise ValidationError(
                        _(
                            "You cannot use the same journal on multiples cash payment methods."
                        )
                    )

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
