/** @odoo-module */

/**
 * Evita crash del quiosco si self_ordering_available_language_ids no viene como array
 * (undefined tras carga parcial del pos.config en el cliente).
 */
import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";

patch(SelfOrder.prototype, {
    _initLanguages() {
        const cfg = this.config;
        let languages = cfg.self_ordering_available_language_ids;
        if (!Array.isArray(languages)) {
            languages = [];
        }
        const def = cfg.self_ordering_default_language_id;
        if (!languages.length && def) {
            languages = [def];
        }
        if (!languages.length) {
            const fb = {
                id: def && typeof def.id === "number" ? def.id : 0,
                code: (def && def.code) || "en_US",
                name: (def && def.name) || "English",
            };
            languages = [fb];
            if (!cfg.self_ordering_default_language_id) {
                cfg.self_ordering_default_language_id = fb;
            }
        }
        cfg.self_ordering_available_language_ids = languages;
        return super._initLanguages(...arguments);
    },

    initData() {
        this.initProducts();
        this._initLanguages();
        const pm = this.models["pos.printer"];
        if (pm && typeof pm.getAll === "function") {
            for (const printerConfig of pm.getAll()) {
                const printer = this.createPrinter(printerConfig);
                if (printer) {
                    printer.config = printerConfig;
                    this.kitchenPrinters.push(printer);
                }
            }
        }
    },
});
