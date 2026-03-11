# Llamadas Web Service CashDro configuradas en el módulo

Referencia: **CashDro Integración por Web Service v415.pdf**.  
Este documento describe todas las llamadas al gateway CashDro que el módulo `cs_pos_smart_cash_cashdro` utiliza y qué hace cada una desde la interfaz de Odoo.

---

## 1. Endpoints base

| Endpoint | Uso |
|----------|-----|
| `https://<ip>/Cashdro3WS/index3.php` | Operaciones con movimiento de efectivo: venta, pago, carga, retirada, cambio, etc. (GET). |
| `https://<ip>/Cashdro3WS/index.php` | Operaciones administrativas y consultas: getInfoDevices, getPiecesCurrency, setDepositLevels, startOperation (type=16, 12, 36) (POST). |

Las credenciales (`name`, `password`) son las del método de pago CashDro configurado en Odoo, salvo donde se indica (canal Exchange_Machine).

---

## 2. Resumen: botón en Odoo → llamadas

| Botón / acción en Odoo | Llamadas al gateway | Doc PDF |
|------------------------|----------------------|---------|
| **Venta** | login → startOperation (type=4, amount) → acknowledgeOperationId | 5.3 |
| **Pago** | login → startOperation (type=3, amount) → acknowledgeOperationId | 5.3 (devolución) |
| **Ingresar** | startOperation (type=16) + acknowledgeOperationId (index.php POST) | 5.5 |
| **Ingresar por importe** | login → startOperation (type=17, parameters.amount) → acknowledgeOperationId | 5.6 |
| **Carga** | login → startOperation (type=1) → acknowledgeOperationId | 5.7 |
| **Retirada** | login → startOperation (type=2) → acknowledgeOperationId; luego URL web unload | 5.8 |
| **Retirada de casete de monedas** | login → startOperation (type=11) → acknowledgeOperationId | 5.13 |
| **Retirada de casete de billetes** | login → startOperation (type=10) → acknowledgeOperationId | 5.12 |
| **Cambio** | login → startOperation (type=18) → acknowledgeOperationId | 5.4 |
| **Inicializar niveles** | startOperation (type=12) → acknowledgeOperationId → askOperation → finishOperation | — |
| **Configurar fianza** | getPiecesCurrency → setDepositLevels (POST) → startOperation (type=36) → acknowledge → askOperation → finishOperation | — |
| **Consultar fianza** | getPiecesCurrency (POST, includeLevels=1) | — |
| **Consulta niveles** | getPiecesCurrency (POST, includeLevels=1) | — |

---

## 3. Detalle por operación

### 3.1 Login

- **Operación:** `login`
- **Parámetros:** `name`, `password`
- **Endpoint:** index3.php (GET)
- **Uso:** Se ejecuta antes de startOperation en index3.php (venta, pago, carga, retirada, cambio, casetes). No se usa para las operaciones que van por index.php (ingresar type=16, fianza, consultas).

### 3.2 Venta (cobro)

- **Botón:** Operaciones → **Venta**
- **Llamadas:**  
  1. `login`  
  2. `startOperation`: type=**4**, `posid`, `posuser`, `parameters` = `{"amount": "<céntimos>"}`, `startnow=true`  
  3. `acknowledgeOperationId` con el `operationId` devuelto  
- **Efecto:** La máquina espera que el cliente introduzca el importe indicado (cobro).
- **Doc:** 5.3 (transacción de pago/venta).

### 3.3 Pago (devolución / dispensa)

- **Botón:** Operaciones → **Pago**
- **Llamadas:**  
  1. `login`  
  2. `startOperation`: type=**3**, mismo esquema de `parameters.amount` (céntimos)  
  3. `acknowledgeOperationId`  
- **Efecto:** La máquina dispensará el importe indicado.
- **Doc:** 5.3 (devolución).

### 3.4 Ingresar (carga genérica)

- **Botón:** Operaciones → **Ingresar**
- **Llamadas:**  
  1. `startOperation` (vía **index.php** POST): type=**16**, `aliasId`, `isManual=0`, `startnow=true`  
  2. `acknowledgeOperationId` (POST index.php)  
- **Efecto:** La máquina entra en modo “cargando”; el operario introduce dinero. No se hace finish ni setOperationImported desde Odoo.
- **Doc:** 5.5 Ingreso.

