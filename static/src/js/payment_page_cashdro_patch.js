/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { PaymentPage } from "@pos_self_order/app/pages/payment_page/payment_page";
import { CashdropPendingDialog } from "./cashdrop_pending_dialog";

/**
 * Patch de la página de pago del kiosk para Cashdrop:
 * - Si payment_status es pending + is_cashdrop: mensaje "Pague en la máquina Cashdro" y polling.
 * - Al recibir OK de la máquina (state 'F'), se cierra el mensaje y se confirma la orden automáticamente.
 */
patch(PaymentPage.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialog = useService("dialog");
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

        // ✓ SI ES CASHDROP Y ESTÁ PENDIENTE: mensaje simple + polling; al OK de la máquina se cierra y confirma
        if (ps.is_cashdrop && ps.status === "pending") {
            console.log("[Cashdrop] Mostrando mensaje y empezando polling");
            this._openCashdropPendingAndPoll(response);
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

    _openCashdropPendingAndPoll(response) {
        const ps = response.payment_status || {};
        const orderData = response.order && (Array.isArray(response.order) ? response.order[0] : response.order);
        const orderId = orderData && (orderData.id || orderData.pos_order_id);
        const transactionId = ps.transaction_id;
        let dialogRef;
        let pollIntervalId = null;

        const closeDialog = () => {
            if (pollIntervalId !== null) {
                clearInterval(pollIntervalId);
                pollIntervalId = null;
            }
            if (dialogRef && typeof dialogRef.close === "function") {
                dialogRef.close();
            }
        };

        const pollStatus = async () => {
            try {
                const base = typeof window !== "undefined" && window.location ? window.location.origin : "";
                const r = await fetch(`${base}/cashdro/payment/status/${encodeURIComponent(transactionId)}`);
                if (!r.ok) return;
                const data = await r.json();
                const state = data.state;
                const status = data.status;
                if (state === "F" || status === "confirmed") {
                    closeDialog();
                    await this._confirmCashdropPayment(transactionId, orderId, () => {});
                    return;
                }
            } catch (e) {
                console.warn("[Cashdrop] Poll status error:", e);
            }
        };

        dialogRef = this.dialog.add(CashdropPendingDialog, {
            onCancel: () => {
                closeDialog();
                this._cancelCashdropPayment(transactionId, () => {});
            },
            close: closeDialog,
        });

        pollIntervalId = setInterval(pollStatus, 2000);
        pollStatus();
    },

    async _confirmCashdropPayment(transactionId, orderId, closeDialog) {
        try {
            const result = await rpc("/cashdro/payment/kiosk/confirm", {
                transaction_id: transactionId,
                order_id: orderId,
            });
            if (result && result.success) {
                closeDialog();
                this.selfOrder.notification?.add?.({
                    message: result.message || "Orden enviada a cocina",
                    type: "success",
                });
                this.router.back();
            } else {
                this.selfOrder.handleErrorNotification(result?.error || "Error al confirmar pago");
            }
        } catch (error) {
            this.selfOrder.handleErrorNotification(error?.message || error || "Error al confirmar pago");
        }
    },

    async _cancelCashdropPayment(transactionId, closeDialog) {
        try {
            await rpc("/cashdro/payment/cancel", {
                transaction_id: transactionId,
            });
        } catch (_e) {
            // Ignorar error de cancelación
        }
        closeDialog();
        this.state.selection = true;
        this.state.paymentMethodId = null;
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
