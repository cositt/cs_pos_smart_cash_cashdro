/** @odoo-module */

import { _t } from "@web/core/l10n/translation";

/**
 * Servicio de integración con gateway CashDro.
 * Ejecuta TODAS las operaciones desde el navegador del cliente.
 * Encapsula comunicación HTTP, polling, parseo de respuestas y manejo de errores.
 * 
 * Basado en gateway_integration.py pero ejecutándose en JavaScript OWL.
 */

export class CashdroGatewayService {
    constructor(gatewayUrl, user, password, options = {}) {
        this.gatewayUrl = gatewayUrl.replace(/\/$/, '');
        this.user = user;
        this.password = password;
        
        // Endpoints del CashDro
        this.endpoint = `${this.gatewayUrl}/Cashdro3WS/index3.php`;
        this.endpointAdmin = `${this.gatewayUrl}/Cashdro3WS/index.php`;
        
        // Credenciales del canal web (para consultas)
        this.exchangeUser = "Exchange_Machine";
        this.exchangePassword = "-99";
        
        // Posición e identificador
        this.posId = options.posId || "1";
        this.posUser = options.posUser || "odoo";
        
        // Configuración de timeout y polling
        this.timeout = options.timeout || 10000;
        this.pollingInterval = options.pollingInterval || 2000;
        this.pollingTimeout = options.pollingTimeout || 180000;
        
        this.verifySSL = options.verifySSL || false;
    }

    /**
     * Realiza una petición GET al endpoint del CashDro.
     * @param {string} endpoint - URL completa (index3.php o index.php)
     * @param {object} params - Parámetros query
     * @returns {Promise<object>} Respuesta parseada JSON
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
                throw new Error(_t("Timeout conectando a CashDro (más de %ds)", Math.floor(this.timeout / 1000)));
            }
            throw error;
        }
    }

    /**
     * Login en el endpoint index3.php.
     * Valida que las credenciales sean válidas.
     */
    async login(user, password) {
        const params = {
            operation: 'login',
            name: user,
            password: password,
        };
        
        const data = await this._request(this.endpoint, params);
        
        if (data.code !== 1) {
            throw new Error(
                data.response?.errorMessage || 
                _t("Login fallido en CashDro")
            );
        }
        
        return data;
    }

    /**
     * Inicia una operación de venta/pago/etc.
     * @param {number} amountEur - Importe en euros (ej. 10.50)
     * @param {number} operationType - 3=pago/dispensa, 4=venta/cobro, etc.
     * @returns {Promise<object>} Respuesta con operationId
     */
    async startOperation(amountEur, operationType = 4) {
        const amountCents = String(Math.round(parseFloat(amountEur) * 100));
        
        const params = {
            operation: 'startOperation',
            name: this.user,
            password: this.password,
            type: operationType,
            posid: this.posId,
            posuser: this.posUser,
            parameters: JSON.stringify({ amount: amountCents }),
            startnow: 'true',
        };
        
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
            throw new Error(
                data.response?.errorMessage || 
                _t("No se recibió operationId")
            );
        }
        
