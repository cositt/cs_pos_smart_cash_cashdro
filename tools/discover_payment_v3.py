#!/usr/bin/env python3
"""
Cashdrop Payment Discovery v3
Basado en investigacion_GPT.txt + operaciones reales encontradas
Prueba con múltiples endpoints, formatos de parámetros y operaciones conocidas
"""

import requests
import json
import time
from CashdropAPI_v2 import CashdropAPI

# Configuración
BASE_URL_ROOT = '10.0.1.140'
USERNAME = 'admin'
PASSWORD = '3428'

# Variaciones de endpoints según versión de Cashdrop
ENDPOINTS = [
    f'https://{BASE_URL_ROOT}/Cashdro3WS/index.php',      # Actual (encontrado)
    f'https://{BASE_URL_ROOT}/Cashdro3WS/index3.php',     # v3 (según GPT)
    f'https://{BASE_URL_ROOT}/Cashdro3WS/index2.php',     # v2
    f'https://{BASE_URL_ROOT}/Cashdro2WS/index.php',      # v2 alternativo
]

# OPERACIONES DE PAGO - Según investigacion_GPT.txt
PAYMENT_OPERATIONS = {
    'startOperation': {
        'description': 'Inicia transacción de venta/cobro',
        'params': [
            {
                'type': 3,           # 3 = pago simple
                'posid': 'POS001',
                'parameters': json.dumps({'amount': 100}),
                'startnow': 'true'
            },
            {
                'type': 4,           # 4 = venta completa
                'posid': 'POS001',
                'amount': '100',
                'startnow': 'true'
            },
            {
                'type': 3,
                'posid': '1',
                'amount': '100'
            },
        ]
    },
    'acknowledgeOperationId': {
        'description': 'Confirma recepción de operationId',
        'params': [
            {'operationId': 'test-operation-id'},
            {'operationId': '0'},
        ]
    },
    'askOperation': {
        'description': 'Consulta estado de operación',
        'params': [
            {'operationId': 'test-operation-id'},
            {'operationId': '0'},
        ]
    },
    'finishOperation': {
        'description': 'Finaliza o cancela operación',
        'params': [
            {'type': 1, 'operationId': 'test-op-id'},    # 1 = finalizar
            {'type': 2, 'operationId': 'test-op-id'},    # 2 = cancelar
        ]
    },
    'setoperationImported': {
        'description': 'Marca operación como importada',
        'params': [
            {'operationId': 'test-op-id'},
        ]
    },
    'askPendingOperations': {
        'description': 'Lista de operaciones abiertas',
        'params': [
            {'terminal': 'POS001'},
            {'posid': 'POS001'},
            {'importManualOperations': 'true'},
        ]
    },
}

# OPERACIONES CONFIRMADAS (ya encontradas)
CONFIRMED_OPERATIONS = {
    'getPiecesCurrency': {
        'description': 'Consulta niveles de efectivo ✅ CONFIRMADA',
        'params': [
            {'currencyId': 'EUR', 'includeImages': '0', 'includeLevels': '1'},
        ]
    },
    'login': {
        'description': 'Autenticación ✅ CONFIRMADA',
        'params': [{}]
    },
    'getUser': {
        'description': 'Información de usuario ✅ CONFIRMADA',
        'params': [{'userId': '1'}]
    },
}

# OPERACIONES ADICIONALES por descubrir
ADDITIONAL_OPERATIONS = {
    'getDiagnosis': {
        'description': 'Diagnóstico de máquina',
        'params': [{}]
    },
    'askOperationExecuting': {
        'description': 'Comprueba si hay operación en curso',
        'params': [{'posid': 'POS001'}, {}]
    },
    'getAlerts': {
        'description': 'Obtiene alertas de la máquina',
        'params': [{}]
    },
    'getVersion': {
        'description': 'Versión del firmware',
        'params': [{}]
    },
    'getStatus': {
        'description': 'Estado general',
        'params': [{}]
    },
    'getInfo': {
        'description': 'Información general',
        'params': [{}]
    },
}

def test_endpoint_with_operation(endpoint, operation, params_dict):
    """
    Prueba una operación específica en un endpoint
    """
    query_params = {
        'operation': operation,
        'name': USERNAME,
        'password': PASSWORD,
    }
    query_params.update(params_dict)
    
    try:
        response = requests.post(
            endpoint,
            params=query_params,
            timeout=5,
            verify=False,
            allow_redirects=False
        )
        
        if response.status_code in [200, 302]:
            try:
                data = response.json()
                code = data.get('code')
                return {
                    'endpoint': endpoint,
                    'operation': operation,
                    'params': params_dict,
                    'code': code,
                    'success': code == 1,
                    'response': data
                }
            except:
                return {
                    'endpoint': endpoint,
                    'operation': operation,
                    'params': params_dict,
                    'code': None,
                    'raw': response.text[:200]
                }
    except Exception as e:
        pass
    
    return None

