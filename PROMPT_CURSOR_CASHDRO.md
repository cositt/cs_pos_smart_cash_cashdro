# Tarea: Migrar Gateway CashDro de Python a JavaScript OWL (Odoo 19)

## Contexto
Tenemos un módulo Odoo 19 (`cs_pos_smart_cash_cashdro`) que integra máquinas CashDro para pagos en punto de venta. El servidor Odoo corre en Docker en un cloud (red 10.0.4.x / 172.18.x.x) y **NO puede alcanzar la IP del CashDro (10.0.1.140)**. Los navegadores de los usuarios/quioscos **SÍ están en la red local** y pueden alcanzar al CashDro.

## La problemática de red
- Servidor Odoo (Docker cloud): red 10.0.4.x → **no tiene ruta a 10.0.1.140**
- CashDro físico en oficina del cliente: **10.0.1.140** (red local)
- Navegador del usuario/quiosco: **conectado a la red local 10.0.1.x** → sí alcanza al CashDro

Todas las operaciones actuales en Python (`gateway_integration.py`, `cashdro_caja_movimientos.py`, wizards) usan `requests.get()` desde el servidor, lo que falla con "Network is unreachable" o timeout. La única solución sin modificar infraestructura de red es **mover toda la lógica del gateway al cliente (JavaScript OWL)**.

---

## ✅ LO QUE YA FUNCIONA: Validación de conexión desde el navegador

Implementamos con éxito la validación de conexión CashDro ejecutándose **100% desde el navegador del cliente**. Este es el patrón a replicar para todas las demás operaciones.

### 1. Python: método vacío en el servidor

En `models/pos_payment_method.py`, el método `action_test_connection_client` **no hace ninguna petición HTTP**. Solo valida que los campos estén completos y retorna `True`:

```python
def action_test_connection_client(self):
    self.ensure_one()
    if not self.cashdro_enabled:
        raise ValidationError(_('Cashdrop no está habilitado'))
    if not self.cashdro_host or not self.cashdro_user or not self.cashdro_password:
        raise ValidationError(_('Por favor completa Host, Usuario y Contraseña'))
    return True  # No retorna ninguna acción, no hace requests
```

El botón en la vista XML sigue siendo `type="object"` como cualquier botón Odoo:
```xml
<button name="action_test_connection_client" type="object" 
        string="Probar Conexión (Cliente)" class="btn-primary"/>
```

### 2. JavaScript OWL: interceptar el clic antes de que llegue al servidor

En `static/src/js/cashdro_form_controller.js`, usamos **`patch()`** sobre `FormController.prototype` y sobreescribimos **`beforeExecuteActionButton()`**. Este método se ejecuta **antes** de que Odoo envíe la petición RPC al servidor.

**Lógica clave:**
- Detectamos si es el botón `action_test_connection_client`
- Detectamos si el modelo es `pos.payment.method`
- Si ambos coinciden: **ejecutamos la lógica CashDro en JavaScript y retornamos `false`**
- Retornar `false` detiene la cadena: **el servidor nunca recibe la petición**

```javascript
/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.notification = useService("notification");
    },

    async beforeExecuteActionButton(clickParams) {
        // Interceptar SOLO el botón de test en el modelo CashDro
        if (clickParams.name === "action_test_connection_client" 
            && this.model?.root?.resModel === "pos.payment.method") {
            
            // Obtener datos del formulario
            const data = this.model.root.data;
            const host = data.cashdro_host;
            const user = data.cashdro_user;
            const password = data.cashdro_password;

            // Validar campos
            if (!host || !user || !password) {
                this.notification.add("Por favor completa Host, Usuario y Contraseña", {
                    type: "warning",
                });
                return false;  // ← DETENER ejecución
            }

            // Notificación de "conectando..."
            this.notification.add("Conectando con CashDro desde navegador...", {
                type: "info",
            });

            // Fetch directo desde el navegador al CashDro
            const url = `https://${host}/Cashdro3WS/index.php`;
            const credentials = btoa(`${user}:${password}`);

            try {
                const response = await fetch(url, {
                    method: "GET",
                    headers: {
                        "Authorization": `Basic ${credentials}`,
                        "Content-Type": "application/json",
                    },
                    mode: "cors",
                    credentials: "omit",
                });

                if (response.ok) {
                    this.notification.add("Conexión exitosa con CashDro", {
                        type: "success",
                    });
                } else {
                    this.notification.add(`Error HTTP ${response.status}`, {
                        type: "danger",
                    });
                }
            } catch (error) {
                this.notification.add(`No se pudo conectar: ${error.message}`, {
                    type: "danger",
                    sticky: true,
                });
            }
            
            return false;  // ← DETENER ejecución, no llamar al servidor
        }
        
        // Para TODOS los demás botones, comportamiento normal
        return super.beforeExecuteActionButton(...arguments);
    }
});
```

### 3. Resultado
- El navegador hace `fetch()` a `https://10.0.1.140/Cashdro3WS/index.php`
- Recibe HTTP 200 OK directamente desde el CashDro
- Muestra notificación toast nativa de Odoo (success / danger)
- **El servidor Odoo nunca sabe que se pulsó el botón** (la petición RPC nunca se envía)

