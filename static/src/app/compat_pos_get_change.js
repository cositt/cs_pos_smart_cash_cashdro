/** Compatibilidad POS: algunos módulos llaman order.getChange()
 * En Odoo 19, el cambio está calculado en PosOrderAccounting.change (getter).
 * Este parche añade un método getChange() que delega al getter change para compatibilidad.
 * 
 * IMPORTANTE: PosOrder extiende PosOrderAccounting que ya tiene un getter `change`
 * que calcula: totalDue - amountPaid, aplicando redondeos si es necesario.
 */
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    /**
     * Método de compatibilidad que retorna el getter `change` de la clase base.
     * Algunos módulos (especialmente enterprise) esperan una función getChange()
     * en lugar de acceder directamente a la propiedad `change`.
     * 
     * @returns {number} El cambio calculado (totalDue - amountPaid con redondeos)
     */
    getChange() {
        // Retorna el getter `change` de PosOrderAccounting (clase base)
        // que contiene la lógica completa de cálculo del cambio
        return this.change;
    },
});

