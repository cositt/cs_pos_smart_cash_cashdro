# Verificar que el parche del Router se carga en Odoo

## 1. Regenerar assets en Odoo

El bundle `pos_self_order.assets` se genera al actualizar el módulo. Haz **una** de estas opciones:

- **Desde la interfaz**: Aplicaciones → buscar "CS POS Smart Cash CashDro" → botón **Actualizar** (Upgrade).
- **Desde línea de comandos** (con Odoo en la raíz del proyecto):
  ```bash
  ./odoo-bin -u cs_pos_smart_cash_cashdro -d TU_BASE_DE_DATOS --stop-after-init
  ```
- **Docker**: reiniciar el contenedor `web` después de actualizar el módulo, o ejecutar la actualización desde dentro del contenedor.

## 2. Forzar recarga del JS en el navegador

- Abre el **quiosco** (URL del self-order / kiosk).
- **Recarga forzada**: `Ctrl+Shift+R` (Windows/Linux) o `Cmd+Shift+R` (Mac), o abre la URL en una **ventana de incógnito**.
- Opcional: añade `?debug=assets` a la URL del quiosco para que Odoo regenere y sirva los assets en modo debug.

## 3. Comprobar que el parche se ejecutó

- Abre las **herramientas de desarrollador** del navegador (F12) y pestaña **Consola**.
- Recarga la página del quiosco.
- Debes ver este mensaje:
  ```text
  [CashDro] Router patch applied: template t-if/t-elif (no dynamic slot)
  ```
- **Si aparece**: el archivo `router_no_dynamic_slot_patch.js` se ha cargado y el Router tiene el template con `t-if`/`t-elif`.
- **Si no aparece**: el bundle antiguo sigue en uso. Repite el paso 1 (actualizar módulo), limpia caché del navegador o usa `?debug=assets` y recarga.

## 4. Comprobar que el parche está en el bundle (opcional)

- En las herramientas de desarrollador, pestaña **Red** (Network), recarga la página.
- Localiza la petición del bundle de JS del self-order (por ejemplo `pos_self_order.assets.js` o similar) y ábrela (ver código fuente).
- Busca en el código:
  - `Router patch applied` o
  - `activeSlot === 'default'`
- Si encuentras alguna de esas cadenas, el contenido del parche está incluido en el bundle que está sirviendo Odoo.

## 5. Si el OwlError sigue saliendo

- Si **sí** ves el mensaje `[CashDro] Router patch applied` pero el error **sigue**:
  - El VToggler que falla puede estar en **otro** componente (por ejemplo dentro de una página como ConfirmationPage o en el index), no en el Router.
  - En ese caso habría que localizar en qué template hay un `t-if`/`t-else` o slot que esté devolviendo un hijo sin `.mount`.
- Si **no** ves el mensaje:
  - El parche no se está cargando: revisa que el módulo esté actualizado, que el asset esté en `__manifest__.py` bajo `pos_self_order.assets` y que no haya errores en consola al cargar el JS.
