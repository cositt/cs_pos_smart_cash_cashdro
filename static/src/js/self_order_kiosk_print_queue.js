/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";

/**
 * Impresión secuencial en quiosco (cocina → ticket): configurable en
 * Ajustes → TPV → Mobile self-order & Kiosk → "Impresión en quiosco".
 * Si self_ordering_kiosk_sequential_print es false, se usa el flujo estándar Odoo.
 */
patch(SelfOrder.prototype, {
    async confirmationPage(screen_mode, device, access_token) {
        if (!access_token) {
            throw new Error("No access token provided for confirmation page");
        }
        const sequential =
            this.kioskMode &&
            this.config.self_ordering_kiosk_sequential_print !== false;

        if (sequential) {
            try {
                await this.printKioskChanges(access_token);
            } catch (e) {
                console.warn("[CashDro] printKioskChanges:", e);
            }
        }

        this.router.navigate("confirmation", {
            orderAccessToken: access_token || this.currentOrder.access_token,
            screenMode: screen_mode,
        });

        if (this.kioskMode && !sequential) {
            this.printKioskChanges(access_token);
        } else if (!this.kioskMode) {
            this.printKioskChanges(access_token);
        }
        this.resetCategorySelection();
    },
});
