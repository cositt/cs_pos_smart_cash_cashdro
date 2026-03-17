# -*- coding: utf-8 -*-
{
    "name": "CS POS Smart Cash CashDro",
    "version": "19.0.1.1.0",
    "category": "Sales/Point of Sale",
    "summary": "Integración de máquinas Cashdrop para pagos en POS",
    "description": """
        Módulo de integración con máquinas Cashdrop para pagos en puntos de venta.
        Proporciona:
        - Configuración por método de pago
        - Transacciones con sincronización en tiempo real
        - 5 endpoints REST para operaciones de pago
        - Polling con reintentos automáticos
        - Historial de transacciones
    """,
    "author": "Juan Cositt, Oz Agent",
    "website": "https://github.com/cositt",
    "license": "LGPL-3",
    "depends": [
        "base",
        "sale",
        "point_of_sale",
        "pos_self_order",
        "pos_self_order_iot",
    ],
    "assets": {
        "pos_self_order.assets": [
            "cs_pos_smart_cash_cashdro/static/src/css/cashdrop_pending_dialog.css",
            "cs_pos_smart_cash_cashdro/static/src/js/cashdrop_pending_dialog.js",
            "cs_pos_smart_cash_cashdro/static/src/js/cashdrop_pending_dialog.xml",
            "cs_pos_smart_cash_cashdro/static/src/js/payment_page_cashdro_icon.xml",
            "cs_pos_smart_cash_cashdro/static/src/js/router_no_dynamic_slot_patch.js",
            "cs_pos_smart_cash_cashdro/static/src/js/payment_page_cashdro_patch.js",
            "cs_pos_smart_cash_cashdro/static/src/js/self_order_cashdro_patch.js",
        ],
        # Caja registradora: compat getChange + interface CashDro (al pulsar Efectivisimo se envía pago a CashDro).
        "point_of_sale._assets_pos": [
            "cs_pos_smart_cash_cashdro/static/src/app/compat_pos_get_change.js",
            "cs_pos_smart_cash_cashdro/static/src/app/compat_payment_validate_get_change.js",
            "cs_pos_smart_cash_cashdro/static/src/app/pos_cashdro_payment.js",
            "cs_pos_smart_cash_cashdro/static/src/app/pos_cashdro_refund_payment.js",
        ],
    },
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Sequences
        "data/ir_sequence.xml",
        # Views (cargan antes que permisos Movimientos para que ir.model exista)
        "views/pos_payment_method_views.xml",
        "views/cashdro_transaction_views.xml",
        "views/cashdro_movimientos_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
    "external_dependencies": {
        "python": ["requests"],
    },
}
