/** Compatibilidad POS: asegurar order.getChange() durante la validación
 * Algunos módulos enterprise siguen llamando order.getChange() dentro de
 * PaymentScreen.validateOrder. Si el método no existe, se produce un TypeError.
 * Este parche lo define dinámicamente sobre la orden actual antes de validar.
 */
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

const superValidateOrder = PaymentScreen.prototype.validateOrder;

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate = false) {
        const order = this.currentOrder;
        if (order && typeof order.getChange !== "function") {
            order.getChange = function () {
                return this.change;
            };
        }
        return await superValidateOrder.call(this, isForceValidate);
    },
});

