#!/usr/bin/env python3
"""
Cashdrop Gateway
Servidor Flask que actúa como intermediario entre Odoo POS y Cashdrop
"""

from flask import Flask, request, jsonify
import json
import logging
from datetime import datetime
import uuid

# Importar cliente Cashdrop
from CashdropAPI_v2 import CashdropAPI, CashdropAuthError, CashdropAPIError

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración por defecto
CASHDROP_CONFIG = {
    'base_url': 'https://10.0.1.140',
    'username': 'admin',
    'password': '3428'
}

# Cliente Cashdrop (inicializado on-demand)
cashdrop_client = None

def get_cashdrop_client():
    """Obtiene o crea cliente Cashdrop"""
    global cashdrop_client
    if cashdrop_client is None:
        cashdrop_client = CashdropAPI(
            base_url=CASHDROP_CONFIG['base_url'],
            username=CASHDROP_CONFIG['username'],
            password=CASHDROP_CONFIG['password'],
            verify_ssl=False
        )
        cashdrop_client.login()
    return cashdrop_client

# ========================
# RUTAS - Health Check
# ========================

@app.route('/health', methods=['GET'])
def health():
    """Verifica estado del gateway"""
    try:
        client = get_cashdrop_client()
        return jsonify({
            'status': 'ok',
            'authenticated': client.is_authenticated(),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ========================
# RUTAS - Información
# ========================

@app.route('/pieces/<currency>', methods=['GET'])
def get_pieces(currency):
    """Obtiene piezas (monedas/billetes) para una divisa"""
    try:
        client = get_cashdrop_client()
        pieces = client.get_pieces_currency(currency)
        
        return jsonify({
            'status': 'success',
            'currency': currency,
            'pieces': pieces,
            'count': len(pieces) if isinstance(pieces, list) else 1
        })
    except CashdropAPIError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error getting pieces: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/status', methods=['GET'])
def get_status():
    """Obtiene estado general de la máquina"""
    try:
        client = get_cashdrop_client()
        user = client.get_user()
        
        return jsonify({
            'status': 'success',
            'user': user,
            'gateway_status': 'online',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ========================
# RUTAS - Pagos (MOCK por ahora)
# ========================

# Almacenar transacciones en memoria (para desarrollo)
payment_transactions = {}

@app.route('/pay', methods=['POST'])
def process_payment():
    """
    Procesa un pago
    
    Body esperado:
    {
        "amount": 10.50,
        "currency": "EUR",
        "reference": "ORDER-123"  # ID único del pedido en Odoo
    }
    """
    data = request.get_json()
    
    # Validación
    if not data or 'amount' not in data or 'currency' not in data:
        return jsonify({
            'status': 'error',
            'message': 'Missing required fields: amount, currency'
        }), 400
    
    try:
        amount = float(data['amount'])
        currency = data['currency']
        reference = data.get('reference', str(uuid.uuid4()))
        
        if amount <= 0:
            return jsonify({
                'status': 'error',
                'message': 'Amount must be greater than 0'
            }), 400
        
        # Crear transacción
        transaction_id = str(uuid.uuid4())
        transaction = {
            'transaction_id': transaction_id,
            'amount': amount,
            'currency': currency,
            'reference': reference,
            'status': 'processing',
            'created_at': datetime.utcnow().isoformat(),
            'message': f'Payment of {amount} {currency} initiated'
        }
        
        # Guardar en memoria
        payment_transactions[transaction_id] = transaction
        logger.info(f"Payment initiated: {transaction_id} - {amount} {currency}")
        
        return jsonify(transaction), 202  # 202 Accepted (asíncrono)
    
    except ValueError:
        return jsonify({
            'status': 'error',
            'message': 'Invalid amount format'
        }), 400
    except Exception as e:
        logger.error(f"Error processing payment: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/payment/<transaction_id>/status', methods=['GET'])
def get_payment_status(transaction_id):
    """Obtiene estado de un pago"""
    if transaction_id not in payment_transactions:
        return jsonify({
            'status': 'error',
            'message': 'Transaction not found'
        }), 404
    
    transaction = payment_transactions[transaction_id]
    return jsonify(transaction)

@app.route('/payment/<transaction_id>/confirm', methods=['POST'])
def confirm_payment(transaction_id):
    """Confirma un pago (simulado)"""
    if transaction_id not in payment_transactions:
        return jsonify({
            'status': 'error',
            'message': 'Transaction not found'
        }), 404
    
    transaction = payment_transactions[transaction_id]
    transaction['status'] = 'confirmed'
    transaction['confirmed_at'] = datetime.utcnow().isoformat()
    
    logger.info(f"Payment confirmed: {transaction_id}")
    return jsonify(transaction)

@app.route('/payment/<transaction_id>/cancel', methods=['POST'])
def cancel_payment(transaction_id):
    """Cancela un pago"""
    if transaction_id not in payment_transactions:
        return jsonify({
            'status': 'error',
            'message': 'Transaction not found'
        }), 404
    
    transaction = payment_transactions[transaction_id]
    if transaction['status'] == 'confirmed':
        return jsonify({
            'status': 'error',
            'message': 'Cannot cancel confirmed payment'
        }), 400
    
    transaction['status'] = 'cancelled'
    transaction['cancelled_at'] = datetime.utcnow().isoformat()
    
    logger.info(f"Payment cancelled: {transaction_id}")
    return jsonify(transaction)

# ========================
# RUTAS - Cash In/Out (MOCK)
# ========================

@app.route('/cash-in', methods=['POST'])
def cash_in():
    """Ingresa efectivo en la máquina (simulado)"""
    data = request.get_json()
    
    if not data or 'amount' not in data:
        return jsonify({
            'status': 'error',
            'message': 'Missing amount'
        }), 400
    
    try:
        amount = float(data['amount'])
        operation_id = str(uuid.uuid4())
        
        return jsonify({
            'status': 'success',
            'operation_id': operation_id,
            'operation_type': 'cash_in',
            'amount': amount,
            'currency': data.get('currency', 'EUR'),
            'timestamp': datetime.utcnow().isoformat(),
            'message': f'Cash in of {amount} initiated'
        }), 202
    except Exception as e:
        logger.error(f"Error in cash in: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/cash-out', methods=['POST'])
def cash_out():
    """Retira efectivo de la máquina (simulado)"""
    data = request.get_json()
    
    if not data or 'amount' not in data:
        return jsonify({
            'status': 'error',
            'message': 'Missing amount'
        }), 400
    
    try:
        amount = float(data['amount'])
        operation_id = str(uuid.uuid4())
        
        return jsonify({
            'status': 'success',
            'operation_id': operation_id,
            'operation_type': 'cash_out',
            'amount': amount,
            'currency': data.get('currency', 'EUR'),
            'timestamp': datetime.utcnow().isoformat(),
            'message': f'Cash out of {amount} initiated'
        }), 202
    except Exception as e:
        logger.error(f"Error in cash out: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ========================
# Main
# ========================

if __name__ == '__main__':
    print("🚀 Iniciando Cashdrop Gateway")
    print("="*60)
    print(f"URL: http://localhost:5000")
    print(f"Cashdrop API: {CASHDROP_CONFIG['base_url']}")
    print("="*60 + "\n")
    
    # Inicializar cliente
    try:
        client = get_cashdrop_client()
        print("✅ Conectado a Cashdrop")
    except Exception as e:
        print(f"⚠️  Error conectando a Cashdrop: {e}")
    
    # Iniciar servidor
    app.run(host='0.0.0.0', port=5000, debug=True)
