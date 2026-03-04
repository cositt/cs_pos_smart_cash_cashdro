/** @odoo-module */

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Diálogo mostrado cuando el pago Cashdrop está pendiente (status: 'pending').
 * El usuario inserta dinero en la máquina y luego pulsa "Confirmar pago".
 */
export class CashdropPendingDialog extends Component {
    static template = "cs_pos_smart_cash_cashdro.CashdropPendingDialog";
    static components = { Dialog };
    static props = {
        message: { type: String, optional: true },
        operation_id: { type: String, optional: true },
        transaction_id: { type: String, optional: true },
        order_id: { type: Number, optional: true },
        onConfirm: { type: Function },
        onCancel: { type: Function },
        close: { type: Function },
    };
}
