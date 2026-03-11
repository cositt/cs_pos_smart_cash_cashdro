# Resumen: CashDro en quiosco y módulo pos_self_order (Odoo 19)

**Documento de referencia** de todo lo realizado para permitir el pago con CashDro en modo quiosco del POS, incluyendo el uso del módulo **pos_self_order** de Odoo 19 y los pasos para que CashDro no cuente como “efectivo” (`is_cash_count = False`).

---

## 1. Módulo pos_self_order (Odoo 19)

### 1.1 Origen y ubicación

- **pos_self_order** es un módulo de **Odoo 19** (Enterprise) que aporta:
  - Autopedido (self-ordering): modo **móvil**, **quiosco** y **consulta**.
  - En **modo quiosco**, el cliente paga en el mismo dispositivo (pantalla táctil) antes de que la orden se envíe a cocina.
  - Controladores, vistas y assets del frontend del kiosk (PaymentPage, flujo de pago, etc.).

- En este proyecto el código de referencia está en:
  - `odoo-19.0/odoo-19.0/addons/pos_self_order/`
- En entornos **Docker**, para que Odoo tenga el módulo disponible, hay que asegurar que **pos_self_order** (y si aplica **pos_self_order_iot**) estén en el **addons-path** que usa el contenedor. Por ejemplo:
  - Copiar la carpeta `addons/pos_self_order` desde el árbol de Odoo 19 (o Enterprise) al directorio que monta el contenedor (p. ej. `/usr/lib/python3/dist-packages/odoo/addons/` o un volumen `/mnt/extra-addons`), de modo que la ruta final sea algo como:
    - `.../odoo/addons/pos_self_order`
  - El `docker-compose.yml` del proyecto define un `addons-path` que incluye, entre otros, `/usr/lib/python3/dist-packages/odoo/addons` y `/mnt/extra-addons`; **pos_self_order** debe estar en una de esas rutas para que se cargue.

### 1.2 Dependencias del addon CashDro

En `cs_pos_smart_cash_cashdro` el **__manifest__.py** declara:

```python
"depends": [
    "base",
    "sale",
    "point_of_sale",
    "pos_self_order",
    "pos_self_order_iot",
],
```

y los assets del kiosk se inyectan en el bundle del self-order:

```python
"assets": {
    "pos_self_order.assets": [
        "cs_pos_smart_cash_cashdro/static/src/js/cashdrop_pending_dialog.js",
        "cs_pos_smart_cash_cashdro/static/src/js/cashdrop_pending_dialog.xml",
        "cs_pos_smart_cash_cashdro/static/src/js/payment_page_cashdro_patch.js",
        "cs_pos_smart_cash_cashdro/static/src/js/self_order_cashdro_patch.js",
    ],
},
```

Sin **pos_self_order** (y en la ruta correcta en Docker/addons-path) el módulo CashDro no puede ofrecer pago en quiosco.

---

## 2. Restricción del core: prohibición de “efectivo” en quiosco

### 2.1 Dónde está la restricción

En **pos_self_order** (Odoo 19):

- **pos.config**  
  `addons/pos_self_order/models/pos_config.py` (aprox. líneas 220–224):

```python
@api.constrains("payment_method_ids", "self_ordering_mode")
def _onchange_payment_method_ids(self):
    if any(record.self_ordering_mode == 'kiosk' and any(pm.is_cash_count for pm in record.payment_method_ids) for record in self):
        raise ValidationError(_("You cannot add cash payment methods in kiosk mode."))
```

- **res.config.settings** (pos_self_order)  
  En el mismo addon, en `res_config_settings.py`, hay un `@api.onchange("pos_payment_method_ids")` que aplica la misma lógica: si modo kiosk y algún método tiene `is_cash_count`, lanza validación (mensaje tipo “You cannot add cash payment methods in kiosk mode.”).

Es decir: en modo **kiosk**, el core **no permite** ningún método de pago con **is_cash_count = True**.

### 2.2 Qué es `is_cash_count`

- En **point_of_sale** (`pos.payment.method`), el campo **is_cash_count** es un **campo computado almacenado**:
  - `compute="_compute_is_cash_count", store=True`
  - En el core: `pm.is_cash_count = (pm.type == 'cash')`.
- El **tipo** del método (`type`) viene del diario: si el diario es “cash”, el método se considera efectivo y **no hay casilla en la UI** para desmarcar “efectivo”; por tanto, no es posible “quitar efectivo” desde la interfaz para un método como “Efectivo cashdro”.

Conclusión: para poder usar **Efectivo cashdro** en quiosco sin tocar el core, hay que hacer que ese método **no cuente como efectivo** a efectos del constraint, es decir, que tenga **is_cash_count = False** cuando está habilitado como CashDro.

---

## 3. Pasos realizados para habilitar CashDro en quiosco (is_cash_count = False)

Se aplicaron **dos líneas de trabajo** (una por modelo, otra por constraint):

