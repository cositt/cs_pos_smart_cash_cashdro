/** @odoo-module */

/**
 * Error boundary: si Owl lanza "this.child.mount is not a function" (VToggler)
 * y tenemos un token pendiente de confirmación CashDro, reintentar confirmationPage.
 */
import { App } from "@odoo/owl";

const _handleError = App.prototype.handleError;
App.prototype.handleError = function (params) {
    const { error } = params || {};
    try {
        const url = typeof window !== "undefined" ? window.location.href : "";
        // Logs de depuracion para correlacionar el momento exacto del OwlError.
        if (typeof console !== "undefined" && console.error) {
            const activeSlot =
                typeof window !== "undefined" && window.posmodel?.router?.activeSlot
                    ? window.posmodel.router.activeSlot
                    : null;
            const routerPath =
                typeof window !== "undefined" && window.posmodel?.router?.path
                    ? window.posmodel.router.path
                    : null;
            console.error("[CashDro][OwlErrorBoundary] OwlError captured:", {
                url,
                errorMessage: error?.message,
                causeMessage: error?.cause?.message,
                routerActiveSlot: activeSlot,
                routerPath,
            });
            if (error?.cause) {
                console.error("[CashDro][OwlErrorBoundary] cause:", error.cause);
            }
        }
    } catch (_) {
        // No romper el flujo de Owl; esto es solo debug.
    }
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
