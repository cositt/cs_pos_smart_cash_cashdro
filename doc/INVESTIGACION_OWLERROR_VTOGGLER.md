# Investigación: OwlError "this.child.mount is not a function"

## Resumen

Tras cerrar el flujo completo de pago CashDro en quiosco (overlay → confirmación backend → navegación a página de confirmación), la orden se tramita correctamente pero en consola aparece un **OwlError** con causa `TypeError: this.child.mount is not a function` en `VToggler.mount`. Este documento recoge el análisis de origen y las opciones para arreglarlo **sin modificar aún el código**.

---

## 1. Stack del error

```
OwlError: An error occured in the owl lifecycle (see this Error's "cause" property)
Caused by: TypeError: this.child.mount is not a function
    at VToggler.mount (pos_self_order.assets.js:8914)
    at B.mount (pos_self_order.assets.js:10010)
    at B.mount (pos_self_order.assets.js:9906)
    at ComponentNode.mount (pos_self_order.assets.js:11499)
    at VMulti.mount (pos_self_order.assets.js:9362)
    at ComponentNode.mount (pos_self_order.assets.js:11499)
    at VList.patch (pos_self_order.assets.js:10231)
    at B.patch (pos_self_order.assets.js:10045)
    at ComponentNode._patch (pos_self_order.assets.js:11529)
    at RootFiber.complete (pos_self_order.assets.js:10597)
```

Conclusión inmediata:

- El fallo ocurre **al hacer patch** (actualización del árbol de Owl), no en el primer montaje.
- Intervienen **VList.patch** → **VMulti** → **ComponentNode** → **VToggler.mount**.
- En ese momento, un **VToggler** tiene un **child** que no tiene método `.mount` (no es un nodo válido de blockdom).

---

## 2. Dónde está el VToggler: Router y slot dinámico

### 2.1 Template del Router (pos_self_order)

```js
// pos_self_order/static/src/app/router.js
static template = xml`<t t-slot="{{activeSlot}}" t-props="slotProps"/>`;
```

- El Router tiene un **único hijo**: un **slot dinámico** cuyo nombre es `activeSlot` (ej. `"payment"`, `"confirmation"`) y al que se le pasan `slotProps`.
- Al cambiar de ruta (p. ej. de payment a confirmation), `activeSlot` y `slotProps` cambian y Owl re-renderiza el Router.

### 2.2 Cómo compila Owl un `t-slot` dinámico (owl.js)

Para un slot **dinámico** y **sin** contenido por defecto, el compilador genera algo equivalente a:

```js
toggler(slotName, callSlot(ctx, node, key, slotName, true, scope))
```

Es decir:

- Se crea un **VToggler** cuya clave es el nombre del slot (`activeSlot`) y cuyo **child** es el resultado de **callSlot(...)**.
- En cada render, `callSlot` devuelve el contenido del slot activo; ese valor es el `child` del VToggler.

Referencia en `owl.js` (aprox. líneas 4892–4896):

- Si `dynamic === true` y no hay `defaultContent`:  
  `blockString = 'toggler(' + name + ', callSlot(ctx, node, ' + key + ', ' + name + ', ' + dynamic + ', ' + scope + '))'`.

### 2.3 Qué hace callSlot (owl.js ~3049)

```js
function callSlot(ctx, parent, key, name, dynamic, extra, defaultContent) {
    key = key + "__slot_" + name;
    const slots = ctx.props.slots || {};
    const { __render, __ctx, __scope } = slots[name] || {};
    const slotScope = ObjectCreate(__ctx || {});
    if (__scope) {
        slotScope[__scope] = extra;  // p. ej. extra = slotProps → scope "url"
    }
    const slotBDom = __render ? __render(slotScope, parent, key) : null;
    if (defaultContent) {
        // Router no usa defaultContent
    }
    return slotBDom || text("");
}
```

- Si existe el slot `name` y tiene `__render`, el contenido del slot es **`slotBDom = __render(slotScope, parent, key)`**.
- Si no hay slot o no hay `__render`, se devuelve **`text("")`** (nodo de texto, que sí tiene `.mount`).

Por tanto, el único modo de que el **child** del VToggler no tenga `.mount` es que **`__render(slotScope, parent, key)` devuelva algo que no sea un nodo blockdom válido** (por ejemplo `undefined`, un objeto plano, o algo que no implemente `.mount`).

---

## 3. De dónde sale el slot "confirmation"

En `self_order_index.xml`:

```xml
<Router t-if="selfIsReady" pos_config_id="selfOrder.config.id">
    ...
    <t t-set-slot="confirmation" route="..." t-slot-scope="url">
        <ConfirmationPage orderAccessToken="url.orderAccessToken" screenMode="url.screenMode" />
    </t>
    ...
</Router>
```

