/** @odoo-module */

/**
 * Error boundary: si Owl lanza "this.child.mount is not a function" (VToggler)
 * y tenemos un token pendiente de confirmación CashDro, reintentar confirmationPage.
 */
import { App } from "@odoo/owl";

const _handleError = App.prototype.handleError;
App.prototype.handleError = function (params) {
    const { error } = params || {};
    const isVTogglerMount =
        error?.cause?.message?.includes?.("mount is not a function") ||
        error?.message?.includes?.("mount is not a function");
    const token = typeof sessionStorage !== "undefined" && sessionStorage.getItem("cashdro_confirm_token");
    if (isVTogglerMount && token && typeof window !== "undefined" && window.posmodel) {
        try {
            sessionStorage.removeItem("cashdro_confirm_token");
            window.posmodel.confirmationPage("pay", "kiosk", token);
            return;
        } catch (e) {
            console.warn("[CashDro] Retry confirmation failed", e);
        }
    }
    return _handleError.call(this, params);
};
