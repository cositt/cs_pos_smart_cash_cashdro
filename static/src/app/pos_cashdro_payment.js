/**
 * Interface de pago CashDro para la caja registradora (POS).
 * Al pulsar el método de pago "Efectivisimo" (use_payment_terminal === 'cashdro'),
 * se añade la línea y se dispara sendPaymentRequest: resumen máquina, start, polling, confirm.
 */
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";

const POLLING_INTERVAL_MS = 2000;
const POLLING_TIMEOUT_MS = 60000;

export class PaymentCashdro extends PaymentInterface {
    setup() {
        super.setup(...arguments);
    }

    get fastPayments() {
        return true;
    }

    async _askMachineSummary() {
        try {
            const summary = await rpc("/cashdro/payment/pos/summary", {
                payment_method_id: this.payment_method_id.id,
            });
            if (!summary || !summary.success) {
                this._showError(summary?.error || _t("Error obteniendo información de CashDro."));
                return false;
            }
            const connectionLabel =
                summary.connection_status === "connected"
                    ? _t("Conectado")
                    : summary.connection_status === "disconnected"
                      ? _t("Desconectado")
                      : summary.connection_status === "error"
                        ? _t("Error")
                        : _t("No probado");
            const body = [
                _t("Estado de conexión: %s", connectionLabel),
                summary.error_message ? _t("Último error: %s", summary.error_message) : "",
                "",
                _t("¿Deseas cobrar esta venta usando la máquina CashDro?"),
            ]
                .filter((l) => l)
                .join("\n");

            return new Promise((resolve) => {
                this.env.services.dialog.add(ConfirmationDialog, {
                    title: _t("Resumen de máquina CashDro"),
                    body,
                    confirmLabel: _t("Cobrar en CashDro"),
                    cancelLabel: _t("Cancelar"),
                    confirm: () => resolve(true),
                    cancel: () => resolve(false),
                });
            });
        } catch (e) {
            const msg =
                (e && (e.message || e.data?.message || e.data?.data?.message)) ||
                (e && typeof e === "string" ? e : null);
            this._showError(
                msg
                    ? _t("CashDro: %s", msg)
                    : _t("No se ha podido obtener el estado de la máquina CashDro. Revisa la conexión.")
            );
            return false;
        }
    }

    async sendPaymentRequest(uuid) {
        const order = this.pos.getOrder();
        const line = order.getPaymentlineByUuid(uuid);
        if (!line) return false;
        const amount = Math.abs(line.getAmount ? line.getAmount() : line.amount);
        if (!amount || amount <= 0) {
            this._showError(_t("El importe de la línea de pago debe ser mayor que cero."));
            line.setPaymentStatus("retry");
            return false;
        }

        const useCashdro = await this._askMachineSummary();
        if (!useCashdro) {
            line.setPaymentStatus("retry");
            return false;
        }

        try {
            line.setPaymentStatus("waiting");
            const posOrderId = order.id || order.server_id || null;
            const result = await rpc("/cashdro/payment/pos/start", {
                payment_method_id: this.payment_method_id.id,
                amount,
                pos_session_id: this.pos.session?.id || null,
                pos_order_id: posOrderId,
            });

            if (!result || !result.success) {
                this._showError(result?.error || _t("Error al iniciar pago en CashDro."));
                line.setPaymentStatus("retry");
                return false;
            }

            const transactionId = result.transaction_id;
            line.uiState = line.uiState || {};
            line.uiState.cashdroTransactionId = transactionId;

            return await this._waitForPayment(line, transactionId);
        } catch (e) {
            this._showError(
                _t(
                    "No se ha podido comunicar con el servidor o con la máquina CashDro. Revisa la conexión."
                )
            );
            line.setPaymentStatus("retry");
            return false;
        }
    }

    async _waitForPayment(line, transactionId) {
        const startedAt = Date.now();

        return new Promise((resolve) => {
            const tick = async () => {
                const stillWaiting =
                    !line.isDone() &&
                    ["waiting", "waitingCard", "timeout"].includes(line.getPaymentStatus?.() || line.payment_status) &&
                    (line.uiState?.cashdroTransactionId === transactionId);

                if (!stillWaiting) {
                    resolve((line.getPaymentStatus?.() || line.payment_status) === "done");
                    return;
                }

                if (Date.now() - startedAt > POLLING_TIMEOUT_MS) {
                    line.setPaymentStatus("timeout");
                    this._showError(
                        _t(
                            "Tiempo de espera agotado esperando confirmación de pago en CashDro. Revisa el estado en la máquina."
                        )
                    );
                    resolve(false);
                    return;
                }

                try {
                    const status = await rpc("/cashdro/payment/pos/status", {
                        transaction_id: transactionId,
                    });
                    if (!status || !status.success) {
                        setTimeout(tick, POLLING_INTERVAL_MS);
                        return;
                    }

                    const txStatus = status.status;
                    if (txStatus === "confirmed") {
                        const confirm = await rpc("/cashdro/payment/pos/confirm", {
                            transaction_id: transactionId,
                        });
                        if (!confirm || !confirm.success) {
                            this._showError(
                                confirm?.error || _t("Error confirmando el pago en CashDro desde el servidor.")
                            );
                            line.setPaymentStatus("retry");
                            resolve(false);
                            return;
                        }
                        const amountReceived = confirm.amount_received || 0;
                        if (amountReceived <= 0) {
                            this._showError(
                                _t(
                                    "La máquina CashDro no ha devuelto ningún importe confirmado. Revisa la operación antes de cerrar el ticket."
                                )
                            );
                            line.setPaymentStatus("retry");
                            resolve(false);
                            return;
                        }
                        line.setPaymentStatus("done");
                        line.transaction_id = transactionId;
                        resolve(true);
                    } else if (["cancelled", "error", "timeout"].includes(txStatus)) {
                        this._showError(
                            status.message ||
                                _t("El pago ha sido cancelado o ha fallado en la máquina CashDro.")
                        );
                        line.setPaymentStatus("retry");
                        resolve(false);
                    } else {
                        setTimeout(tick, POLLING_INTERVAL_MS);
                    }
                } catch (e) {
                    setTimeout(tick, POLLING_INTERVAL_MS);
                }
            };
            setTimeout(tick, POLLING_INTERVAL_MS);
        });
    }

    async sendPaymentCancel(order, uuid) {
        const line = order.getPaymentlineByUuid(uuid);
        const transactionId = line?.uiState?.cashdroTransactionId;
        if (!transactionId) return true;
        try {
            await rpc("/cashdro/payment/cancel", {
                transaction_id: transactionId,
            });
            return true;
        } catch (e) {
            return false;
        }
    }

    _showError(msg) {
        this.env.services.dialog.add(AlertDialog, {
            title: _t("Error CashDro"),
            body: msg,
        });
    }
}

register_payment_method("cashdro", PaymentCashdro);