- El slot `confirmation` tiene **t-slot-scope="url"**: al invocarlo, Owl pasa `slotProps` como `url` (p. ej. `{ orderAccessToken, screenMode }`).
- El contenido del slot es un **solo componente**: `<ConfirmationPage ... />`.
- En condiciones normales, ese contenido se compila a un `__render` que debería devolver un **ComponentNode** (o un bloque que contenga uno), que sí tiene `.mount`.

Conclusión: el error aparece cuando, **en el momento del patch** (cambio de payment → confirmation), el resultado de **llamar a `__render` del slot "confirmation"** no es un nodo con `.mount`. Posibles causas:

1. **`ctx.props.slots`** en el Router no es el esperado en ese ciclo de render (p. ej. slot `confirmation` ausente o con `__render` distinto).
2. **`__render`** del slot confirmation devuelve `undefined` o un valor no bloque en algún caso (p. ej. scope `url` mal formado o props inválidas).
3. **Condición de carrera**: el cambio de ruta (p. ej. `confirmationPage()` o `requestAnimationFrame`) hace que el Router re-renderice en un momento en que el árbol de slots o el contexto no están listos, y esa combinación produce un retorno no-nodo.

El stack con **VList.patch** sugiere que el VToggler está dentro de un **Block** que tiene varios hijos (lista de bloques). Eso encaja con que el template compilado del Router tenga una estructura tipo “multi” o lista de bloques, y uno de ellos sea el VToggler del slot dinámico.

---

## 4. Flujo que dispara el error (CashDro)

1. Usuario paga en máquina CashDro; el backend confirma y responde éxito.
2. Frontend: se cierra el overlay, se muestra notificación y se llama a  
   `this.selfOrder.confirmationPage("pay", "kiosk", accessToken)`  
   (en nuestro caso a veces envuelto en `requestAnimationFrame`).
3. Eso hace `router.navigate("confirmation", { orderAccessToken, screenMode })` → cambia la URL y el estado del router.
4. En el **siguiente render**, el Router tiene `activeSlot === "confirmation"` y `slotProps === { orderAccessToken, screenMode }`.
5. Owl re-renderiza el Router; se evalúa de nuevo  
   `toggler("confirmation", callSlot(ctx, node, key, "confirmation", true, slotProps))`.
6. Si en ese momento **callSlot** devuelve algo sin `.mount`, al hacer **patch** del VToggler anterior (slot "payment") contra este nuevo VToggler, Owl intenta **montar** el nuevo `child` y se produce `this.child.mount is not a function`.

---

## 5. Posibles causas técnicas (resumen)

| Hipótesis | Descripción |
|-----------|-------------|
| **A. Slot "confirmation" no disponible en ese render** | En el ciclo donde ya `activeSlot === "confirmation"`, `ctx.props.slots["confirmation"]` podría ser `undefined` o no tener `__render`. Entonces `callSlot` devolvería `text("")`. Los nodos `text` sí tienen `.mount`, así que esto por sí solo no explica el error a menos que en el bundle se use otra variante de `callSlot`/`text`. |
| **B. __render del slot devuelve un no-nodo** | El template compilado del slot (ConfirmationPage con props desde `url`) podría, en algún borde (props undefined, error interno), devolver `undefined` o un valor que no sea un bloque. Ese valor se convierte en `child` del VToggler y falla en `.mount`. |
| **C. Orden/timing de actualización** | `matchURL()` se ejecuta en `onWillRender` del Router. Si la URL y el estado del router se actualizan en un momento raro respecto al ciclo de render del padre (selfOrderIndex), podría haber un frame donde `activeSlot` ya es "confirmation" pero `props.slots` aún corresponde a un estado anterior o a otro componente. |
| **D. VList en otro nivel** | El VList.patch podría corresponder a otro listado (p. ej. métodos de pago en PaymentPage u otra lista dentro de una página). Pero el stack apunta a un **mount** (no solo patch de hijos ya montados), y el mount que falla es el del **child** del VToggler, lo que encaja con “contenido del slot activo” en el Router. |

La explicación más coherente con el código de Owl y pos_self_order es **B** o **C**: que en el momento del cambio de slot, el resultado de renderizar el slot "confirmation" no sea un nodo con `.mount`, o que el contexto (props.slots / scope) no sea el correcto para ese render.

---

## 6. Opciones de arreglo (sin implementar aún)

### 6.1 Asegurar que el slot nunca devuelva un no-nodo (Owl / pos_self_order)

