-- Script para limpiar referencias al wizard de Odoo BD
-- Ejecutar esto si el módulo falla por referencias cached al wizard

-- 1. Eliminar vistas XML relacionadas con wizard
DELETE FROM ir_ui_view WHERE model = 'cashdro.config.wizard';

-- 2. Eliminar acciones relacionadas
DELETE FROM ir_actions_act_window WHERE res_model = 'cashdro.config.wizard';

-- 3. Eliminar el modelo si existe en la tabla de modelos
DELETE FROM ir_model WHERE model = 'cashdro.config.wizard';

-- 4. Eliminar campos del modelo si existen
DELETE FROM ir_model_fields WHERE model_id IN (
    SELECT id FROM ir_model WHERE model = 'cashdro.config.wizard'
);

-- 5. Limpiar archivos XML en caché (opcional)
-- TRUNCATE TABLE ir_attachment WHERE res_model = 'ir.ui.view' AND name LIKE '%wizard%';

-- Para ejecutar en PostgreSQL:
-- psql -U odoo -d nombre_base_datos < CLEANUP_DB.sql

-- O directamente en psql:
-- \c nombre_base_datos
-- \i CLEANUP_DB.sql

-- IMPORTANTE: Hacer backup de la BD antes de ejecutar
-- Después de ejecutar, reiniciar Odoo
