<p align="center">
  <img src="./static/icon.png" alt="CS POS Smart Cash CashDro" width="220" />
</p>

# CS POS Smart Cash CashDro - Módulo Odoo 19

Integración completa de máquinas de pago Cashdrop para puntos de venta en Odoo 19.

## Características

- ✅ Configuración por método de pago con validación
- ✅ Transacciones con sincronización en tiempo real
- ✅ 5 endpoints REST para operaciones de pago
- ✅ Polling automático con reintentos configurables
- ✅ Historial completo de transacciones con auditoría
- ✅ UI integrada en Odoo (vistas, menús, búsqueda)
- ✅ Control de acceso granular (ACL)
- ✅ Suite de 36 tests unitarios e integración
- ✅ Logging detallado con niveles configurables

## Arquitectura

```
models/
├── pos_payment_method.py       # Extensión con config Cashdrop
├── cashdro_transaction.py       # Registro de transacciones
└── res_config_settings.py       # Configuración global

controllers/
├── gateway_integration.py       # Cliente HTTP para Cashdrop
├── payment_method_integration.py # Orquestación de pagos
└── pos_payment.py              # 5 endpoints REST

views/
├── pos_payment_method_views.xml # UI para métodos de pago
├── cashdro_transaction_views.xml # UI para transacciones
├── res_config_settings_views.xml # Configuración
└── menu_views.xml              # Menú navegable

tests/
├── test_models.py              # Tests de modelos (22)
├── test_gateway_integration.py  # Tests de gateway (17)
└── test_payment_method_integration.py # Tests integración (17)
```

## Instalación

1. Copiar módulo a `custom_addons/`:
```bash
cp -r cs_pos_smart_cash_cashdro /path/to/odoo/addons/
```

2. Actualizar lista de aplicaciones en Odoo:
```
Configuración > Aplicaciones > Actualizar lista de aplicaciones
```

3. Instalar módulo:
```
Buscar "CS POS Smart Cash CashDro" e instalar
```

4. Configurar:
   - Ir a Configuración > Cashdrop > Configuración
   - Habilitar Cashdrop
   - Configurar URL del gateway y credenciales por defecto
   - Probar conexión

## Configuración

### Nivel Global (Settings)

**Ruta:** Configuración > Cashdrop > Configuración

| Campo | Defecto | Descripción |
|-------|---------|-------------|
| `cashdro_enabled` | False | Habilitar integración |
| `cashdro_default_gateway_url` | - | URL base (ej: `https://10.0.1.140`) |
| `cashdro_connection_timeout` | 10s | Timeout conexión HTTP |
| `cashdro_polling_timeout` | 180s | Timeout total de polling |
| `cashdro_polling_interval` | 500ms | Intervalo entre intentos |
| `cashdro_verify_ssl` | False | Verificar certificado SSL |
| `cashdro_max_retries` | 3 | Máximo reintentos en error |
| `cashdro_retry_delay` | 2s | Delay entre reintentos |
| `cashdro_auto_confirm_payments` | True | Confirmar automáticamente |
| `cashdro_log_level` | INFO | Nivel de logging (DEBUG/INFO/WARNING/ERROR) |

### Nivel Método de Pago

**Ruta:** POS > Configuración > Métodos de Pago > [Seleccionar] > Configuración Cashdrop

| Campo | Requerido | Descripción |
|-------|-----------|-------------|
| `cashdro_enabled` | Sí | Habilitar para este método |
| `cashdro_host` | Sí | IP/hostname (ej: `10.0.1.140`) |
| `cashdro_user` | Sí | Usuario de autenticación |
| `cashdro_password` | Sí | Contraseña |
| `cashdro_gateway_url` | Sí | URL completa del gateway |

## Endpoints REST

Base: `/cashdro/payment/`

### 1. Iniciar Pago
```
POST /cashdro/payment/start
Content-Type: application/json

{
    "order_id": 123,
    "payment_method_id": 456,
    "amount": 99.99,
    "pos_session_id": 789,               # opcional
    "user_credentials": {                 # opcional
        "user": "username",
        "password": "password"
    }
}
```

**Response (200):**
```json
{
    "success": true,
    "operation_id": "12345",
    "transaction_id": "uuid-string",
    "message": "Pago iniciado, esperando inserción de dinero"
}
```

### 2. Confirmar Pago
```
POST /cashdro/payment/confirm
Content-Type: application/json

{
    "transaction_id": "uuid-string",      # o
    "operation_id": "12345",              # operation_id
    "payment_method_id": 456              # opcional
}
```

**Response (200):**
```json
{
    "success": true,
    "transaction_id": "uuid-string",
    "amount_received": 99.99,
    "message": "Pago confirmado"
}
```

### 3. Cancelar Pago
```
POST /cashdro/payment/cancel
Content-Type: application/json

{
    "transaction_id": "uuid-string",
    "operation_id": "12345"               # o uno de estos dos
}
```

**Response (200):**
```json
{
    "success": true,
    "transaction_id": "uuid-string",
    "message": "Pago cancelado"
}
```

### 4. Obtener Estado
```
GET /cashdro/payment/status/{transaction_id}
```

**Response (200):**
```json
{
    "success": true,
    "status": "processing|confirmed|cancelled|error|timeout",
    "operation_id": "12345",
    "state": "P|F",
    "amount_received": 99.99,
    "message": "Estado obtenido"
}
```

### 5. Información de Transacción
```
POST /cashdro/payment/info
Content-Type: application/json

{
    "transaction_id": "uuid-string",
    "operation_id": "12345"               # o uno de estos
}
```

