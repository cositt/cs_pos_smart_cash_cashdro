#!/usr/bin/env python3
"""
Verificación del parsing de datos para Consulta de niveles y Estado de fianza.
Ejecutar desde la raíz del addon: python3 tools/verify_levels_parsing.py
No requiere Odoo; solo comprueba la lógica con respuestas de ejemplo.
"""
import json
import sys
import os

# Estructura que devuelve get_consult_levels (misma lógica que gateway_integration.get_consult_levels)
def parse_ask_operation_data(data):
    """Parsea 'data' como la respuesta askOperation (type=12). Devuelve result como get_consult_levels."""
    moneda_denom = [2.0, 1.0, 0.5, 0.2, 0.1, 0.05]
    billete_denom = [100, 50, 20, 10, 5]
    result = {
        'moneda': [(v, 0, 0.0, 0, 0.0) for v in moneda_denom],
        'billete': [(v, 0, 0.0, 0, 0.0) for v in billete_denom],
    }
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return result
    if not isinstance(data, dict):
        return result
    devices = data.get('devices') or data.get('Devices') or []
    for dev in devices:
        typ = str(dev.get('Type') or dev.get('type') or '')
        pieces = dev.get('pieces') or dev.get('Pieces') or []
        for p in pieces:
            if not isinstance(p, dict):
                continue
            val_raw = p.get('value') or p.get('Value') or 0
            try:
                val_int = int(float(val_raw))
            except Exception:
                continue
            rec = int(float(p.get('finishlevelrecycler') or p.get('startlevelrecycler') or p.get('unitsinrecycler') or p.get('unitsInRecycler') or 0))
            cas = int(float(p.get('finishlevelcassette') or p.get('startlevelcassette') or p.get('unitsincassette') or p.get('unitsInCassette') or 0))
            if typ == '2':
                val_eur = val_int / 100.0
                idx = next((i for i, d in enumerate(moneda_denom) if abs(d - val_eur) < 0.01), None)
                if idx is not None:
                    total_rec = rec * val_eur
                    total_cas = cas * val_eur
                    result['moneda'][idx] = (moneda_denom[idx], rec, total_rec, cas, total_cas)
            elif typ == '3':
                val_eur = (val_int / 100.0) if val_int >= 100 else val_int
                if val_eur not in billete_denom and val_int in (5, 10, 20, 50, 100, 200):
                    val_eur = val_int
                if val_eur in billete_denom:
                    idx = billete_denom.index(val_eur)
                    total_rec = rec * val_eur
                    total_cas = cas * val_eur
                    result['billete'][idx] = (val_eur, rec, total_rec, cas, total_cas)
    return result


# Respuesta típica askOperation (type=12) - como la captura de red
SAMPLE_ASK_DATA_STR = '''{
  "operation": {"operationid": "15568", "state": "E", "type": "12"},
  "devices": [
    {"type": "1", "state": "3", "pieces": []},
    {"type": "2", "state": "3", "pieces": [
      {"value": "5", "currencyid": "EUR", "finishlevelrecycler": "0", "finishlevelcassette": "0"},
      {"value": "10", "currencyid": "EUR", "finishlevelrecycler": "0", "finishlevelcassette": "0"},
      {"value": "200", "currencyid": "EUR", "finishlevelrecycler": "0", "finishlevelcassette": "0"}
    ]},
    {"type": "3", "state": "3", "pieces": [
      {"value": "1000", "currencyid": "EUR", "finishlevelrecycler": "1", "finishlevelcassette": "0"},
      {"value": "500", "currencyid": "EUR", "finishlevelrecycler": "1", "finishlevelcassette": "0"}
    ]}
  ]
}'''

