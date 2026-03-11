#!/usr/bin/env python3
"""
Prueba real: getPiecesCurrency con includeLevels=1.
Documentación: CashDro v415 cap. 6.3 - Consulta de niveles de efectivo.
No modifica Odoo; solo llama al CashDro y muestra la respuesta.
"""
import requests
import json
import os

# Misma config que en tools (cashdrop_gateway.py, discover_payment_operation.py)
BASE_URL = os.environ.get('CASHDRO_URL', 'https://10.0.1.140').rstrip('/')
USERNAME = os.environ.get('CASHDRO_USER', 'admin')
PASSWORD = os.environ.get('CASHDRO_PASSWORD', '3428')

# Probar index.php (el que usa el addon) y opcionalmente index3.php (doc)
ENDPOINTS = [
    ('index.php', f'{BASE_URL}/Cashdro3WS/index.php'),
    ('index3.php', f'{BASE_URL}/Cashdro3WS/index3.php'),
]

def main():
    requests.packages.urllib3.disable_warnings()
    params = {
        'operation': 'getPiecesCurrency',
        'name': USERNAME,
        'password': PASSWORD,
        'currencyId': 'EUR',
        'includeImages': '0',
        'includeLevels': '1',
    }
    print('=' * 80)
    print('PRUEBA: getPiecesCurrency (includeLevels=1)')
    print('=' * 80)
    print(f'BASE_URL = {BASE_URL}')
    print(f'Usuario  = {USERNAME}')
    print()

    for label, url in ENDPOINTS:
        print('-' * 80)
        print(f'Endpoint: {label}  ->  {url}')
        print('-' * 80)
        try:
            # POST como hace gateway_integration
            r = requests.post(url, params=params, timeout=15, verify=False)
            r.raise_for_status()
            data = r.json()
            print('Código HTTP:', r.status_code)
            print('Respuesta JSON (completa):')
            print(json.dumps(data, indent=2, ensure_ascii=False))
            # Extraer piezas: puede ser data['data'] o data['response']['operation']['pieces']
            pieces = None
            if isinstance(data.get('data'), list):
                pieces = data['data']
                print('\n[Piezas en data]')
            elif isinstance(data, dict):
                op = (data.get('response') or {}).get('operation') or {}
                if isinstance(op.get('pieces'), list):
                    pieces = op['pieces']
                    print('\n[Piezas en response.operation.pieces]')
            if pieces:
                print('\nResumen niveles (Value, Type, LevelRecycler, LevelCasete):')
                for p in pieces:
                    if not isinstance(p, dict):
                        continue
                    val = p.get('Value') or p.get('value') or '?'
                    typ = p.get('Type') or p.get('type') or '?'
                    rec = p.get('LevelRecycler') or p.get('levelRecycler') or 0
                    cas = p.get('LevelCasete') or p.get('levelCasete') or 0
                    print(f"  Value={val}, Type={typ} -> LevelRecycler={rec}, LevelCasete={cas}")
            else:
                print('\n(No se encontró lista de piezas en la respuesta)')
        except requests.exceptions.ConnectionError as e:
            print('ERROR: No hay conexión con', BASE_URL, '-', e)
        except requests.exceptions.Timeout:
            print('ERROR: Timeout')
        except Exception as e:
            print('ERROR:', e)
        print()

if __name__ == '__main__':
    main()
