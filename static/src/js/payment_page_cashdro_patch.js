/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { PaymentPage } from "@pos_self_order/app/pages/payment_page/payment_page";
import { createCashdroKioskService } from "@cs_pos_smart_cash_cashdro/app/self_order/cashdro_kiosk_service";

/**
 * Patch de la página de pago del kiosk para CashDro - VERSIÓN MIGRADA A JAVASCRIPT.
 * 
 * Cambios principales:
 * - Antes: Hacía RPC al servidor Python, que hacía requests al CashDro
 * - Ahora: JavaScript hace fetch() directo al CashDro desde el navegador
 * - Polling desde cliente (no RPC al servidor)
 * - Solo RPC al servidor para guardar resultado (persistencia)
 */
patch(PaymentPage.prototype, {

    selectMethod(methodId) {
        const method = this.selfOrder?.models?.["pos.payment.method"]?.get?.(methodId);

        this.state.paymentMethodId = methodId;
        if (!method || !method.cashdro_enabled) {
            this.state.selection = false;
        }
        this.startPayment();
    },

    /**
     * Reemplaza startPayment para usar el nuevo flujo JavaScript directo al CashDro.
     */
    async startPayment() {
        this.selfOrder.paymentError = false;

        const method = this.selfOrder?.models?.["pos.payment.method"]?.get?.(this.state.paymentMethodId);
        
        // Si NO es CashDro, usar flujo normal
        if (!method || !method.cashdro_enabled) {
            await super.startPayment();
            return;
        }

        // ✓ ES CASHDRO: Usar nuevo flujo JavaScript directo
        console.log("[CashDro Kiosk] Iniciando pago con nuevo flujo JavaScript");
        
        try {
            // Crear servicio CashDro
            const cashdroService = createCashdroKioskService(this.selfOrder, this.state.paymentMethodId);
            
            // Obtener datos de la orden
            const order = this.selfOrder.currentOrder;
            const amount = order?.getTotal?.() || order?.amount_total || 0;
            const orderId = order?.id || order?.serverId;
            
            console.log("[CashDro Kiosk] Orden:", { orderId, amount });
            
            // Mostrar overlay de "Pague en la máquina"
            let removeOverlay;
            const handleCancel = () => {
                cashdroService.cancel();
                this._cancelCashdroKiosk(removeOverlay);
            };
            removeOverlay = this._showCashdropOverlay(handleCancel);
            
            // Timeout de seguridad (3 minutos)
            const TIMEOUT_MS = 180 * 1000;
            const timeoutId = setTimeout(() => {
                cashdroService.cancel();
                this._cancelCashdroKiosk(removeOverlay);
            }, TIMEOUT_MS);
            
            // Procesar pago con polling
            const result = await cashdroService.processPayment(amount, orderId, (progress) => {
                console.log(`[CashDro Kiosk] Progreso: ${progress.state}, intento ${progress.attemptCount}`);
            });
            
            clearTimeout(timeoutId);
            
            if (result.cancelled) {
                removeOverlay?.();
                this.selfOrder.notification?.add?.(_t("Pago cancelado"), { type: "warning" });
                this.state.selection = true;
                this.state.paymentMethodId = null;
                this.selfOrder.paymentError = true;
                return;
            }
            
            if (!result.success) {
                removeOverlay?.();
                this.selfOrder.handleErrorNotification(result.message || _t("Error en el pago"));
                this.selfOrder.paymentError = true;
                return;
            }
            
            // ✓ PAGO EXITOSO
            removeOverlay?.();
            console.log("[CashDro Kiosk] Pago exitoso, confirmando orden...");
            
            // Confirmar orden en Odoo
            await this._confirmOrderAfterPayment(orderId);
            
        } catch (error) {
            console.error("[CashDro Kiosk] Error:", error);
            this.selfOrder.handleErrorNotification(error.message || _t("Error en el pago CashDro"));
            this.selfOrder.paymentError = true;
        }
    },

    /**
     * Confirma la orden después de pago exitoso.
     */
    async _confirmOrderAfterPayment(orderId) {
        try {
            // Llamar al endpoint de confirmación
            const result = await rpc("/cashdro/payment/kiosk/confirm-js", {
                order_id: orderId,
            });
            
            if (result && result.success) {
                // Sincronizar datos de la orden
                if (result.order_sync && this.selfOrder.models?.connectNewData) {
                    try {
                        this.selfOrder.models.connectNewData(result.order_sync);
                    } catch (e) {
                        console.warn("Error sincronizando orden:", e);
                    }
                }
                
                // Notificación de éxito
                const msg = result.message || _t("Orden pagada y enviada a cocina");
                this.selfOrder.notification?.add?.(msg, { type: "success" });
                
                // Navegar a página de confirmación
                const accessToken =
                    result.order_sync?.["pos.order"]?.[0]?.access_token ||
                    this.selfOrder.currentOrder?.access_token;
                
                if (accessToken) {
                    this.selfOrder.confirmationPage("order", "kiosk", accessToken);
                } else {
                    this.router.back();
                }
            } else {
                this.selfOrder.handleErrorNotification(result?.error || _t("Error al confirmar orden"));
                this.selfOrder.paymentError = true;
            }
        } catch (error) {
            console.error("[CashDro Kiosk] Error confirmando orden:", error);
            this.selfOrder.handleErrorNotification(_t("Error al confirmar la orden en Odoo"));
            this.selfOrder.paymentError = true;
        }
    },

    /**
     * Cancela el pago del quiosco.
     */
    async _cancelCashdroKiosk(removeOverlay) {
        removeOverlay?.();
        this.state.selection = true;
        this.state.paymentMethodId = null;
        this.selfOrder.paymentError = true;
        if (this.router && typeof this.router.navigate === "function") {
            this.router.navigate("default");
        }
    },

    /**
     * Muestra overlay de "Pague en la máquina CashDro".
     */
    _showCashdropOverlay(onCancel) {
        const overlay = document.createElement("div");
        overlay.className = "cashdrop-pending-overlay position-fixed top-0 start-0 end-0 bottom-0 d-flex align-items-center justify-content-center bg-dark bg-opacity-75";
        overlay.style.zIndex = "9999";
        overlay.innerHTML = `
            <div class="bg-white rounded-4 shadow-lg p-5 text-center mx-3" style="max-width: 22em;">
                <div class="mb-4">
                    <i class="fa fa-money fa-4x text-success" aria-hidden="true"></i>
                </div>
                <h2 class="mb-3 fw-bold text-dark">Pague en la máquina Cashdro</h2>
                <p class="lead text-muted mb-0">Inserte el efectivo en la máquina. La orden se confirmará automáticamente al completar el pago.</p>
                <button type="button" class="btn btn-outline-secondary mt-4 w-100 cashdrop-cancel-btn">
                    Cancelar pago y volver
                </button>
            </div>
        `;
        document.body.appendChild(overlay);
        const cancelBtn = overlay.querySelector(".cashdrop-cancel-btn");
        if (cancelBtn && typeof onCancel === "function") {
            cancelBtn.addEventListener("click", (ev) => {
                ev.preventDefault();
                onCancel();
            });
        }
        return () => {
            if (overlay.parentNode) {
                overlay.remove();
            }
        };
    },
});
