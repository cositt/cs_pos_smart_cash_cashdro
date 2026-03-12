/** @odoo-module */

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Mensaje atractivo mientras el pago Cashdrop está pendiente.
 * Sin botón cancelar: se cierra automáticamente al recibir OK de la máquina (polling en PaymentPage).
 */
export class CashdropPendingDialog extends Component {
    static template = "cs_pos_smart_cash_cashdro.CashdropPendingDialog";
    static components = { Dialog };
    // El servicio de diálogos inyecta automáticamente la prop `close`
    // (misma convención que TimeoutPopup en pos_self_order).
    static props = ["close"];
}
