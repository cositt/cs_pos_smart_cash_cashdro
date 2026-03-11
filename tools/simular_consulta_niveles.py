#!/usr/bin/env python3
"""
Simula pulsar "Consulta niveles": misma llamada que el gateway y misma lógica
que _get_levels_from_pieces. Muestra la respuesta cruda y el levels resultante.
"""
import requests
import json
import os

BASE_URL = os.environ.get('CASHDRO_URL', 'https://10.0.1.140').rstrip('/')
USERNAME = os.environ.get('CASHDRO_USER', 'admin')
PASSWORD = os.environ.get('CASHDRO_PASSWORD', '3428')
URL = f'{BASE_URL}/Cashdro3WS/index.php'

def get_levels_from_pieces(pieces_resp):
    """Copia de la lógica de cashdro_caja_movimientos._get_levels_from_pieces"""
    moneda_denom = [2.0, 1.0, 0.5, 0.2, 0.1, 0.05]
    billete_denom = [100, 50, 20, 10, 5]
    levels = {
        'moneda': [(v, 0, 0.0, 0, 0.0) for v in moneda_denom],
        'billete': [(v, 0, 0.0, 0, 0.0) for v in billete_denom],
    }

    if not pieces_resp or pieces_resp.get('code') != 1:
        print('[get_levels_from_pieces] code != 1 o vacío, devolviendo levels a cero')
        return levels

    data = pieces_resp.get('data')
    if data is None:
        resp = pieces_resp.get('response') or {}
        data = resp.get('data') if isinstance(resp, dict) else None
    if data is None:
        op = (pieces_resp.get('response') or {}).get('operation') or {}
        data = op.get('pieces')  # index3.php devuelve response.operation.pieces
    if data is None:
        print('[get_levels_from_pieces] No se encontró data ni response.operation.pieces')
        return levels

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = []
    if not isinstance(data, list):
        data = [data] if isinstance(data, dict) else []

    print(f'[get_levels_from_pieces] Procesando {len(data)} piezas')
    for p in data:
        if not isinstance(p, dict):
            continue
        try:
            val_raw = p.get('value') or p.get('Value') or 0
            typ = str(p.get('Type') or p.get('type') or '')
            rec_limit = int(float(p.get('RecyclerLimit') or 0))
            rec = int(float(p.get('LevelRecycler') or p.get('levelRecycler') or 0))
            cas = int(float(p.get('LevelCasete') or p.get('levelCasete') or 0))
            val_int = int(float(val_raw))
        except (TypeError, ValueError):
            continue

        if not rec_limit:
            continue

        if typ == '1':
            val_eur = round(val_int / 100.0, 2)
            if val_eur in moneda_denom:
                idx = moneda_denom.index(val_eur)
                total_rec = rec * val_eur
                total_cas = cas * val_eur
                levels['moneda'][idx] = (val_eur, rec, total_rec, cas, total_cas)
        elif typ == '2':
            val_eur = float(val_int) / 100.0
            if val_eur in billete_denom:
                idx = billete_denom.index(val_eur)
                total_rec = rec * val_eur
                total_cas = cas * val_eur
                levels['billete'][idx] = (val_eur, rec, total_rec, cas, total_cas)

    return levels

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
    print('=' * 60)
    print('SIMULACIÓN: pulsar botón "Consulta niveles"')
    print('=' * 60)
    print(f'POST {URL}')
    print(f'Params: {params}')
    print()

    try:
        r = requests.post(URL, params=params, timeout=15, verify=False)
        r.raise_for_status()
        pieces_resp = r.json()
    except Exception as e:
        print('ERROR en la llamada:', e)
        return

    print('--- Respuesta cruda (code y primer elemento de data) ---')
    print('code:', pieces_resp.get('code'))
    data = pieces_resp.get('data')
    if data is not None and isinstance(data, list) and len(data) > 0:
        print('data[0]:', json.dumps(data[0], indent=2))
        print(f'... total {len(data)} piezas')
    else:
        print('data:', data)
    if 'response' in pieces_resp:
        print('response.operation.pieces (si existe):', 'Sí' if (pieces_resp.get('response') or {}).get('operation', {}).get('pieces') else 'No')
    print()

    levels = get_levels_from_pieces(pieces_resp)

    print('--- levels resultante (lo que pinta la tabla) ---')
    print('Moneda (valor_eur, niv_rec, total_rec, niv_cas, total_cas):')
    for t in levels['moneda']:
        print(' ', t)
    print('Billete:')
    for t in levels['billete']:
        print(' ', t)
    print()
    total_moneda = sum(t[2] for t in levels['moneda']) + sum(t[4] for t in levels['moneda'])
    total_billete = sum(t[2] for t in levels['billete']) + sum(t[4] for t in levels['billete'])
    print(f'Total monedas: {total_moneda:.2f} €  |  Total billetes: {total_billete:.2f} €')

if __name__ == '__main__':
    main()
