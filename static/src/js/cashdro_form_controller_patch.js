/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { CashdroGatewayService } from "./cashdro_gateway_service";

/**
 * Interceptor para FormController que ejecuta operaciones CashDro desde el navegador.
 * 
 * Detecta cuando se pulsa un botón de operación CashDro en:
 * 1. Formulario cashdro.caja.movimientos (consultas simples y botones que abren wizards)
 * 2. Formularios de wizards cashdro.movimiento.*.wizard (botones action_execute, etc.)
 * 
 * Si es CashDro, ejecuta la lógica en JS y retorna false para no ejecutar el servidor.
 */

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.cashdroGateway = null;
    },

    /**
     * Intercepta click en botones ANTES de que se envíe RPC al servidor.
     * Retorna false para detener la cadena de ejecución.
     */
    async beforeExecuteActionButton(clickParams) {
        const model = this.model?.root?.resModel;
        const buttonName = clickParams.name;
        const data = this.model?.root?.data || {};
        
        // Detectar si es una operación CashDro
        if (!this._isCashdroOperation(model, buttonName)) {
            return super.beforeExecuteActionButton(...arguments);
        }
        
        try {
            // Construir gateway desde datos del formulario/wizard
            const gateway = await this._getCashdroGateway(data, model);
            
            // Despachar según el tipo de operación
            if (buttonName === 'action_consultar_fianza') {
                return await this._handleConsultarFianza(gateway, data, model);
            } else if (buttonName === 'action_consulta_niveles') {
                return await this._handleConsultaNiveles(gateway, data, model);
            } else if (this._isSimpleConsultation(buttonName)) {
                return await this._handleSimpleConsultation(gateway, buttonName, data, model);
            } else if (this._isWizardOperation(model)) {
                return await this._handleWizardOperation(gateway, buttonName, data, model);
            }
            
            // Para botones que solo abren wizards (no hacen operación aquí)
            return super.beforeExecuteActionButton(...arguments);
        } catch (error) {
            console.error("[CashDro] Error en beforeExecuteActionButton:", error);
            this.notification.add(
                _t("Error CashDro: %s", error.message),
                { type: "danger", sticky: true }
            );
            return false; // Detener ejecución del servidor
        }
    },

    /**
     * Determina si es una operación CashDro que debe interceptar.
     * 
     * IMPORTANTE: Solo interceptamos:
     * 1. Consultas simples en cashdro.caja.movimientos (fianza, niveles)
     * 2. Botones de ejecución dentro de wizards (action_execute, etc.)
     * 
     * Los botones que abren wizards (action_pago, action_cambio, etc.) NO se interceptan
     * en el formulario principal - dejan que Odoo abra el wizard normalmente.
     */
    _isCashdroOperation(model, buttonName) {
        if (!model) return false;
        
        // cashdro.caja.movimientos - SOLO consultas simples (no botones que abren wizards)
        if (model === 'cashdro.caja.movimientos') {
            // Solo interceptar consultas que se ejecutan directamente
            return [
                'action_consultar_fianza',
                'action_consulta_niveles',
            ].includes(buttonName);
        }
        
        // Wizards CashDro - botones de ejecución DENTRO del wizard
        // Estos son los que realmente ejecutan la operación en el CashDro
        if (model && model.startsWith('cashdro.movimiento.')) {
            return [
                'action_execute',
                'action_iniciar',
                'action_iniciar_carga',
                'action_iniciar_retirada',
                'action_aplicar',
            ].includes(buttonName);
        }
        
        return false;
    },

    /**
     * Obtiene datos del gateway desde el formulario.
     * Busca payment_method_id y extrae credenciales del servidor.
     */
    async _getCashdroGateway(formData, model) {
        // Intentar obtener payment_method_id de múltiples fuentes
        let paymentMethodId = null;
        
        // Opción 1: Desde los datos del formulario (formato [id, name] de Odoo)
        if (formData.payment_method_id) {
            if (Array.isArray(formData.payment_method_id)) {
                paymentMethodId = formData.payment_method_id[0];
            } else if (typeof formData.payment_method_id === 'object' && formData.payment_method_id.id) {
                paymentMethodId = formData.payment_method_id.id;
            } else if (typeof formData.payment_method_id === 'number') {
                paymentMethodId = formData.payment_method_id;
            }
        }
        
        // Opción 2: Desde el contexto del wizard
        if (!paymentMethodId && this.env?.context?.default_payment_method_id) {
            paymentMethodId = this.env.context.default_payment_method_id;
        }
        
        // Opción 3: Desde this.model.root.data (por si formData no está sincronizado)
        if (!paymentMethodId && this.model?.root?.data?.payment_method_id) {
            const pm = this.model.root.data.payment_method_id;
            if (Array.isArray(pm)) {
                paymentMethodId = pm[0];
            } else if (typeof pm === 'number') {
                paymentMethodId = pm;
            }
        }
        
        if (!paymentMethodId) {
            console.error("[CashDro] No se pudo obtener payment_method_id. Datos disponibles:", {
                formData: formData,
                model: model,
                env_context: this.env?.context,
            });
            throw new Error(_t("No se encontró el método de pago CashDro. Asegúrate de seleccionar un método de pago."));
        }
        
        console.log("[CashDro] Usando payment_method_id:", paymentMethodId);
        
        // Obtener credenciales desde servidor (garantiza que son válidas)
        const methodData = await this.orm.read('pos.payment.method', [paymentMethodId], [
            'cashdro_host',
            'cashdro_user',
            'cashdro_password',
            'cashdro_enabled',
        ]);
        
        if (!methodData || !methodData[0]) {
            throw new Error(_t("Método de pago no encontrado"));
        }
        
        const method = methodData[0];
        if (!method.cashdro_enabled) {
            throw new Error(_t("CashDro no está habilitado en este método de pago"));
        }
        
        if (!method.cashdro_host || !method.cashdro_user || !method.cashdro_password) {
            throw new Error(_t("Falta configurar Host, Usuario o Contraseña del CashDro"));
        }
        
        // Construir URL del gateway
        const url = this._buildGatewayUrl(method.cashdro_host);
        
        // Crear instancia del gateway
        return new CashdroGatewayService(
            url,
            method.cashdro_user,
            method.cashdro_password,
            {
                timeout: 10000,
                pollingInterval: 2000,
                pollingTimeout: 180000,
            }
        );
    },

    /**
     * Construye URL del gateway desde el host.
     */
    _buildGatewayUrl(host) {
        if (host.startsWith('http://') || host.startsWith('https://')) {
            return host;
        }
        return `https://${host}`;
    },

    /**
     * Determina si es una consulta simple (sin wizard, sin operación en máquina).
     */
    _isSimpleConsultation(buttonName) {
        return ['action_consultar_fianza', 'action_consulta_niveles'].includes(buttonName);
    },

    /**
     * Determina si el modelo es un wizard CashDro.
     */
    _isWizardOperation(model) {
        return model && model.startsWith('cashdro.movimiento.') && model.includes('.wizard');
    },

    /**
     * Maneja consulta de fianza (getPiecesCurrency).
     */
    async _handleConsultarFianza(gateway, formData, model) {
        this.notification.add(_t("Consultando fianza..."), { type: "info" });
        
        try {
            const response = await gateway.getPiecesCurrency('EUR', '1');
            
            if (response.code === 1) {
                this.notification.add(_t("Fianza consultada correctamente"), { type: "success" });
                
                // Procesar datos y actualizar campos del formulario
                const levels = this._parsePiecesResponse(response);
                const fianzaHtml = this._buildEstadoFianzaHtml(levels);
                const nivelesHtml = this._buildConsultaNivelesHtml(levels);
                
                // Actualizar campos del formulario directamente
                await this.model.root.update({
                    state_fianza: fianzaHtml,
                    state_display: nivelesHtml,
                    state_raw: JSON.stringify({
                        getPiecesCurrency_fianza: response,
                        levels_fianza: levels,
                        timestamp: new Date().toISOString(),
                    }, null, 2),
                });
                
                // Guardar resultado en Odoo
                const paymentMethodId = formData.payment_method_id?.[0];
                if (paymentMethodId) {
                    await this._saveOperationToOdoo({
                        payment_method_id: paymentMethodId,
                        operation_type: 'consulta_fianza',
                        amount: 0,
                        state: 'completed',
                        operation_id: '',
                        concept: 'Consulta de fianza',
                    });
                }
            } else {
                throw new Error(_t("Error consultando fianza (code=%s)", response.code));
            }
        } catch (error) {
            this.notification.add(
                _t("Error consultando fianza: %s", error.message),
                { type: "danger", sticky: true }
            );
        }
        
        return false; // Detener ejecución del servidor
    },

    /**
     * Maneja consulta de niveles (getPiecesCurrency con niveles).
     */
    async _handleConsultaNiveles(gateway, formData, model) {
        this.notification.add(_t("Consultando niveles..."), { type: "info" });
        
        try {
            const response = await gateway.getPiecesCurrency('EUR', '1');
            
            if (response.code === 1) {
                this.notification.add(_t("Niveles consultados correctamente"), { type: "success" });
                
                // Procesar datos y actualizar campos del formulario
                const levels = this._parsePiecesResponse(response);
                const nivelesHtml = this._buildConsultaNivelesHtml(levels);
                
                // Actualizar campos del formulario directamente
                await this.model.root.update({
                    state_display: nivelesHtml,
                    state_raw: JSON.stringify({
                        getPiecesCurrency_niveles: response,
                        levels: levels,
                        timestamp: new Date().toISOString(),
                    }, null, 2),
                });
                
                // Guardar resultado en Odoo
                const paymentMethodId = formData.payment_method_id?.[0];
                if (paymentMethodId) {
                    await this._saveOperationToOdoo({
                        payment_method_id: paymentMethodId,
                        operation_type: 'consulta_niveles',
                        amount: 0,
                        state: 'completed',
                        operation_id: '',
                        concept: 'Consulta de niveles',
                    });
                }
            } else {
                throw new Error(_t("Error consultando niveles (code=%s)", response.code));
            }
        } catch (error) {
            this.notification.add(
                _t("Error consultando niveles: %s", error.message),
                { type: "danger", sticky: true }
            );
        }
        
        return false;
    },

    /**
     * Maneja consultas simples genéricas.
     */
    async _handleSimpleConsultation(gateway, buttonName, formData, model) {
        return false; // Ya manejadas arriba
    },

    /**
     * Maneja operaciones desde wizards (pago, devolución, etc.).
     * Abre un dialog de progreso y ejecuta polling.
     */
    async _handleWizardOperation(gateway, buttonName, formData, model) {
        // Validar datos según el tipo de wizard
        // El gateway ya fue creado exitosamente, así que el payment_method_id es válido
        if (!gateway) {
            throw new Error(_t("No se pudo inicializar la conexión con CashDro"));
        }
        
        // Extraer parámetros según el modelo
        const operationConfig = this._getOperationConfig(model, formData);
        
        if (!operationConfig) {
            throw new Error(_t("Configuración de operación no válida"));
        }
        
        // Ejecutar la operación con polling
        await this._executeOperationWithPolling(gateway, operationConfig, formData);
        
        return false;
    },

    /**
     * Obtiene la configuración de operación según el modelo del wizard.
     */
    _getOperationConfig(model, formData) {
        // Mapeo de modelos a tipos de operación y configuración
        const configMap = {
            'cashdro.movimiento.pago.wizard': {
                operationType: 4, // VENTA/COBRO
                amountField: 'amount',
                description: _t('Venta'),
                requiresAmount: true,
                requiresPolling: true,
            },
            'cashdro.movimiento.devolucion.wizard': {
                operationType: 3, // DEVOLUCIÓN/DISPENSA
                amountField: 'amount',
                description: _t('Pago'),
                requiresAmount: true,
                requiresPolling: true,
            },
            'cashdro.movimiento.cambio.wizard': {
                operationType: 18, // CAMBIO
                operationAdmin: true,
                description: _t('Cambio'),
                requiresAmount: false,
                requiresPolling: false,
                webInterface: true,
            },
            'cashdro.movimiento.carga.wizard': {
                operationType: 16, // INGRESAR genérico
                operationAdmin: true,
                description: _t('Ingresar'),
                requiresAmount: false,
                requiresPolling: false,
                waitForMachine: true, // La máquina se queda en modo ingreso hasta que el usuario termine
            },
            'cashdro.movimiento.ingreso.importe.wizard': {
                operationType: 17, // INGRESAR POR IMPORTE
                operationAdmin: true,
                amountField: 'amount',
                description: _t('Ingresar por importe'),
                requiresAmount: true,
                requiresPolling: false,
            },
            'cashdro.movimiento.carga.operacion.wizard': {
                operationType: 1, // CARGA
                description: _t('Carga'),
                requiresAmount: false,
                requiresPolling: false,
            },
            'cashdro.movimiento.retirada.wizard': {
                operationType: 2, // RETIRADA
                description: _t('Retirada'),
                requiresAmount: false,
                requiresPolling: false,
                webInterface: true,
            },
            'cashdro.movimiento.retirada.casete.monedas.wizard': {
                operationType: 11, // RETIRADA CASETE MONEDAS
                description: _t('Retirada casete monedas'),
                requiresAmount: false,
                requiresPolling: false,
            },
            'cashdro.movimiento.retirada.casete.billetes.wizard': {
                operationType: 10, // RETIRADA CASETE BILLETES
                description: _t('Retirada casete billetes'),
                requiresAmount: false,
                requiresPolling: false,
            },
            'cashdro.movimiento.inicializar.wizard': {
                operationType: 12, // INICIALIZAR NIVELES
                description: _t('Inicializar niveles'),
                requiresAmount: false,
                requiresPolling: false,
            },
            'cashdro.movimiento.fianza.wizard': {
                operationType: 36, // APLICAR FIANZA
                description: _t('Configurar fianza'),
                requiresAmount: false,
                requiresPolling: false,
                applyDepositLevels: true,
            },
        };
        
        return configMap[this.model?.root?.resModel] || null;
    },

    /**
     * Parsea la respuesta de getPiecesCurrency y extrae niveles.
     */
    _parsePiecesResponse(response) {
        const monedaDenom = [2.0, 1.0, 0.5, 0.2, 0.1, 0.05];
        const billeteDenom = [100, 50, 20, 10, 5];
        
        const levels = {
            moneda: monedaDenom.map(v => [v, 0, 0.0, 0, 0.0]),
            billete: billeteDenom.map(v => [v, 0, 0.0, 0, 0.0]),
        };
        
        if (!response || response.code !== 1) {
            return levels;
        }
        
        let data = response.data || response.response?.data;
        if (!data && response.response?.operation?.pieces) {
            data = response.response.operation.pieces;
        }
        
        if (!data) return levels;
        
        if (typeof data === 'string') {
            try {
                data = JSON.parse(data);
            } catch (e) {
                return levels;
            }
        }
        
        if (!Array.isArray(data)) {
            data = data ? [data] : [];
        }
        
        data.forEach(p => {
            if (!p || typeof p !== 'object') return;
            
            const valRaw = p.value || p.Value || 0;
            const typ = String(p.type || p.Type || '');
            const recLimit = parseFloat(p.RecyclerLimit || p.recyclerLimit || 0);
            const rec = parseFloat(p.LevelRecycler || p.levelRecycler || 
                                 p.startlevelrecycler || p.unitsinrecycler || 0);
            const cas = parseFloat(p.LevelCasete || p.levelCasete || 
                                 p.startlevelcassette || p.unitsincassette || 0);
            const deposit = parseFloat(p.DepositLevel || p.depositLevel || 0);
            
            if (!recLimit) return;
            
            try {
                const valInt = parseInt(valRaw);
                
                if (typ === '1' || typ === '3') {
                    // Monedas: valor en céntimos → euros
                    const valEur = Math.round(valInt) / 100.0;
                    const idx = monedaDenom.findIndex(d => Math.abs(d - valEur) < 0.01);
                    if (idx >= 0) {
                        const totalRec = rec * valEur;
                        const totalCas = cas * valEur;
                        levels.moneda[idx] = [valEur, rec, totalRec, cas, totalCas];
                    }
                } else if (typ === '2') {
                    // Billetes
                    let valEur = valInt / 100.0;
                    if (valInt >= 100) valEur = valInt / 100.0;
                    else if ([5, 10, 20, 50, 100, 200].includes(valInt)) valEur = valInt;
                    
                    const idx = billeteDenom.findIndex(d => Math.abs(d - valEur) < 0.01);
                    if (idx >= 0) {
                        const totalRec = rec * valEur;
                        const totalCas = cas * valEur;
                        levels.billete[idx] = [valEur, rec, totalRec, cas, totalCas];
                    }
                }
            } catch (e) {
                console.warn("Error procesando pieza:", p, e);
            }
        });
        
        return levels;
    },

    /**
     * Genera HTML de estado de fianza (similar al Python).
     */
    _buildEstadoFianzaHtml(levels) {
        const orderDenom = [200, 100, 50, 20, 10, 5, 2.0, 1.0, 0.5, 0.2, 0.1, 0.05];
        const billeteDenom = [100, 50, 20, 10, 5];
        const monedaDenom = [2.0, 1.0, 0.5, 0.2, 0.1, 0.05];
        
        // Obtener niveles de fianza desde datos (usar 0 como default)
        const fianzaLevels = {};
        orderDenom.forEach(v => fianzaLevels[v] = 0);
        
        let rows = [];
        let totalFianza = 0, totalRec = 0, totalFaltante = 0;
        
        orderDenom.forEach(v => {
            const nf = fianzaLevels[v] || 0;
            
            // Buscar en billetes o monedas
            let recData = levels.billete.find(x => Math.abs(x[0] - v) < 0.01);
            if (!recData) {
                recData = levels.moneda.find(x => Math.abs(x[0] - v) < 0.01);
            }
            
            const nr = recData ? recData[1] : 0;
            const tr = nr * v;
            const faltante = Math.max(0, nf - nr);
            const tf = nf * v;
            const tfalt = faltante * v;
            
            totalFianza += tf;
            totalRec += tr;
            totalFaltante += tfalt;
            
            const css = nr === 0 ? 'background-color: #f8d7da;' : '';
            const label = v >= 1 ? `${parseInt(v)} €` : `${v.toFixed(2)} €`;
            
            rows.push(`<tr style="${css}">
                <td>${label}</td>
                <td>${nf}</td>
                <td>${tf.toFixed(2)} €</td>
                <td>${nr}</td>
                <td>${tr.toFixed(2)} €</td>
                <td>${faltante}</td>
                <td>${tfalt.toFixed(2)} €</td>
            </tr>`);
        });
        
        return `<p style="margin-bottom:0.5rem;">Estado de fianza (getPiecesCurrency).</p>
        <table class="table table-sm table-bordered" style="width:100%; table-layout:fixed;">
            <thead><tr>
                <th>Denominación</th><th>Nivel fianza</th><th>Total Fianza</th>
                <th>Niv. reciclador</th><th>Total reciclador</th>
                <th>Niv. faltante</th><th>Total faltante</th>
            </tr></thead>
            <tbody>${rows.join('')}</tbody>
            <tfoot><tr style="font-weight:bold;">
                <td>Total</td><td></td><td>${totalFianza.toFixed(2)} €</td>
                <td></td><td>${totalRec.toFixed(2)} €</td><td></td><td>${totalFaltante.toFixed(2)} €</td>
            </tr></tfoot>
        </table>`;
    },

    /**
     * Genera HTML de consulta de niveles (similar al Python).
     */
    _buildConsultaNivelesHtml(levels) {
        const rowMoneda = (val, rec, totalRec, cas, totalCas) => {
            const css = (rec === 0 && cas === 0) ? 'background-color: #f8d7da;' : '';
            return `<tr style="${css}">
                <td>${val.toFixed(2)} €</td>
                <td>${rec}</td><td>${totalRec.toFixed(2)} €</td>
                <td>${cas}</td><td>${totalCas.toFixed(2)} €</td>
            </tr>`;
        };
        
        const rowBillete = (val, rec, totalRec, cas, totalCas) => {
            const css = (rec === 0 && cas === 0) ? 'background-color: #f8d7da;' : '';
            return `<tr style="${css}">
                <td>${parseInt(val)} €</td>
                <td>${rec}</td><td>${totalRec.toFixed(0)} €</td>
                <td>${cas}</td><td>${totalCas.toFixed(0)} €</td>
            </tr>`;
        };
        
        const monedaRows = levels.moneda.map(m => rowMoneda(m[0], m[1], m[2], m[3], m[4])).join('');
        const billeteRows = levels.billete.map(b => rowBillete(b[0], b[1], b[2], b[3], b[4])).join('');
        
        const sumMonRec = levels.moneda.reduce((s, m) => s + m[1], 0);
        const sumMonCas = levels.moneda.reduce((s, m) => s + m[3], 0);
        const totMonRec = levels.moneda.reduce((s, m) => s + m[2], 0);
        const totMonCas = levels.moneda.reduce((s, m) => s + m[4], 0);
        const totMon = totMonRec + totMonCas;
        
        const sumBillRec = levels.billete.reduce((s, b) => s + b[1], 0);
        const sumBillCas = levels.billete.reduce((s, b) => s + b[3], 0);
        const totBillRec = levels.billete.reduce((s, b) => s + b[2], 0);
        const totBillCas = levels.billete.reduce((s, b) => s + b[4], 0);
        const totBill = totBillRec + totBillCas;
        
        return `<div style="width:100%; max-width:100%; box-sizing:border-box;">
            <table class="table table-sm table-bordered" style="width:100%; table-layout:fixed; margin-bottom:1.5rem;">
                <caption style="text-align:left; font-weight:bold;">Moneda</caption>
                <thead><tr>
                    <th style="width:12%">Valor</th>
                    <th style="width:22%">Niv. reciclador</th>
                    <th style="width:22%">Total reciclador</th>
                    <th style="width:22%">Niv. casete</th>
                    <th style="width:22%">Total casete</th>
                </tr></thead>
                <tbody>${monedaRows}</tbody>
                <tfoot><tr style="font-weight:bold;">
                    <td>Total</td><td>${sumMonRec}</td><td>${totMonRec.toFixed(2)} €</td>
                    <td>${sumMonCas}</td><td>${totMonCas.toFixed(2)} €</td>
                </tr></tfoot>
            </table>
            <table class="table table-sm table-bordered" style="width:100%; table-layout:fixed; margin-bottom:1.5rem;">
                <caption style="text-align:left; font-weight:bold;">Billete</caption>
                <thead><tr>
                    <th style="width:12%">Valor</th>
                    <th style="width:22%">Niv. reciclador</th>
                    <th style="width:22%">Total reciclador</th>
                    <th style="width:22%">Niv. casete</th>
                    <th style="width:22%">Total casete</th>
                </tr></thead>
                <tbody>${billeteRows}</tbody>
                <tfoot><tr style="font-weight:bold;">
                    <td>Total</td><td>${sumBillRec}</td><td>${totBillRec.toFixed(0)} €</td>
                    <td>${sumBillCas}</td><td>${totBillCas.toFixed(0)} €</td>
                </tr></tfoot>
            </table>
            <p style="margin:0.5rem 0;">
                <strong>Total monedas:</strong> ${totMon.toFixed(2)} € &nbsp;|&nbsp;
                <strong>Total billetes:</strong> ${totBill.toFixed(0)} € &nbsp;|&nbsp;
                <strong>Total:</strong> ${(totMon + totBill).toFixed(2)} €
            </p>
        </div>`;
    },

    /**
     * Convierte el código numérico de operación a nombre legible.
     */
    _getOperationTypeName(operationType) {
        const typeNames = {
            1: 'carga',
            2: 'retirada',
            3: 'pago',
            4: 'venta',
            10: 'retirada_casete_billetes',
            11: 'retirada_casete_monedas',
            12: 'inicializar_niveles',
            16: 'ingresar',
            17: 'ingreso_importe',
            18: 'cambio',
            36: 'fianza',
        };
        return typeNames[operationType] || 'operacion';
    },

    /**
     * Guarda el resultado de la operación en Odoo vía RPC.
     * Crea un registro en cashdro.caja.movimientos con los datos de la operación.
     */
    async _saveOperationToOdoo(operationData) {
        try {
            console.log("[CashDro] Guardando operación en Odoo:", operationData);
            
            // Validar datos antes de enviar
            if (!operationData.payment_method_id) {
                throw new Error("payment_method_id es requerido");
            }
            if (!operationData.operation_type) {
                throw new Error("operation_type es requerido");
            }
            
            // Usar el nuevo modelo cashdro.operation.log
            const recordData = {
                payment_method_id: operationData.payment_method_id,
                operation_type: operationData.operation_type,
                amount: operationData.amount || 0.0,
                state: operationData.state || 'completed',
                cashdro_operation_id: operationData.operation_id || '',
                concept: operationData.concept || '',
            };
            
            console.log("[CashDro] Datos a enviar:", recordData);
            
            const recordId = await this.orm.create('cashdro.operation.log', [recordData]);
            
            console.log("[CashDro] Operación guardada en Odoo con ID:", recordId);
            this.notification.add(
                _t("Operación guardada en Odoo correctamente (ID: %s)", recordId),
                { type: "success" }
            );
            return recordId;
        } catch (error) {
            console.error("[CashDro] Error guardando en Odoo:", error);
            // Extraer mensaje de error más detallado
            let errorMsg = error.message || "Error desconocido";
            if (error.data && error.data.message) {
                errorMsg = error.data.message;
            } else if (error.data && error.data.debug) {
                errorMsg = error.data.debug.split('\n')[0]; // Primera línea del traceback
            }
            
            // No lanzamos error para no interrumpir el flujo, pero notificamos
            this.notification.add(
                _t("Advertencia: Operación completada en CashDro pero no guardada en Odoo: %s", errorMsg),
                { type: "warning", sticky: true }
            );
            return null;
        }
    },

    /**
     * Ejecuta una operación CashDro con polling y mostrador de progreso.
     */
    async _executeOperationWithPolling(gateway, config, formData) {
        let operationId = null;
        
        // DEBUG: Ver qué tenemos en formData
        console.log("[CashDro DEBUG] formData:", formData);
        console.log("[CashDro DEBUG] env.context:", this.env?.context);
        
        // Obtener payment_method_id de múltiples fuentes
        let paymentMethodId = null;
        
        // Fuente 1: formData.payment_method_id (puede ser [id, name], {id, name}, número, o Proxy)
        if (formData.payment_method_id) {
            const pm = formData.payment_method_id;
            console.log("[CashDro DEBUG] payment_method_id type:", typeof pm, "value:", pm);
            
            if (Array.isArray(pm)) {
                paymentMethodId = pm[0];
            } else if (typeof pm === 'number') {
                paymentMethodId = pm;
            } else if (typeof pm === 'object') {
                // Puede ser {id: X, name: '...'} o un Proxy
                paymentMethodId = pm.id || pm[0];
            }
        }
        
        // Fuente 2: Contexto del wizard
        if (!paymentMethodId && this.env?.context?.default_payment_method_id) {
            paymentMethodId = this.env.context.default_payment_method_id;
        }
        
        // Fuente 3: Buscar en el modelo root
        if (!paymentMethodId && this.model?.root?.data?.payment_method_id) {
            const pm = this.model.root.data.payment_method_id;
            if (Array.isArray(pm)) paymentMethodId = pm[0];
            else if (typeof pm === 'number') paymentMethodId = pm;
            else if (typeof pm === 'object') paymentMethodId = pm.id || pm[0];
        }
        
        console.log("[CashDro DEBUG] paymentMethodId obtenido:", paymentMethodId);
        
        const amount = config.requiresAmount ? formData[config.amountField] : 0;
        
        try {
            // PASO 1: Iniciar operación
            this.notification.add(
                _t("%s: iniciando operación...", config.description),
                { type: "info" }
            );
            
            let startResponse;
            if (config.operationAdmin) {
                startResponse = await gateway.startOperationAdmin(config.operationType, {});
            } else {
                if (config.requiresAmount && (!amount || amount <= 0)) {
                    throw new Error(_t("El importe debe ser mayor que 0"));
                }
                startResponse = await gateway.startOperation(amount, config.operationType);
            }
            
            operationId = startResponse.operation_id;
            console.log("[CashDro] OperationId obtenido:", operationId);
            
            // PASO 2: Reconocer la operación (ACKNOWLEDGE es CRÍTICO para mostrar pantalla en máquina)
            // Sin esto, la máquina no muestra la pantalla de operación
            try {
                console.log("[CashDro] Enviando acknowledgeOperation...");
                
                // Para operaciones administrativas (Ingresar, Carga, etc.) usar acknowledgeOperationAdmin
                // que usa POST a index.php como en el código Python original
                if (config.operationAdmin) {
                    console.log("[CashDro] Usando acknowledgeOperationAdmin (POST a index.php)");
                    await gateway.acknowledgeOperationAdmin(operationId);
                } else {
                    console.log("[CashDro] Usando acknowledgeOperation (GET a index3.php)");
                    await gateway.acknowledgeOperation(operationId);
                }
                
                console.log("[CashDro] Acknowledge enviado correctamente");
            } catch (ackErr) {
                console.warn("[CashDro] Acknowledge error (no crítico):", ackErr);
            }
            
            // PASO 3: Si requiere polling
            if (config.requiresPolling) {
                this.notification.add(
                    _t("Operación iniciada (ID=%s). Inserte dinero en la máquina...", operationId),
                    { type: "success", sticky: true }
                );
                
                const finalResponse = await gateway.pollUntilComplete(operationId, (progress) => {
                    console.log(`[CashDro Polling] Intento ${progress.attemptCount}, Estado: ${progress.state}, Tiempo: ${progress.elapsedSeconds}s`);
                });
                
                this.notification.add(_t("Operación completada"), { type: "success" });
                
                // PASO 3b: Guardar resultado en Odoo después de completar
                if (paymentMethodId) {
                    await this._saveOperationToOdoo({
                        payment_method_id: paymentMethodId,
                        operation_type: this._getOperationTypeName(config.operationType),
                        amount: amount,
                        state: 'completed',
                        operation_id: operationId,
                        concept: config.description,
                    });
                } else {
                    console.warn("[CashDro] No se guardó en Odoo: falta payment_method_id");
                }
                
            } else if (config.applyDepositLevels) {
                // Especial: aplicar fianza
                await gateway.applyDepositLevels();
                this.notification.add(_t("Fianza aplicada correctamente"), { type: "success" });
                
                // Guardar en Odoo
                if (paymentMethodId) {
                    await this._saveOperationToOdoo({
                        payment_method_id: paymentMethodId,
                        operation_type: 'fianza',
                        amount: 0,
                        state: 'completed',
                        operation_id: operationId || '',
                        concept: config.description,
                    });
                }
                
            } else if (config.webInterface) {
                // Abrir interfaz web
                const webUrl = config.operationType === 2 
                    ? gateway.getRetiradaWebUrl(operationId)
                    : gateway.getCambioWebUrl(operationId);
                window.open(webUrl, 'cashdro_web', 'width=1024,height=768');
                this.notification.add(
                    _t("Interfaz web abierta. Complete la operación en la máquina y en la ventana."),
                    { type: "info", sticky: true }
                );
                
                // Guardar en Odoo
                if (paymentMethodId) {
                    await this._saveOperationToOdoo({
                        payment_method_id: paymentMethodId,
                        operation_type: this._getOperationTypeName(config.operationType),
                        amount: 0,
                        state: 'pending',
                        operation_id: operationId,
                        concept: config.description,
                    });
                }
                
            } else {
                // Operación iniciada pero sin polling (ej: Ingresar, Carga, etc.)
                this.notification.add(
                    _t("Operación '%s' iniciada (ID=%s). La máquina debería mostrar la pantalla de operación. Si no aparece, verifique la conexión con el CashDro.", config.description, operationId),
                    { type: "success", sticky: true }
                );
                
                // Guardar en Odoo
                if (paymentMethodId) {
                    await this._saveOperationToOdoo({
                        payment_method_id: paymentMethodId,
                        operation_type: this._getOperationTypeName(config.operationType),
                        amount: amount || 0,
                        state: 'completed',
                        operation_id: operationId,
                        concept: config.description,
                    });
                } else {
                    console.warn("[CashDro] Operación completada pero no guardada: falta payment_method_id");
                }
            }
            
            // PASO 4: Finalizar (solo para operaciones que lo requieren)
            // NO hacer finish para: Ingresar(16), Carga(1), Cambio(18), etc.
            // Solo hacer finish para operaciones que necesitan confirmación explícita
            const shouldFinish = config.operationType === 12; // Solo inicializar niveles (type=12)
            
            if (shouldFinish) {
                try {
                    console.log("[CashDro] Finalizando operación type=" + config.operationType);
                    await gateway.finishOperation(operationId, 1);
                } catch (finErr) {
                    console.warn("Finish error:", finErr);
                }
            } else {
                console.log("[CashDro] No se finaliza operación type=" + config.operationType + " - la máquina permanece en modo operación");
            }
            
            // PASO 5: Cerrar wizard
            this.env?.dialogData?.close?.();
            
        } catch (error) {
            console.error("[CashDro] Error en operación:", error);
            
            // Intentar cancelar operación
            if (operationId) {
                try {
                    await gateway.finishOperation(operationId, 2);
                } catch (cancelErr) {
                    console.warn("Cancel error:", cancelErr);
                }
            }
            
            throw error;
        }
    },
});
