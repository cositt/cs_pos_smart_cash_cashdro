/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";

/**
 * Servicio de integración CashDro para Quiosco/Kiosk (Self-Order).
 * 
 * Este servicio ejecuta TODAS las operaciones CashDro desde el navegador (JavaScript fetch),
 * no desde el servidor Python. Esto resuelve el problema de red donde el servidor Odoo
 * no puede alcanzar la IP del CashDro (10.0.1.140).
 * 
 * Flujo:
 * 1. Usuario selecciona CashDro como método de pago
 * 2. JavaScript hace fetch() directo al CashDro para iniciar operación
 * 3. JavaScript hace polling cada 2 segundos hasta que el usuario complete el pago
 * 4. JavaScript guarda el resultado en Odoo vía RPC (solo persistencia)
 */

export class CashdroKioskService {
    constructor(selfOrder, paymentMethod) {
        this.selfOrder = selfOrder;
        this.paymentMethod = paymentMethod;
        this.gatewayUrl = this._buildGatewayUrl(paymentMethod.cashdro_host);
        this.user = paymentMethod.cashdro_user;
        this.password = paymentMethod.cashdro_password;
        
        // Endpoints del CashDro
        this.endpoint = `${this.gatewayUrl}/Cashdro3WS/index3.php`;
        this.endpointAdmin = `${this.gatewayUrl}/Cashdro3WS/index.php`;
        
        // Credenciales del canal web (para consultas)
        this.exchangeUser = "Exchange_Machine";
        this.exchangePassword = "-99";
        
        // Posición e identificador
        this.posId = "1";
        this.posUser = "kiosk";
        
        // Configuración
        this.timeout = 10000;
        this.pollingInterval = 2000;
        this.pollingTimeout = 180000; // 3 minutos
        
        // Estado
        this._pollingTimer = null;
        this._isCancelled = false;
    }

    /**
     * Construye URL del gateway desde el host.
     */
    _buildGatewayUrl(host) {
        if (host.startsWith('http://') || host.startsWith('https://')) {
            return host;
        }
        return `https://${host}`;
    }

    /**
     * Realiza una petición GET al endpoint del CashDro.
     */
    async _request(endpoint, params) {
        const queryString = new URLSearchParams(params).toString();
        const url = `${endpoint}?${queryString}`;
        
        try {
            const response = await fetch(url, {
                method: "GET",
                headers: {
                    "Content-Type": "application/json",
                },
                mode: "cors",
                credentials: "omit",
                signal: AbortSignal.timeout(this.timeout),
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            return data;
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error(_t("Timeout conectando a CashDro"));
            }
            throw error;
        }
    }

    /**
     * Realiza una petición POST al endpoint del CashDro.
     */
    async _requestPost(endpoint, params) {
        const queryString = new URLSearchParams(params).toString();
        const url = `${endpoint}?${queryString}`;
        
        try {
            const response = await fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                mode: "cors",
                credentials: "omit",
                signal: AbortSignal.timeout(this.timeout),
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            return data;
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error(_t("Timeout conectando a CashDro"));
            }
            throw error;
        }
    }

    /**
     * Inicia una operación de pago en el CashDro.
     * @param {number} amount - Importe en euros (ej: 10.50)
     * @returns {Promise<string>} operationId
     */
    async startPayment(amount) {
        const amountCents = String(Math.round(parseFloat(amount) * 100));
        
        const params = {
            operation: 'startOperation',
            name: this.user,
            password: this.password,
            type: 4, // VENTA/COBRO
            posid: this.posId,
            posuser: this.posUser,
            parameters: JSON.stringify({ amount: amountCents }),
            startnow: 'true',
        };
        
        console.log("[CashDro Kiosk] Iniciando pago:", { amount, amountCents });
        
        const data = await this._request(this.endpoint, params);
        
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
        
        console.log("[CashDro Kiosk] OperationId obtenido:", operationId);
        
        // ACKNOWLEDGE - CRÍTICO para mostrar pantalla en máquina
        try {
            console.log("[CashDro Kiosk] Enviando acknowledge...");
            await this._acknowledgeOperation(operationId);
            console.log("[CashDro Kiosk] Acknowledge enviado correctamente");
        } catch (ackErr) {
            console.warn("[CashDro Kiosk] Acknowledge error (no crítico):", ackErr);
        }
        
        return operationId;
    }

