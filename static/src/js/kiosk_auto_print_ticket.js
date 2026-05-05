/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ConfirmationPage } from "@pos_self_order/app/pages/confirmation_page/confirmation_page";

/**
 * Auto-impresión de ticket en quiosco al completar pedido.
 * 
 * Funciona con Chrome en modo kiosk (--kiosk --kiosk-printing) para imprimir
 * automáticamente sin mostrar el diálogo de Windows.
 * 
 * Si no está en kiosk mode, se abrirá el diálogo normal de impresión.
 */

patch(ConfirmationPage.prototype, {
    setup() {
        super.setup(...arguments);
        
        // Esperar un poco para que la UI se estabilice antes de imprimir
        setTimeout(() => {
            this.autoPrintTicket();
        }, 1000);
    },

    /**
     * Genera e imprime el ticket del pedido automáticamente.
     */
    autoPrintTicket() {
        const order = this.selfOrder.currentOrder;
        
        if (!order) {
            console.warn("[Kiosk Auto Print] No hay pedido actual");
            return;
        }

        console.log("[Kiosk Auto Print] Imprimiendo ticket para pedido:", order.tracking_number);

        // Generar HTML del ticket
        const ticketHTML = this.generateTicketHTML(order);

        // Abrir ventana de impresión
        const printWindow = window.open('', '_blank', 'width=800,height=600');
        
        if (!printWindow) {
            console.error("[Kiosk Auto Print] No se pudo abrir ventana de impresión (popup bloqueado?)");
            return;
        }

        printWindow.document.write(ticketHTML);
        printWindow.document.close();

        // Esperar a que cargue el contenido antes de imprimir
        printWindow.onload = function() {
            printWindow.print();
            
            // Cerrar ventana después de imprimir
            setTimeout(() => {
                printWindow.close();
            }, 1000);
        };
    },

    /**
     * Genera el HTML del ticket con los datos del pedido.
     */
    generateTicketHTML(order) {
        const company = this.selfOrder.config.company_id;
        const config = this.selfOrder.config;
        const lines = order.lines || [];
        
        // Formatear fecha y hora
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
                    <td>${product.display_name || 'Producto'}</td>
                    <td class="text-right">${this.formatCurrency(subtotal)}</td>
                </tr>
            `;
        }).join('');

        return `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Ticket - Pedido #${order.tracking_number}</title>
    <style>
        @page {
            size: 80mm auto;
            margin: 0;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.4;
            width: 80mm;
            padding: 5mm;
            background: white;
        }
        
        .header {
            text-align: center;
            margin-bottom: 10px;
            border-bottom: 2px dashed #000;
            padding-bottom: 10px;
        }
        
        .company-name {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .order-number {
            font-size: 24px;
            font-weight: bold;
            margin: 15px 0;
            text-align: center;
            border: 2px solid #000;
            padding: 10px;
        }
        
        .info-line {
            margin: 3px 0;
        }
        
        table {
            width: 100%;
            margin: 10px 0;
            border-collapse: collapse;
        }
        
        th, td {
            padding: 5px 2px;
            text-align: left;
        }
        
        th {
            border-bottom: 1px solid #000;
            border-top: 1px solid #000;
            font-weight: bold;
        }
        
        .text-right {
            text-align: right;
        }
        
        .total-section {
            margin-top: 10px;
            border-top: 2px solid #000;
            padding-top: 10px;
        }
        
        .total-line {
            display: flex;
            justify-content: space-between;
            margin: 5px 0;
            font-size: 14px;
        }
        
        .total-line.grand-total {
            font-size: 16px;
            font-weight: bold;
            margin-top: 10px;
            border-top: 1px dashed #000;
            padding-top: 10px;
        }
        
        .footer {
            margin-top: 20px;
            text-align: center;
            border-top: 2px dashed #000;
            padding-top: 10px;
            font-size: 11px;
        }
        
        @media print {
            body {
                background: white;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="company-name">${company[1] || 'La Trufa'}</div>
        <div class="info-line">Fecha: ${dateStr} ${timeStr}</div>
        <div class="info-line">TPV: ${config.name || 'Quiosco'}</div>
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

    /**
     * Formatea cantidad como moneda.
     */
    formatCurrency(amount) {
        return this.selfOrder.formatMonetary(amount);
    },
});