**Response (200):**
```json
{
    "success": true,
    "transaction": {
        "id": "uuid-string",
        "operation_id": "12345",
        "order_id": 123,
        "amount": 99.99,
        "amount_received": 99.99,
        "status": "confirmed",
        "created_at": "2026-03-03T14:30:00",
        "confirmed_at": "2026-03-03T14:31:00",
        "cancelled_at": null,
        "error_message": null,
        "user": "Administrator",
        "pos_session": "Session 001"
    }
}
```

## Errores

Todos los endpoints retornan:
```json
{
    "success": false,
    "error": "Descripción del error",
    "timestamp": "2026-03-03T14:30:00"
}
```

Códigos HTTP:
- `200` - Éxito
- `400` - Error validación o configuración
- `404` - Transacción no encontrada
- `500` - Error servidor

## Flujo de Pago

```
1. Cliente -> POST /start
   - Validar parámetros
   - Crear transacción (estado: processing)
   - Iniciar operación en Cashdrop
   - Retornar operation_id

2. Usuario inserta dinero en máquina

3. Cliente -> POST /confirm
   - Reconocer operación
   - Poll askOperation cada 500ms (max 60s)
   - Cuando state='F': actualizar monto_recibido
   - Cambiar estado a 'confirmed'
   - Retornar resultado

4. Si error:
   - POST /cancel o action_retry en formulario
   - Marcar como cancelled/error
```

## Estados de Transacción

| Estado | Descripción |
|--------|-------------|
| `processing` | Operación iniciada, esperando dinero |
| `confirmed` | Pago completado exitosamente |
| `cancelled` | Usuario/sistema canceló pago |
| `error` | Error en operación (reintentable) |
| `timeout` | Timeout esperando dinero (reintentable) |

## Testing

Ejecutar tests:
```bash
cd /path/to/odoo

# Todos los tests
python -m pytest custom_addons/cs_pos_smart_cash_cashdro/tests/ -v

# Tests específicos
python -m pytest custom_addons/cs_pos_smart_cash_cashdro/tests/test_models.py -v
python -m pytest custom_addons/cs_pos_smart_cash_cashdro/tests/test_gateway_integration.py -v
python -m pytest custom_addons/cs_pos_smart_cash_cashdro/tests/test_payment_method_integration.py -v

# Con cobertura
pytest custom_addons/cs_pos_smart_cash_cashdro/tests/ --cov=custom_addons.cs_pos_smart_cash_cashdro
```

## Logging

Los logs se guardan en:
- Odoo: `var/log/odoo.log`
- Módulo: buscar líneas con `cs_pos_smart_cash_cashdro`

Niveles configurables en **Configuración > Cashdrop > Logging y Depuración**

Ejemplos de logging:
```
DEBUG: "Intentando login en https://10.0.1.140 con usuario user"
INFO: "Login exitoso en https://10.0.1.140"
INFO: "Operación iniciada: operation_id=12345"
WARNING: "Error en polling, reintentando (1/3)"
ERROR: "Timeout esperando pago (operación_id=12345)"
```

## Permisos

Los siguientes grupos tienen acceso:

| Grupo | Acceso |
|-------|--------|
| Usuarios POS | Lectura/Creación/Edición de transacciones |
| Gerentes POS | Control total de transacciones |
| Administrador | Acceso a configuración global |

## Integración con Sale Order

Las transacciones se vinculan a órdenes de venta mediante:
- Campo `order_id` (Many2one -> sale.order)
- Validación de cascada (eliminar orden → eliminar transacciones)

## Notas

1. **SSL**: En desarrollo, `verify_ssl=False` es recomendado
2. **Timeouts**: Ajustar según latencia de red (default: 10s conexión, 180s polling)
3. **Reintentos**: Default 3 reintentos cada 2 segundos
4. **Secuencias**: Nombres automáticos con formato `TXN-202603-000001`
5. **Auditoría**: Todos los campos tienen create_date, write_date, user_id

## Troubleshooting

**"Timeout conectando a Cashdrop"**
- Verificar IP/URL del gateway
- Aumentar `cashdro_connection_timeout`
- Verificar conectividad: `ping 10.0.1.140`

**"Cashdrop respondió con código 401"**
- Verificar usuario/contraseña
- Confirmar credenciales en máquina Cashdrop

**"Timeout esperando pago"**
- Normal si usuario no inserta dinero a tiempo
- Aumentar `cashdro_polling_timeout` si es necesario
- Usar action_retry para reintentar

**Tests fallando**
- Asegurar `requests` library instalado: `pip install requests`
- Asegurar Odoo >= 19.0
- Ejecutar desde raíz del proyecto Odoo

## Desarrollo

### Estructura de commits

```
Sprint 1: Crear 3 modelos Odoo para Cashdrop
Sprint 2: Controllers y endpoints REST para pagos Cashdrop
Sprint 3: Vistas XML, menú y configuración de Odoo
Sprint 4: Suite completa de tests unitarios e integración
```

### Dependencias

```python
# Python
requests>=2.28.0

# Odoo
point_of_sale
sale
```

## Licencia

Este proyecto se distribuye bajo los términos de la **GNU Lesser General Public License v3.0 o posterior (LGPL-3.0-or-later)**, en línea con el estándar de módulos Odoo.

**Copyright (c) 2026 Cositt**  
Repositorio/organización: `https://github.com/cositt`

## Autor

Juan Cositt, Oz Agent
