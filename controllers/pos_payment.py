# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

import json
import logging
from datetime import datetime
from odoo import http, _
from odoo.exceptions import UserError
from .payment_method_integration import PaymentMethodIntegration

_logger = logging.getLogger(__name__)


class CashdropPaymentController(http.Controller):
    """
    Controller REST para operaciones de pago Cashdrop
    
    Endpoints:
    - POST /cashdro/payment/start
    - POST /cashdro/payment/confirm
    - POST /cashdro/payment/cancel
    - GET  /cashdro/payment/status/<transaction_id>
    - POST /cashdro/payment/info
    """
    
    # ========================
    # ENDPOINT 1: INICIAR PAGO
    # ========================
    
    @http.route('/cashdro/payment/start', auth='public', type='http', methods=['POST'], csrf=False)
    def start_payment(self, **kwargs):
        """
        Endpoint para iniciar pago
        
        Request JSON:
        {
            "order_id": 123,
            "payment_method_id": 456,
            "amount": 99.99,
            "pos_session_id": 789 (optional),
            "user_credentials": {
                "user": "username",
                "password": "password"
            } (optional)
        }
        
        Response JSON:
        {
            "success": true,
            "operation_id": "12345",
            "transaction_id": "uuid",
            "message": "Pago iniciado, esperando inserción de dinero"
        }
        """
        try:
            try:
                data = json.loads(http.request.httprequest.data)
            except (json.JSONDecodeError, ValueError):
                return self._error_response('Request JSON inválido', 400)
            
            # Validar parámetros requeridos
            order_id = data.get('order_id')
            pos_order_id = data.get('pos_order_id')
            payment_method_id = data.get('payment_method_id')
            amount = data.get('amount')
            
            # Debe haber al menos una orden (sale.order o pos.order)
            if not (order_id or pos_order_id):
                return self._error_response(
                    'Parámetros faltantes: order_id o pos_order_id, payment_method_id, amount',
                    400
                )
            if not payment_method_id or not amount:
                return self._error_response(
                    'Parámetros faltantes: payment_method_id, amount',
                    400
                )
            
            # Validar monto
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                return self._error_response('Amount debe ser numérico', 400)
            
            # Inicializar integración
            integration = PaymentMethodIntegration(
                http.request.env,
                payment_method_id=payment_method_id
            )
            
            # Validar configuración
            validation = integration.validate_configuration()
            if not validation['valid']:
                msg = '; '.join(validation['errors'])
                return self._error_response(msg, 400)
            
            # Crear transacción
            transaction = integration.create_transaction(
                order_id=order_id,
                pos_order_id=pos_order_id,
                amount=amount,
                user_id=http.request.env.user.id,
                pos_session_id=data.get('pos_session_id')
            )
            
            # Iniciar pago
            result = integration.start_payment(
                transaction,
                user_credentials=data.get('user_credentials')
            )
            
            _logger.info(f"Payment started: operation_id={result['operation_id']}")
            return self._success_response(result)
        
        except UserError as e:
            _logger.warning(f"Payment start error: {e}")
            return self._error_response(str(e), 400)
        
        except Exception as e:
            _logger.error(f"Payment start exception: {e}", exc_info=True)
            return self._error_response(_('Error interno del servidor'), 500)
    
    # ========================
    # ENDPOINT 2: CONFIRMAR PAGO
    # ========================
    
    @http.route('/cashdro/payment/confirm', auth='public', type='http', methods=['POST'], csrf=False)
    def confirm_payment(self, **kwargs):
        """
        Endpoint para confirmar pago (polling + confirmación)
        
        Request JSON:
        {
            "transaction_id": "uuid" OR "operation_id": "12345",
            "payment_method_id": 456 (optional, para búsqueda)
        }
        
        Response JSON:
        {
            "success": true,
            "transaction_id": "uuid",
            "amount_received": 99.99,
            "message": "Pago confirmado"
        }
        """
        try:
            try:
                data = json.loads(http.request.httprequest.data)
            except (json.JSONDecodeError, ValueError):
                return self._error_response('Request JSON inválido', 400)
            
            # Buscar transacción
            transaction = self._get_transaction(data)
            if not transaction:
                return self._error_response('Transacción no encontrada', 404)
            
            # Inicializar integración
            integration = PaymentMethodIntegration(
                http.request.env,
                payment_method_id=transaction.payment_method_id.id
            )
            
            # Confirmar pago
            result = integration.confirm_payment(transaction)
            
            _logger.info(f"Payment confirmed: transaction_id={result['transaction_id']}")
            return self._success_response(result)
        
        except UserError as e:
            _logger.warning(f"Payment confirm error: {e}")
            return self._error_response(str(e), 400)
        
        except Exception as e:
            _logger.error(f"Payment confirm exception: {e}", exc_info=True)
            return self._error_response(_('Error interno del servidor'), 500)
    
    # ========================
    # ENDPOINT 3: CANCELAR PAGO
    # ========================
    
    @http.route('/cashdro/payment/cancel', auth='public', type='http', methods=['POST'], csrf=False)
    def cancel_payment(self, **kwargs):
        """
        Endpoint para cancelar pago
        
        Request JSON:
        {
            "transaction_id": "uuid" OR "operation_id": "12345",
            "payment_method_id": 456 (optional)
        }
        
        Response JSON:
        {
            "success": true,
            "transaction_id": "uuid",
            "message": "Pago cancelado"
        }
        """
        try:
            try:
                data = json.loads(http.request.httprequest.data)
            except (json.JSONDecodeError, ValueError):
                return self._error_response('Request JSON inválido', 400)
            
            # Buscar transacción
            transaction = self._get_transaction(data)
            if not transaction:
                return self._error_response('Transacción no encontrada', 404)
            
            # Inicializar integración
            integration = PaymentMethodIntegration(
                http.request.env,
                payment_method_id=transaction.payment_method_id.id
            )
            
            # Cancelar pago
            result = integration.cancel_payment(transaction)
            
            _logger.info(f"Payment cancelled: transaction_id={result['transaction_id']}")
            return self._success_response(result)
        
        except UserError as e:
            _logger.warning(f"Payment cancel error: {e}")
            return self._error_response(str(e), 400)
        
        except Exception as e:
            _logger.error(f"Payment cancel exception: {e}", exc_info=True)
            return self._error_response(_('Error interno del servidor'), 500)
    
    # ========================
    # ENDPOINT 4: OBTENER ESTADO
    # ========================
    
    @http.route('/cashdro/payment/status/<string:transaction_id>', 
                 auth='public', type='http', methods=['GET'])
    def get_payment_status(self, transaction_id, **kwargs):
        """
        Endpoint para obtener estado de pago
        
        URL: /cashdro/payment/status/{transaction_id}
        
        Response JSON:
        {
            "success": true,
            "status": "processing|confirmed|cancelled|error|timeout",
            "operation_id": "12345",
            "state": "P|F",
            "amount_received": 99.99,
            "message": "Estado obtenido"
        }
        """
        try:
            # Buscar transacción por transaction_id
            transaction_model = http.request.env['cashdro.transaction']
            transaction = transaction_model.get_by_transaction_id(transaction_id)
            
            if not transaction:
                return self._error_response('Transacción no encontrada', 404)
            
            # Inicializar integración
            integration = PaymentMethodIntegration(
                http.request.env,
                payment_method_id=transaction.payment_method_id.id
            )
            
            # Obtener estado
            result = integration.get_payment_status(transaction)
            
            return self._success_response(result)
        
        except UserError as e:
            _logger.warning(f"Get status error: {e}")
            return self._error_response(str(e), 400)
        
        except Exception as e:
            _logger.error(f"Get status exception: {e}", exc_info=True)
            return self._error_response(_('Error interno del servidor'), 500)
    
    # ========================
    # ENDPOINT 5: INFORMACIÓN DE PAGO
    # ========================
    
    @http.route('/cashdro/payment/info', auth='public', type='http', methods=['POST'], csrf=False)
    def get_payment_info(self, **kwargs):
        """
        Endpoint para obtener información general de un pago
        
        Request JSON:
        {
            "transaction_id": "uuid" OR "operation_id": "12345"
        }
        
        Response JSON:
        {
            "success": true,
            "transaction": {
                "id": "uuid",
                "operation_id": "12345",
                "order_id": 123,
                "amount": 99.99,
                "amount_received": 99.99,
                "status": "confirmed",
                "created_at": "2026-03-03T14:30:00",
                "confirmed_at": "2026-03-03T14:31:00",
                "error_message": null
            }
        }
        """
        try:
            try:
                data = json.loads(http.request.httprequest.data)
            except (json.JSONDecodeError, ValueError):
                return self._error_response('Request JSON inválido', 400)
            
            # Buscar transacción
            transaction = self._get_transaction(data)
            if not transaction:
                return self._error_response('Transacción no encontrada', 404)
            
            # Construir respuesta
            transaction_info = {
                'id': transaction.transaction_id,
                'operation_id': transaction.operation_id or None,
                'order_id': transaction.order_id.id,
                'amount': transaction.amount,
                'amount_received': transaction.amount_received,
                'status': transaction.status,
                'created_at': transaction.create_date.isoformat() if transaction.create_date else None,
                'confirmed_at': transaction.confirmed_at.isoformat() if transaction.confirmed_at else None,
                'cancelled_at': transaction.cancelled_at.isoformat() if transaction.cancelled_at else None,
                'error_message': transaction.error_message or None,
                'user': transaction.user_id.name,
                'pos_session': transaction.pos_session_id.name if transaction.pos_session_id else None,
            }
            
            return self._success_response({
                'success': True,
                'transaction': transaction_info
            })
        
        except UserError as e:
            _logger.warning(f"Get info error: {e}")
            return self._error_response(str(e), 400)
        
        except Exception as e:
            _logger.error(f"Get info exception: {e}", exc_info=True)
            return self._error_response(_('Error interno del servidor'), 500)
    
    # ========================
    # UTILIDADES
    # ========================
    
    def _get_transaction(self, data):
        """
        Obtener transacción desde transaction_id u operation_id
        
        Args:
            data (dict): Request data
            
        Returns:
            cashdro.transaction o None
        """
        transaction_model = http.request.env['cashdro.transaction']
        
        transaction_id = data.get('transaction_id')
        operation_id = data.get('operation_id')
        
        if transaction_id:
            return transaction_model.get_by_transaction_id(transaction_id)
        elif operation_id:
            return transaction_model.get_by_operation_id(operation_id)
        
        return None
    
    def _success_response(self, data):
        """
        Construir respuesta exitosa
        
        Args:
            data (dict): Datos de respuesta
            
        Returns:
            http.Response: JSON response con success=True
        """
        response = {'success': True}
        response.update(data)
        return http.Response(
            json.dumps(response),
            status=200,
            mimetype='application/json'
        )
    
    def _error_response(self, message, status_code=400):
        """
        Construir respuesta de error

        Args:
            message (str): Mensaje de error
            status_code (int): Código HTTP

        Returns:
            http.Response: JSON response con success=False
        """
        response = {
            'success': False,
            'error': str(message),
            'timestamp': datetime.now().isoformat()
        }
        return http.Response(
            json.dumps(response),
            status=status_code,
            mimetype='application/json'
        )

    # ========================
    # ENDPOINT: CONFIRMAR PAGO EN KIOSK
    # ========================

    @http.route('/cashdro/payment/kiosk/confirm', auth='public', type='http', methods=['POST'], csrf=False)
    def kiosk_payment_confirm(self, **kwargs):
        """
        Confirmar pago en kiosk después de que Cashdrop procesa.
        El frontend llama aquí cuando el cliente toca "Confirmar pago";
        se confirma la transacción y se tramita la orden (action_pos_order_paid).

        Request JSON: {"transaction_id": "uuid", "order_id": 123}
        Response: {"success": true, "message": "...", "order_id": 123}
        """
        try:
            try:
                data = json.loads(http.request.httprequest.data)
            except (json.JSONDecodeError, ValueError):
                return self._error_response('Request JSON inválido', 400)
            transaction_id = data.get('transaction_id')
            order_id = data.get('order_id')

            if not transaction_id or not order_id:
                return self._error_response(
                    'Parámetros faltantes: transaction_id, order_id', 400
                )

            transaction_model = http.request.env['cashdro.transaction']
            transaction = transaction_model.get_by_transaction_id(transaction_id)
            if not transaction:
                return self._error_response('Transacción no encontrada', 404)

            integration = PaymentMethodIntegration(
                http.request.env,
                payment_method_id=transaction.payment_method_id.id
            )

            try:
                result = integration.confirm_payment(transaction)
            except UserError as e:
                return self._error_response(str(e), 400)

            if not result.get('success'):
                return self._error_response(
                    result.get('error', 'Error al confirmar pago en Cashdrop'),
                    400
                )

            order = http.request.env['pos.order'].browse(order_id)
            if not order.exists():
                return self._error_response('Orden no encontrada', 404)

            order.action_pos_order_paid()
            _logger.info(
                "Kiosk payment confirmed and order sent to kitchen: order_id=%s",
                order_id
            )
            return self._success_response({
                'message': 'Pago confirmado, orden enviada a cocina',
                'order_id': order.id
            })

        except Exception as e:
            _logger.error("Kiosk payment confirm error: %s", e, exc_info=True)
            return self._error_response(str(e), 500)