---

## 🔧 Qué necesitamos ahora: replicar este patrón para TODAS las operaciones

El gateway completo en Python (`gateway_integration.py`, ~800 líneas) debe migrarse a JavaScript. Las operaciones incluyen:

### Consultas simples (sin wizard)
- `action_consultar_fianza` → `getPiecesCurrency` con `include_levels='1'`
- `action_consulta_niveles` → `getPiecesCurrency` + parsear niveles de monedas/billetes

### Operaciones con importe (abren wizard)
- `action_pago` / `action_devolucion` / `action_cambio` / `action_ingresar` / `action_ingreso_importe`
- `action_carga` / `action_retirada` / `action_retirada_casete_monedas` / `action_retirada_casete_billetes`
- `action_inicializar_niveles` / `action_configurar_fianza`

Estos abren wizards donde el usuario introduce importe/concepto, y luego pulsa `action_execute` o `action_iniciar_*`.

### Wizards involucrados
- `cashdro.movimiento.pago.wizard` → `action_execute`
- `cashdro.movimiento.devolucion.wizard` → `action_execute`
- `cashdro.movimiento.cambio.wizard` → `action_execute`
- `cashdro.movimiento.ingresar.wizard` → `action_execute`
- `cashdro.movimiento.carga.wizard` → `action_iniciar_carga`
- `cashdro.movimiento.retirada.wizard` → `action_iniciar_retirada`
- `cashdro.movimiento.retirada.casete.monedas.wizard` → `action_iniciar`
- `cashdro.movimiento.retirada.casete.billetes.wizard` → `action_iniciar`
- `cashdro.movimiento.configurar.fianza.wizard` → `action_aplicar`

---

## 📋 API del CashDro (base: `https://{host}/Cashdro3WS/index.php`)

Todas las operaciones son **GET** con parámetros query string:

| Parámetro | Descripción |
|---|---|
| `operation` | Nombre de la operación |
| `name` | Usuario admin |
| `password` | Contraseña admin |

**Operaciones necesarias:**
1. **Implicit login**: Cada request lleva `name` + `password` en query params. No hay token separado.
2. **`getMainCurrency`** → obtiene moneda principal
3. **`getPiecesCurrency`** → obtiene niveles de monedas/billetes
   - `currency_id='EUR'`, `include_images='0'`, `include_levels='1'`
4. **`administrationOperation`** → iniciar operación
   - `operationType`: 1=venta, 2=devolución, 3=cambio, 4=pago, 5=ingresar, 6=retirar, 7=carga
   - `amount`: importe en céntimos (ej: 10.00€ = 1000)
   - `posid`: identificador POS (ej: "Terminal1")
   - `posuser`: usuario POS (ej: "Odoo")
   - `concept`: concepto descriptivo
   - Respuesta incluye `operationId`
5. **`askOperation`** → consultar estado de operación (polling)
   - `operationId`: ID devuelto por start
   - Debe llamarse cada ~2 segundos hasta que estado sea "finished"
6. **`acknowledgeOperation`** → confirmar operación completada
7. **`cancelOperation`** → cancelar operación pendiente

**Respuesta típica del CashDro:**
```json
{
  "code": 0,
  "response": {
    "errorMessage": "none",
    "operation": {
      "operationid": "12345",
      "state": "executing",
      ...
    }
  }
}
```

---

## 🏗️ Estrategia de implementación

### Paso 1: Servicio JavaScript CashDro
Crear un servicio OWL (`@web/core/service`) o una clase utilitaria en un módulo Odoo que encapsule:
- `login(user, password)` → valida credenciales con un fetch
- `startOperation(type, amount, concept, posid, posuser)` → devuelve `operationId`
- `askOperation(operationId)` → devuelve estado actual
- `pollUntilComplete(operationId, timeoutMs=180000)` → polling cada 2s, resuelve cuando `state === "finished"` o timeout
- `acknowledgeOperation(operationId)` → confirmar
- `cancelOperation(operationId)` → cancelar
- `getPiecesCurrency(currencyId='EUR')` → consultar niveles
- Parseo de respuestas: extraer `code`, `response.errorMessage`, `response.operation.*`

