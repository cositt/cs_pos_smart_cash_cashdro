/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";

/**
 * Patch del servicio de self-order para que el kiosk trate CashDro
 * como un método de pago válido y navegue a la PaymentPage.
 *
 * Por defecto, filterPaymentMethods solo considera terminales Adyen/Stripe.
 * Aquí añadimos también el método de efectivo CashDro para que
 * `confirmOrder()` haga `router.navigate("payment")` en modo kiosk.
 */
patch(SelfOrder.prototype, {
    filterPaymentMethods(pms) {
        // Llamamos al comportamiento original
        const base = super.filterPaymentMethods
            ? super.filterPaymentMethods(pms)
            : (this.config.self_ordering_mode === "kiosk"
                  ? pms.filter((rec) => ["adyen", "stripe"].includes(rec.use_payment_terminal))
                  : []);

        // Solo en modo kiosk nos interesa forzar CashDro
        if (this.config.self_ordering_mode !== "kiosk") {
            return base;
        }

        // Incluir métodos CashDro: por flag (backend los envía si _load_pos_self_data_domain los incluye)
        // o por nombre por compatibilidad.
        const cashdroMethods = pms.filter(
            (pm) => pm.cashdro_enabled === true || pm.name === "Efectivo cashdro"
        );

        if (!cashdroMethods.length) {
            return base;
        }

        const merged = [...base];
        for (const m of cashdroMethods) {
            if (!merged.includes(m)) {
                merged.push(m);
            }
        }
        return merged;
    },
});

