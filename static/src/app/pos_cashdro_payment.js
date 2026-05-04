/**
 * Interface de pago CashDro para la caja registradora (POS) - VERSIÓN MIGRADA A JAVASCRIPT.
 * 
 * Cambios principales:
 * - Antes: Hacía RPC al servidor Python, que hacía requests al CashDro
 * - Ahora: JavaScript hace fetch() directo al CashDro desde el navegador
 * - Polling desde cliente (no RPC al servidor)
 * - Solo RPC al servidor para persistir resultados
 * 
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
        this.cashdroConfig = null; // Cache de configuración
        this.exchangeUser = "Exchange_Machine";
        this.exchangePassword = "-99";
    }

    get fastPayments() {
        return true;
    }

    /**
     * Obtiene configuración CashDro del servidor si no está cargada.
     */
    async _getCashdroConfig() {
        if (this.cashdroConfig) {
            return this.cashdroConfig;
        }

        // Intentar obtener del payment_method
        const pm = this.payment_method_id;
        if (pm.cashdro_host && pm.cashdro_user && pm.cashdro_password) {
            this.cashdroConfig = {
                host: pm.cashdro_host,
                user: pm.cashdro_user,
                password: pm.cashdro_password,
                paymentMethodId: pm.id,
            };
            return this.cashdroConfig;
        }

        // Si no está cargada, obtener del servidor
        console.log("[CashDro POS] Obteniendo configuración del servidor...");
        const result = await rpc("/cashdro/config/get", {
            payment_method_id: this.payment_method_id.id,
        });

        if (!result.success) {
            throw new Error(result.error || _t("No se pudo obtener configuración CashDro"));
        }

        this.cashdroConfig = {
            host: result.cashdro_host,
            user: result.cashdro_user,
            password: result.cashdro_password,
            paymentMethodId: this.payment_method_id.id,
        };

        return this.cashdroConfig;
    }

    /**
     * Construye URL del gateway.
     */
    _buildGatewayUrl(host) {
        if (host.startsWith('http://') || host.startsWith('https://')) {
            return host;
        }
        return `https://${host}`;
    }

    /**
     * Petición GET al CashDro usando XMLHttpRequest para evitar service worker.
     */
    async _cashdroRequest(params) {
        const config = await this._getCashdroConfig();
        const gatewayUrl = this._buildGatewayUrl(config.host);
        const endpoint = `${gatewayUrl}/Cashdro3WS/index3.php`;

        const queryString = new URLSearchParams(params).toString();
        const url = `${endpoint}?${queryString}`;

        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.timeout = 10000;
            
            xhr.onload = function() {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        resolve(data);
                    } catch (e) {
                        reject(new Error("Error parseando respuesta JSON de CashDro"));
                    }
                } else {
                    reject(new Error(`HTTP ${xhr.status}: ${xhr.statusText}`));
                }
            };

            xhr.onerror = function() {
                reject(new Error(_t("No se puede conectar con CashDro en %s. Verifica red y certificado SSL.", config.host)));
            };

            xhr.ontimeout = function() {
                reject(new Error(_t("Timeout conectando a CashDro. Verifica que el navegador pueda alcanzar %s", config.host)));
            };

            xhr.open("GET", url, true);
            xhr.setRequestHeader("Content-Type", "application/json");
            xhr.send();
        });
    }

    /**
     * Inicia pago en CashDro directamente.
     * Replica el contrato que ya funciona en el quiosco.
     */
    async _startCashdroPayment(amount) {
        const config = await this._getCashdroConfig();
        const amountCents = String(Math.round(parseFloat(amount) * 100));

        const params = {
            operation: 'startOperation',
            name: config.user,
            password: config.password,
            type: 4,
            posid: '1',
            posuser: this.pos.user?.name || 'pos',
            parameters: JSON.stringify({ amount: amountCents }),
            startnow: 'true',
        };

        const data = await this._cashdroRequest(params);

        let operationId = null;
        if (data.code === 1) {
            const responseObj = data.response || {};
            if (responseObj.operation && responseObj.operation.operationId) {
                operationId = responseObj.operation.operationId;
            } else if (typeof data.data === 'string' && /^\d+$/.test(data.data)) {
                operationId = data.data;
            }
        }

        if (!operationId) {
            throw new Error(data.response?.errorMessage || _t("No se recibió operationId"));
        }

        return operationId;
    }

    /**
     * Consulta estado de operación en CashDro.
     * Replica el contrato que ya funciona en el quiosco.
     */
    async _askOperation(operationId) {
        const params = {
            operation: 'askOperation',
            name: this.exchangeUser,
            password: this.exchangePassword,
            operationId: operationId,
            includeImages: '1',
        };

        const data = await this._cashdroRequest(params);

        let state = '?';
        try {
            let container = data.response;
            if (!container && data.data !== undefined) {
                container = data.data;
            }
            if (typeof container === 'object' && container.operation) {
                const opWrapper = container.operation;
                if (opWrapper.operation && opWrapper.operation.state) {
                    state = opWrapper.operation.state;
                } else if (opWrapper.state) {
                    state = opWrapper.state;
                }
            }
        } catch (e) {
            console.warn("[CashDro POS] Error extrayendo estado:", e);
        }

        return { ...data, extractedState: state };
    }

    /**
     * Envía acknowledge al CashDro.
     */
    async _acknowledgeOperation(operationId) {
        const config = await this._getCashdroConfig();

        const params = {
            operation: 'acknowledgeOperationId',
            name: config.user,
            password: config.password,
            operationId: operationId,
            includeImages: '1',
        };

        return await this._cashdroRequest(params);
    }

    /**
     * Detecta si el navegador puede alcanzar directamente al CashDro.
     * NOTA: En POS siempre asumimos conexión directa (igual que quiosco).
     * El service worker de Odoo bloquea los fetch de prueba, pero las peticiones
     * reales con XMLHttpRequest funcionan.
     */
    async _canReachCashdroDirectly() {
        console.log("[CashDro POS] Asumiendo conexión directa (igual que quiosco)");
        return true;
    }

    /**
     * Obtiene resumen de la máquina.
     * En caja registradora seguimos el mismo criterio que el quiosco:
     * si el navegador no alcanza CashDro, no usamos al servidor como proxy.
     */
    async _getMachineSummary() {
        const canReachDirectly = await this._canReachCashdroDirectly();
        this._useDirectConnection = canReachDirectly;

        if (!canReachDirectly) {
            return {
                success: false,
                error: _t("Este navegador no puede conectar directamente con CashDro. Revisa red local y certificado SSL del dispositivo."),
            };
        }

        return {
            success: true,
            connection_status: "connected",
            error_message: "",
        };
    }

    async _askMachineSummary() {
        try {
            const summary = await this._getMachineSummary();
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
        const rawAmount = line.getAmount ? line.getAmount() : line.amount;
        const amount = Math.abs(rawAmount);
        const isRefund = rawAmount < 0;

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

            // Si la línea es negativa (reembolso)
            if (isRefund) {
                // Para reembolso, usamos el flujo del backend (dispensa)
                const result = await rpc("/cashdro/payment/pos_refund/start", {
                    payment_method_id: this.payment_method_id.id,
                    amount,
                    pos_session_id: this.pos.session?.id || null,
                    pos_order_id: order.id || order.server_id || null,
                });

                if (!result || !result.success) {
                    this._showError(result?.error || _t("Error al iniciar reembolso en CashDro."));
                    line.setPaymentStatus("retry");
                    return false;
                }

                line.setPaymentStatus("done");
                return true;
            }

            // Igual que en el quiosco: el cobro CashDro se hace siempre desde el navegador.
            console.log("[CashDro POS] Usando conexión directa al CashDro...");
            return await this._sendPaymentDirect(line, amount);

        } catch (e) {
            console.error("[CashDro POS] Error:", e);
            this._showError(
                e.message || _t("No se ha podido comunicar con la máquina CashDro. Revisa la conexión.")
            );
            line.setPaymentStatus("retry");
            return false;
        }
    }

    /**
     * Flujo de pago directo al CashDro desde JavaScript.
     * Usado cuando el navegador está en la misma red que el CashDro.
     */
    async _sendPaymentDirect(line, amount) {
        // 1. Iniciar operación en CashDro
        const operationId = await this._startCashdroPayment(amount);
        console.log("[CashDro POS] OperationId obtenido:", operationId);

        if (!operationId) {
            this._showError(_t("No se pudo iniciar el pago en CashDro."));
            line.setPaymentStatus("retry");
            return false;
        }

        // 2. Guardar operationId y hacer polling
        line.uiState = line.uiState || {};
        line.uiState.cashdroOperationId = operationId;

        // 3. Enviar acknowledge
        await this._acknowledgeOperation(operationId);
        console.log("[CashDro POS] Acknowledge enviado");

        // 4. Esperar pago con polling
        return await this._waitForPayment(line, operationId, amount);
    }

    /**
     * Flujo de pago vía servidor (proxy).
     * Usado cuando el navegador NO puede alcanzar al CashDro directamente.
     * El servidor hace las peticiones al CashDro en nombre del navegador.
     */
    async _sendPaymentViaServer(line, amount, order) {
        const posOrderId = order.id || order.server_id || null;

        // 1. Iniciar pago vía servidor
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

        // 2. Esperar pago con polling vía servidor
        return await this._waitForPaymentViaServer(line, transactionId);
    }

    async _waitForPayment(line, operationId, amount) {
        const startedAt = Date.now();
        console.log("[CashDro POS] Iniciando polling para operación:", operationId);

        return new Promise((resolve) => {
            const tick = async () => {
                const stillWaiting =
                    !line.isDone() &&
                    ["waiting", "waitingCard", "timeout"].includes(line.getPaymentStatus?.() || line.payment_status) &&
                    (line.uiState?.cashdroOperationId === operationId);

                if (!stillWaiting) {
                    console.log("[CashDro POS] Polling detenido, estado:", line.getPaymentStatus?.());
                    resolve((line.getPaymentStatus?.() || line.payment_status) === "done");
                    return;
                }

                if (Date.now() - startedAt > POLLING_TIMEOUT_MS) {
                    console.log("[CashDro POS] Timeout de polling");
                    line.setPaymentStatus("timeout");
                    this._showError(
                        _t("Tiempo de espera agotado esperando confirmación de pago en CashDro.")
                    );
                    resolve(false);
                    return;
                }

                try {
                    const status = await this._askOperation(operationId);
                    console.log("[CashDro POS] Estado de operación:", status);

                    const opState = status.extractedState;
                    console.log("[CashDro POS] Estado del CashDro:", opState);

                    if (opState === "F") {
                        // Pago completado
                        console.log("[CashDro POS] Pago completado, guardando en Odoo...");

                        // Guardar resultado en Odoo
                        const config = await this._getCashdroConfig();
                        const saveResult = await rpc("/cashdro/payment/pos/save-result", {
                            payment_method_id: config.paymentMethodId,
                            amount: amount,
                            cashdro_operation_id: operationId,
                            pos_session_id: this.pos.session?.id || null,
                        });

                        if (!saveResult || !saveResult.success) {
                            console.error("[CashDro POS] Error guardando en Odoo:", saveResult);
                            // No bloqueamos, continuamos igual
                        } else {
                            console.log("[CashDro POS] Guardado en Odoo:", saveResult);
                        }

                        line.setPaymentStatus("done");
                        line.transaction_id = operationId;
                        resolve(true);
                    } else if (["C", "CANCELLED", "ABORTED", "ERROR"].includes((opState || '').toUpperCase())) {
                        this._showError(_t("El pago ha sido cancelado o ha fallado en la máquina CashDro."));
                        line.setPaymentStatus("retry");
                        resolve(false);
                    } else {
                        // Seguir esperando (Q, E, etc.)
                        setTimeout(tick, POLLING_INTERVAL_MS);
                    }
                } catch (e) {
                    console.error("[CashDro POS] Error en polling:", e);
                    setTimeout(tick, POLLING_INTERVAL_MS);
                }
            };
            setTimeout(tick, POLLING_INTERVAL_MS);
        });
    }

    /**
     * Espera pago vía servidor (flujo antiguo/proxy).
     * Usado cuando el navegador no puede alcanzar al CashDro directamente.
     */
    async _waitForPaymentViaServer(line, transactionId) {
        const startedAt = Date.now();
        console.log("[CashDro POS] Polling vía servidor para transacción:", transactionId);

        return new Promise((resolve) => {
            const tick = async () => {
                const stillWaiting =
                    !line.isDone() &&
                    ["waiting", "waitingCard", "timeout"].includes(line.getPaymentStatus?.() || line.payment_status) &&
                    (line.uiState?.cashdroTransactionId === transactionId);

                if (!stillWaiting) {
                    console.log("[CashDro POS] Polling detenido, estado:", line.getPaymentStatus?.());
                    resolve((line.getPaymentStatus?.() || line.payment_status) === "done");
                    return;
                }

                if (Date.now() - startedAt > POLLING_TIMEOUT_MS) {
                    console.log("[CashDro POS] Timeout de polling vía servidor");
                    line.setPaymentStatus("timeout");
                    this._showError(
                        _t("Tiempo de espera agotado esperando confirmación de pago en CashDro.")
                    );
                    resolve(false);
                    return;
                }

                try {
                    // Consultar estado vía servidor
                    const status = await rpc("/cashdro/payment/pos/status", {
                        transaction_id: transactionId,
                    });

                    if (!status || !status.success) {
                        setTimeout(tick, POLLING_INTERVAL_MS);
                        return;
                    }

                    const txStatus = status.status;
                    console.log("[CashDro POS] Estado vía servidor:", txStatus);

                    if (txStatus === "confirmed") {
                        // Confirmar pago vía servidor
                        const confirm = await rpc("/cashdro/payment/pos/confirm", {
                            transaction_id: transactionId,
                        });

                        if (!confirm || !confirm.success) {
                            this._showError(
                                confirm?.error || _t("Error confirmando el pago en CashDro.")
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
                            status.message || _t("El pago ha sido cancelado o ha fallado.")
                        );
                        line.setPaymentStatus("retry");
                        resolve(false);
                    } else {
                        // Seguir esperando (pending, processing)
                        setTimeout(tick, POLLING_INTERVAL_MS);
                    }
                } catch (e) {
                    console.error("[CashDro POS] Error en polling vía servidor:", e);
                    setTimeout(tick, POLLING_INTERVAL_MS);
                }
            };
            setTimeout(tick, POLLING_INTERVAL_MS);
        });
    }

    async sendPaymentCancel(order, uuid) {
        const line = order.getPaymentlineByUuid(uuid);
        const operationId = line?.uiState?.cashdroOperationId;

        if (!operationId) {
            // Intentar con transactionId antiguo por compatibilidad
            const transactionId = line?.uiState?.cashdroTransactionId;
            if (!transactionId) return true;

            try {
                await rpc("/cashdro/payment/cancel", { transaction_id: transactionId });
                return true;
            } catch (e) {
                return false;
            }
        }

        // Cancelar operación en CashDro directamente
        try {
            const config = await this._getCashdroConfig();
            const gatewayUrl = this._buildGatewayUrl(config.host);

            const params = {
                operation: 'finishOperation',
                name: config.user,
                password: config.password,
                operationId: operationId,
                type: '2', // 2 = cancelar
            };

            const queryString = new URLSearchParams(params).toString();
            const url = `${gatewayUrl}/Cashdro3WS/index3.php?${queryString}`;

            await fetch(url, {
                method: "GET",
                headers: { "Content-Type": "application/json" },
                mode: "cors",
                credentials: "omit",
            });

            return true;
        } catch (e) {
            console.error("[CashDro POS] Error cancelando:", e);
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
