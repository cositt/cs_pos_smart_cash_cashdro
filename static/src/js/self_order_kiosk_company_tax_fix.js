/** @odoo-module */

/**
 * Lista de productos: getTaxDetails usa config.company_id; si falta o no trae
 * tax_calculation_rounding_method, add_tax_details_in_base_line revienta.
 */
import { patch } from "@web/core/utils/patch";
import { ProductTemplateAccounting } from "@point_of_sale/app/models/accounting/product_template_accounting";
import { accountTaxHelpers } from "@account/helpers/account_tax";

function resolveCompany(models) {
    const config = models?.["pos.config"]?.getFirst?.();
    let company = config?.company_id;
    if (typeof company === "number" && models["res.company"]?.get) {
        company = models["res.company"].get(company);
    }
    if (!company || !company.tax_calculation_rounding_method) {
        const cid = company?.id;
        if (cid && models["res.company"]?.get) {
            const full = models["res.company"].get(cid);
            if (full?.tax_calculation_rounding_method) {
                company = full;
            }
        }
    }
    if (!company) {
        company = models["res.company"]?.getFirst?.();
    }
    const currency = config?.currency_id;
    const cur = company?.currency_id || currency || { id: 0, rounding: 0.01 };
    if (!company) {
        return {
            id: 0,
            currency_id: cur,
            tax_calculation_rounding_method: "round_per_line",
        };
    }
    if (!company.currency_id) {
        company = { ...company, currency_id: cur };
    }
    if (!company.tax_calculation_rounding_method) {
        return {
            ...company,
            tax_calculation_rounding_method: "round_globally",
        };
    }
    return company;
}

patch(ProductTemplateAccounting.prototype, {
    getTaxDetails(opts = {}) {
        const company = resolveCompany(this.models);
        const baseLine = this.getBaseLine(opts);
        accountTaxHelpers.add_tax_details_in_base_line(baseLine, company);
        accountTaxHelpers.round_base_lines_tax_details([baseLine], company);
        return baseLine.tax_details;
    },
});
