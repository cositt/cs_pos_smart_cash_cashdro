/** Compatibilidad POS: algunos módulos llaman order.getChange()
 * En Odoo 19, el cambio está en la propiedad `change`, no en un método.
 * Este parche añade un wrapper getChange() para evitar TypeError.
 */
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    getChange() {
        return this.change;
    },
});

