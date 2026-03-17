/**
 * Interface de reembolso CashDro para la caja registradora (POS).
 * Asociado a métodos de pago con use_payment_terminal === 'cashdro_refund'.
 * No modifica el flujo de cobro existente (terminal 'cashdro').
 */
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";

export class PaymentCashdroRefund extends PaymentInterface {
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
                _t("¿Deseas realizar el reembolso usando la máquina CashDro?"),
            ]
                .filter((l) => l)
                .join("\n");

            return new Promise((resolve) => {
                this.env.services.dialog.add(ConfirmationDialog, {
                    title: _t("Resumen de máquina CashDro"),
                    body,
                    confirmLabel: _t("Reembolsar en CashDro"),
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
            this._showError(_t("El importe de la línea de reembolso debe ser mayor que cero."));
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
            const result = await rpc("/cashdro/payment/pos_refund/start", {
                payment_method_id: this.payment_method_id.id,
                amount,
            });

            if (!result || !result.success) {
                this._showError(result?.error || _t("Error al iniciar reembolso en CashDro."));
                line.setPaymentStatus("retry");
                return false;
            }

            // Flujo simple: si startOperation ha ido bien, dejamos que la máquina gestione
            // la dispensación y marcamos la línea como completada.
            line.setPaymentStatus("done");
            return true;
        } catch (e) {
            this._showError(
                _t(
                    "No se ha podido comunicar con el servidor o con la máquina CashDro para el reembolso. Revisa la conexión."
                )
            );
            line.setPaymentStatus("retry");
            return false;
        }
    }

    async sendPaymentCancel(_order, _uuid) {
        // El reembolso usa un flujo simple sin seguimiento de transacción; no hay nada que cancelar.
        return true;
    }

    _showError(msg) {
        this.env.services.dialog.add(AlertDialog, {
            title: _t("Error CashDro"),
            body: msg,
        });
    }
}

register_payment_method("cashdro_refund", PaymentCashdroRefund);