### 3.5 Ingresar por importe

- **Botón:** Operaciones → **Ingresar por importe**
- **Llamadas:**  
  1. `login`  
  2. `startOperation`: type=**17**, `parameters` = `{"amount": "<céntimos>"}`, `startnow=true`  
  3. `acknowledgeOperationId`  
- **Efecto:** Ingreso con importe objetivo indicado desde Odoo.
- **Doc:** 5.6 Ingreso por importe.

### 3.6 Carga (operación tipo “Carga”)

- **Botón:** Operaciones → **Carga**
- **Llamadas:**  
  1. `login`  
  2. `startOperation`: type=**1**, `posid`, `posuser`, `startnow=true`  
  3. `acknowledgeOperationId`  
- **Efecto:** La máquina muestra pantalla de carga; el usuario acepta/finaliza en la máquina. El módulo no abre ventana web ni llama a setOperationImported automáticamente.
- **Doc:** 5.7 Carga.

### 3.7 Retirada

- **Botón:** Operaciones → **Retirada**
- **Llamadas:**  
  1. `login`  
  2. `startOperation`: type=**2**, `posid`, `posuser`, `startnow=true`  
  3. `acknowledgeOperationId`  
  4. Se abre en el navegador la **URL de la interfaz web**:  
     `https://<ip>/Cashdro3Web/#/unload/<operationId>/true/?username=...&password=...`  
     Para indicar las piezas a retirar (doc 5.8.3); sin esta pantalla la máquina puede quedarse en “Retirando…”.
- **Doc:** 5.8 Retirada.

### 3.8 Retirada de casete de monedas

- **Botón:** Operaciones → **Retirada de casete de monedas**
- **Llamadas:**  
  1. `login`  
  2. `startOperation`: type=**11**, `posid`, `posuser`, `startnow=true`  
  3. `acknowledgeOperationId`  
- **Efecto:** Orden a la máquina; el proceso se completa físicamente en la máquina.
- **Doc:** 5.13.

### 3.9 Retirada de casete de billetes

- **Botón:** Operaciones → **Retirada de casete de billetes**
- **Llamadas:**  
  1. `login`  
  2. `startOperation`: type=**10**, `posid`, `posuser`, `startnow=true`  
  3. `acknowledgeOperationId`  
- **Efecto:** Orden a la máquina; se completa en la máquina.
- **Doc:** 5.12 Retirar casete de billetes.

### 3.10 Cambio

- **Botón:** Operaciones → **Cambio**
- **Llamadas:**  
  1. `login`  
  2. `startOperation`: type=**18**, `posid`, `posuser`, `startnow=true`  
  3. `acknowledgeOperationId`  
- **Efecto:** Se envía la orden de cambio a la máquina; el usuario completa el cambio en CashDro. El módulo no abre ventana (solo notificación).
- **Doc:** 5.4 Cambio.

### 3.11 Inicializar niveles

- **Botón:** Operaciones → **Inicializar niveles**
- **Llamadas:**  
  1. `startOperation` (index3.php GET): type=**12**, `posid`, `posuser`, `aliasid`  
  2. `acknowledgeOperationId`  
  3. `askOperation` (opcional, para estado)  
  4. `finishOperation` (operationId, type=1)  
- **Efecto:** Operación administrativa para inicializar niveles en la máquina.

### 3.12 Configurar fianza

- **Botón:** Operaciones → **Configurar fianza**
- **Llamadas:**  
  1. `getPiecesCurrency` (POST index.php): para leer configuración actual y construir la lista de niveles.  
  2. `setDepositLevels` (POST index.php): `operation=setDepositLevels`, `levels` = JSON con `limitRecyclerCheck` y `config` (lista de niveles por denominación).  
  3. `startOperation` (POST index.php): type=**36**, `startnow=true`.  
  4. `acknowledgeOperationId` (POST).  
  5. `askOperation` (POST, opcional).  
  6. `finishOperation` (POST).  
- **Efecto:** Define y aplica la fianza (depósito) en la máquina.

### 3.13 Consultar fianza