def discover_payment_operations():
    """
    Descubre operaciones de pago probando:
    1. Múltiples endpoints
    2. Operaciones conocidas de GPT
    3. Múltiples formatos de parámetros
    """
    print("\n" + "="*80)
    print("CASHDROP PAYMENT DISCOVERY v3")
    print("Basado en investigacion_GPT.txt + operaciones reales encontradas")
    print("="*80)
    
    # Desactivar warnings de SSL
    requests.packages.urllib3.disable_warnings()
    
    # Autenticar primero
    print("\n[PASO 1/4] Autenticando con CashdropAPI_v2...")
    try:
        client = CashdropAPI(f'https://{BASE_URL_ROOT}', USERNAME, PASSWORD, verify_ssl=False)
        client.login()
        print("✅ Autenticado correctamente")
    except Exception as e:
        print(f"⚠️  No se pudo autenticar: {e}")
    
    successful_operations = []
    
    # Probar operaciones de pago (PRINCIPAL)
    print("\n[PASO 2/4] Probando operaciones de PAGO...")
    print("-" * 80)
    
    for endpoint in ENDPOINTS:
        print(f"\n🔗 Endpoint: {endpoint}")
        
        for operation, config in PAYMENT_OPERATIONS.items():
            for params in config['params']:
                result = test_endpoint_with_operation(endpoint, operation, params)
                
                if result:
                    code = result.get('code')
                    if code == 1:
                        print(f"  ✅ {operation:30} code=1 ← ÉXITO")
                        successful_operations.append(result)
                    elif code == 0:
                        print(f"  ❌ {operation:30} code=0 (unknown operation)")
                    else:
                        print(f"  ⚠️  {operation:30} code={code}")
                
                time.sleep(0.05)
    
    # Probar operaciones confirmadas (VALIDACIÓN)
    print("\n[PASO 3/4] Validando operaciones CONFIRMADAS...")
    print("-" * 80)
    
    for endpoint in ENDPOINTS[:1]:  # Solo primer endpoint para validación
        for operation, config in CONFIRMED_OPERATIONS.items():
            for params in config['params']:
                result = test_endpoint_with_operation(endpoint, operation, params)
                
                if result:
                    code = result.get('code')
                    if code == 1:
                        print(f"  ✅ {operation:30} CONFIRMADA")
                    else:
                        print(f"  ❌ {operation:30} code={code}")
                
                time.sleep(0.05)
    
    # Probar operaciones adicionales (BONUS)
    print("\n[PASO 4/4] Buscando operaciones ADICIONALES...")
    print("-" * 80)
    
    for endpoint in ENDPOINTS[:1]:
        for operation, config in ADDITIONAL_OPERATIONS.items():
            for params in config['params']:
                result = test_endpoint_with_operation(endpoint, operation, params)
                
                if result:
                    code = result.get('code')
                    if code == 1:
                        print(f"  ✅ {operation:30} Encontrada")
                        successful_operations.append(result)
                    else:
                        print(f"  ❌ {operation:30} code={code}")
                
                time.sleep(0.05)
    
    # Mostrar resultados
    print("\n" + "="*80)
    print("RESULTADOS FINALES")
    print("="*80)
    
    if successful_operations:
        print(f"\n✅ OPERACIONES EXITOSAS ENCONTRADAS: {len(successful_operations)}\n")
        
        for i, op in enumerate(successful_operations, 1):
            print(f"{i}. Operación: {op['operation']}")
            print(f"   Endpoint: {op['endpoint']}")
            print(f"   Parámetros: {op['params']}")
            print(f"   Respuesta: {op.get('response', {})}")
            print()
    else:
        print("\n❌ No se encontraron operaciones de pago exitosas")
        print("\nRECOMENDACIONES:")
        print("1. La máquina podría tener una versión diferente")
        print("2. Probar inspeccionar tráfico en navegador de Cashdrop UI")
        print("3. DevTools → Network tab → buscar /Cashdro3WS/")
        print("4. Copiar exactamente la operación y parámetros de una petición exitosa")
        print("5. Contactar a CashDro: comercial@cashdro.com")
    
    print("\n" + "="*80)
    return successful_operations

if __name__ == '__main__':
    successful = discover_payment_operations()
    
    if successful:
        print("\n✨ PRÓXIMOS PASOS:")
        print("="*80)
        print("1. Actualizar CashdropAPI_v2.py con método para operación encontrada")
        print("2. Probar método directamente")
        print("3. Actualizar cashdrop_gateway.py para usar operación real")
        print("4. Ejecutar test_gateway.py")
        print("5. Proceder a integración Odoo")
        print("="*80)