### 3.1 Opción A por código: override de `_compute_is_cash_count` (recomendada)

**Objetivo:** Que los métodos de pago con **CashDro habilitado** tengan **is_cash_count = False** sin cambiar la UI.

**Implementación:**

- En **cs_pos_smart_cash_cashdro/models/pos_payment_method.py** se extiende `pos.payment.method` y se sobrescribe **`_compute_is_cash_count`**:

```python
@api.depends('type', 'cashdro_enabled')
def _compute_is_cash_count(self):
    for pm in self:
        if getattr(pm, 'cashdro_enabled', False):
            pm.is_cash_count = False
        else:
            pm.is_cash_count = pm.type == 'cash'
```

- Efecto:
  - Si **Habilitar Cashdrop** está marcado (`cashdro_enabled = True`), el método **no** se considera efectivo para el constraint del core (`is_cash_count = False`).
  - El mensaje *"No puede agregar métodos de pago en efectivo al modo de quiosco"* (o el equivalente en inglés) **deja de aparecer** al añadir “Efectivo cashdro” a un POS en modo kiosk.
- No hace falta ninguna casilla nueva en la UI; basta con el checkbox existente “Habilitar Cashdrop” en el método de pago.

### 3.2 Recálculo al actualizar el módulo (post_init_hook)

Para que los **métodos CashDro ya existentes** pasen a tener `is_cash_count = False` en base de datos tras una actualización del módulo, en **__init__.py** del addon, dentro de **post_init_hook**, se añadió:

```python
PaymentMethod = env["pos.payment.method"]
cashdro_methods = PaymentMethod.search([("cashdro_enabled", "=", True)])
if cashdro_methods:
    cashdro_methods._compute_is_cash_count()
    cashdro_methods.flush_recordset(["is_cash_count"])
```

Así, al **actualizar** `cs_pos_smart_cash_cashdro`, todos los métodos con CashDro habilitado quedan con `is_cash_count` recalculado y persistido.

### 3.3 Opción B: sustituir el constraint del core (pos.config)

**Objetivo:** Que la validación en **pos.config** permita explícitamente “efectivo CashDro” en kiosk.

**Implementación:**

1. **Nuestro constraint (sustituto)**  
   En **cs_pos_smart_cash_cashdro/models/pos_config.py** se define un `@api.constrains("payment_method_ids", "self_ordering_mode")` en `pos.config` que:
   - Solo prohíbe métodos que son **efectivo Y no CashDro**:  
     `pm.is_cash_count and not getattr(pm, "cashdro_enabled", False)`  
   - Lanza un mensaje del tipo: *"No puede agregar métodos de pago en efectivo al modo de quiosco, excepto Cashdrop."*

2. **Quitar el constraint del core en registro**  
En el **post_init_hook** del addon (**__init__.py**) se modifica la clase `pos.config` del registro para **eliminar** el constraint original de **pos_self_order** (`_onchange_payment_method_ids` que bloquea todo efectivo en kiosk), de modo que solo quede nuestro constraint que hace la excepción CashDro:

```python
PosConfig = env["pos.config"].__class__
if hasattr(PosConfig, "_constrains"):
    new_constrains = {}
    for name, (func, fields, msg) in PosConfig._constrains.items():
        if (
            func.__name__ == "_onchange_payment_method_ids"
            and "payment_method_ids" in fields
            and "self_ordering_mode" in fields
            and getattr(func, "__module__", "").startswith("odoo.addons.pos_self_order")
        ):
            continue
        new_constrains[name] = (func, fields, msg)
    PosConfig._constrains = new_constrains
```

- **Importante:** Este hook solo se ejecuta al **instalar o actualizar** el módulo `cs_pos_smart_cash_cashdro`; si el upgrade no se ejecutó contra la base correcta (p. ej. en Docker con otra BD por defecto), el constraint del core podría seguir activo. La **Opción A** (override de `_compute_is_cash_count`) evita depender de ese parche: con `is_cash_count = False` para CashDro, el constraint del core simplemente no se dispara.

### 3.4 Carga de métodos de pago en quiosco (`_load_pos_self_data_domain`)

**Problema detectado:**  
Incluso con el constraint resuelto, el flujo del quiosco seguía ignorando los métodos de pago y enviando las órdenes directamente a cocina. La causa era que el modelo `pos.payment.method` de **pos_self_order** define:

```python
@api.model
def _load_pos_self_data_domain(self, data, config):
    return [('id', '=', False)]
```

Es decir, el quiosco **no cargaba ningún método de pago**. Como consecuencia:

- `SelfOrder.hasPaymentMethod()` devolvía `False`.
- En `SelfOrder.confirmOrder()`, al no haber métodos de pago, el flujo tomaba la rama de “no hay pagos en kiosk” y llevaba la orden directa a cocina sin pasar por la página de pago.

**Solución aplicada (nuestro addon):**

En `cs_pos_smart_cash_cashdro/models/pos_payment_method.py` se sobrescribe `_load_pos_self_data_domain` para el modo quiosco:

