/** @odoo-module */

/**
 * Guard para depurar y evitar crash Owl:
 * - Si un toggler genera un child que NO tiene `.mount`, logueamos `key` y el shape del child.
 * - Reemplazamos ese child por `blockDom.text("")` para evitar `this.child.mount is not a function`.
 *
 * Nota: esto es para investigación/diagnóstico y estabilidad del kiosko.
 */
import { blockDom } from "@odoo/owl";

if (blockDom && typeof blockDom.toggler === "function" && typeof blockDom.text === "function" && !blockDom.__cashdroVTogglerMountPatched__) {
    blockDom.__cashdroVTogglerMountPatched__ = true;
    console.log("[CashDro][TogglerGuard] initialized (patch VToggler.mount)");

    // Obtener la clase real de VToggler usando un toggler de muestra.
    const sample = blockDom.toggler("__cashdro_sample__", blockDom.text(""));
    const VTogglerClass = sample?.constructor;
    const originalMount = VTogglerClass?.prototype?.mount;

    if (typeof originalMount === "function") {
        VTogglerClass.prototype.mount = function (parent, afterNode) {
            const child = this?.child;
            const hasMount = Boolean(child && typeof child.mount === "function");
            if (!hasMount) {
                try {
                    const stack = new Error().stack;
                    let keys = [];
                    if (child && typeof child === "object" && !Array.isArray(child)) {
                        keys = Object.keys(child).slice(0, 30);
                    } else if (Array.isArray(child)) {
                        keys = [`<array len=${child.length}>`];
                    }
                    const childType =
                        child?.constructor?.name ||
                        (typeof child === "object" ? "object" : typeof child);
                    const key = this?.key;
                    const hasFirstNode = Boolean(child && typeof child.firstNode === "function");
                    console.error(
                        "[CashDro][TogglerGuard] child missing mount (patched mount)",
                        "key=", key,
                        "childType=", childType,
                        "hasFirstNode=", hasFirstNode,
                        "childKeys=", keys
                    );
                    if (stack) {
                        console.error("[CashDro][TogglerGuard] stack (patched mount)", stack);
                    }
                } catch (e) {
                    console.error("[CashDro][TogglerGuard] log failed", e);
                }
                this.child = blockDom.text("");
            }
            return originalMount.call(this, parent, afterNode);
        };
    } else {
        console.warn("[CashDro][TogglerGuard] VTogglerClass.mount not found");
    }
}

