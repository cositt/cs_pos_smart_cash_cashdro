# Análisis: Investigación GPT vs Discovery Realizado

## 📊 Comparativa de Operaciones Encontradas

### Investigación GPT (investigacion_GPT.txt)
**Fuente:** Análisis de documentación CashDro v2.04 y v4.12 + sitio demo cashdro.js

**Operaciones reportadas:**
1. `startOperation` - Inicia transacción de venta/cobro (type=3 o 4)
2. `acknowledgeOperationId` - Confirma recepción de operationId
3. `askOperation` - Consulta estado de operación
4. `finishOperation` - Finaliza o cancela operación (type=1 o 2)
5. `setoperationImported` - Marca operación como importada
6. `askPendingOperations` - Lista de operaciones abiertas
7. `getPiecesCurrency` - Consulta niveles de efectivo ✅ CONFIRMADO
8. `getDiagnosis` - Diagnóstico de máquina
9. `askOperationExecuting` - Comprueba si hay operación en curso
10. `getAlerts` - Obtiene alertas de la máquina

**Endpoint base:** `https://[IP]/Cashdro3WS/index3.php` (nota: `index3.php`, no `index.php`)

### Discovery Realizado (discover_payment_v2.py)

**Operaciones confirmadas:**
1. `login` ✅ Encontrada
2. `getUser` ✅ Encontrada
3. `getPiecesCurrency` ✅ Encontrada (15 piezas EUR)

**Operaciones NO encontradas en nuestro discovery:**
- `startOperation` ❌ (19 variaciones probadas sin resultado)
- `acknowledgeOperationId` ❌
- `askOperation` ❌
- `finishOperation` ❌

**Endpoint usado:** `https://10.0.1.140/Cashdro3WS/index.php` (nota: `index.php`)

---

## 🔍 Problemas Identificados

### 1. **Diferencia en Endpoint**
- GPT menciona: `/Cashdro3WS/index3.php` ← Versión 3
- Encontrado: `/Cashdro3WS/index.php` ← Versión genérica

**Acción:** Probar con `index3.php`

### 2. **Diferencia en Parámetros**
GPT muestra:
```
?operation=startOperation&name=[user]&password=[pass]&type=3&posid=[id]&parameters={"amount":"[amount]"}
```

Nuestro formato:
```
?operation=startOperation&name=[user]&password=[pass]
```

**Acción:** Incluir parámetros adicionales: `type`, `posid`, `parameters` con JSON

### 3. **Posible Versión Antigua**
Las máquinas existentes podrían tener:
- Version v2.x con endpoint `/Cashdro3WS/` (antiguo)
- Version v3.x con endpoint `/Cashdro3Web/` (actual)
- Version v4.x con endpoint diferente

**Acción:** Probar múltiples versiones de endpoint

---

## ✅ Acciones Recomendadas

### 1. Actualizar Discovery Script (CRÍTICO)

Crear `discover_payment_v3.py` que pruebe:

```python
# Variaciones de endpoint
ENDPOINTS = [
    'https://10.0.1.140/Cashdro3WS/index.php',      # Actual
    'https://10.0.1.140/Cashdro3WS/index3.php',     # v3
    'https://10.0.1.140/Cashdro3WS/index2.php',     # v2
    'https://10.0.1.140/Cashdro3Web/api/payment',   # v4 web
]

# Operaciones conocidas
OPERATIONS = {
    'startOperation': {
        'type': 3,           # 3=pago, 4=venta
        'posid': 'POS001',
        'parameters': '{"amount":"100"}'
    },
    'acknowledgeOperationId': {
        'operationId': 'test-op-id'
    },
    'askOperation': {
        'operationId': 'test-op-id'
    },
    'finishOperation': {
        'type': 1,           # 1=finish, 2=cancel
        'operationId': 'test-op-id'
    },
    # ... resto de operaciones
}
```

### 2. Pruebas de Formato de Parámetros

La documentación GPT menciona:
- Algunos parámetros en URL (query string)
- Algunos parámetros en JSON dentro de `parameters=`

Probar:
```python
# Formato 1: Todo en query string
params = {
    'operation': 'startOperation',
    'name': 'admin',
    'password': '3428',
    'type': 3,
    'posid': 'POS001',
    'amount': 100,
    'startnow': 'true'
}

# Formato 2: JSON en parámetro
params = {
    'operation': 'startOperation',
    'name': 'admin',
    'password': '3428',
    'type': 3,
    'parameters': json.dumps({'amount': 100})
}
```

### 3. Validar con Módulos Existentes

Los módulos mencionados en GPT que son referencias:
- **pos_payment_method_cashdro** (OCA) - Gratuito
- **dphi_cashdro_pos** (DPHI SRL) - Comercial
- **pos_smart_cash_cashdro** (Next Level Digital) - Comercial