```python
@api.model
def _load_pos_self_data_domain(self, data, config):
    if config.self_ordering_mode == "kiosk":
        # En kiosk: devolver exactamente los métodos de pago configurados en el POS.
        return [("id", "in", config.payment_method_ids.ids)]
    # Otros modos: respetar el comportamiento estándar de pos_self_order.
    return super()._load_pos_self_data_domain(data, config)
```

Y se amplían los campos cargados para incluir el flag de CashDro:

```python
@api.model
def _load_pos_self_data_fields(self, config):
    fields = super()._load_pos_self_data_fields(config)
    if config.self_ordering_mode == "kiosk" and "cashdro_enabled" not in fields:
        fields = list(fields) + ["cashdro_enabled"]
    return fields
```

Efectos:

- En modo **quiosco**, el endpoint `/pos-self/data/<config_id>` devuelve todos los métodos de pago asignados al POS (incluido **Efectivo cashdro**).
- `SelfOrder.hasPaymentMethod()` pasa a ser `True`, por lo que `confirmOrder()` navega a la **PaymentPage** y no salta directamente a la confirmación.
- El parche de frontend `self_order_cashdro_patch.js` puede identificar CashDro con seguridad mediante `pm.cashdro_enabled === true` (además del nombre para compatibilidad) y añadirlo a la lista de métodos considerados válidos para ir a la pantalla de pago.

---

## 4. Resumen de archivos implicados

| Tema | Archivo |
|------|--------|
| pos_self_order (origen) | `odoo-19.0/odoo-19.0/addons/pos_self_order/` (y en Docker, la copia en el addons-path del contenedor) |
| Constraint core kiosk | `pos_self_order/models/pos_config.py` → `_onchange_payment_method_ids` |
| is_cash_count en core | `point_of_sale/models/pos_payment_method.py` → `_compute_is_cash_count`, `is_cash_count` |
| Override is_cash_count para CashDro | `cs_pos_smart_cash_cashdro/models/pos_payment_method.py` → `_compute_is_cash_count` |
| Carga de métodos pago kiosk | `cs_pos_smart_cash_cashdro/models/pos_payment_method.py` → `_load_pos_self_data_domain`, `_load_pos_self_data_fields` |
| Constraint nuestro en pos.config | `cs_pos_smart_cash_cashdro/models/pos_config.py` → `_onchange_payment_method_ids` |
| Hook y recálculo is_cash_count | `cs_pos_smart_cash_cashdro/__init__.py` → `post_init_hook` |
| Dependencias y assets kiosk | `cs_pos_smart_cash_cashdro/__manifest__.py` |

---

## 5. Pasos para el usuario: habilitar CashDro en quiosco

1. **Asegurar pos_self_order en el addons-path**  
   En Docker (o en la instalación), que la carpeta **pos_self_order** de Odoo 19 esté en una ruta incluida en `--addons-path` (p. ej. copiada a `/usr/lib/python3/dist-packages/odoo/addons/pos_self_order` o en `/mnt/extra-addons`).

2. **Instalar o actualizar el módulo**  
   Instalar/actualizar **cs_pos_smart_cash_cashdro** contra la base de datos correcta para que se ejecute el `post_init_hook` (recálculo de `is_cash_count` y, si aplica, parche de constraints).

3. **Configurar el método de pago**  
   En **Ajustes → Métodos de pago** (o desde el menú CashDro): crear o editar el método “Efectivo cashdro”, asignar diario de tipo efectivo, marcar **Habilitar Cashdrop** y rellenar Host, Usuario y Contraseña. Guardar.

4. **Añadir el método al POS en modo quiosco**  
   En **Punto de venta → Configuración** del POS que usa modo **Quiosco**, en “Métodos de pago”, añadir **Efectivo cashdro** y guardar. No debería aparecer el error de “no se puede agregar métodos de pago en efectivo al modo de quiosco”, porque para ese método `is_cash_count` es False cuando CashDro está habilitado.

5. **Probar el flujo**  
   En el kiosk, elegir pago con CashDro, completar el pago en la máquina y confirmar; la orden debe tramitarse a cocina según lo descrito en `IMPLEMENTACION_CASHDROP_KIOSK.md` y `FLUJO_PAGOS.md`.

---

## 6. Referencia cruzada con otros documentos

- **Flujo de pagos y rutas kiosk:** `doc/FLUJO_PAGOS.md`, `doc/IMPLEMENTACION_CASHDROP_KIOSK.md`
- **Llamadas al Web Service CashDro:** `doc/LLAMADAS_WEB_SERVICE_CASHDRO.md`
- **Especificación general:** `doc/ESPECIFICACION_CASHDRO_POS.md`

Este documento resume el contexto de **pos_self_order**, la restricción de efectivo en quiosco y los **pasos realizados para que CashDro quede habilitado en quiosco con is_cash_count = False** (override del computed y, opcionalmente, sustitución del constraint del core en el registro).