- **Dónde**: En el runtime de Owl, en `callSlot`, garantizar que el retorno sea siempre un nodo blockdom (p. ej. si `slotBDom` es falsy o no tiene `.mount`, devolver `text("")` y usar ese como child del VToggler).
- **Ventaja**: Elimina el fallo para cualquier slot dinámico que devuelva algo raro.
- **Inconveniente**: Requiere tocar `owl.js` (o un wrapper del slot) y puede enmascarar bugs en los templates.

### 6.2 Evitar el slot dinámico en el Router

- **Dónde**: En pos_self_order, cambiar el Router para que **no** use `<t t-slot="{{activeSlot}}" t-props="slotProps"/>`. Por ejemplo, usar un `t-if` / `t-elif` por cada ruta y renderizar explícitamente `<PaymentPage />`, `<ConfirmationPage ... />`, etc., según `activeSlot`.
- **Ventaja**: Ya no se usa el VToggler generado por el slot dinámico; cada ruta es un componente explícito y se evita el caso donde callSlot devuelve un no-nodo.
- **Inconveniente**: Template más largo y más difícil de mantener; hay que mantener a mano la lista de rutas.

### 6.3 Normalizar navegación y estado antes de cambiar de slot

- **Dónde**: En nuestro patch de CashDro (o en pos_self_order), antes de llamar a `confirmationPage()` / `router.navigate("confirmation", ...)`:
  - Asegurar que `slotProps` esté ya rellenado (orderAccessToken, screenMode).
  - Forzar un tick (o un requestAnimationFrame) y que la navegación ocurra cuando el árbol esté estable (por ejemplo después de que el overlay se haya quitado y no haya actualizaciones pendientes del PaymentPage).
- **Ventaja**: Puede evitar la condición de carrera (hipótesis C).
- **Inconveniente**: Si el fallo es por __render devolviendo un no-nodo (B), esto no lo arregla.

### 6.4 Wrapper del contenido del slot "confirmation"

- **Dónde**: En pos_self_order, en el template del index, en lugar de  
  `<ConfirmationPage orderAccessToken="url.orderAccessToken" screenMode="url.screenMode" />`  
  usar un componente intermedio que reciba `url` y que siempre renderice un nodo (p. ej. un div con un componente dentro, o un componente que en `render` nunca devuelva undefined).
- **Ventaja**: Si el fallo viene de ConfirmationPage o de cómo se pasan las props, el wrapper puede asegurar que el slot siempre devuelva un bloque válido.
- **Inconveniente**: Requiere tocar pos_self_order y un poco de estructura.

### 6.5 Reportar a Odoo con mínimo caso reproducible

- Reproducir el error en un build limpio de pos_self_order (navegación de payment a confirmation con un método que use el mismo flujo que CashDro).
- Documentar stack, versión de Owl y de pos_self_order.
- Proponer un parche tipo 6.1 (callSlot siempre devuelve un nodo) o 6.2 (evitar slot dinámico en Router) como sugerencia upstream.

---

## 7. Siguientes pasos recomendados

1. **Reproducir con logs**: En desarrollo, añadir un log temporal en el Router (o en un monkey-patch de `callSlot`) para ver, cuando `activeSlot === "confirmation"`, el valor de `ctx.props.slots["confirmation"]` y el tipo/valor retornado por `__render(slotScope, parent, key)`. Así se confirma si el fallo es por slot ausente (A), retorno no-nodo (B) o timing (C).
2. **Probar 6.2 en fork**: En una copia local de pos_self_order, sustituir el slot dinámico del Router por un `t-if`/`t-elif` por ruta y comprobar si el error desaparece. Si sí, confirma que el problema está en el uso del slot dinámico + VToggler.
3. **Decidir enfoque**:
   - Si no quieres tocar Odoo: intentar solo 6.3 (nuestro lado) y, si no basta, 6.4 en un módulo que extienda pos_self_order.
   - Si puedes tocar el addon: implementar 6.2 o 6.4 y, si es posible, enviar 6.1 o 6.2 como propuesta a Odoo.

---

## 8. Referencias de código (odoo-19.0)

- **VToggler** y **toggler**: `addons/web/static/lib/owl/owl.js` ~líneas 35–84.
- **callSlot**: `addons/web/static/lib/owl/owl.js` ~3049–3070.
- **Compilación de t-slot dinámico**: `addons/web/static/lib/owl/owl.js` ~4888–4900.
- **Router**: `addons/pos_self_order/static/src/app/router.js`.
- **Index y slots**: `addons/pos_self_order/static/src/app/self_order_index.xml`.
- **ConfirmationPage**: `addons/pos_self_order/static/src/app/pages/confirmation_page/confirmation_page.js` y `.xml`.

---

*Documento generado sin aplicar cambios en el código; solo análisis y opciones para decidir el arreglo del OwlError.*
