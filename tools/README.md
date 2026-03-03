# Herramientas Cashdrop - Documentación

Este directorio contiene las herramientas y scripts para integración con la máquina Cashdrop.

## Archivos

### 1. `CashdropAPI_v2.py`
Cliente Python para comunicación con la API de Cashdrop.

**Características:**
- Autenticación con usuario/contraseña
- Manejo de errores
- Context manager para gestión de sesiones
- Métodos para operaciones de API confirmadas

**Uso:**
```python
from CashdropAPI_v2 import CashdropAPI

client = CashdropAPI(
    base_url='https://10.0.1.140',
    username='admin',
    password='3428',
    verify_ssl=False
)

# Login
client.login()

# Obtener datos del usuario
user = client.get_user()

# Obtener piezas disponibles
pieces = client.get_pieces_currency('EUR')

# Como context manager
with CashdropAPI('https://10.0.1.140', 'admin', '3428') as api:
    user = api.get_user()
```

---

### 2. `cashdrop_gateway.py`
**Gateway Flask** - Servidor intermedio entre Odoo POS y Cashdrop.

**Características:**
- ✅ API REST con endpoints para pagos, información de máquina
- ✅ Autenticación automática con Cashdrop
- ✅ Manejo de transacciones
- ✅ Operaciones de cash in/out (simuladas por ahora)
- ✅ Manejo completo de errores

**Endpoints:**
- `GET /health` - Estado del gateway
- `GET /status` - Estado de máquina
- `GET /pieces/<currency>` - Piezas disponibles
- `POST /pay` - Iniciar pago
- `GET /payment/<id>/status` - Estado de pago
- `POST /payment/<id>/confirm` - Confirmar pago
- `POST /payment/<id>/cancel` - Cancelar pago
- `POST /cash-in` - Ingreso de efectivo
- `POST /cash-out` - Retiro de efectivo

**Ejecución:**
```bash
python cashdrop_gateway.py
```

El gateway se ejecutará en `http://localhost:5000`

**Documentación completa:** Ver `GATEWAY_DOCS.md`

---

### 3. `discover_payment_v2.py`
Script mejorado para **descubrir la operación de pago** en Cashdrop.

**Estrategia:**
1. Prueba 34 variaciones de nombres de operación
2. Si no encuentra coincidencias, prueba con parámetros (amount, currency)
3. Reporta todas las operaciones exitosas encontradas

**Operaciones probadas:**
- `pay`, `payment`, `processPayment`, `makePayment`, `acceptPayment`
- `transaction`, `processTransaction`, `chargePayment`
- `cashPayment`, `cashTransaction`, `cashOut`, `cashIn`
- `transfer`, `exchange`, `deposit`, `withdraw`
- Y más...

**Ejecución:**
```bash
python discover_payment_v2.py
```

**Salida esperada:**
```
======================================================================
DESCUBRIDOR DE OPERACIÓN DE PAGO - CASHDROP
======================================================================

[1/3] Autenticando...
✅ Autenticado

[2/3] Probando operaciones SIN parámetros adicionales...
------
❌ pay                       → code=0
❌ payment                   → code=0
...

RESULTADOS
======================================================================
✅ ENCONTRADA OPERACIÓN EXITOSA:

1. Operación: chargePayment
   Parámetros: {}
   Respuesta: {"code": 1, "data": {...}}
```

---

### 4. `test_gateway.py`
Suite de pruebas **automática** para el gateway Flask.

**Pruebas incluidas:**
1. Health check
2. Obtención de estado de máquina
3. Obtención de piezas
4. Flujo completo de pago
5. Cancelación de pago
6. Operaciones de cash in/out
7. Casos de error (validación)

**Ejecución:**
```bash
# Terminal 1: Ejecutar gateway
python cashdrop_gateway.py

# Terminal 2: Ejecutar pruebas
python test_gateway.py
```

**Salida:**
```
████████████████████████████████████████████████████████████████████
█                                                                    █
█                    CASHDROP GATEWAY - TEST SUITE                  █
█                                                                    █
████████████████████████████████████████████████████████████████████

Conectando a http://localhost:5000...
✅ Gateway accesible

======================================================================
  TEST 1: Health Check
======================================================================

✅ PASS | GET /health
  Status: 200
  Body: {
    "status": "ok",
    "authenticated": true
  }

[...más pruebas...]

======================================================================
  RESUMEN DE PRUEBAS
======================================================================

  Total: 15
  Pasadas: 15 ✅
  Fallidas: 0 ❌

  🎉 ¡TODAS LAS PRUEBAS PASARON!
```

---

### 5. `GATEWAY_DOCS.md`
Documentación completa del gateway Flask.

Incluye:
- Arquitectura del sistema
- Referencia completa de API
- Flujo de pago típico
- Ejemplos de uso
- Configuración
- Estado del desarrollo

---

## Requisitos

```bash
pip install requests flask
```

Para desarrollo/testing:
```bash
pip install flask requests pytest
```

---

## Flujo de Integración

### Fase 1: Descubrimiento ✅
1. Ejecutar `discover_payment_v2.py` para encontrar operación de pago
2. Actualizar `CashdropAPI_v2.py` con método para la operación encontrada

### Fase 2: Gateway 🔄 (Actual)
1. Ejecutar `cashdrop_gateway.py`
2. Probar con `test_gateway.py`
3. Validar endpoints específicos

### Fase 3: Integración Odoo (Próxima)
1. Crear payment method en Odoo
2. Integrar gateway con POS
3. Implementar interfaz de usuario

---

## Troubleshooting

### "Connection refused" al ejecutar gateway
- Asegúrate que Cashdrop está accesible en `https://10.0.1.140`
- Prueba: `ping 10.0.1.140`
- Verifica credenciales (admin / 3428)

### "Unknown operation" en discovery
- La API podría usar diferentes parámetros
- Intenta inspeccionar tráfico del navegador en UI nativa de Cashdrop
- Revisa si hay otras versiones: `/Cashdro2WS`, `/Cashdro4WS`

### Gateway conecta pero pagos no funcionan
- La operación de pago aún no ha sido descubierta
- Ejecuta `discover_payment_v2.py` de nuevo
- Revisa logs del gateway para más detalles

---

## Notas de Desarrollo

- **SSL**: Verificación de certificado deshabilitada (`verify=False`). En producción usar certificados válidos.
- **Transacciones**: Almacenadas en memoria. Para producción usar base de datos (Redis, PostgreSQL, etc.)
- **Autenticación**: Credenciales fijas. Considerar múltiples usuarios/roles en futuro.
- **Asincronía**: Endpoints usan código síncrono. Considerar Celery o asyncio para operaciones largas.

---

## API de Cashdrop Confirmada

Base URL: `https://10.0.1.140/Cashdro3WS/index.php`

**Operaciones confirmadas:**
- `login` (POST) - Requiere: `name`, `password`
- `getUser` (GET/POST) - Requiere: `name`, `password`, `userId`
- `getPiecesCurrency` (POST) - Requiere: `currencyId`, `includeImages`, `includeLevels`

**Respuesta estándar:**
```json
{
  "code": 1,          // 1 = éxito, 0 = operación desconocida, -3 = sin usuario
  "data": {...}       // Datos específicos de la operación
}
```

---

## Próximos Pasos

1. **Priority 1**: Descubrir operación de pago (ejecutar `discover_payment_v2.py`)
2. **Priority 2**: Una vez descubierta, actualizar `CashdropAPI_v2.py`
3. **Priority 3**: Integrar con Odoo POS backend
4. **Priority 4**: Crear interfaz POS frontend

---

*Última actualización: 2024-01*
