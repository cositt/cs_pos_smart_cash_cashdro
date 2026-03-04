# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class CashdroTransaction(models.Model):
    """Modelo para transacciones de pago con Cashdrop"""
    
    _name = 'cashdro.transaction'
    _description = 'Transacción Cashdrop'
    _order = 'create_date desc'
    
    # ========================
    # CAMPOS PRINCIPALES
    # ========================
    
    name = fields.Char(
        string='Referencia',
        readonly=True,
        copy=False,
        help='Referencia única de la transacción'
    )
    
    order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        required=False,
        readonly=True,
        ondelete='cascade',
        help='Orden de venta relacionada (opcional si es pago desde POS/kiosk)'
    )

    pos_order_id = fields.Many2one(
        'pos.order',
        string='Orden POS',
        required=False,
        readonly=True,
        ondelete='cascade',
        help='Orden POS relacionada (kiosk/tienda)'
    )
    
    payment_method_id = fields.Many2one(
        'pos.payment.method',
        string='Método de Pago',
        required=True,
        readonly=True,
        ondelete='restrict'
    )
    
    # ========================
    # IDENTIFICADORES
    # ========================
    
    transaction_id = fields.Char(
        string='ID Transacción',
        required=True,
        readonly=True,
        copy=False,
        index=True,
        help='Identificador único de la transacción en nuestro sistema'
    )
    
    operation_id = fields.Char(
        string='ID Operación Cashdrop',
        readonly=True,
        copy=False,
        help='ID de operación retornado por Cashdrop (para tracking)'
    )
    
    # ========================
    # DATOS FINANCIEROS
    # ========================
    
    amount = fields.Float(
        string='Monto',
        required=True,
        readonly=True,
        help='Monto en EUR a pagar'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Divisa',
        required=True,
        readonly=True,
        default=lambda self: self.env.ref('base.EUR')
    )
    
    amount_received = fields.Float(
        string='Monto Recibido',
        readonly=True,
        help='Monto realmente recibido por la máquina'
    )
    
    # ========================
    # ESTADO
    # ========================
    
    status = fields.Selection(
        selection=[
            ('processing', 'Procesando'),
            ('confirmed', 'Confirmado'),
            ('cancelled', 'Cancelado'),
            ('error', 'Error'),
            ('timeout', 'Timeout')
        ],
        default='processing',
        required=True,
        readonly=True,
        help='Estado actual de la transacción'
    )
    
    # ========================
    # DATOS TÉCNICOS
    # ========================
    
    response_data = fields.Json(
        string='Respuesta Cashdrop',
        readonly=True,
        help='Respuesta JSON completa de Cashdrop'
    )
    
    error_message = fields.Text(
        string='Mensaje de Error',
        readonly=True,
        help='Detalle del error si la transacción falló'
    )
    
    # ========================
    # AUDITORÍA
    # ========================
    
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        readonly=True,
        default=lambda self: self.env.user
    )
    
    pos_session_id = fields.Many2one(
        'pos.session',
        string='Sesión POS',
        readonly=True,
        ondelete='set null',
        help='Sesión de POS en la que se realizó la transacción'
    )
    
    confirmed_at = fields.Datetime(
        string='Confirmado en',
        readonly=True,
        help='Timestamp cuando se confirmó el pago'
    )
    
    cancelled_at = fields.Datetime(
        string='Cancelado en',
        readonly=True,
        help='Timestamp cuando se canceló el pago'
    )
    
    # ========================
    # SECUENCIAS
    # ========================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generar ID secuencial y transaction_id al crear"""
        for vals in vals_list:
            # Generar 'name' (referencia secuencial)
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'cashdro.transaction.sequence'
                ) or f"TXN-{datetime.now().timestamp()}"
            # Generar 'transaction_id' si no está proporcionado
            if not vals.get('transaction_id'):
                vals['transaction_id'] = self.env['ir.sequence'].next_by_code(
                    'cashdro.transaction.sequence'
                ) or f"TXN-{datetime.now().timestamp()}"
        return super().create(vals_list)
    
    # ========================
    # VALIDACIONES
    # ========================
    
    @api.constrains('order_id', 'pos_order_id')
    def _check_order_reference(self):
        """Al menos uno de order_id o pos_order_id debe estar definido"""
        for record in self:
            if not record.order_id and not record.pos_order_id:
                raise ValidationError(
                    _('Debe indicar orden de venta (order_id) u orden POS (pos_order_id)')
                )

    @api.constrains('amount')
    def _check_amount(self):
        """Validar que el monto sea positivo"""
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_('El monto debe ser mayor a 0'))
    
    @api.constrains('amount_received')
    def _check_amount_received(self):
        """Validar que el monto recibido sea válido"""
        for record in self:
            if record.amount_received < 0:
                raise ValidationError(_('El monto recibido no puede ser negativo'))
    
    # ========================
    # MÉTODOS DE TRANSICIÓN DE ESTADO
    # ========================
    
    def action_confirm(self):
        """Confirmar la transacción"""
        for record in self:
            if record.status not in ['processing', 'error']:
                raise UserError(
                    _('Solo se pueden confirmar transacciones en estado "Procesando" o "Error"')
                )
            record.write({
                'status': 'confirmed',
                'confirmed_at': datetime.now()
            })
            _logger.info(f"Transacción {record.name} confirmada")
    
    def action_cancel(self):
        """Cancelar la transacción"""
        for record in self:
            if record.status not in ['processing', 'error']:
                raise UserError(
                    _('Solo se pueden cancelar transacciones en estado "Procesando" o "Error"')
                )
            record.write({
                'status': 'cancelled',
                'cancelled_at': datetime.now()
            })
            _logger.info(f"Transacción {record.name} cancelada")
    
    def action_retry(self):
        """Reintentar una transacción fallida"""
        for record in self:
            if record.status not in ['error', 'timeout', 'cancelled']:
                raise UserError(
                    _('Solo se pueden reintentar transacciones fallidas o canceladas')
                )
            record.write({
                'status': 'processing',
                'error_message': False
            })
            _logger.info(f"Reintento de transacción {record.name}")
    
    # ========================
    # MÉTODOS DE BÚSQUEDA
    # ========================
    
    @api.model
    def get_by_operation_id(self, operation_id):
        """Buscar transacción por operation_id de Cashdrop"""
        return self.search([('operation_id', '=', operation_id)], limit=1)
    
    @api.model
    def get_by_transaction_id(self, transaction_id):
        """Buscar transacción por transaction_id"""
        return self.search([('transaction_id', '=', transaction_id)], limit=1)
    
    # ========================
    # MÉTODOS DE SINCRONIZACIÓN
    # ========================
    
    def update_from_gateway_response(self, response_data):
        """
        Actualizar transacción con datos del gateway
        
        Args:
            response_data (dict): Respuesta del gateway/Cashdrop
        """
        self.ensure_one()
        
        try:
            if isinstance(response_data, str):
                response_data = json.loads(response_data)
            
            values = {
                'response_data': response_data
            }
            
            # Extraer información según el formato de respuesta
            if 'operation_id' in response_data:
                values['operation_id'] = response_data['operation_id']
            
            if 'data' in response_data:
                # Si es string JSON, parsear
                data = response_data['data']
                if isinstance(data, str):
                    data = json.loads(data)
                
                # Extraer estado y monto
                if isinstance(data, dict) and 'operation' in data:
                    operation = data['operation']
                    if 'state' in operation:
                        state = operation['state']
                        # 'F' = finished
                        if state == 'F':
                            values['status'] = 'confirmed'
                            values['confirmed_at'] = datetime.now()
                        
                        # Extraer monto recibido (en centavos)
                        if 'totalin' in operation:
                            values['amount_received'] = operation['totalin'] / 100
            
            self.write(values)
            _logger.info(f"Transacción {self.name} actualizada con respuesta del gateway")
        
        except Exception as e:
            _logger.error(f"Error actualizando transacción: {e}")
            raise ValidationError(_('Error procesando respuesta del gateway: %s') % str(e))
    
    def mark_timeout(self):
        """Marcar transacción como timeout"""
        self.write({
            'status': 'timeout',
            'error_message': 'Timeout esperando respuesta de Cashdrop'
        })
        _logger.warning(f"Transacción {self.name} marcada como timeout")
    
    def mark_error(self, error_message):
        """Marcar transacción como error"""
        self.write({
            'status': 'error',
            'error_message': error_message
        })
        _logger.error(f"Transacción {self.name} marcada como error: {error_message}")
    
    # ========================
    # MÉTODOS AUXILIARES
    # ========================
    
    def get_display_name(self):
        """Retorna nombre para mostrar"""
        return f"{self.name} - {self.amount} {self.currency_id.name}"
    
    def is_confirmed(self):
        """¿Está confirmado el pago?"""
        return self.status == 'confirmed'
    
    def is_cancelled(self):
        """¿Está cancelado el pago?"""
        return self.status == 'cancelled'
    
    def is_processing(self):
        """¿Está procesándose el pago?"""
        return self.status == 'processing'
    
    def is_error(self):
        """¿Hay un error?"""
        return self.status in ['error', 'timeout']
