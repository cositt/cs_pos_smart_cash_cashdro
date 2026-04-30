# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

from odoo import fields, models, api, _


class CashdroOperationLog(models.Model):
    """
    Registro persistente de operaciones CashDro.
    Guarda el historial de todas las operaciones realizadas desde el navegador.
    """
    _name = 'cashdro.operation.log'
    _description = 'Registro de operaciones CashDro'
    _order = 'create_date desc'
    
    payment_method_id = fields.Many2one(
        'pos.payment.method',
        string='Método de pago',
        required=True,
        domain=[('cashdro_enabled', '=', True)],
    )
    
    operation_type = fields.Selection([
        ('venta', 'Venta'),
        ('pago', 'Pago/Devolución'),
        ('cambio', 'Cambio'),
        ('carga', 'Carga'),
        ('retirada', 'Retirada'),
        ('retirada_casete_monedas', 'Retirada casete monedas'),
        ('retirada_casete_billetes', 'Retirada casete billetes'),
        ('ingresar', 'Ingresar'),
        ('ingreso_importe', 'Ingreso por importe'),
        ('fianza', 'Configurar fianza'),
        ('inicializar_niveles', 'Inicializar niveles'),
        ('consulta_fianza', 'Consulta fianza'),
        ('consulta_niveles', 'Consulta niveles'),
        ('operacion', 'Otra operación'),
    ], string='Tipo de operación', required=True)
    
    amount = fields.Float(
        string='Importe (€)',
        digits=(16, 2),
        default=0.0,
    )
    
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
        ('error', 'Error'),
    ], string='Estado', default='completed', required=True)
    
    cashdro_operation_id = fields.Char(
        string='ID Operación CashDro',
        help='Identificador de la operación en la máquina CashDro',
    )
    
    concept = fields.Char(
        string='Concepto/Descripción',
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        default=lambda self: self.env.user,
        readonly=True,
    )
    
    # Campos opcionales para debugging
    request_data = fields.Text(
        string='Datos de solicitud',
        help='JSON con los datos enviados al CashDro',
    )
    
    response_data = fields.Text(
        string='Datos de respuesta',
        help='JSON con la respuesta del CashDro',
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Sobrescribir para asegurar que se guarden correctamente."""
        for vals in vals_list:
            # Asegurar que amount sea float
            if 'amount' in vals and vals['amount'] is None:
                vals['amount'] = 0.0
            # Asegurar que cashdro_operation_id sea string
            if 'cashdro_operation_id' in vals and vals['cashdro_operation_id'] is None:
                vals['cashdro_operation_id'] = ''
        return super(CashdroOperationLog, self).create(vals_list)