### Paso 2: Extender el interceptor en FormController
Ampliar `static/src/js/cashdro_form_controller.js` para cubrir:
- **Modelo `cashdro.caja.movimientos`**: interceptar `action_consultar_fianza`, `action_consulta_niveles`, y todas las operaciones
- **Wizards**: interceptar `action_execute`, `action_iniciar_*`, `action_aplicar` cuando el modelo del wizard sea uno de los `cashdro.movimiento.*.wizard`

**Para consultas simples** (fianza, niveles):
- Hacer fetch directo
- Mostrar resultado en notificación toast o actualizar campos del formulario vía `this.model.root.update()`
- Retornar `false`

**Para operaciones con wizard**:
- El wizard de Odoo se abre normalmente (campos de importe, etc.)
- Cuando el usuario pulsa `action_execute` dentro del wizard, el interceptor JS debe:
  1. Leer datos del wizard (importe, concepto)
  2. Llamar `startOperation()` → obtener `operationId`
  3. Mostrar notificación "Operación iniciada, inserte dinero en CashDro"
  4. Iniciar polling cada 2s con `askOperation()`
  5. Mostrar progreso al usuario (notificaciones toast o un modal/dialogo)
  6. Cuando estado es "finished":
     - Llamar `acknowledgeOperation()`
     - Hacer RPC a Odoo para crear/guardar el movimiento en BD (`this.orm.create('cashdro.caja.movimientos', {...})`)
     - Cerrar wizard (`this.env.dialogData?.close()` o recargar)
  7. Si timeout o cancelación: llamar `cancelOperation()` y notificar

### Paso 3: Persistencia en servidor (después del éxito)
Una vez la operación se completó en el CashDro desde JS, llamar al servidor SOLO para guardar:
```javascript
await this.orm.create("cashdro.caja.movimientos", {
    payment_method_id: this.model.root.data.payment_method_id[0],
    operation_type: "pago",  // o el tipo correspondiente
    amount: 10.00,
    state: "completed",
    cashdro_operation_id: operationId,
    // ... otros campos
});
```

El servidor Python recibe los datos finales y los guarda. **Nunca hace requests al CashDro**.

---

## 📁 Archivos a crear/modificar

**Nuevos:**
- `static/src/js/cashdro_gateway_service.js` — servicio/clase con todas las operaciones CashDro
- Posiblemente `static/src/js/cashdro_dialog.js` + `.xml` — modal de progreso durante polling

**Modificar:**
- `static/src/js/cashdro_form_controller.js` — ampliar interceptor para todos los botones
- `__manifest__.py` — asegurar que nuevos JS están en `web.assets_backend`
- `models/cashdro_caja_movimientos.py` — simplificar métodos de botones (solo validar, retornar True)
- `models/cashdro_movimiento_wizards.py` — simplificar `action_execute`/`action_iniciar_*` (solo validar, retornar True)

**No modificar (vistas XML se mantienen):**
- `views/cashdro_movimientos_views.xml` — botones existentes
- `views/cashdro_movimiento_wizard_views.xml` — wizards existentes

---

## ⚠️ Consideraciones técnicas

1. **CORS**: El CashDro debe aceptar `Origin` del servidor Odoo. Si no, las peticiones `fetch()` con `mode: "cors"` fallarán. Si el CashDro no soporta CORS, puede ser necesario `mode: "no-cors"` (pero entonces no se puede leer la respuesta). En nuestro caso la validación funcionó con CORS, así que presumiblemente el CashDro lo soporta.

2. **Credenciales**: El usuario/password del CashDro debe estar disponible en el formulario/wizard. Actualmente se obtienen del `payment_method_id` relacionado. Asegurar que los campos `gateway_user`, `gateway_password` estén en la vista o accesibles vía `this.model.root.data`.

3. **Polling**: Usar `setTimeout` recursivo, NO `setInterval`, para evitar solapamiento si una petición tarda más de 2 segundos.

4. **Cancelación**: El usuario debe poder cancelar durante el polling. Implementar un botón "Cancelar" en el diálogo de progreso que llame `cancelOperation()` y limpie el timeout.

5. **Modelo del wizard**: Para interceptar botones dentro de wizards, hay que detectar el `resModel` del wizard (ej: `cashdro.movimiento.pago.wizard`). El `FormController` del wizard es una instancia separada, así que el patch aplica también allí.

6. **Duplicación de lógica**: Todo lo que ahora está en `gateway_integration.py` (parseo de respuestas, manejo de errores, estructuras de datos) debe replicarse en JavaScript. Mantener los comentarios y docstrings originales como referencia.
