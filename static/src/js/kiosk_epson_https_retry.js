/** @odoo-module */

/**
 * Mismo comportamiento que pos_epson_force_https, pero SOLO en el bundle del quiosco.
 * Cargar esos JS desde pos_epson_force_https en pos_self_order.assets rompe con
 * "odoo.define is not a function" (bundle distinto al de la caja).
 */
import { patch } from "@web/core/utils/patch";
import { EpsonPrinter } from "@point_of_sale/app/utils/printer/epson_printer";
import { getLNATargetAddressSpace } from "@point_of_sale/app/utils/init_lna";
import { _t } from "@web/core/l10n/translation";

patch(EpsonPrinter.prototype, {
    setup({ ip }) {
        super.setup(...arguments);
        const protocol = "https:";
        this.url = protocol + "//" + ip;
        this.address = this.url + "/cgi-bin/epos/service.cgi?devid=local_printer";
        if (odoo.use_lna) {
            this.lnaTargetAddressSpace = getLNATargetAddressSpace(this.address);
        }
    },
});

const ERROR_HTTP_503 = "HTTP_503";
const ERROR_HTTP_OTHER = "HTTP_ERROR";
const ERROR_EMPTY_RESPONSE = "EMPTY_RESPONSE";
const ERROR_CODE_PRINTER_NOT_REACHABLE = "PRINTER_NOT_REACHABLE";

function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
}

patch(EpsonPrinter.prototype, {
    async sendPrintingJob(img) {
        const maxAttempts = 7;
        const params = {
            method: "POST",
            body: img,
            signal: AbortSignal.timeout(25000),
        };
        if (this.lnaTargetAddressSpace) {
            params.targetAddressSpace = this.lnaTargetAddressSpace;
        }

        let lastError = ERROR_CODE_PRINTER_NOT_REACHABLE;

        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                const res = await fetch(this.address, params);
                const body = await res.text();

                if (res.status === 503 || (res.ok && !body.trim())) {
                    lastError = ERROR_HTTP_503;
                    if (attempt < maxAttempts) {
                        await sleep(1000 * attempt);
                        continue;
                    }
                }

                if (!res.ok && res.status !== 503) {
                    return {
                        result: false,
                        canRetry: true,
                        errorCode: `${ERROR_HTTP_OTHER}_${res.status}`,
                        httpStatus: res.status,
                    };
                }

                if (!res.ok) {
                    return {
                        result: false,
                        canRetry: true,
                        errorCode: ERROR_HTTP_503,
                        httpStatus: 503,
                    };
                }

                if (!body.trim()) {
                    lastError = ERROR_EMPTY_RESPONSE;
                    if (attempt < maxAttempts) {
                        await sleep(1000 * attempt);
                        continue;
                    }
                    return {
                        result: false,
                        canRetry: true,
                        errorCode: ERROR_EMPTY_RESPONSE,
                    };
                }

                const parser = new DOMParser();
                const parsedBody = parser.parseFromString(body, "application/xml");
                const response = parsedBody.querySelector("response");
                if (!response) {
                    lastError = ERROR_EMPTY_RESPONSE;
                    if (attempt < maxAttempts) {
                        await sleep(1000 * attempt);
                        continue;
                    }
                    return {
                        result: false,
                        canRetry: true,
                        errorCode: ERROR_EMPTY_RESPONSE,
                    };
                }

                return {
                    result: response.getAttribute("success") === "true",
                    errorCode: response.getAttribute("code"),
                    status: parseInt(response.getAttribute("status"), 10) || 0,
                    canRetry: true,
                };
            } catch {
                lastError = ERROR_CODE_PRINTER_NOT_REACHABLE;
                if (attempt < maxAttempts) {
                    await sleep(1000 * attempt);
                    continue;
                }
            }
        }

        return {
            result: false,
            canRetry: true,
            errorCode: lastError,
        };
    },

    getResultsError(printResult) {
        const code = printResult?.errorCode;
        if (code === ERROR_HTTP_503) {
            return {
                successful: false,
                errorCode: code,
                status: printResult?.status || 0,
                canRetry: true,
                message: {
                    title: _t("Printing failed"),
                    body: _t(
                        "The printer web service returned unavailable (HTTP 503). Often happens right after power-on or when the ePOS service is busy. Wait a few seconds and retry."
                    ),
                },
            };
        }
        if (code === ERROR_EMPTY_RESPONSE) {
            return {
                successful: false,
                errorCode: code,
                status: 0,
                canRetry: true,
                message: {
                    title: _t("Printing failed"),
                    body: _t(
                        "The printer answered but returned no data. Retry; if it repeats, restart the printer or check ePOS-Print is enabled."
                    ),
                },
            };
        }
        if (code && String(code).startsWith(`${ERROR_HTTP_OTHER}_`)) {
            return {
                successful: false,
                errorCode: code,
                status: printResult?.httpStatus || 0,
                canRetry: true,
                message: {
                    title: _t("Printing failed"),
                    body:
                        _t("HTTP error from printer:") +
                        " " +
                        String(printResult?.httpStatus || code),
                },
            };
        }
        return super.getResultsError(printResult);
    },
});