**Recomendación:** Revisar código fuente de OCA module (gratuito) en GitHub

```bash
# Clonar módulo OCA para referencia
git clone https://github.com/OCA/pos-cashdro.git
# O buscar en: https://github.com/OCA?q=cashdro
```

---

## 🎯 Flujo Correcto de Pago

Según GPT, el flujo debería ser:

```
1. startOperation(type=3, amount=100)
   ↓ Response: operationId
   
2. acknowledgeOperationId(operationId)
   ↓ Response: estado=confirmado
   
3. askOperation(operationId) [POLLING cada 500ms]
   ↓ Response: estado del cliente pagando
   
4. [Usuario inserta dinero en máquina]
   ↓ Máquina valida dinero
   
5. askOperation(operationId) [nuevo poll]
   ↓ Response: amount_paid=100
   
6. finishOperation(operationId, type=1)
   ↓ Response: operación completada
```

**vs. nuestro actual (mock):**

```
1. POST /pay → transaction_id
2. GET /payment/{id}/status → status=processing
3. POST /payment/{id}/confirm → confirmed
```

---

## 📱 Archivos de Referencia en investigacionAPI/

Archivos que pueden contener código útil:

```
investigacionAPI/
├── CashdropAPI.py                      # v1 del cliente
├── CashdropAPI_v2.py                   # v2 del cliente ✅ USAR ESTE
├── cashdrop_real_operations.py          # Operaciones encontradas
├── cashdrop_real_operations.json        # JSON de operaciones
├── cashdrop_authenticated_investigator.py  # Investigación exhaustiva
└── cashdrop_auto_investigator.py        # Auto-discovery
```

**Recomendación:** Revisar `cashdrop_real_operations.py` para ver qué operaciones ya fueron probadas.

---

## 🔑 Claves de la Documentación GPT

### Credenciales y Configuración
- Usuario: `admin` ✅ Confirmado
- Contraseña: `3428` ✅ Confirmado
- Red local obligatoria ✅
- HTTPS con certificado autofirmado ✅

### Parámetros Importantes Detectados
1. **type:** Diferencia entre venta (4) y pago (3)
2. **posid:** Identificador del terminal POS (ej: "POS001")
3. **posuser:** Usuario del operario de caja
4. **parameters:** Objeto JSON con parámetros adicionales (amount, etc)
5. **operationId:** ID único de transacción devuelto por máquina

### URLs Web Adicionales
```
Web Interface (iframe): https://[IP]/Cashdro3Web/index.html#/menu?username=[user]&password=[pass]&posid=[posid]&posuser=[posuser]
API REST: https://[IP]/Cashdro3WS/index.php (o index3.php)
Diagnóstico: GET /health o /status endpoints
```

---

## 🎬 Próximos Pasos (Prioridad)

### INMEDIATO (Hoy)
1. ✅ Leer `investigacion_GPT.txt` - YA HECHO
2. 🔄 Crear `discover_payment_v3.py` con variaciones de endpoint
3. 🔄 Probar con `index3.php` en lugar de `index.php`
4. 🔄 Incluir parámetros `type`, `posid`, `parameters` en discovery

### HOY-MAÑANA
5. 📦 Buscar módulo OCA en GitHub para referencia
6. 📖 Revisar `cashdrop_real_operations.py` en investigacionAPI/
7. 🧪 Ejecutar nuevo discovery v3 contra máquina real

### ESTA SEMANA (Si discovery v3 falla)
8. 📊 Inspeccionar tráfico HTTP en Cashdrop UI nativa con DevTools
9. 🔗 Contactar a CashDro (comercial@cashdro.com) si es necesario
10. 💻 Descargar módulo OCA y adaptarlo para nuestra integración

---

## 📋 Checklist de Validación

- [ ] Probar endpoint `/Cashdro3WS/index3.php`
- [ ] Probar con parámetro `type=3` (pago simple)
- [ ] Probar con parámetro `posid='POS001'`
- [ ] Probar con `parameters='{"amount":"100"}'` (JSON)
- [ ] Revisar respuesta para campo `operationId`
- [ ] Validar flujo: startOp → acknowledge → askOp → finish
- [ ] Revisar código en investigacionAPI/cashdrop_real_operations.py
- [ ] Descargar módulo OCA para referencia
- [ ] Si todo falla → contactar CashDro

---

## 📞 Contactos de CashDro

**Según GPT:**
- Email: comercial@cashdro.com
- Disponible: Documentación v2.04 y v4.12 (requiere solicitud)
- Soporte: Para integración completa y multi-sucursal

---

*Documento creado basado en análisis de investigacion_GPT.txt*
*Fecha: 2026-03-03*
