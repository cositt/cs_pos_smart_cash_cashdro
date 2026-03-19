/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { PaymentPage } from "@pos_self_order/app/pages/payment_page/payment_page";

/**
 * Patch de la página de pago del kiosk para Cashdrop:
 * - Si payment_status es pending + is_cashdrop: overlay "Pague en la máquina Cashdro" (sin servicio dialog, evita OwlError VToggler).
 * - Al recibir OK de la máquina (state 'F'), se quita el overlay y se confirma la orden.
 * - Para CashDro no se pone state.selection = false, así no se re-renderiza la rama t-else y se evita el VToggler "solo primera vez".
 */
patch(PaymentPage.prototype, {

    selectMethod(methodId) {
        this.state.paymentMethodId = methodId;
        const method = this.selfOrder.models["pos.payment.method"].get(methodId);
        if (!method || !method.cashdro_enabled) {
            this.state.selection = false;
        }
        this.startPayment();
    },

    /**
     * Reemplaza startPayment para capturar la respuesta y manejar Cashdrop pending.
     */
    async startPayment() {
        this.selfOrder.paymentError = false;

        const payload = {
            order: this.selfOrder.currentOrder.serializeForORM(),
            access_token: this.selfOrder.access_token,
            payment_method_id: this.state.paymentMethodId,
        };

        let response;
        try {
            response = await rpc(
                `/kiosk/payment/${this.selfOrder.config.id}/kiosk`,
                payload
            );
            console.log("[Cashdrop] RPC Response:", response);
        } catch (error) {
            console.error("[Cashdrop] RPC Error:", error);
            this.selfOrder.handleErrorNotification(error);
            this.selfOrder.paymentError = true;
            return;
        }

        let ps = response?.payment_status || {};
        console.log("[Cashdrop] Payment Status:", ps);

        // Fallback: si el backend no devolvió payment_status pero tenemos orden y método de pago,
        // intentar iniciar pago CashDro con nuestro endpoint (por si pos_self_order no inyecta payment_status).
        if (!ps.status && response?.order && this.state.paymentMethodId) {
            const orderData = Array.isArray(response.order) ? response.order[0] : response.order;
            const orderId = orderData?.id ?? orderData?.pos_order_id;
            const amount = orderData?.amount_total ?? this.selfOrder.currentOrder?.getTotal?.();
            if (orderId) {
                try {
                    const startResult = await rpc("/cashdro/payment/kiosk/start", {
                        order_id: orderId,
                        payment_method_id: this.state.paymentMethodId,
                        amount: amount,
                    });
                    if (startResult?.success && startResult?.payment_status) {
                        ps = startResult.payment_status;
                        response = { ...response, payment_status: ps, order: response.order };
                        console.log("[Cashdrop] Fallback start OK, payment_status:", ps);
                    }
                } catch (err) {
                    console.warn("[Cashdrop] Fallback start failed (method may not be CashDro):", err);
                }
            }
        }

        // ✓ SI ES CASHDROP Y ESTÁ PENDIENTE: mostrar mensaje y delegar en backend la espera/confirmación
        if (ps.is_cashdrop && ps.status === "pending") {
            console.log("[Cashdrop] Mostrando mensaje y delegando confirmación al backend");
            this._openCashdropPendingAndConfirm(response);
            return;
        }

        // ✗ SI CASHDROP DEVOLVIÓ ERROR
        if (ps.is_cashdrop && ps.status === "error") {
            console.error("[Cashdrop] Payment error:", ps.message);
            this.selfOrder.handleErrorNotification(ps.message || "Error en Cashdrop");
            this.selfOrder.paymentError = true;
            return;
        }

        // ✓ SI NO ES CASHDROP O EL PAGO YA ESTÁ CONFIRMADO: CONTINUAR FLUJO NORMAL
        console.log("[Cashdrop] Applying success, continuing normal flow");
        await super.startPayment();
    },

    _openCashdropPendingAndConfirm(response) {
        const ps = response.payment_status || {};
        const orderData =
            response.order && (Array.isArray(response.order) ? response.order[0] : response.order);
        const orderId = orderData && (orderData.id || orderData.pos_order_id);
        const transactionId = ps.transaction_id;
        const operationId = ps.operation_id;

        // Overlay DOM puro (sin dialog service) para evitar OwlError "this.child.mount is not a function" al cerrar.
        let removeOverlay;
        const handleCancel = () => {
            this._clearCashdropTimeout();
            this._cancelCashdrop(transactionId, operationId, removeOverlay);
        };
        removeOverlay = this._showCashdropOverlay(handleCancel);

        this._cashdropCancelled = false;
        // Si en 60 s no se paga ni se cancela: cancelar en CashDro y reiniciar quiosco.
        const TIMEOUT_MS = 60 * 1000;
        this._cashdropTimeoutId = setTimeout(() => {
            this._cashdropTimeoutId = null;
            this._cancelCashdrop(transactionId, operationId, removeOverlay);
        }, TIMEOUT_MS);

        this._autoConfirmCashdrop(transactionId, orderId, removeOverlay);
    },

    _clearCashdropTimeout() {
        if (this._cashdropTimeoutId != null) {
            clearTimeout(this._cashdropTimeoutId);
            this._cashdropTimeoutId = null;
        }
    },

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

    async _cancelCashdrop(transactionId, operationId, removeOverlay) {
        this._clearCashdropTimeout();
        try {
            this._cashdropCancelled = true;
            const payload = { transaction_id: transactionId };
            if (operationId) {
                payload.operation_id = operationId;
            }
            const result = await rpc("/cashdro/payment/cancel", payload);
            removeOverlay?.();
            if (result && result.success) {
                this.selfOrder.notification?.add?.({
                    message: result.message || "Pago cancelado",
                    type: "warning",
                });
            } else {
                this.selfOrder.handleErrorNotification(
                    result?.error || "Error al cancelar pago en CashDro"
                );
            }
        } catch (error) {
            removeOverlay?.();
            this.selfOrder.handleErrorNotification(
                error?.message || error || "Error al cancelar pago en CashDro"
            );
        }
        this.state.selection = true;
        this.state.paymentMethodId = null;
        this.selfOrder.paymentError = true;
        if (this.router && typeof this.router.navigate === "function") {
            this.router.navigate("default");
        }
    },

    async _autoConfirmCashdrop(transactionId, orderId, removeOverlay) {
        try {
            const result = await rpc("/cashdro/payment/kiosk/confirm", {
                transaction_id: transactionId,
                order_id: orderId,
            });
            if (this._cashdropCancelled) {
                this._clearCashdropTimeout();
                removeOverlay?.();
                return;
            }
            if (result && result.success) {
                this._clearCashdropTimeout();
                removeOverlay?.();
                // Igual que PAYMENT_STATUS en terminal: datos pagados en el modelo local
                // para que el ticket comensal y printKioskChanges (cocina) tengan líneas/estado correctos.
                if (result.order_sync && this.selfOrder.models?.connectNewData) {
                    try {
                        this.selfOrder.models.connectNewData(result.order_sync);
                    } catch (e) {
                        console.warn("[Cashdrop] connectNewData order_sync:", e);
                    }
                }
                this.selfOrder.notification?.add?.({
                    message: result.message || "Orden enviada a cocina",
                    type: "success",
                });
                const accessToken =
                    result.order_sync?.["pos.order"]?.[0]?.access_token ||
                    this.selfOrder.currentOrder?.access_token;
                const navigate = () => {
                    if (accessToken) {
                        // "order" alinea con pos_self_order tras pago terminal (no "pay").
                        this.selfOrder.confirmationPage("order", "kiosk", accessToken);
                    } else {
                        this.router.back();
                    }
                };
                requestAnimationFrame(() => {
                    requestAnimationFrame(navigate);
                });
            } else {
                this._clearCashdropTimeout();
                removeOverlay?.();
                this.selfOrder.handleErrorNotification(result?.error || "Error al confirmar pago");
            }
        } catch (error) {
            this._clearCashdropTimeout();
            removeOverlay?.();
            this.selfOrder.handleErrorNotification(error?.message || error || "Error al confirmar pago");
        }
    },

    _applyPaymentSuccess(response) {
        // Cargar resultado de orden si el servicio lo permite (pos_self_order puede exponer loadOrderResult)
        if (typeof this.selfOrder.loadOrderResult === "function") {
            this.selfOrder.loadOrderResult(response);
        } else if (response.order) {
            const orderList = Array.isArray(response.order) ? response.order : [response.order];
            if (orderList.length && orderList[0]) {
                this.selfOrder.currentOrder.serverId = orderList[0].id;
            }
        }
        this.router.back();
    },
});
