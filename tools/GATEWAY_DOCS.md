# Cashdrop Gateway - Documentación

Gateway Flask que actúa como intermediario entre Odoo POS y la máquina Cashdrop.

## Arquitectura

```
┌─────────────┐
│ Odoo POS    │
└──────┬──────┘
       │ HTTP REST
       ▼
┌──────────────────────────┐
│ Cashdrop Gateway (Flask) │  ← Puerto 5000
│  - Validación            │
│  - Manejo de errores     │
│  - Transacciones        │
└──────┬───────────────────┘
       │ HTTPS
       ▼
┌─────────────────────┐
│ Cashdrop API        │
│ (10.0.1.140)       │
└─────────────────────┘
```

## Instalación

### Requisitos
```bash
pip install flask requests
```

### Ejecución
```bash
python cashdrop_gateway.py
```

El gateway estará disponible en `http://localhost:5000`

## API Endpoints

### 1. Health Check

**GET** `/health`

Verifica el estado del gateway y la conexión con Cashdrop.

**Respuesta exitosa (200):**
```json
{
  "status": "ok",
  "authenticated": true,
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

---

### 2. Obtener Información de Piezas

**GET** `/pieces/<currency>`

Obtiene las monedas y billetes disponibles para una divisa.

**Parámetros:**
- `currency` (path): Código de divisa (ej: EUR)

**Respuesta exitosa (200):**
```json
{
  "status": "success",
  "currency": "EUR",
  "pieces": [
    {
      "id": 1,
      "value": 0.01,
      "type": "coin",
      "name": "1 cent"
    },
    {
      "id": 2,
      "value": 0.02,
      "type": "coin",
      "name": "2 cents"
    }
  ],
  "count": 15
}
```

---

### 3. Obtener Estado de la Máquina

**GET** `/status`

Obtiene información del estado actual de la máquina y usuario autenticado.

**Respuesta exitosa (200):**
```json
{
  "status": "success",
  "user": {
    "id": 1,
    "name": "admin",
    "permissions": [...]
  },
  "gateway_status": "online",
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

---

### 4. Procesar Pago

**POST** `/pay`

Inicia un proceso de pago. Retorna una transacción en estado `processing`.

**Body:**
```json
{
  "amount": 10.50,
  "currency": "EUR",
  "reference": "ORDER-2024-001"
}
```

**Parámetros:**
- `amount` (required): Monto a pagar (decimal)
- `currency` (required): Código de divisa (ej: EUR)
- `reference` (optional): Referencia única del pedido en Odoo

**Respuesta (202 Accepted):**
```json
{
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": 10.50,
  "currency": "EUR",
  "reference": "ORDER-2024-001",
  "status": "processing",
  "created_at": "2024-01-15T10:30:45.123456",
  "message": "Payment of 10.5 EUR initiated"
}
```

**Errores:**
- `400`: Campos requeridos faltantes o cantidad inválida
- `500`: Error del servidor

---

### 5. Obtener Estado de Pago

**GET** `/payment/<transaction_id>/status`

Obtiene el estado actual de una transacción.

**Parámetros:**
- `transaction_id` (path): ID de la transacción retornado por `/pay`

**Respuesta (200):**
```json
{
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": 10.50,
  "currency": "EUR",
  "reference": "ORDER-2024-001",
  "status": "processing|confirmed|cancelled",
  "created_at": "2024-01-15T10:30:45.123456",
  "confirmed_at": "2024-01-15T10:31:00.123456"
}
```

**Errores:**
- `404`: Transacción no encontrada

---

### 6. Confirmar Pago

**POST** `/payment/<transaction_id>/confirm`

Confirma una transacción en estado `processing`.

**Parámetros:**
- `transaction_id` (path): ID de la transacción

**Respuesta (200):**
```json
{
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "confirmed",
  "confirmed_at": "2024-01-15T10:31:00.123456"
}
```

---

### 7. Cancelar Pago

**POST** `/payment/<transaction_id>/cancel`

Cancela una transacción en estado `processing`.

**Parámetros:**
- `transaction_id` (path): ID de la transacción

**Respuesta (200):**
```json
{
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "cancelled",
  "cancelled_at": "2024-01-15T10:31:05.123456"
}
```

**Errores:**
- `400`: No se puede cancelar un pago confirmado
- `404`: Transacción no encontrada

---

### 8. Ingresar Efectivo

**POST** `/cash-in`

Ingresa efectivo en la máquina.

**Body:**
```json
{
  "amount": 50.00,
  "currency": "EUR"
}
```

**Respuesta (202 Accepted):**
```json
{
  "operation_id": "550e8400-e29b-41d4-a716-446655440000",
  "operation_type": "cash_in",
  "amount": 50.00,
  "currency": "EUR",
  "timestamp": "2024-01-15T10:30:45.123456",
  "message": "Cash in of 50.0 initiated"
}
```

---

### 9. Retirar Efectivo

**POST** `/cash-out`

Retira efectivo de la máquina.

**Body:**
```json
{
  "amount": 50.00,
  "currency": "EUR"
}
```

**Respuesta (202 Accepted):**
```json
{
  "operation_id": "550e8400-e29b-41d4-a716-446655440000",
  "operation_type": "cash_out",
  "amount": 50.00,
  "currency": "EUR",
  "timestamp": "2024-01-15T10:30:45.123456",
  "message": "Cash out of 50.0 initiated"
}
```

---

## Flujo de Pago Típico

```
1. POS → POST /pay
   ↓ (retorna transaction_id)
   
2. POS → GET /payment/{id}/status (polling cada 500ms)
   ↓ (espera confirmación del usuario)
   
3. Usuario confirma en máquina
   ↓
   
4. POS → POST /payment/{id}/confirm
   ↓ (transacción completada)
```

## Configuración

Edita las variables al inicio de `cashdrop_gateway.py`:

```python
CASHDROP_CONFIG = {
    'base_url': 'https://10.0.1.140',  # URL de la máquina
    'username': 'admin',                 # Usuario de API
    'password': '3428'                   # Contraseña
}
```

## Logs

Los logs se muestran en consola con prefijo de nivel:
- `INFO`: Información general
- `ERROR`: Errores

## Estado del Desarrollo

- ✅ Health check y autenticación
- ✅ Endpoints de información (pieces, status)
- 🔄 Endpoints de pago (simulados - esperando descubrimiento de operación real)
- 🔄 Endpoints de cash in/out (simulados)
- ⏳ Integración con Odoo POS

## Notas Importantes

1. **SSL**: Actualmente se desactiva la verificación de certificado (`verify=False`). En producción, usar certificados válidos.
2. **Transacciones**: Las transacciones se almacenan en memoria. Para producción, usar base de datos.
3. **Autenticación**: El gateway usa las mismas credenciales para todas las conexiones. Considerar multi-usuario en el futuro.
4. **Operación de Pago**: El endpoint `/pay` es actualmente un mock. Será actualizado cuando se descubra la operación real en Cashdrop.
