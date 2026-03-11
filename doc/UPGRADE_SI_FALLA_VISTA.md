# Si el upgrade falla: "action_consultar_fianza no es una acción válida"

La vista exige que el modelo tenga los métodos `action_consultar_fianza` y `action_consulta_niveles`.  
Si el servidor (contenedor) tiene una versión antigua del Python, el upgrade falla.

**Qué hacer (en este orden):**

1. Copiar el archivo **actual** del addon al servidor:
   - Origen (en tu máquina): `custom_addons/cs_pos_smart_cash_cashdro/models/cashdro_caja_movimientos.py`
   - Destino en el servidor: la misma ruta dentro del addon que use Odoo (ej. `/mnt/custom-addons/cs_pos_smart_cash_cashdro/models/cashdro_caja_movimientos.py`).

2. **Reiniciar Odoo** para que cargue el Python nuevo (no basta con actualizar el módulo).

3. En Odoo, **Actualizar el módulo** de nuevo.

Comprobar que el archivo en el servidor contiene las líneas:
- `def action_consultar_fianza(self):`
- `def action_consulta_niveles(self):`

Si usas volumen Docker, asegúrate de que el directorio montado es el de tu proyecto (donde está este `.py` actualizado).
