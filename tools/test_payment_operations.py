#!/usr/bin/env python3
"""
Script de Prueba - Operaciones de Pago Cashdrop
Basado en análisis del módulo OCA pos_payment_method_cashdro
Parámetros validados contra código de producción
"""

import requests
import json
import time
from datetime import datetime
from CashdropAPI_v2 import CashdropAPI

# Configuración
BASE_URL = 'https://10.0.1.140'
USERNAME = 'admin'
PASSWORD = '3428'

# Desactivar warnings SSL
requests.packages.urllib3.disable_warnings()

class CashdropPaymentTester:
    def __init__(self):
        self.results = []
        self.operation_id = None
        
    def print_header(self, title):
        """Imprime encabezado de sección"""
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}\n")
    
    def print_test(self, name, success, url=None, response=None, error=None):
        """Imprime resultado de prueba"""
        status = "✅ ÉXITO" if success else "❌ FALLO"
        print(f"{status} | {name}")
        
        if url:
            print(f"  URL: {url}")
        
        if response:
            try:
                print(f"  Status Code: {response.status_code}")
                data = response.json()
                print(f"  Response: {json.dumps(data, indent=2)}")
            except:
                print(f"  Response: {response.text[:200]}")
        
        if error:
            print(f"  Error: {error}")
        
        self.results.append({'name': name, 'success': success})
    
    def test_connection(self):
        """Test 1: Verificar conectividad básica"""
        self.print_header("TEST 1: Conectividad Básica")
        
        try:
            response = requests.get(
                f'{BASE_URL}/Cashdro3WS/index.php',
                params={'name': USERNAME, 'password': PASSWORD, 'operation': 'login'},
                timeout=5,
                verify=False
            )
            success = response.status_code == 200
            self.print_test("Conexión a Cashdrop", success, response=response)
            return success
        except Exception as e:
            self.print_test("Conexión a Cashdrop", False, error=str(e))
            return False
    
    def test_login(self):
        """Test 2: Autenticación"""
        self.print_header("TEST 2: Autenticación")
        
        try:
            client = CashdropAPI(BASE_URL, USERNAME, PASSWORD, verify_ssl=False)
            client.login()
            self.print_test("Login con CashdropAPI_v2", True)
            return True
        except Exception as e:
            self.print_test("Login con CashdropAPI_v2", False, error=str(e))
            return False
    
    def test_get_pieces_currency(self):
        """Test 3: Obtener disponibilidad de efectivo"""
        self.print_header("TEST 3: Obtener Piezas de Divisa")
        
        try:
            client = CashdropAPI(BASE_URL, USERNAME, PASSWORD, verify_ssl=False)
            client.login()
            pieces = client.get_pieces_currency('EUR')
            
            success = pieces is not None and len(pieces) > 0
            self.print_test(
                "getPiecesCurrency (EUR)",
                success,
                response=None
            )
            
            if success:
                print(f"  Piezas encontradas: {len(pieces)}")
                for i, piece in enumerate(pieces[:3]):
                    print(f"    {i+1}. {piece.get('Value')} {piece.get('CurrencyId')} - {piece.get('Type')}")
            
            return success
        except Exception as e:
            self.print_test("getPiecesCurrency", False, error=str(e))
            return False
    
    def test_start_operation(self, amount_eur=10.50):
        """Test 4: Iniciar operación de pago (CRÍTICO)"""
        self.print_header("TEST 4: Iniciar Operación de Pago (startOperation)")
        
        print(f"Parámetros a usar:")
        print(f"  Amount (EUR): {amount_eur}")
        print(f"  Amount (Centavos): {int(amount_eur * 100)}")
        print(f"  type: 4 (venta completa)")
        print(f"  posid: pos-TEST")
        print(f"  posuser: 1")
        
        try:
            amount_cents = int(amount_eur * 100)
            
            # Construir URL exacta como en código OCA
            url = f"{BASE_URL}/Cashdro3WS/index.php"
            params = {
                'name': USERNAME,
                'password': PASSWORD,
                'operation': 'startOperation',
                'type': 4,  # ← CRÍTICO: type=4 (venta), NO type=3
                'posid': 'pos-TEST',
                'posuser': 1,
                'parameters': json.dumps({'amount': amount_cents})  # ← CENTAVOS
            }
            
            response = requests.get(url, params=params, timeout=10, verify=False)
            
            print(f"\n  URL construida:")
            full_url = f"{url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
            print(f"  {full_url[:120]}...")
            
            success = response.status_code == 200
            self.print_test("startOperation", success, response=response)
            
            if success:
                try:
                    data = response.json()
                    if data.get('code') == 1 and data.get('data'):
                        self.operation_id = data.get('data')
                        print(f"  ✅ Operation ID obtenido: {self.operation_id}")
                        return True
                    else:
                        print(f"  ⚠️  Respuesta: code={data.get('code')}, data={data.get('data')}")
                except:
                    pass
            
            return False
        
        except Exception as e:
            self.print_test("startOperation", False, error=str(e))
            return False
    
    def test_acknowledge_operation(self):
        """Test 5: Reconocer operación"""
        self.print_header("TEST 5: Reconocer Operación (acknowledgeOperationId)")
        
        if not self.operation_id:
            print("⚠️  No hay operation_id. Saltando prueba.")
            return False
        
        try:
            url = f"{BASE_URL}/Cashdro3WS/index.php"
            params = {
                'name': USERNAME,
                'password': PASSWORD,
                'operation': 'acknowledgeOperationId',
                'operationId': self.operation_id
            }
            
            response = requests.get(url, params=params, timeout=10, verify=False)
            success = response.status_code == 200
            self.print_test("acknowledgeOperationId", success, response=response)
            
            return success
        
        except Exception as e:
            self.print_test("acknowledgeOperationId", False, error=str(e))
            return False
    
    def test_ask_operation(self, timeout=5):
        """Test 6: Consultar estado de operación (con polling limitado)"""
        self.print_header("TEST 6: Consultar Estado de Operación (askOperation)")
        
        if not self.operation_id:
            print("⚠️  No hay operation_id. Saltando prueba.")
            return False
        
        print(f"Esperando estado 'F' (finished) por máximo {timeout} segundos...")
        
        try:
            url = f"{BASE_URL}/Cashdro3WS/index.php"
            start_time = time.time()
            attempt = 0
            
            while time.time() - start_time < timeout:
                attempt += 1
                print(f"\n  [Intento {attempt}]", end=" ")
                
                params = {
                    'name': USERNAME,
                    'password': PASSWORD,
                    'operation': 'askOperation',
                    'operationId': self.operation_id
                }
                
                response = requests.get(url, params=params, timeout=10, verify=False)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get('data'):
                            # ⚠️ IMPORTANTE: response.data es un STRING con JSON dentro!
                            operation_data = json.loads(data.get('data'))
                            state = operation_data.get('operation', {}).get('state')
                            print(f"State: {state}")
                            
                            if state == 'F':  # ← FINISHED
                                print(f"\n  ✅ Estado F (finished) obtenido!")
                                totalin = operation_data.get('operation', {}).get('totalin')
                                if totalin:
                                    amount_eur = totalin / 100
                                    print(f"  Amount recibido: {amount_eur} EUR (centavos: {totalin})")
                                return True
                        else:
                            print(f"Sin data")
                    except Exception as e:
                        print(f"Error parsing: {e}")
                else:
                    print(f"Status: {response.status_code}")
                
                time.sleep(1)
            
            print(f"\n  ⏱️  Timeout: No se obtuvo estado 'F' en {timeout}s")
            self.print_test("askOperation (timeout)", False)
            return False
        
        except Exception as e:
            self.print_test("askOperation", False, error=str(e))
            return False
    
    def test_finish_operation(self):
        """Test 7: Finalizar operación (cancelación)"""
        self.print_header("TEST 7: Finalizar Operación (finishOperation - CANCEL)")
        
        if not self.operation_id:
            print("⚠️  No hay operation_id. Saltando prueba.")
            return False
        
        try:
            url = f"{BASE_URL}/Cashdro3WS/index.php"
            params = {
                'name': USERNAME,
                'password': PASSWORD,
                'operation': 'finishOperation',
                'type': 2,  # ← type=2 para cancelación
                'operationId': self.operation_id
            }
            
            response = requests.get(url, params=params, timeout=10, verify=False)
            success = response.status_code == 200
            self.print_test("finishOperation (cancel)", success, response=response)
            
            return success
        
        except Exception as e:
            self.print_test("finishOperation", False, error=str(e))
            return False
    
    def print_summary(self):
        """Imprime resumen final"""
        self.print_header("RESUMEN DE PRUEBAS")
        
        passed = sum(1 for r in self.results if r['success'])
        total = len(self.results)
        
        print(f"Total de pruebas: {total}")
        print(f"Pasadas: {passed} ✅")
        print(f"Fallidas: {total - passed} ❌")
        print(f"Porcentaje: {(passed/total*100):.1f}%\n")
        
        print("Detalle:")
        for result in self.results:
            status = "✅" if result['success'] else "❌"
            print(f"  {status} {result['name']}")
        
        self.print_header("CONCLUSIONES")
        
        if passed >= 4:
            print("✅ OPERACIONES BÁSICAS FUNCIONAN:")
            print("   - Conectividad ✅")
            print("   - Autenticación ✅")
            print("   - Información de máquina ✅")
            print("   - Inicio de operación ✅")
        
        if passed >= 6:
            print("\n✅ FLUJO COMPLETO FUNCIONA:")
            print("   - Acknowledge ✅")
            print("   - Polling de estado ✅")
        
        if self.operation_id:
            print(f"\n⚠️  Operation ID pendiente de limpieza: {self.operation_id}")
            print("   (Se canceló automáticamente en finishOperation)")
    
    def run_all_tests(self):
        """Ejecuta todas las pruebas"""
        print("\n" + "█"*80)
        print("█" + " "*78 + "█")
        print("█" + "  CASHDROP PAYMENT OPERATIONS - TEST FINAL".center(78) + "█")
        print("█" + "  Basado en Código OCA pos_payment_method_cashdro".center(78) + "█")
        print("█" + " "*78 + "█")
        print("█"*80)
        
        print(f"\nFecha: {datetime.now().isoformat()}")
        print(f"Host: {BASE_URL}")
        print(f"Usuario: {USERNAME}")
        
        # Ejecutar pruebas secuenciales
        tests = [
            ('connection', self.test_connection),
            ('login', self.test_login),
            ('pieces', self.test_get_pieces_currency),
            ('start_op', lambda: self.test_start_operation(10.50)),
            ('ack_op', self.test_acknowledge_operation),
            ('ask_op', lambda: self.test_ask_operation(timeout=10)),
            ('finish_op', self.test_finish_operation),
        ]
        
        for test_name, test_func in tests:
            try:
                test_func()
                time.sleep(0.5)
            except Exception as e:
                print(f"❌ Excepción en {test_name}: {e}")
            time.sleep(1)
        
        # Resumen
        self.print_summary()


if __name__ == '__main__':
    tester = CashdropPaymentTester()
    tester.run_all_tests()
