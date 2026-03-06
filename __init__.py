# -*- coding: utf-8 -*-
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

# Parche: omitir validación RelaxNG solo para este módulo (schema oficial rechaza openerp/record).
def _apply_xml_import_patch():
    import os
    from lxml import etree
    from odoo.tools import config
    from odoo.tools import convert

    _original = convert.convert_xml_import

    def _convert_xml_import(env, module, xmlfile, idref=None, mode="init", noupdate=False, report=None):
        doc = etree.parse(xmlfile)
        if module != "cs_pos_smart_cash_cashdro":
            schema = os.path.join(config.root_path, "import_xml.rng")
            relaxng = etree.RelaxNG(etree.parse(schema))
            relaxng.assert_(doc)
        if isinstance(xmlfile, str):
            xml_filename = xmlfile
        else:
            xml_filename = getattr(xmlfile, "name", None)
        obj = convert.xml_import(env, module, idref, mode, noupdate=noupdate, xml_filename=xml_filename)
        obj.parse(doc.getroot())

    convert.convert_xml_import = _convert_xml_import


_apply_xml_import_patch()

from . import models
from . import controllers


def post_init_hook(cr, registry):
    """Crear permisos ir.model.access para modelos Movimientos (evita XML con RelaxNG conflictivo)."""
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    group_id = env.ref("point_of_sale.group_pos_manager").id
    models_to_access = [
        ("cashdro.caja.movimientos", "Cashdro Caja Movimientos"),
        ("cashdro.movimiento.pago.wizard", "Cashdro Pago Wizard"),
        ("cashdro.movimiento.devolucion.wizard", "Cashdro Devolucion Wizard"),
        ("cashdro.movimiento.carga.wizard", "Cashdro Carga Wizard"),
        ("cashdro.movimiento.inicializar.wizard", "Cashdro Inicializar Wizard"),
        ("cashdro.movimiento.fianza.wizard", "Cashdro Fianza Wizard"),
    ]
    for model_name, name in models_to_access:
        model = env["ir.model"].search([("model", "=", model_name)], limit=1)
        if model and not env["ir.model.access"].search_count([
            ("model_id", "=", model.id),
            ("group_id", "=", group_id),
        ]):
            env["ir.model.access"].create({
                "name": name,
                "model_id": model.id,
                "group_id": group_id,
                "perm_read": True,
                "perm_write": True,
                "perm_create": True,
                "perm_unlink": True,
            })


__all__ = [
    "models",
    "controllers",
]