        data.operation_id = operationId;
        return data;
    }

    /**
     * Inicia una operación administrativa (carga, retirada, etc.).
     * @param {number} operationType - 1=carga, 2=retirada, 12=inicializar, 36=aplicar fianza, etc.
     * @param {object} options - {aliasId, isManual, parameters}
     * @returns {Promise<object>} Respuesta con operationId
     */
    async startOperationAdmin(operationType, options = {}) {
        const params = {
            operation: 'startOperation',
            name: this.user,
            password: this.password,
            type: operationType,
            aliasId: options.aliasId || '',
            isManual: options.isManual || '0',
            startnow: 'true',
            parameters: options.parameters || '',
        };
        
        const data = await this._request(this.endpointAdmin, params);
        
        let operationId = null;
        if (data.code === 1 || data.code === 0) {
            if (typeof data.data === 'string' && /^\d+$/.test(data.data)) {
                operationId = data.data;
            } else if (data.response?.operation?.operationId) {
                operationId = data.response.operation.operationId;
            }
        }
        
        if (!operationId || operationId === 'Operation not queued') {
            const errorMsg = data.response?.errorMessage || data.data || _t("No se recibió operationId");
            if (data.code === -2) {
                throw new Error(_t("Máquina ocupada (code=-2). Espere a que termine la operación actual."));
            }
            throw new Error(errorMsg);
        }
        
        data.operation_id = operationId;
        return data;
    }

    /**
     * Consulta el estado de una operación.
     * @param {string} operationId - ID de la operación
     * @returns {Promise<object>} Estado actual de la operación
     */
    async askOperation(operationId) {
        const params = {
            operation: 'askOperation',
            name: this.exchangeUser,
            password: this.exchangePassword,
            operationId: operationId,
            includeImages: '1',
        };
        
        const data = await this._request(this.endpoint, params);
        
        // Normalizar estructura de respuesta
        let normalizedOperation = {};
        try {
            let container = data.response;
            if (!container && data.data !== undefined) {
                container = data.data;
                if (typeof container === 'string') {
                    container = JSON.parse(container);
                }
            }
            if (typeof container === 'object') {
                const opWrapper = container.operation || {};
                if (opWrapper.operation) {
                    normalizedOperation = opWrapper.operation;
                } else {
                    normalizedOperation = opWrapper;
                }
            }
        } catch (e) {
            console.warn("Error normalizando respuesta askOperation:", e);
        }
        
        data.normalized_operation = normalizedOperation;
        return data;
    }

    /**
     * Polling: consulta operación cada N milisegundos hasta que esté finalizada.
     * @param {string} operationId - ID de la operación
     * @param {function} onProgress - Callback para actualizar UI (opcional)
     * @returns {Promise<object>} Respuesta cuando state === 'F'
     */
    async pollUntilComplete(operationId, onProgress) {
        const startTime = Date.now();
        let attemptCount = 0;
        
        return new Promise((resolve, reject) => {
            const poll = async () => {
                try {
                    attemptCount++;
                    const response = await this.askOperation(operationId);
                    
                    const state = response.normalized_operation?.state || '?';
                    
                    if (onProgress) {
                        onProgress({
                            state,
                            attemptCount,
                            elapsedSeconds: Math.floor((Date.now() - startTime) / 1000),
                        });
                    }
                    
                    if (state === 'F') {
                        resolve(response);
                        return;
                    }
                    
                    const elapsed = Date.now() - startTime;
                    if (elapsed > this.pollingTimeout) {
                        reject(new Error(
                            _t("Timeout esperando pago (operationId=%s, %ds)", operationId, Math.floor(this.pollingTimeout / 1000))
                        ));
                        return;
                    }
                    
                    setTimeout(poll, this.pollingInterval);
                } catch (error) {
                    reject(error);
                }
            };
            
            poll();
        });
    }

    /**
     * Finaliza una operación.
     * @param {string} operationId - ID de la operación
     * @param {number} type - 1=finalizar, 2=cancelar
     * @returns {Promise<object>} Respuesta
     */
    async finishOperation(operationId, type = 1) {
        const params = {
            operation: 'finishOperation',
            name: this.user,
            password: this.password,
            operationId: operationId,
            type: type,
        };
        
        const data = await this._request(this.endpoint, params);
        
        if (data.code !== 1) {
            console.warn("finishOperation devolvió code:", data.code);
        }
        
        return data;
    }

    /**
     * Reconoce una operación (muestra la pantalla en la máquina).
     * DEPRECATED: en algunos casos causa finalización prematura.
     */
    async acknowledgeOperation(operationId) {
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
     * Obtiene el estado de fianza (getPiecesCurrency).
     * @param {string} currencyId - 'EUR' por defecto
     * @param {string} includeLevels - '1' para incluir niveles
     * @returns {Promise<object>} Datos de piezas y niveles
     */
    async getPiecesCurrency(currencyId = 'EUR', includeLevels = '1') {
        const params = {
            operation: 'getPiecesCurrency',
            name: this.user,
            password: this.password,
            currencyId: currencyId,
            includeImages: '0',
            includeLevels: includeLevels,
        };
        
        try {
            const data = await this._request(this.endpointAdmin, params);
            return data;
        } catch (error) {
            console.warn("getPiecesCurrency error:", error);
            return { code: 0, data: [] };
        }
    }

    /**
     * Obtiene moneda principal.
     */
    async getMainCurrency() {
        const params = {
            operation: 'getMainCurrency',
            name: this.exchangeUser,
            password: this.exchangePassword,
        };
        
        const data = await this._request(this.endpoint, params);
        return data;
    }

    /**
     * Indica al CashDro que la transacción ha sido procesada.
     */
    async setOperationImported(operationId) {
        const params = {
            operation: 'setOperationImported',
            name: this.user,
            password: this.password,
            operationId: operationId,
        };
        
        const data = await this._request(this.endpoint, params);
        return data;
    }

    /**
     * Configura los niveles de fianza.
     */
    async setDepositLevels(levelsConfig) {
        const params = {
            operation: 'setDepositLevels',
            name: this.user,
            password: this.password,
            levels: JSON.stringify(levelsConfig),
        };
        
        const data = await this._request(this.endpointAdmin, params);
        return data;
    }

    /**
     * Aplica la fianza configurada (type=36).
     */
    async applyDepositLevels() {
        try {
            // START type=36
            const startData = await this.startOperationAdmin(36, {});
            const operationId = startData.operation_id;
            
            // ACKNOWLEDGE
            await this.acknowledgeOperation(operationId);
            
            // Esperar un poco
            await new Promise(r => setTimeout(r, 2000));
            
            // ASK (optional, solo para logging)
            await this.askOperation(operationId);
            
            // FINISH
            const finishData = await this.finishOperation(operationId, 1);
            
            return {
                success: true,
                operation_id: operationId,
                responses: { start: startData, finish: finishData },
            };
        } catch (error) {
            throw new Error(_t("Error aplicando fianza: %s", error.message));
        }
    }

    /**
     * Obtiene URL de la interfaz web para retirada.
     */
    getRetiradaWebUrl(operationId) {
        const params = new URLSearchParams({
            username: this.user,
            password: this.password,
        }).toString();
        const base = this.gatewayUrl;
        return `${base}/Cashdro3Web/#/unload/${operationId}/true/?${params}`;
    }

    /**
     * Obtiene URL de la interfaz web para cambio.
     */
    getCambioWebUrl(operationId = null) {
        const base = this.gatewayUrl;
        if (operationId) {
            return `${base}/Cashdro3Web/index.html#/splash/${operationId}/true`;
        }
        return `${base}/Cashdro3Web/index.html#/splash/true`;
    }
}