    /**
     * Reconoce una operación (muestra la pantalla en la máquina).
     */
    async _acknowledgeOperation(operationId) {
        const params = {
            operation: 'acknowledgeOperationId',
            name: this.user,
            password: this.password,
            operationId: operationId,
            includeImages: '1',
        };
        
        const data = await this._request(this.endpoint, params);
        return data;
    }

    /**
     * Consulta el estado de una operación.
     */
    async _askOperation(operationId) {
        const params = {
            operation: 'askOperation',
            name: this.exchangeUser,
            password: this.exchangePassword,
            operationId: operationId,
            includeImages: '1',
        };
        
        const data = await this._request(this.endpoint, params);
        
        // Extraer estado
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
            console.warn("Error extrayendo estado:", e);
        }
        
        return { ...data, extractedState: state };
    }

    /**
     * Polling: espera hasta que la operación se complete o timeout.
     * @param {string} operationId - ID de la operación
     * @param {function} onProgress - Callback para actualizar UI
     * @returns {Promise<boolean>} true si se completó, false si se canceló
     */
    async pollUntilComplete(operationId, onProgress) {
        const startTime = Date.now();
        let attemptCount = 0;
        
        return new Promise((resolve, reject) => {
            const poll = async () => {
                if (this._isCancelled) {
                    resolve(false);
                    return;
                }
                
                try {
                    attemptCount++;
                    const response = await this._askOperation(operationId);
                    const state = response.extractedState;
                    const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
                    
                    console.log(`[CashDro Kiosk Polling] Intento ${attemptCount}, Estado: ${state}, Tiempo: ${elapsedSeconds}s`);
                    
                    if (onProgress) {
                        onProgress({ state, attemptCount, elapsedSeconds });
                    }
                    
                    // 'F' = Finished (completado)
                    if (state === 'F') {
                        resolve(true);
                        return;
                    }
                    
                    // 'C' = Cancelled (cancelado)
                    if (state === 'C') {
                        resolve(false);
                        return;
                    }
                    
                    // Timeout
                    if (Date.now() - startTime > this.pollingTimeout) {
                        reject(new Error(_t("Timeout esperando pago")));
                        return;
                    }
                    
                    // Siguiente intento
                    this._pollingTimer = setTimeout(poll, this.pollingInterval);
                } catch (error) {
                    reject(error);
                }
            };
            
            poll();
        });
    }

    /**
     * Cancela el polling y marca como cancelado.
     */
    cancel() {
        this._isCancelled = true;
        if (this._pollingTimer) {
            clearTimeout(this._pollingTimer);
            this._pollingTimer = null;
        }
    }

    /**
     * Finaliza una operación (cancelar en CashDro).
     */
    async finishOperation(operationId, type = 2) {
        const params = {
            operation: 'finishOperation',
            name: this.user,
            password: this.password,
            operationId: operationId,
            type: type, // 1 = finalizar, 2 = cancelar
        };
        
        const data = await this._request(this.endpoint, params);
        return data;
    }

    /**
     * Guarda el resultado del pago en Odoo vía RPC.
     * @param {object} paymentData - Datos del pago
     * @returns {Promise<number>} ID del registro creado
     */
    async savePaymentToOdoo(paymentData) {
        try {
            console.log("[CashDro Kiosk] Guardando pago en Odoo:", paymentData);
            
            const recordId = await rpc('/cashdro/payment/kiosk/save-result', {
                order_id: paymentData.order_id,
                payment_method_id: this.paymentMethod.id,
                amount: paymentData.amount,
                cashdro_operation_id: paymentData.operation_id,
                state: paymentData.success ? 'completed' : 'cancelled',
            });
            
            console.log("[CashDro Kiosk] Pago guardado en Odoo con ID:", recordId);
            return recordId;
        } catch (error) {
            console.error("[CashDro Kiosk] Error guardando en Odoo:", error);
            // No lanzamos error para no interrumpir el flujo
            return null;
        }
    }

    /**
     * Flujo completo de pago: inicia, hace polling, guarda resultado.
     * @param {number} amount - Importe en euros
     * @param {number} orderId - ID de la orden en Odoo
     * @param {function} onProgress - Callback para actualizar UI
     * @returns {Promise<object>} Resultado del pago
     */
    async processPayment(amount, orderId, onProgress) {
        this._isCancelled = false;
        
        try {
            // PASO 1: Iniciar pago en CashDro
            const operationId = await this.startPayment(amount);
            
            // PASO 2: Hacer polling hasta que se complete
            const completed = await this.pollUntilComplete(operationId, onProgress);
            
            if (this._isCancelled) {
                // Cancelar operación en CashDro
                try {
                    await this.finishOperation(operationId, 2);
                } catch (e) {
                    console.warn("Error cancelando en CashDro:", e);
                }
                
                return {
                    success: false,
                    cancelled: true,
                    operation_id: operationId,
                    message: _t("Pago cancelado por el usuario"),
                };
            }
            
            if (!completed) {
                return {
                    success: false,
                    operation_id: operationId,
                    message: _t("El pago no se completó"),
                };
            }
            
            // PASO 3: Guardar resultado en Odoo
            await this.savePaymentToOdoo({
                order_id: orderId,
                amount: amount,
                operation_id: operationId,
                success: true,
            });
            
            return {
                success: true,
                operation_id: operationId,
                message: _t("Pago completado correctamente"),
            };
            
        } catch (error) {
            console.error("[CashDro Kiosk] Error en proceso de pago:", error);
            return {
                success: false,
                error: error.message,
                message: _t("Error en el pago: %s", error.message),
            };
        }
    }
}

