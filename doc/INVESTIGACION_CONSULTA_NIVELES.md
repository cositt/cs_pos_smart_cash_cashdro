# Investigación: por qué "Consulta niveles" pinta ceros en Odoo

Cuando pulses **Consulta niveles** en Movimientos CashDro, el servidor Odoo escribe en el log mensajes que permiten ver qué está fallando.

## Cómo ver el log

Arranca Odoo con log del módulo visible, por ejemplo:

```bash
./odoo-bin ... --log-level=info --log-handler=cs_pos_smart_cash_cashdro:INFO
```

O en Docker, revisa los logs del contenedor después de pulsar el botón.

## Qué buscar en el log (en orden)

### 1. ¿Se ejecuta la acción correcta?

Busca la línea:

```
CashDro action_refresh: context consulta_niveles=... consultar_fianza=... -> ...
```

- Si pone **`-> consultar_fianza`** cuando has pulsado **Consulta niveles**, el contexto no está llegando (vista antigua o caché). Entonces se ejecuta solo fianza y **no se escribe state_display** → la pestaña Estado niveles no se actualiza o sigue en ceros.
- Si pone **`-> consulta_niveles`**, el despacho es correcto.

### 2. ¿La llamada al gateway funciona?

Busca:

```
CashDro action_consulta_niveles: gateway_url=...
CashDro action_consulta_niveles: get_pieces_currency falló -> ...
CashDro action_consulta_niveles: code=... data_len=...
```

- Si aparece **`get_pieces_currency falló`**: el servidor donde corre Odoo (p. ej. contenedor) no puede conectar al CashDro (URL, red, timeout). La respuesta se sustituye por `code=0, data=[]` y la tabla sale toda a cero.
- Si **code=1** y **data_len=0**: la API respondió bien pero sin piezas (poco probable).
- Si **code=1** y **data_len=15** (o similar): la API devolvió datos correctamente.

### 3. ¿Se parsean niveles?

Busca:

```
CashDro _get_levels_from_pieces: devolviendo ceros (code=...)
CashDro _get_levels_from_pieces: no hay data ni response.operation.pieces -> ceros
CashDro _get_levels_from_pieces: procesando N piezas
CashDro action_consulta_niveles: levels total_moneda=X.XX total_billete=X.XX
```

- Si **devolviendo ceros** o **no hay data**: la respuesta no tiene `code=1` o no tiene lista de piezas donde el código la busca (`data` o `response.operation.pieces`).
- Si **procesando 15 piezas** pero **total_moneda=0.00 total_billete=0.00**: todas las piezas tienen `RecyclerLimit=0` o el formato de la respuesta no coincide (nombres de campos distintos).

## Resumen de causas probables

| Síntoma en log | Causa probable |
|----------------|----------------|
| `-> consultar_fianza` al pulsar Consulta niveles | Contexto no llega; vista/caché antigua. |
| `get_pieces_currency falló` | Odoo no puede conectar al CashDro (URL, red, credenciales). |
| `code=0` o `data_len=0` | Misma conexión/API; revisar URL y credenciales del método de pago. |
| `code=1 data_len=15` pero `total_moneda=0 total_billete=0` | Respuesta con estructura distinta o solo piezas con RecyclerLimit=0. |

## Comprobar conectividad desde el servidor Odoo

Desde el **mismo host/contenedor** donde corre Odoo:

```bash
curl -k -X POST "https://10.0.1.140/Cashdro3WS/index.php?operation=getPiecesCurrency&currencyId=EUR&includeImages=0&includeLevels=1&name=admin&password=TU_PASSWORD"
```

Si desde ahí falla o no responde, Odoo tampoco podrá obtener niveles (y verás `get_pieces_currency falló` en el log).
