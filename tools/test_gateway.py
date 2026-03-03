#!/usr/bin/env python3
"""
Script de prueba para Cashdrop Gateway
Ejecutar cuando el gateway esté corriendo en http://localhost:5000
"""

import requests
import json
import time
from typing import Dict, Any

# URL base del gateway
GATEWAY_URL = 'http://localhost:5000'

class GatewayTester:
    def __init__(self, base_url=GATEWAY_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []
    
    def print_section(self, title):
        """Imprime un encabezado de sección"""
        print("\n" + "="*70)
        print(f"  {title}")
        print("="*70)
    
    def print_test(self, name, success, response=None, error=None):
        """Imprime resultado de una prueba"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"\n{status} | {name}")
        
        if response:
            print(f"  Status: {response.status_code}")
            print(f"  Body: {json.dumps(response.json(), indent=2)}")
        
        if error:
            print(f"  Error: {error}")
        
        self.test_results.append({
            'name': name,
            'success': success
        })
    
    def test_health(self):
        """Prueba endpoint /health"""
        self.print_section("TEST 1: Health Check")
        
        try:
            response = self.session.get(f'{self.base_url}/health')
            success = response.status_code == 200
            self.print_test("GET /health", success, response=response)
            return success
        except Exception as e:
            self.print_test("GET /health", False, error=str(e))
            return False
    
    def test_status(self):
        """Prueba endpoint /status"""
        self.print_section("TEST 2: Obtener Estado de Máquina")
        
        try:
            response = self.session.get(f'{self.base_url}/status')
            success = response.status_code == 200
            self.print_test("GET /status", success, response=response)
            return success
        except Exception as e:
            self.print_test("GET /status", False, error=str(e))
            return False
    
    def test_pieces(self):
        """Prueba endpoint /pieces"""
        self.print_section("TEST 3: Obtener Piezas Disponibles")
        
        try:
            response = self.session.get(f'{self.base_url}/pieces/EUR')
            success = response.status_code == 200
            self.print_test("GET /pieces/EUR", success, response=response)
            return response.json() if success else None
        except Exception as e:
            self.print_test("GET /pieces/EUR", False, error=str(e))
            return None
    
    def test_payment_flow(self):
        """Prueba flujo completo de pago"""
        self.print_section("TEST 4: Flujo Completo de Pago")
        
        # 1. Crear pago
        print("\n[4.1] Iniciando pago...")
        try:
            response = self.session.post(
                f'{self.base_url}/pay',
                json={
                    'amount': 15.50,
                    'currency': 'EUR',
                    'reference': 'TEST-ORDER-001'
                }
            )
            success = response.status_code == 202
            self.print_test("POST /pay", success, response=response)
            
            if not success:
                return False
            
            transaction_id = response.json()['transaction_id']
            
            # 2. Verificar estado
            print("\n[4.2] Verificando estado del pago...")
            time.sleep(0.5)
            
            response = self.session.get(f'{self.base_url}/payment/{transaction_id}/status')
            success = response.status_code == 200
            self.print_test("GET /payment/{id}/status", success, response=response)
            
            if not success:
                return False
            
            # 3. Confirmar pago
            print("\n[4.3] Confirmando pago...")
            time.sleep(0.5)
            
            response = self.session.post(f'{self.base_url}/payment/{transaction_id}/confirm')
            success = response.status_code == 200
            self.print_test("POST /payment/{id}/confirm", success, response=response)
            
            return success
        
        except Exception as e:
            self.print_test("Payment flow", False, error=str(e))
            return False
    
    def test_payment_cancellation(self):
        """Prueba cancelación de pago"""
        self.print_section("TEST 5: Cancelación de Pago")
        
        try:
            # Crear pago
            response = self.session.post(
                f'{self.base_url}/pay',
                json={
                    'amount': 5.00,
                    'currency': 'EUR',
                    'reference': 'TEST-CANCEL-001'
                }
            )
            
            if response.status_code != 202:
                self.print_test("POST /pay (para cancelación)", False, response=response)
                return False
            
            transaction_id = response.json()['transaction_id']
            time.sleep(0.3)
            
            # Cancelar pago
            response = self.session.post(f'{self.base_url}/payment/{transaction_id}/cancel')
            success = response.status_code == 200
            self.print_test("POST /payment/{id}/cancel", success, response=response)
            
            return success
        
        except Exception as e:
            self.print_test("Payment cancellation", False, error=str(e))
            return False
    
    def test_cash_operations(self):
        """Prueba operaciones de cash in/out"""
        self.print_section("TEST 6: Operaciones de Efectivo")
        
        try:
            # Cash in
            response = self.session.post(
                f'{self.base_url}/cash-in',
                json={
                    'amount': 100.00,
                    'currency': 'EUR'
                }
            )
            success = response.status_code == 202
            self.print_test("POST /cash-in", success, response=response)
            
            if not success:
                return False
            
            time.sleep(0.3)
            
            # Cash out
            response = self.session.post(
                f'{self.base_url}/cash-out',
                json={
                    'amount': 50.00,
                    'currency': 'EUR'
                }
            )
            success = response.status_code == 202
            self.print_test("POST /cash-out", success, response=response)
            
            return success
        
        except Exception as e:
            self.print_test("Cash operations", False, error=str(e))
            return False
    
    def test_error_cases(self):
        """Prueba casos de error"""
        self.print_section("TEST 7: Casos de Error")
        
        all_pass = True
        
        # Falta de parámetros requeridos
        try:
            response = self.session.post(
                f'{self.base_url}/pay',
                json={'amount': 10}  # Falta currency
            )
            success = response.status_code == 400
            self.print_test("POST /pay (sin currency)", success, response=response)
            all_pass = all_pass and success
        except Exception as e:
            self.print_test("POST /pay (sin currency)", False, error=str(e))
            all_pass = False
        
        time.sleep(0.2)
        
        # Monto inválido
        try:
            response = self.session.post(
                f'{self.base_url}/pay',
                json={
                    'amount': -10,
                    'currency': 'EUR'
                }
            )
            success = response.status_code == 400
            self.print_test("POST /pay (monto negativo)", success, response=response)
            all_pass = all_pass and success
        except Exception as e:
            self.print_test("POST /pay (monto negativo)", False, error=str(e))
            all_pass = False
        
        time.sleep(0.2)
        
        # Transacción no encontrada
        try:
            response = self.session.get(f'{self.base_url}/payment/invalid-id/status')
            success = response.status_code == 404
            self.print_test("GET /payment/invalid-id/status", success, response=response)
            all_pass = all_pass and success
        except Exception as e:
            self.print_test("GET /payment/invalid-id/status", False, error=str(e))
            all_pass = False
        
        return all_pass
    
    def run_all_tests(self):
        """Ejecuta todas las pruebas"""
        print("\n" + "█"*70)
        print("█" + " "*68 + "█")
        print("█" + "  CASHDROP GATEWAY - TEST SUITE".center(68) + "█")
        print("█" + " "*68 + "█")
        print("█"*70)
        
        # Verificar conexión
        print(f"\nConectando a {self.base_url}...")
        try:
            response = self.session.get(f'{self.base_url}/health', timeout=2)
            print("✅ Gateway accesible")
        except Exception as e:
            print(f"❌ No se puede conectar al gateway: {e}")
            print("   Asegúrate de que el gateway está corriendo: python cashdrop_gateway.py")
            return
        
        # Ejecutar pruebas
        self.test_health()
        time.sleep(0.5)
        
        self.test_status()
        time.sleep(0.5)
        
        self.test_pieces()
        time.sleep(0.5)
        
        self.test_payment_flow()
        time.sleep(0.5)
        
        self.test_payment_cancellation()
        time.sleep(0.5)
        
        self.test_cash_operations()
        time.sleep(0.5)
        
        self.test_error_cases()
        
        # Resumen
        self.print_summary()
    
    def print_summary(self):
        """Imprime resumen de pruebas"""
        self.print_section("RESUMEN DE PRUEBAS")
        
        passed = sum(1 for r in self.test_results if r['success'])
        total = len(self.test_results)
        
        print(f"\n  Total: {total}")
        print(f"  Pasadas: {passed} ✅")
        print(f"  Fallidas: {total - passed} ❌")
        
        if passed == total:
            print("\n  🎉 ¡TODAS LAS PRUEBAS PASARON!")
        else:
            print(f"\n  ⚠️  {total - passed} prueba(s) fallida(s)")
        
        print("\n" + "="*70 + "\n")

if __name__ == '__main__':
    tester = GatewayTester()
    tester.run_all_tests()