/**
 * Factory para crear instancias del servicio (ASÍNCRONA).
 * 
 * Es asíncrona porque puede necesitar hacer RPC para obtener los campos CashDro
 * si no están cargados en el modelo del quiosco.
 */
export async function createCashdroKioskService(selfOrder, paymentMethodId) {
    let paymentMethod = selfOrder.models?.["pos.payment.method"]?.get?.(paymentMethodId);
    
    if (!paymentMethod || !paymentMethod.cashdro_enabled) {
        throw new Error(_t("Método de pago CashDro no válido"));
    }
    
    // Si no tenemos los campos de configuración, los obtenemos del servidor
    if (!paymentMethod.cashdro_host || !paymentMethod.cashdro_user || !paymentMethod.cashdro_password) {
        console.log("[CashDro Kiosk] Campos no cargados, obteniendo configuración del servidor...");
        
        try {
            const result = await rpc("/cashdro/config/get", {
                payment_method_id: paymentMethodId,
            });
            
            if (!result.success) {
                throw new Error(result.error || _t("No se pudo obtener configuración CashDro"));
            }
            
            // Crear objeto con los datos del servidor
            // Preservar el ID explícitamente ya que puede estar en un Proxy
            const pmId = paymentMethod.id || paymentMethodId;
            paymentMethod = {
                id: pmId,
                name: paymentMethod.name || paymentMethod.display_name || 'CashDro',
                cashdro_host: result.cashdro_host,
                cashdro_user: result.cashdro_user,
                cashdro_password: result.cashdro_password,
                cashdro_enabled: true,
            };
            console.log("[CashDro Kiosk] PaymentMethod creado con ID:", pmId);
            
            console.log("[CashDro Kiosk] Configuración obtenida del servidor");
        } catch (error) {
            console.error("[CashDro Kiosk] Error obteniendo configuración:", error);
            throw new Error(_t("Método de pago CashDro no configurado correctamente"));
        }
    }
    
    return new CashdroKioskService(selfOrder, paymentMethod);
}
