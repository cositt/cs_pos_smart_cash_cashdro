/** Compatibilidad POS: asegurar order.getChange() durante la validación
 * Algunos módulos enterprise siguen llamando order.getChange() dentro de
 * PaymentScreen.validateOrder. Si el método no existe, se produce un TypeError.
 * Este parche lo define dinámicamente sobre la orden actual antes de validar.
 * 
 * NOTA: Con el compat_pos_get_change.js ya activado, esto es redundante,
 * pero se mantiene como capas de defensa en caso de que el orden de carga
 * de módulos sea diferente o para máxima compatibilidad.
 */
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

const superValidateOrder = PaymentScreen.prototype.validateOrder;

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate = false) {
        const order = this.currentOrder;
        // Asegurar que existe el método getChange (como medida de defensa)
        if (order && typeof order.getChange !== "function") {
            order.getChange = function () {
                // Retorna el getter `change` de PosOrderAccounting
                return this.change;
            };
        }
        return await superValidateOrder.call(this, isForceValidate);
    },
});

