/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.notification = useService("notification");
    },

    async beforeExecuteActionButton(clickParams) {
        console.log("🎯 beforeExecuteActionButton:", clickParams.name, clickParams.type, "modelo:", this.model?.root?.resModel);
        
        // Si es el botón de CashDro en el modelo pos.payment.method
        if (clickParams.name === "action_test_connection_client" && this.model?.root?.resModel === "pos.payment.method") {
            console.log("🚀 Interceptando validación CashDro");
            
            const data = this.model.root.data;
            const host = data.cashdro_host;
            const user = data.cashdro_user;
            const password = data.cashdro_password;

            console.log("📋 Host:", host, "User:", user);

            if (!host || !user || !password) {
                this.notification.add("Por favor completa Host, Usuario y Contraseña", {
                    type: "warning",
                });
                return false;
            }

            this.notification.add("Conectando con CashDro desde navegador...", {
                type: "info",
            });

            const url = `https://${host}/Cashdro3WS/index.php`;
            const credentials = btoa(`${user}:${password}`);

            console.log("📡 Fetch a:", url);

            try {
                const response = await fetch(url, {
                    method: "GET",
                    headers: {
                        "Authorization": `Basic ${credentials}`,
                        "Content-Type": "application/json",
                    },
                    mode: "cors",
                    credentials: "omit",
                });

                console.log("✅ Respuesta:", response.status);

                if (response.ok) {
                    this.notification.add("✅ Conexión exitosa con CashDro", {
                        type: "success",
                    });
                } else {
                    this.notification.add(`❌ Error HTTP ${response.status}`, {
                        type: "danger",
                    });
                }
            } catch (error) {
                console.error("❌ Error:", error);
                this.notification.add(`❌ No se pudo conectar: ${error.message}`, {
                    type: "danger",
                    sticky: true,
                });
            }
            
            return false; // Detener ejecución - no llamar al servidor
        }
        
        // Para otras acciones, comportamiento normal
        return super.beforeExecuteActionButton(...arguments);
    }
});

// Registrar una vista dummy para que js_class no falle
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
registry.category("views").add("cashdro_payment_method_form", {
    ...formView,
});