- **Botón:** En el formulario de Movimientos, pestaña “Estado de fianza” (o acción que refresca fianza).
- **Llamada:** `getPiecesCurrency` (POST index.php): `currencyId=EUR`, `includeImages=0`, `includeLevels=1`.
- **Efecto:** Obtiene piezas por denominación y niveles; el módulo muestra el estado de fianza en la pestaña.

### 3.14 Consulta niveles

- **Botón:** “Consulta niveles” o “Consultar fianza” según contexto (refresco de la caja).
- **Llamada:** `getPiecesCurrency` (POST index.php) con `includeLevels=1`.
- **Efecto:** Rellena la pestaña “Estado niveles” (reciclador/casete por denominación).

La acción **Consultar fianza** usa la misma llamada y actualiza la pestaña “Estado de fianza”.  
El flujo interno **get_consult_levels** (type=12 + acknowledge + askOperation + finishOperation) se usa para “Consulta de niveles” con tipo 12 y permite obtener niveles vía askOperation; la vista principal de niveles se alimenta con getPiecesCurrency.

---

## 4. Llamadas auxiliares usadas por el módulo

| Operación | Endpoint | Descripción |
|-----------|----------|-------------|
| **acknowledgeOperationId** | index3.php (GET) o index.php (POST) | Confirma y arranca la operación ya encolada con el `operationId` dado. |
| **askOperation** | index3.php / index.php | Consulta el estado de una operación (p. ej. state, totalin, totalout, devices). |
| **askOperationExecuting** | index3.php / index.php | Consulta si hay una operación en ejecución (credenciales Exchange_Machine en algunos flujos). |
| **finishOperation** | index3.php (GET) | Finaliza la operación (`operationId`, `type=1` finalizar, `type=2` cancelar). |
| **setOperationImported** | index3.php (GET) | Marca la operación como importada/procesada por el Host (doc 5.7.6, 5.4.6, etc.). |
| **getMainCurrency** | index3.php | Moneda principal (canal Exchange_Machine). |
| **getInfoDevices** | index.php (POST) | Información de dispositivos (billetes/monedas, estado). |
| **getActiveCurrencies** | index.php (POST) | Monedas activas y niveles. |
| **getPiecesCurrency** | index.php (POST) | Piezas por moneda; con `includeLevels=1` devuelve niveles reciclador/casete. Usado para fianza y consulta niveles. |
| **get_retirada_web_url(operation_id)** | — | Construye la URL de la web CashDro para la retirada: `#/unload/<operationId>/true/`. |
| **get_cambio_web_url(operation_id)** | — | Construye la URL de la web para cambio: `#/splash/<operationId>/true` o `#/splash/true`. No se abre automáticamente en el flujo actual de “Cambio”. |

---

## 5. Tipos de operación (type) utilizados

| type | Operación en Odoo | Doc |
|------|-------------------|-----|
| 1 | Carga | 5.7 |
| 2 | Retirada | 5.8 |
| 3 | Pago (devolución/dispensa) | 5.3 |
| 4 | Venta (cobro) | 5.3 |
| 10 | Retirada casete billetes | 5.12 |
| 11 | Retirada casete monedas | 5.13 |
| 12 | Inicializar niveles / consulta niveles (flujo interno) | — |
| 16 | Ingresar (carga genérica) | 5.5 |
| 17 | Ingresar por importe | 5.6 |
| 18 | Cambio | 5.4 |
| 36 | Aplicar fianza (tras setDepositLevels) | — |

---

## 6. Dónde está implementado en el código

- **Gateway (todas las llamadas HTTP):** `gateway_integration.py` (raíz del addon).
- **Acciones y wizards:**  
  - Botones y método `_open_wizard`: `models/cashdro_caja_movimientos.py`.  
  - Wizards de operaciones: `models/cashdro_movimiento_wizards.py`.  
  - Wizard de fianza: `models/cashdro_movimiento_fianza_wizard.py`.
- **Consultar fianza / Consulta niveles:** `action_consultar_fianza` y `action_consulta_niveles` en `cashdro_caja_movimientos.py`, usando `get_pieces_currency`; el flujo type=12 para niveles está en `get_consult_levels` en el gateway.

Referencia oficial de cada operación: **CashDro Integración por Web Service v415.pdf**, secciones 5.3–5.13 y operaciones administrativas descritas en el documento.
