#!/usr/bin/env python3
"""
Discover Payment Operation in Cashdrop
Intenta encontrar la operación de pago real en Cashdrop
"""

import sys
import json
import subprocess
from urllib.parse import urljoin, urlencode

class PaymentOperationDiscovery:
    def __init__(self, base_url="https://10.0.1.140", username="admin", password="3428"):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.found_operations = {}
        
    def curl_request(self, path, method="GET"):
        """Realiza petición con curl"""
        url = urljoin(self.base_url, path)
        
        cmd = ["curl", "-s", "-k", "-w", "\n%{http_code}\n", "-X", method, url]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            output = result.stdout
            
            lines = output.strip().split('\n')
            status = lines[-1] if lines else "000"
            body = '\n'.join(lines[:-1]) if len(lines) > 1 else ""
            
            return {'status': status, 'body': body}
        except:
            return {'status': 'error', 'body': ''}
    
    def build_url(self, operation, **params):
        """Construye URL con parámetros"""
        query_params = {
            'name': self.username,
            'password': self.password,
            'operation': operation
        }
        query_params.update(params)
        
        query_string = urlencode(query_params)
        return f"/Cashdro3WS/index.php?{query_string}"
    
    def test_payment_operation(self, operation_name, amount=1.00, currency="EUR", reference="test123"):
        """Prueba una operación de pago potencial"""
        
        # Variantes de parámetros según naming convention
        param_variants = [
            {
                'amount': str(amount),
                'currencyId': currency,
                'reference': reference
            },
            {
                'amount': str(int(amount * 100)),  # Centavos
                'currencyId': currency,
                'reference': reference
            },
            {
                'amount': str(amount),
                'currency': currency,
                'reference': reference
            },
            {
                'amount': str(int(amount * 100)),
                'currency': currency,
                'transactionId': reference
            },
            {
                'value': str(amount),
                'currencyId': currency,
                'reference': reference
            },
            {
                'total': str(amount),
                'currencyId': currency,
                'reference': reference
            },
        ]
        
        for params in param_variants:
            path = self.build_url(operation_name, **params)
            result = self.curl_request(path, method="POST")
            
            if result['status'] == '200' and result['body']:
                try:
                    data = json.loads(result['body'])
                    code = data.get('code')
                    
                    # Éxito si code == 1
                    if code == 1:
                        return {
                            'operation': operation_name,
                            'params': params,
                            'code': code,
                            'data': data.get('data'),
                            'success': True
                        }
                    # Si es code 0 (unknown op), pero al menos responde
                    elif code == 0:
                        return {
                            'operation': operation_name,
                            'params': params,
                            'code': code,
                            'data': data.get('data'),
                            'success': False,
                            'reason': 'Unknown operation'
                        }
                except:
                    pass
        
        return None
    
    def discover(self):
        """Intenta descubrir operación de pago"""
        print("🔍 Investigando operaciones de pago en Cashdrop\n")
        
        # Nombres probables para operación de pago
        payment_operations = [
            'pay',
            'processPay',
            'addTransaction',
            'transaction',
            'makePayment',
            'acceptPayment',
            'cashIn',
            'deposit',
            'depositCash',
            'insert',
            'insertCash',
            'receiveCash',
            'accept',
            'receive',
            'process',
            'executePayment',
            'startPayment',
            'createTransaction',
            'newTransaction',
        ]
        
        print(f"Probando {len(payment_operations)} nombres de operación...\n")
        
        for op_name in payment_operations:
            print(f"📋 {op_name:20s}...", end=" ", flush=True)
            
            result = self.test_payment_operation(op_name)
            
            if result:
                if result['success']:
                    print("✅ ÉXITO")
                    self.found_operations[op_name] = result
                else:
                    print(f"⚠️  Operación existe pero {result['reason']}")
            else:
                print("❌")
        
        return self.found_operations
    
    def display_results(self):
        """Muestra resultados"""
        print(f"\n{'='*60}")
        print(f"OPERACIONES DE PAGO ENCONTRADAS: {len(self.found_operations)}")
        print(f"{'='*60}\n")
        
        if not self.found_operations:
            print("⚠️  No se encontraron operaciones de pago válidas")
            print("\nPróximos pasos:")
            print("1. Revisar otros patrones de nombres")
            print("2. Buscar documentación de Cashdrop")
            print("3. Inspeccionar tráfico de red del navegador")
            return
        
        for op_name, result in self.found_operations.items():
            print(f"✅ {op_name}")
            print(f"   Parámetros: {result['params']}")
            print(f"   Código: {result['code']}")
            if result.get('data'):
                print(f"   Respuesta: {str(result['data'])[:100]}")
            print()
    
    def save_findings(self):
        """Guarda hallazgos"""
        report = {
            'operations_found': len(self.found_operations),
            'operations': {}
        }
        
        for op_name, result in self.found_operations.items():
            report['operations'][op_name] = {
                'params': result['params'],
                'code': result['code'],
                'data': str(result.get('data'))[:200]
            }
        
        filename = 'cashdrop_payment_operations.json'
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"✅ Hallazgos guardados en: {filename}\n")
        
        # También mostrar comando curl de ejemplo
        if self.found_operations:
            first_op = list(self.found_operations.values())[0]
            op_name = first_op['operation']
            params = first_op['params']
            
            print("📝 Ejemplo de CURL para prueba manual:")
            print(f"curl -X POST 'https://10.0.1.140/Cashdro3WS/index.php?")
            print(f"  name=admin&")
            print(f"  password=3428&")
            print(f"  operation={op_name}&")
            for key, val in params.items():
                print(f"  {key}={val}&")
            print("'")
    
    def run(self):
        """Ejecuta investigación completa"""
        print("🚀 Investigación de Operación de Pago - Cashdrop")
        print("="*60 + "\n")
        
        results = self.discover()
        self.display_results()
        self.save_findings()
        
        return len(results) > 0

if __name__ == '__main__':
    discoverer = PaymentOperationDiscovery(
        base_url="https://10.0.1.140",
        username="admin",
        password="3428"
    )
    
    success = discoverer.run()
    sys.exit(0 if success else 1)
