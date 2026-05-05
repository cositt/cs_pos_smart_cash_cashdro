/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ConfirmationPage } from "@pos_self_order/app/pages/confirmation_page/confirmation_page";

console.log("[Kiosk Auto Print] ✅ Módulo cargado correctamente");

/**
 * Auto-impresión de ticket en quiosco al completar pedido.
 * Usa iframe oculto para que el cliente no vea nada.
 */

patch(ConfirmationPage.prototype, {
    setup() {
        console.log("[Kiosk Auto Print] 🔧 Setup llamado, aplicando patch...");
        super.setup(...arguments);
        
        setTimeout(() => {
            console.log("[Kiosk Auto Print] ⏰ Timeout completado, llamando autoPrintTicket...");
            try {
                this.autoPrintTicket();
            } catch (error) {
                console.error("[Kiosk Auto Print] ❌ Error en autoPrintTicket:", error);
            }
        }, 1500);
    },

    /**
     * Genera e imprime el ticket usando iframe oculto.
     */
    autoPrintTicket() {
        console.log("[Kiosk Auto Print] 🎫 Iniciando autoPrintTicket...");
        
        const order = this.selfOrder?.currentOrder;
        
        if (!order) {
            console.warn("[Kiosk Auto Print] ⚠️ No hay pedido actual");
            return;
        }

        console.log("[Kiosk Auto Print] 📄 Imprimiendo ticket para pedido:", order.tracking_number || order.id);

        try {
            // Crear iframe oculto
            const iframe = document.createElement('iframe');
            iframe.style.position = 'absolute';
            iframe.style.width = '0px';
            iframe.style.height = '0px';
            iframe.style.border = 'none';
            iframe.style.visibility = 'hidden';
            
            document.body.appendChild(iframe);
            console.log("[Kiosk Auto Print] ✅ Iframe creado (oculto)");

            // Generar y escribir HTML
            const ticketHTML = this.generateTicketHTML(order);
            const iframeDoc = iframe.contentWindow.document;
            iframeDoc.open();
            iframeDoc.write(ticketHTML);
            iframeDoc.close();

            // Esperar a que cargue e imprimir
            iframe.onload = () => {
                console.log("[Kiosk Auto Print] 🖨️ Imprimiendo...");
                setTimeout(() => {
                    iframe.contentWindow.print();
                    console.log("[Kiosk Auto Print] ✅ print() ejecutado");
                    
                    // Limpiar iframe después de imprimir
                    setTimeout(() => {
                        document.body.removeChild(iframe);
                        console.log("[Kiosk Auto Print] 🚪 Iframe eliminado");
                    }, 1000);
                }, 100);
            };
            
        } catch (error) {
            console.error("[Kiosk Auto Print] ❌ Error durante la impresión:", error);
        }
    },

    /**
     * Genera el HTML del ticket optimizado para impresoras térmicas 80mm.
     */
    generateTicketHTML(order) {
        const company = this.selfOrder.config?.company_id;
        const config = this.selfOrder.config;
        const lines = order.lines || [];
        
        const now = new Date();
        const dateStr = now.toLocaleDateString('es-ES');
        const timeStr = now.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });

        // Generar líneas de productos
        const linesHTML = lines.map(line => {
            const product = line.product_id;
            const qty = line.qty;
            const price = line.price_unit;
            const subtotal = qty * price;
            
            return `
                <tr>
                    <td>${qty}x</td>
                    <td>${product?.display_name || product?.name || 'Producto'}</td>
                    <td class="text-right">${this.formatCurrency(subtotal)}</td>
                </tr>
            `;
        }).join('');

        return `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Ticket ${order.tracking_number || order.id}</title>
    <style>
        @page {
            /* Papel térmico 80mm de ancho, alto automático según contenido */
            size: 80mm auto;
            margin: 0;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Courier New', Courier, monospace;
            font-size: 11px;
            line-height: 1.3;
            width: 80mm;
            padding: 3mm 4mm;
            background: white;
            color: black;
        }
        
        .header {
            text-align: center;
            margin-bottom: 8px;
            padding-bottom: 8px;
            border-bottom: 1px dashed #000;
        }
        
        .company-name {
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 4px;
        }
        
        .info-line {
            font-size: 10px;
            margin: 2px 0;
        }
        
        .order-number {
            font-size: 22px;
            font-weight: bold;
            margin: 12px 0;
            text-align: center;
            border: 2px solid #000;
            padding: 8px;
        }
        
        table {
            width: 100%;
            margin: 8px 0;
            border-collapse: collapse;
        }
        
        thead {
            border-bottom: 1px solid #000;
            border-top: 1px solid #000;
        }
        
        th {
            padding: 4px 2px;
            font-weight: bold;
            font-size: 10px;
        }
        
        td {
            padding: 3px 2px;
            font-size: 11px;
        }
        
        .text-right {
            text-align: right;
        }
        
        .total-section {
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid #000;
        }
        
        .total-line {
            display: flex;
            justify-content: space-between;
            margin: 4px 0;
            font-size: 12px;
        }
        
        .total-line.grand-total {
            font-size: 15px;
            font-weight: bold;
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px dashed #000;
        }
        
        .footer {
            margin-top: 12px;
            padding-top: 8px;
            text-align: center;
            font-size: 10px;
            border-top: 1px dashed #000;
        }
        
        .footer div {
            margin: 3px 0;
        }
        
        @media print {
            body {
                background: white;
            }
            
            /* Asegurar que no haya saltos de página innecesarios */
            .header, .order-number, table, .total-section, .footer {
                page-break-inside: avoid;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="company-name">${company ? company[1] : 'La Trufa'}</div>
        <div class="info-line">Fecha: ${dateStr} ${timeStr}</div>
        <div class="info-line">TPV: ${config?.name || 'Quiosco'}</div>
    </div>

    <div class="order-number">
        PEDIDO #${order.tracking_number || order.id}
    </div>

    <table>
        <thead>
            <tr>
                <th width="15%">Cant</th>
                <th width="55%">Producto</th>
                <th width="30%" class="text-right">Precio</th>
            </tr>
        </thead>
        <tbody>
            ${linesHTML}
        </tbody>
    </table>

    <div class="total-section">
        <div class="total-line">
            <span>Subtotal:</span>
            <span>${this.formatCurrency(order.amount_total || 0)}</span>
        </div>
        <div class="total-line grand-total">
            <span>TOTAL:</span>
            <span>${this.formatCurrency(order.amount_total || 0)}</span>
        </div>
    </div>

    <div class="footer">
        <div>¡Gracias por su compra!</div>
        <div>Conserve este ticket para recoger su pedido</div>
    </div>
</body>
</html>
        `.trim();
    },

    formatCurrency(amount) {
        try {
            return this.selfOrder.formatMonetary(amount);
        } catch (error) {
            return `${amount.toFixed(2)}€`;
        }
    },
});

console.log("[Kiosk Auto Print] 🎯 Patch aplicado a ConfirmationPage");
