# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

import json
import logging
from datetime import datetime
from odoo import http, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero
from .payment_method_integration import PaymentMethodIntegration
from ..gateway_integration import CashdropGatewayIntegration

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
            
            # Buscar transacción (usar sudo para evitar restricciones de permiso)
            transaction_model = http.request.env['cashdro.transaction'].sudo()
            transaction_id = data.get('transaction_id')
            operation_id = data.get('operation_id')
            if transaction_id:
                transaction = transaction_model.search([('transaction_id', '=', transaction_id)], limit=1)
            elif operation_id:
                transaction = transaction_model.search([('operation_id', '=', operation_id)], limit=1)
            else:
                transaction = None
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
    
    @http.route('/cashdro/payment/cancel', auth='public', type='jsonrpc', csrf=False)
    def cancel_payment(self, transaction_id=None, operation_id=None, **kwargs):
        """
        Cancelar pago (type='jsonrpc' para rpc() desde el frontend del kiosk).
        """
        data = {'transaction_id': transaction_id or kwargs.get('transaction_id'), 'operation_id': operation_id or kwargs.get('operation_id')}
        transaction = self._get_transaction(data)
        if not transaction:
            return {'success': False, 'error': 'Transacción no encontrada'}
        try:
            integration = PaymentMethodIntegration(
                http.request.env,
                payment_method_id=transaction.payment_method_id.id
            )
            result = integration.cancel_payment(transaction)
            _logger.info("Payment cancelled: transaction_id=%s", result.get('transaction_id'))
            return {'success': True, 'transaction_id': result.get('transaction_id'), 'message': result.get('message')}
        except UserError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            _logger.exception("Payment cancel exception")
            return {'success': False, 'error': str(e)}
    
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
    # CAJA REGISTRADORA (POS): rutas JSON para el frontend PaymentScreen
    # ========================

    @http.route('/cashdro/payment/pos/summary', type='jsonrpc', auth='user')
    def pos_payment_summary(self, payment_method_id=None):
        """Resumen de la máquina para el diálogo de confirmación antes de cobrar."""
        try:
            if not payment_method_id:
                return {'success': False, 'error': _('Falta payment_method_id')}
            env = http.request.env
            pm = env['pos.payment.method'].sudo().browse(int(payment_method_id))
            if not pm.exists():
                return {'success': False, 'error': _('Método de pago no encontrado')}
            if not getattr(pm, 'cashdro_enabled', False):
                return {'success': False, 'error': _('Método de pago no es CashDro')}
            return {
                'success': True,
                'connection_status': getattr(pm, 'cashdro_connection_status', 'not_tested'),
                'error_message': getattr(pm, 'cashdro_error_message', None) or '',
                'pieces_info': {},
                'deposit_levels_json': getattr(pm, 'cashdro_deposit_levels_json', None) or '',
            }
        except Exception as e:
            _logger.exception("POS CashDro summary error")
            return {'success': False, 'error': str(e)}

    def _safe_int_id(self, value):
        """Convierte a int solo si es numérico. Evita int(UUID) cuando el front envía order.id/session.id como UUID."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        s = str(value).strip()
        if not s or "-" in s or not s.isdigit():
            return None
        try:
            return int(s)
        except (ValueError, TypeError):
            return None

    # ========================
    # CAJA REGISTRADORA (POS): COBRO (flujo estándar, SIN CAMBIOS)
    # ========================
    @http.route('/cashdro/payment/pos/start', type='jsonrpc', auth='user')
    def pos_payment_start(self, payment_method_id=None, amount=None, pos_session_id=None, pos_order_id=None, **kwargs):
        """Iniciar pago en CashDro desde la caja. Devuelve transaction_id para polling."""
        if not payment_method_id or amount is None:
            return {'success': False, 'error': _('Faltan payment_method_id o amount')}
        amount_val = float(amount)
        if amount_val <= 0:
            return {'success': False, 'error': _('El importe debe ser mayor que cero')}
        env = http.request.env
        pm = env['pos.payment.method'].sudo().browse(int(payment_method_id))
        if not pm.exists() or not getattr(pm, 'cashdro_enabled', False):
            return {'success': False, 'error': _('Método de pago no es CashDro')}
        try:
            _logger.info(
                "POS CashDro PAYMENT START /pos/start: method_id=%s amount=%s pos_session_id=%s pos_order_id=%s",
                pm.id,
                amount_val,
                pos_session_id,
                pos_order_id,
            )
            integration = PaymentMethodIntegration(env, payment_method_id=pm.id)
            validation = integration.validate_configuration()
            if not validation['valid']:
                return {'success': False, 'error': '; '.join(validation['errors'])}
            transaction = integration.create_transaction(
                amount=amount_val,
                user_id=env.user.id,
                pos_session_id=self._safe_int_id(pos_session_id),
                pos_order_id=self._safe_int_id(pos_order_id),
            )
            result = integration.start_payment(transaction, user_credentials=None)
            if not result.get('success'):
                return {'success': False, 'error': result.get('error', _('Error al iniciar pago'))}
            return {
                'success': True,
                'transaction_id': transaction.transaction_id,
                'operation_id': result.get('operation_id'),
            }
        except UserError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            _logger.exception("POS CashDro start error")
            return {'success': False, 'error': str(e)}

    @http.route('/cashdro/payment/pos/status', type='jsonrpc', auth='user')
    def pos_payment_status(self, transaction_id=None, **kwargs):
        """Estado del pago (polling). Devuelve status: pending|confirmed|cancelled|error|timeout."""
        if not transaction_id:
            return {'success': False, 'error': _('Falta transaction_id')}
        env = http.request.env
        tx = env['cashdro.transaction'].sudo().search([('transaction_id', '=', transaction_id)], limit=1)
        if not tx:
            return {'success': False, 'error': _('Transacción no encontrada')}
        try:
            integration = PaymentMethodIntegration(env, payment_method_id=tx.payment_method_id.id)
            info = integration.get_payment_status(tx)
            state = (info.get('state') or '').upper()
            # Gateway puede devolver:
            # - 'E' (Ended / Finalizada) o 'F' / 'FINISHED' / 'COMPLETED' para operación terminada correctamente
            # - 'C' (Cancelled) o 'CANCELLED' / 'ABORTED' / 'ERROR' para cancelación o fallo
            if state in ('E', 'F', 'FINISHED', 'COMPLETED') or tx.is_confirmed():
                return {'success': True, 'status': 'confirmed', 'message': _('Pago confirmado')}
            if state in ('C', 'CANCELLED', 'ABORTED', 'ERROR'):
                return {'success': True, 'status': 'cancelled', 'message': info.get('message', _('Operación cancelada'))}
            return {'success': True, 'status': 'processing', 'message': _('Esperando pago...')}
        except Exception as e:
            _logger.warning("POS status %s: %s", transaction_id, e)
            return {'success': True, 'status': 'processing', 'message': str(e)}

    @http.route('/cashdro/payment/pos/confirm', type='jsonrpc', auth='user')
    def pos_payment_confirm(self, transaction_id=None, **kwargs):
        """Confirmar pago en servidor y devolver amount_received."""
        if not transaction_id:
            return {'success': False, 'error': _('Falta transaction_id')}
        env = http.request.env
        tx = env['cashdro.transaction'].sudo().search([('transaction_id', '=', transaction_id)], limit=1)
        if not tx:
            return {'success': False, 'error': _('Transacción no encontrada')}
        try:
            integration = PaymentMethodIntegration(env, payment_method_id=tx.payment_method_id.id)
            result = integration.confirm_payment(tx)
            if not result.get('success'):
                return {'success': False, 'error': result.get('error', _('Error al confirmar'))}
            return {
                'success': True,
                'amount_received': result.get('amount_received', 0),
            }
        except UserError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            _logger.exception("POS CashDro confirm error")
            return {'success': False, 'error': str(e)}

    # ========================
    # CAJA REGISTRADORA (POS): REEMBOLSO SIMPLE (PAGO AL CLIENTE)
    # ========================

    @http.route('/cashdro/payment/pos_refund/start', type='jsonrpc', auth='user')
    def pos_refund_start(self, payment_method_id=None, amount=None, **kwargs):
        """
        Iniciar un reembolso en CashDro desde la caja.
        No crea cashdro.transaction ni hace polling: replica el flujo del wizard
        CashdroMovimientoDevolucionWizard usando startOperation type=3.
        """
        if not payment_method_id or amount is None:
            return {'success': False, 'error': _('Faltan payment_method_id o amount')}
        try:
            amount_val = float(amount)
        except (TypeError, ValueError):
            return {'success': False, 'error': _('El importe debe ser numérico')}
        if amount_val <= 0:
            return {'success': False, 'error': _('El importe debe ser mayor que cero')}

        env = http.request.env
        pm = env['pos.payment.method'].sudo().browse(int(payment_method_id))
        if not pm.exists() or not getattr(pm, 'cashdro_enabled', False):
            return {'success': False, 'error': _('Método de pago no es CashDro')}

        # Construir gateway igual que en cashdro_movimiento_wizards._get_gateway_from_method
        try:
            _logger.info(
                "POS CashDro REFUND START /pos_refund/start: method_id=%s amount=%s",
                pm.id,
                amount_val,
            )
            config = env['res.config.settings'].sudo().get_cashdro_config()
            url = pm.get_gateway_url()
            gateway = CashdropGatewayIntegration(
                gateway_url=url,
                timeout=config.get('connection_timeout', 10),
                verify_ssl=config.get('verify_ssl', False),
                log_level=config.get('log_level', 'INFO'),
                user=pm.cashdro_user,
                password=pm.cashdro_password,
            )
            # type=3 = DEVOLUCIÓN/DISPENSA (payOutProgress). La máquina dispensará el importe.
            res = gateway.start_operation(amount_val, operation_type=3)
            _logger.info(
                "POS CashDro REFUND START OK: operation_id=%s response_code=%s",
                res.get('operation_id'),
                res.get('code'),
            )
            return {
                'success': True,
                'operation_id': res.get('operation_id'),
                'message': _('Reembolso iniciado. La máquina dispensará el importe.'),
            }
        except UserError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            _logger.exception("POS CashDro refund start error")
            return {'success': False, 'error': str(e)}

    # ========================
    # KIOSK: INICIAR PAGO CASHDRO (fallback cuando el backend no devuelve payment_status)
    # ========================

    @http.route('/cashdro/payment/kiosk/start', auth='public', type='jsonrpc', csrf=False)
    def kiosk_payment_start(self, order_id=None, payment_method_id=None, amount=None, **kwargs):
        """
        Iniciar pago CashDro desde el kiosk cuando el flujo estándar no devuelve payment_status.
        Crea la transacción, inicia el pago en la máquina y devuelve payment_status para mostrar el diálogo.
        """
        order_id = order_id or kwargs.get('order_id')
        payment_method_id = payment_method_id or kwargs.get('payment_method_id')
        amount = amount or kwargs.get('amount')
        if not order_id or not payment_method_id:
            return {'success': False, 'error': 'Faltan order_id o payment_method_id'}
        _logger.info(
            "Kiosk CashDro start request: order_id=%s payment_method_id=%s amount=%s",
            order_id,
            payment_method_id,
            amount,
        )
        env = http.request.env
        order = env['pos.order'].sudo().browse(int(order_id))
        if not order.exists():
            return {'success': False, 'error': 'Orden no encontrada'}
        pm = env['pos.payment.method'].sudo().browse(int(payment_method_id))
        if not pm.exists() or not getattr(pm, 'cashdro_enabled', False):
            return {'success': False, 'error': 'Método de pago no es CashDro'}
        amount_val = float(amount) if amount is not None else order.amount_total
        if amount_val <= 0:
            return {'success': False, 'error': 'Importe no válido'}
        try:
            integration = PaymentMethodIntegration(
                env,
                payment_method_id=pm.id
            )
            validation = integration.validate_configuration()
            if not validation['valid']:
                return {'success': False, 'error': '; '.join(validation['errors'])}
            transaction = integration.create_transaction(
                pos_order_id=order.id,
                amount=amount_val,
                user_id=env.user.id,
                pos_session_id=order.session_id.id if order.session_id else None,
            )
            result = integration.start_payment(transaction, user_credentials=None)
            if not result.get('success'):
                return {'success': False, 'error': result.get('error', 'Error al iniciar pago')}
            return {
                'success': True,
                'payment_status': {
                    'status': 'pending',
                    'is_cashdrop': True,
                    'transaction_id': transaction.transaction_id,
                    'operation_id': result.get('operation_id'),
                    'message': _('Esperando confirmación de pago en Cashdrop...'),
                },
                'order': {'id': order.id},
            }
        except UserError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            _logger.exception("Kiosk payment start error")
            return {'success': False, 'error': str(e)}

    # ========================
    # ENDPOINT: CONFIRMAR PAGO EN KIOSK (type='jsonrpc' para rpc() del frontend)
    # ========================

    @http.route('/cashdro/payment/kiosk/confirm', auth='public', type='jsonrpc', csrf=False)
    def kiosk_payment_confirm_json(self, transaction_id=None, order_id=None, **kwargs):
        """
        Confirmar pago en kiosk (llamado por rpc() desde el frontend).
        Se confirma la transacción y se tramita la orden (action_pos_order_paid).
        """
        transaction_id = transaction_id or kwargs.get('transaction_id')
        order_id = order_id or kwargs.get('order_id')
        if not transaction_id or not order_id:
            return {'success': False, 'error': 'Parámetros faltantes: transaction_id, order_id'}
        _logger.info(
            "Kiosk CashDro confirm request: transaction_id=%s order_id=%s",
            transaction_id,
            order_id,
        )

        transaction_model = http.request.env['cashdro.transaction'].sudo()
        transaction = transaction_model.search([('transaction_id', '=', transaction_id)], limit=1)
        if not transaction:
            return {'success': False, 'error': 'Transacción no encontrada'}

        integration = PaymentMethodIntegration(
            http.request.env,
            payment_method_id=transaction.payment_method_id.id
        )
        try:
            result = integration.confirm_payment(transaction)
        except UserError as e:
            return {'success': False, 'error': str(e)}
        if not result.get('success'):
            return {'success': False, 'error': result.get('error', 'Error al confirmar pago en Cashdrop')}

        order = http.request.env['pos.order'].sudo().browse(int(order_id))
        if not order.exists():
            return {'success': False, 'error': 'Orden no encontrada'}

        # Registrar el pago en la orden; sin esto action_pos_order_paid() lanza "no se pagó por completo"
        if not float_is_zero(order.amount_total - order.amount_paid, precision_rounding=order.currency_id.rounding):
            order.add_payment({
                'amount': order.amount_total,
                'payment_method_id': transaction.payment_method_id.id,
                'pos_order_id': order.id,
            })
        order.action_pos_order_paid()
        # Mismo efecto que tras pago Stripe/Adyen vía _send_payment_result (sin PAYMENT_STATUS):
        # email de recibo si aplica, pantallas de preparación / hooks _send_order.
        order._send_self_order_receipt()
        order._send_order()
        cfg = order.config_id
        order_sync = {
            'pos.order': order.read(order._load_pos_self_data_fields(cfg), load=False),
            'pos.order.line': order.lines.read(
                order.lines._load_pos_self_data_fields(cfg), load=False
            ),
        }
        _logger.info(
            "Kiosk CashDro paid: order_id=%s order.amount_total=%s order.amount_paid=%s order_sync_lines=%s",
            order.id,
            order.amount_total,
            order.amount_paid,
            len(order_sync['pos.order.line']),
        )
        return {
            'success': True,
            'message': _('Pago confirmado, orden enviada a cocina'),
            'order_id': order.id,
            'order_sync': order_sync,
        }

