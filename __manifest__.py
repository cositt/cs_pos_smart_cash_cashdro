# -*- coding: utf-8 -*-
{
    "name": "CS POS Smart Cash CashDro",
    "version": "19.0.1.0.0",
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
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Sequences
        "data/ir_sequence.xml",
        # Views
        "views/pos_payment_method_views.xml",
        "views/cashdro_transaction_views.xml",
        "views/res_config_settings_views.xml",
        "views/menu_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
    "external_dependencies": {
        "python": ["requests"],
    },
}
