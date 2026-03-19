/** @odoo-module */

/**
 * Tras connectNewData (pago CashDro) la orden puede recomputar precios antes de que
 * pos.config.company_id esté enlazado → company undefined → crash en get_tax_totals_summary.
 */
import { patch } from "@web/core/utils/patch";
import { PosOrderAccounting } from "@point_of_sale/app/models/accounting/pos_order_accounting";
import { accountTaxHelpers } from "@account/helpers/account_tax";

function emptyPriceData(documentSign, currency) {
    const cur = currency || { id: 0, rounding: 0.01 };
    return {
        taxDetails: {
            total_amount_currency: 0,
            total_amount: 0,
            currency_id: cur.id,
            currency_pd: cur.rounding,
            company_currency_id: cur.id,
            company_currency_pd: cur.rounding,
            has_tax_groups: false,
            subtotals: [],
            base_amount_currency: 0,
            base_amount: 0,
            tax_amount_currency: 0,
            tax_amount: 0,
            order_sign: documentSign,
            total_amount_no_rounding: 0,
        },
        baseLines: [],
        baseLineByLineUuids: {},
    };
}

patch(PosOrderAccounting.prototype, {
    _computeAllPrices(opts = {}) {
        const cfg = this.models?.["pos.config"]?.getFirst?.();
        const currency = this.currency || cfg?.currency_id;
        let company = this.company || cfg?.company_id;

        if (!company && currency) {
            company = {
                id: cfg?.company_id?.id ?? 0,
                currency_id: currency,
            };
        } else if (company && !company.currency_id && currency) {
            company = { ...company, currency_id: currency };
        }

        if (!currency || !company?.currency_id) {
            return emptyPriceData(this.isRefund ? -1 : 1, currency);
        }

        const lines = opts.lines || this.lines || [];
        const documentSign = this.isRefund ? -1 : 1;
        const baseLines = lines.map((l) =>
            l.getBaseLine({
                quantity: l.qty,
                price_unit: l.price_unit,
                ...(opts.baseLineOpts || {}),
            })
        );

        try {
            accountTaxHelpers.add_tax_details_in_base_lines(baseLines, company);
            accountTaxHelpers.round_base_lines_tax_details(baseLines, company);
        } catch (e) {
            console.warn("[CashDro] add_tax_details_in_base_lines:", e);
            return emptyPriceData(documentSign, currency);
        }

        const config = this.config || cfg;
        const cashRounding = config?.cash_rounding ? config?.rounding_method : null;
        let data;
        try {
            data = accountTaxHelpers.get_tax_totals_summary(baseLines, currency, company, {
                cash_rounding: cashRounding,
            });
        } catch (e) {
            console.warn("[CashDro] get_tax_totals_summary:", e);
            return emptyPriceData(documentSign, currency);
        }

        const total = data.total_amount_currency - (data.cash_rounding_base_amount_currency || 0.0);
        data.order_sign = documentSign;
        data.total_amount_no_rounding = total;

        const baseLineByLineUuids = baseLines.reduce((acc, line) => {
            acc[line.record.uuid] = line;
            return acc;
        }, {});

        return { taxDetails: data, baseLines, baseLineByLineUuids };
    },
});
