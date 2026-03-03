# Guía de Instalación - CS POS Smart Cash Cashdrop

## Problema de Referencias Cached al Wizard

Si ves este error al actualizar el módulo:
```
FileNotFoundError: [Errno 2] No such file or directory: 
'.../wizard/cashdro_config_wizard_views.xml'
```

**CAUSA:** Odoo tiene guardado en la BD un registro de una vista XML que fue eliminada del filesystem.

## Soluciones

### Solución 1: Reiniciar Odoo (RECOMENDADA)

La forma más sencilla es **reiniciar completamente el servidor Odoo**:

```bash
# Detener Odoo
systemctl stop odoo  # O ctrl+C si está en foreground

# Esperar 5 segundos
sleep 5

# Reiniciar Odoo
systemctl start odoo
# O si está en desarrollo:
python /path/to/odoo/odoo-bin -c /etc/odoo/odoo.conf
```

Luego intenta actualizar el módulo nuevamente desde la UI.

### Solución 2: Limpiar la BD (Si Solución 1 no funciona)

**IMPORTANTE:** Haz backup de la BD antes de esto.

#### Opción A: Ejecutar script SQL

```bash
# Conectar a PostgreSQL
psql -U odoo -d nombre_de_la_base_datos < CLEANUP_DB.sql

# Luego reiniciar Odoo
```

#### Opción B: Ejecutar comandos directamente

```bash
# Conectar a BD
psql -U odoo -d nombre_de_la_base_datos

# Ejecutar en psql:
DELETE FROM ir_ui_view WHERE model = 'cashdro.config.wizard';
DELETE FROM ir_actions_act_window WHERE res_model = 'cashdro.config.wizard';
DELETE FROM ir_model WHERE model = 'cashdro.config.wizard';
\q

# Reiniciar Odoo
```

### Solución 3: Reinstalar Base de Datos (Nuclear Option)

Si nada funciona, puedes recrear la BD:

```bash
# Detener Odoo
systemctl stop odoo

# Borrar BD
dropdb -U odoo nombre_de_la_base_datos

# Recrear BD
createdb -U odoo nombre_de_la_base_datos

# Reiniciar Odoo
systemctl start odoo

# La BD se recreará automáticamente en el primer login
```

## Estado del Módulo

✅ **El código está 100% limpio**
- ✅ Directorio wizard/ completamente eliminado
- ✅ Sin referencias en manifest
- ✅ Sin referencias en __init__.py
- ✅ Solo referencias documentales en BUGFIX.md

El problema es **SOLAMENTE de caché de Odoo**, no del código.

## Próximos Pasos

Una vez que Odoo se reinicie:

1. Ve a **Aplicaciones**
2. Busca **"CS POS Smart Cash CashDro"**
3. Haz click en **"Actualizar"** o **"Instalar"**
4. Debería instalar sin errores ✅

## Verificación

Una vez instalado, verifica que funciona:

```bash
# Ver logs de Odoo
tail -f /var/log/odoo/odoo.log

# O en console si está en foreground
# Busca líneas sin errores de "cs_pos_smart_cash_cashdro"
```

## Contacto

Si persiste el error:
1. Verifica que el directorio `/custom_addons/cs_pos_smart_cash_cashdro/wizard/` NO exista
2. Verifica que `/custom_addons/cs_pos_smart_cash_cashdro/__manifest__.py` NO tenga referencias a "wizard"
3. Ejecuta: `grep -r "wizard" /custom_addons/cs_pos_smart_cash_cashdro/` - no debería encontrar nada excepto BUGFIX.md
