#!/usr/bin/env python3
"""
Descubridor mejorado de operación de pago
Prueba con variaciones de parámetros y formatos
"""

import requests
import json
from itertools import product
import time
from CashdropAPI_v2 import CashdropAPI

# Configuración
BASE_URL = 'https://10.0.1.140'
USERNAME = 'admin'
PASSWORD = '3428'

# Variaciones de nombres de operación
OPERATION_VARIANTS = [
    # Variantes de pago
    'pay', 'payment', 'processPayment', 'process_payment',
    'makePayment', 'make_payment', 'acceptPayment', 'accept_payment',
    'authorizePayment', 'authorize_payment', 'chargePayment', 'charge_payment',
    
    # Variantes de transacción
    'transaction', 'processTransaction', 'process_transaction',
    'authorizeTransaction', 'authorize_transaction',
    
    # Variantes con cash
    'cashPayment', 'cash_payment', 'cashTransaction', 'cash_transaction',
    'cashOut', 'cash_out', 'cashIn', 'cash_in',
    
    # Variantes simples
    'transfer', 'exchange', 'deposit', 'withdraw',
]

# Variaciones de parámetros para el amount
AMOUNT_VARIANTS = [
    ('amount', 100),           # 100 EUR
    ('amount', 10000),         # 100.00 en centavos
    ('amount', '100.00'),      # String
    ('amount_cents', 10000),   # Parámetro alternativo
    ('value', 100),
    ('sum', 100),
    ('total', 100),
]

# Variaciones de parámetros para moneda
CURRENCY_VARIANTS = [
    ('currency', 'EUR'),
    ('currency_code', 'EUR'),
    ('currencyCode', 'EUR'),
    ('currency_id', '1'),      # Podría ser ID numérico
]

def test_operation(session, auth_params, operation_name, extra_params=None):
    """
    Prueba una operación específica
    """
    params = auth_params.copy()
    params['operation'] = operation_name
    
    if extra_params:
        params.update(extra_params)
    
    try:
        # Intentar POST primero (más probable para pagos)
        response = session.post(
            f'{BASE_URL}/Cashdro3WS/index.php',
            params=params,
            timeout=5,
            verify=False
        )
        
        data = response.json()
        code = data.get('code')
        
        return {
            'operation': operation_name,
            'params': extra_params or {},
            'code': code,
            'success': code == 1,
            'response': data
        }
    except Exception as e:
        return {
            'operation': operation_name,
            'params': extra_params or {},
            'error': str(e)
        }

def discover_payment_operation():
    """
    Descubre la operación de pago probando variaciones
    """
    print("\n" + "="*70)
    print("DESCUBRIDOR DE OPERACIÓN DE PAGO - CASHDROP")
    print("="*70)
    
    # Crear sesión con certificado deshabilitado
    session = requests.Session()
    requests.packages.urllib3.disable_warnings()
    
    # Obtener cookies de autenticación
    print("\n[1/3] Autenticando...")
    auth_client = CashdropAPI(BASE_URL, USERNAME, PASSWORD, verify_ssl=False)
    auth_client.login()
    print("✅ Autenticado")
    
    auth_params = {
        'name': USERNAME,
        'password': PASSWORD
    }
    
    # Estrategia 1: Probar sin parámetros adicionales
    print("\n[2/3] Probando operaciones SIN parámetros adicionales...")
    print("-" * 70)
    
    successful_ops = []
    tested = 0
    
    for operation in OPERATION_VARIANTS:
        result = test_operation(session, auth_params, operation)
        tested += 1
        
        if result.get('success'):
            successful_ops.append(result)
            print(f"✅ {operation:30} → code={result['code']}")
        elif 'error' not in result:
            print(f"❌ {operation:30} → code={result.get('code')}")
        
        time.sleep(0.1)  # Pequeño delay para no sobrecargar
    
    print(f"\n✓ Probadas {tested} operaciones")
    print(f"✓ Operaciones exitosas: {len(successful_ops)}")
    
    # Estrategia 2: Probar CON parámetros de amount
    if not successful_ops:
        print("\n[3/3] Probando operaciones CON parámetros...")
        print("-" * 70)
        
        # Seleccionar operaciones más probables
        probable_ops = [
            'pay', 'payment', 'processPayment', 'makePayment',
            'transaction', 'cashPayment', 'chargePayment'
        ]
        
        test_count = 0
        for operation in probable_ops:
            # Probar con diferentes formatos de amount
            for amount_param, amount_val in AMOUNT_VARIANTS[:3]:  # Limitar a 3 variantes
                extra = {amount_param: amount_val, 'currency': 'EUR'}
                result = test_operation(session, auth_params, operation, extra)
                test_count += 1
                
                if result.get('success'):
                    successful_ops.append(result)
                    print(f"✅ {operation:25} + {amount_param}={amount_val} → ÉXITO")
                elif result.get('code') == 1:
                    print(f"✅ {operation:25} + {amount_param}={amount_val} → code=1")
                
                time.sleep(0.05)
        
        print(f"\n✓ Probadas {test_count} combinaciones adicionales")
    
    # Mostrar resultados
    print("\n" + "="*70)
    print("RESULTADOS")
    print("="*70)
    
    if successful_ops:
        print(f"\n✅ ENCONTRADAS {len(successful_ops)} OPERACIONES EXITOSAS:\n")
        for i, op in enumerate(successful_ops, 1):
            print(f"{i}. Operación: {op['operation']}")
            if op.get('params'):
                print(f"   Parámetros: {op['params']}")
            print(f"   Respuesta: {op['response']}\n")
    else:
        print("\n❌ No se encontraron operaciones de pago exitosas")
        print("\nPruebas recomendadas adicionales:")
        print("1. Inspeccionar tráfico del navegador en la interfaz web de Cashdrop")
        print("2. Buscar operaciones con parámetros en el body (JSON) en lugar de query string")
        print("3. Revisar si hay versiones de API diferentes (/Cashdro2WS, /Cashdro4WS, etc.)")
        print("4. Contactar al fabricante para documentación de API de pagos")
    
    return successful_ops

if __name__ == '__main__':
    successful = discover_payment_operation()
    
    if successful:
        print("\n" + "="*70)
        print("PRÓXIMOS PASOS:")
        print("="*70)
        print("1. Actualizar CashdropAPI_v2.py con la operación encontrada")
        print("2. Testar la operación con cantidad variable")
        print("3. Implementar en el gateway Flask")
        print("="*70)