# Billetes: value 1000 = 10€, 500 = 5€ → rec 1 cada uno → Total rec 15€
# Monedas: value 5=0.05€, 10=0.10€, 200=2€ → rec 0 → todo 0
def test_consulta_niveles_parsing():
    data = json.loads(SAMPLE_ASK_DATA_STR)
    result = parse_ask_operation_data(data)
    # Billetes: 10€ rec=1, 5€ rec=1
    billete_10 = next((x for x in result['billete'] if abs(x[0] - 10) < 0.01), None)
    billete_5 = next((x for x in result['billete'] if abs(x[0] - 5) < 0.01), None)
    assert billete_10 is not None, "Debería existir 10€ en billete"
    assert billete_5 is not None, "Debería existir 5€ en billete"
    assert billete_10[1] == 1 and billete_10[2] == 10.0, "10€: niv.rec=1, total rec=10€"
    assert billete_5[1] == 1 and billete_5[2] == 5.0, "5€: niv.rec=1, total rec=5€"
    total_billete = sum(x[2] for x in result['billete']) + sum(x[4] for x in result['billete'])
    assert abs(total_billete - 15.0) < 0.01, "Total billetes reciclador debería ser 15€"
    print("[OK] Consulta de niveles: parsing de askOperation (devices/pieces, value 1000/500 → 10€/5€, type 2/3) correcto.")
    return True


def parse_fianza_config(levels_json_str):
    """Extrae fianza_by_eur desde el JSON de setDepositLevels (misma lógica que _build_estado_fianza_html)."""
    try:
        config_data = json.loads(levels_json_str)
    except (TypeError, json.JSONDecodeError):
        return {}
    config_list = config_data.get('config') or []
    fianza_by_eur = {}
    for item in config_list:
        try:
            val_raw = item.get('Value') or item.get('value') or 0
            val_int = int(float(val_raw))
            typ = str(item.get('Type') or item.get('type') or '1')
            dep = int(float(item.get('DepositLevel') or item.get('depositLevel') or 0))
        except (TypeError, ValueError):
            continue
        if typ in ('1', '3'):
            valor_eur = val_int
            if valor_eur in (100, 50, 20, 10, 5):
                fianza_by_eur[valor_eur] = dep
        elif typ == '2':
            valor_eur = round(val_int / 100.0, 2)
            if valor_eur in (2.0, 1.0, 0.5, 0.2, 0.1, 0.05):
                fianza_by_eur[valor_eur] = dep
    return fianza_by_eur


SAMPLE_FIANZA_JSON = '''{
  "limitRecyclerCheck": 0,
  "config": [
    {"CurrencyId": "EUR", "DepositLevel": "1", "Value": "10", "Type": "1"},
    {"CurrencyId": "EUR", "DepositLevel": "1", "Value": "5", "Type": "1"},
    {"CurrencyId": "EUR", "DepositLevel": "5", "Value": "20", "Type": "2"},
    {"CurrencyId": "EUR", "DepositLevel": "4", "Value": "10", "Type": "2"}
  ]
}'''

def test_estado_fianza_config_parsing():
    fianza = parse_fianza_config(SAMPLE_FIANZA_JSON)
    # Type 1: Value 10 -> 10€, Value 5 -> 5€
    assert fianza.get(10) == 1, "Fianza 10€ = 1"
    assert fianza.get(5) == 1, "Fianza 5€ = 1"
    # Type 2: Value 20 -> 0.20€, Value 10 -> 0.10€ (cents)
    assert fianza.get(0.2) == 5, "Fianza 0.20€ = 5"
    assert fianza.get(0.1) == 4, "Fianza 0.10€ = 4"
    print("[OK] Estado de fianza: parsing de config (DepositLevel, Value, Type 1/2) correcto.")
    return True


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ok = True
    try:
        test_consulta_niveles_parsing()
    except AssertionError as e:
        print("[FAIL] Consulta de niveles:", e)
        ok = False
    try:
        test_estado_fianza_config_parsing()
    except AssertionError as e:
        print("[FAIL] Estado fianza config:", e)
        ok = False
    if not ok:
        sys.exit(1)
    print("\nVerificación completada: los datos que se muestran se obtienen correctamente del parsing.")


if __name__ == '__main__':
    main()
