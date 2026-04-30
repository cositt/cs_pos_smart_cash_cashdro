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
                // Recargar el formulario para que muestre los datos actualizados
                await this.model.load();
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
                // Recargar el formulario
                await this.model.load();
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
                operationType: 16, // INGRESAR
                operationAdmin: true,
                description: _t('Ingresar'),
                requiresAmount: false,
                requiresPolling: false,
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
     * Ejecuta una operación CashDro con polling y mostrador de progreso.
     */
    async _executeOperationWithPolling(gateway, config, formData) {
        let operationId = null;
        
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
                const amount = config.requiresAmount ? formData[config.amountField] : 0;
                if (config.requiresAmount && (!amount || amount <= 0)) {
                    throw new Error(_t("El importe debe ser mayor que 0"));
                }
                startResponse = await gateway.startOperation(amount, config.operationType);
            }
            
            operationId = startResponse.operation_id;
            
            // PASO 2: Reconocer la operación (solo para algunas)
            if (!config.operationAdmin || config.operationType === 4) {
                try {
                    await gateway.acknowledgeOperation(operationId);
                } catch (ackErr) {
                    console.warn("Acknowledge error:", ackErr);
                }
            }
            
            // PASO 3: Si requiere polling
            if (config.requiresPolling) {
                this.notification.add(
                    _t("Operación iniciada (ID=%s). Inserte dinero en la máquina...", operationId),
                    { type: "success", sticky: true }
                );
                
                await gateway.pollUntilComplete(operationId, (progress) => {
                    console.log(`[CashDro Polling] Intento ${progress.attemptCount}, Estado: ${progress.state}, Tiempo: ${progress.elapsedSeconds}s`);
                });
                
                this.notification.add(_t("Operación completada"), { type: "success" });
            } else if (config.applyDepositLevels) {
                // Especial: aplicar fianza
                await gateway.applyDepositLevels();
                this.notification.add(_t("Fianza aplicada correctamente"), { type: "success" });
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
            } else {
                this.notification.add(
                    _t("Operación iniciada en la máquina (ID=%s)", operationId),
                    { type: "success" }
                );
            }
            
            // PASO 4: Finalizar (si aplica)
            if (config.operationAdmin && config.operationType !== 2) {
                try {
                    await gateway.finishOperation(operationId, 1);
                } catch (finErr) {
                    console.warn("Finish error:", finErr);
                }
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
