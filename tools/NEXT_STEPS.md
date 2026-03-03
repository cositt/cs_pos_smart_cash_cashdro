# Cashdrop POS Integration - Próximos Pasos

## Estado Actual ✅

**Completado:**
- ✅ Investigación de API de Cashdrop
- ✅ Cliente Python funcional (CashdropAPI_v2.py)
- ✅ Gateway Flask (cashdrop_gateway.py) con 9 endpoints
- ✅ Suite de pruebas (test_gateway.py)
- ✅ Documentación completa

**Bloqueado:** 
- ⏳ Operación de pago aún no descubierta

**Archivos Creados:**
```
tools/
├── CashdropAPI_v2.py              (Cliente Python)
├── cashdrop_gateway.py            (Gateway Flask - 9 endpoints)
├── discover_payment_v2.py          (Script de discovery mejorado)
├── test_gateway.py                (Suite de pruebas - 15 tests)
├── GATEWAY_DOCS.md                (Documentación API gateway)
├── README.md                       (Documentación general)
└── NEXT_STEPS.md                  (Este archivo)
```

---

## 🚀 Quick Start (5 minutos)

### Terminal 1: Iniciar Gateway
```bash
cd /Users/juan/Desktop/cashdro-prueba/custom_addons/cs_pos_smart_cash_cashdro/tools
python cashdrop_gateway.py
```

Esperado:
```
🚀 Iniciando Cashdrop Gateway
======================================================
URL: http://localhost:5000
Cashdrop API: https://10.0.1.140
======================================================

✅ Conectado a Cashdrop
 * Running on http://0.0.0.0:5000
```

### Terminal 2: Pruebas
```bash
cd /Users/juan/Desktop/cashdro-prueba/custom_addons/cs_pos_smart_cash_cashdro/tools
python test_gateway.py
```

Esperado: **15 tests pasan** ✅

### Terminal 3: Descubrir Operación de Pago (IMPORTANTE)
```bash
cd /Users/juan/Desktop/cashdro-prueba/custom_addons/cs_pos_smart_cash_cashdro/tools
python discover_payment_v2.py
```

---

## 📋 Fases de Implementación

### Fase 1: Discovery de Operación de Pago ⏳ (ACTIVA)

**Objetivo:** Encontrar la operación correcta para procesar pagos en Cashdrop.

**Acciones:**

1. **Ejecutar discovery script:**
   ```bash
   python discover_payment_v2.py
   ```

2. **Si encuentra operación exitosa:**
   - Anotar nombre de operación (ej: `chargePayment`)
   - Anotar parámetros requeridos
   - Anotar formato de respuesta

3. **Si NO encuentra (código=0):**
   - Opción A: Inspeccionar tráfico del navegador
     - Abrir DevTools (F12) en Cashdrop UI
     - Ir a Network tab
     - Iniciar pago manual
     - Buscar petición a `/Cashdro3WS/index.php`
     - Copiar nombre de operación exacto y parámetros
   
   - Opción B: Revisar alternativas
     - ¿Existe `/Cashdro2WS` o `/Cashdro4WS`?
     - ¿API usa JSON en body en lugar de query string?
     - ¿Requiere autenticación diferente?

4. **Actualizar CashdropAPI_v2.py:**
   ```python
   def pay(self, amount, currency='EUR'):
       """Procesa un pago"""
       params = {
           'operation': 'chargePayment',  # <-- Cambiar según discovery
           'amount': amount,
           'currency': currency
       }
       return self._request('POST', params)
   ```

5. **Actualizar gateway:**
   ```python
   # En cashdrop_gateway.py, reemplazar mock con llamada real:
   
   @app.route('/pay', methods=['POST'])
   def process_payment():
       ...
       # Cambiar de:
       #   return jsonify(transaction), 202
       # A:
       try:
           client = get_cashdrop_client()
           result = client.pay(amount, currency)
           return jsonify(result), 200
       except Exception as e:
           ...
   ```

**Tiempo estimado:** 1-2 horas

---

### Fase 2: Backend Odoo ⏸️ (Espera Phase 1)

**Archivo:** `/Users/juan/Desktop/cashdro-prueba/custom_addons/cs_pos_smart_cash_cashdro/models/payment_gateway.py`

**Tareas:**

1. Crear modelo `CashdropPaymentGateway`:
   ```python
   class CashdropPaymentGateway(models.Model):
       _name = 'cashdrop.payment.gateway'
       
       name = fields.Char('Nombre', required=True)
       gateway_url = fields.Char('URL Gateway', default='http://localhost:5000')
       enabled = fields.Boolean('Habilitado', default=True)
       
       def test_connection(self):
           """Prueba conexión al gateway"""
           # Llamar a GET /health
       
       def process_payment(self, amount, currency):
           """Procesa un pago"""
           # Llamar a POST /pay
   ```

2. Crear modelo `CashdropPaymentTransaction`:
   ```python
   class CashdropPaymentTransaction(models.Model):
       _name = 'cashdrop.payment.transaction'
       
       sale_order_id = fields.Many2one('sale.order')
       transaction_id = fields.Char(unique=True)
       amount = fields.Float()
       currency_id = fields.Many2one('res.currency')
       status = fields.Selection([
           ('processing', 'Procesando'),
           ('confirmed', 'Confirmado'),
           ('cancelled', 'Cancelado'),
           ('error', 'Error')
       ])
       gateway_response = fields.Json()
   ```

3. Registrar método de pago en POS:
   ```python
   # En __init__.py o payment_method.py
   
   PAYMENT_METHODS = {
       'cashdrop': 'Cashdrop - Máquina de Efectivo',
       'card': 'Tarjeta',
       'cash': 'Efectivo Manual'
   }
   ```

**Tiempo estimado:** 1-2 horas

**Dependencias:** Phase 1 completada

---

### Fase 3: Controlador POS ⏸️ (Espera Phase 1-2)

**Archivo:** `/Users/juan/Desktop/cashdro-prueba/custom_addons/cs_pos_smart_cash_cashdro/controllers/pos_payment.py`

**Tareas:**

1. Crear endpoint `/pos/payment/start`:
   ```python
   @http.route('/pos/payment/start', type='json', auth='user', methods=['POST'])
   def pos_payment_start(self, **kwargs):
       """Inicia un pago desde POS"""
       sale_id = kwargs.get('sale_id')
       amount = kwargs.get('amount')
       
       # Obtener gateway
       gateway = request.env['cashdrop.payment.gateway'].search(
           [('enabled', '=', True)], limit=1
       )
       
       # Procesar pago
       transaction = gateway.process_payment(amount, 'EUR')
       return {'transaction_id': transaction.id}
   ```

2. Crear endpoint `/pos/payment/status`:
   ```python
   @http.route('/pos/payment/status', type='json', auth='user')
   def pos_payment_status(self, **kwargs):
       """Obtiene estado de un pago"""
       transaction_id = kwargs.get('transaction_id')
       # Llamar a gateway GET /payment/{id}/status
   ```

3. Crear endpoint `/pos/payment/confirm`:
   ```python
   @http.route('/pos/payment/confirm', type='json', auth='user', methods=['POST'])
   def pos_payment_confirm(self, **kwargs):
       """Confirma un pago"""
       # Llamar a gateway POST /payment/{id}/confirm
   ```

**Tiempo estimado:** 1 hora

---

### Fase 4: Frontend POS ⏸️ (Espera Phase 1-3)

**Archivo:** `/Users/juan/Desktop/cashdro-prueba/custom_addons/cs_pos_smart_cash_cashdro/static/src/js/payment_widget.js`

**Tareas:**

1. Crear widget de pago Cashdrop:
   ```javascript
   odoo.define('cs_pos_smart_cash_cashdro.PaymentWidget', function(require) {
       const PosBaseWidget = require('point_of_sale.BaseWidget');
       
       return PosBaseWidget.extend({
           template: 'CashdropPaymentWidget',
           
           start_payment: function() {
               // POST /pos/payment/start
               // Mostrar UI de "esperando pago"
           },
           
           poll_status: function() {
               // GET /pos/payment/status cada 500ms
               // Actualizar UI
           },
           
           confirm_payment: function() {
               // POST /pos/payment/confirm
           }
       });
   });
   ```

2. Crear template:
   ```xml
   <t t-name="CashdropPaymentWidget">
       <div class="cashdrop-payment-container">
           <h3>Pago con Cashdrop</h3>
           <div id="status-display">
               Esperando confirmación en máquina...
           </div>
           <button id="confirm-btn">Confirmar</button>
           <button id="cancel-btn">Cancelar</button>
       </div>
   </t>
   ```

3. Integrar con POS ticket:
   - Agregar botón "Pagar con Cashdrop" en Payment Methods
   - Mostrar widget cuando se seleccione

**Tiempo estimado:** 2 horas

---

## 🔍 Debugging Tips

### Verificar gateway está corriendo:
```bash
curl -X GET http://localhost:5000/health
```

Respuesta esperada:
```json
{"status": "ok", "authenticated": true}
```

### Verificar conexión a Cashdrop:
```bash
curl -X GET http://localhost:5000/status
```

### Verificar piezas disponibles:
```bash
curl -X GET http://localhost:5000/pieces/EUR
```

### Hacer un pago de prueba:
```bash
curl -X POST http://localhost:5000/pay \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 10.50,
    "currency": "EUR",
    "reference": "TEST-001"
  }'
```

### Ver logs del gateway:
```bash
# Los logs se muestran en la terminal donde ejecutaste:
# python cashdrop_gateway.py
```

---

## 📱 Arquitetura Final

```
┌─────────────────────┐
│    Odoo POS UI      │
│  (Frontend JS/HTML) │
└──────────┬──────────┘
           │ HTTP REST
           ▼
┌──────────────────────────┐
│  Odoo Controllers        │
│ /pos/payment/start       │
│ /pos/payment/status      │
│ /pos/payment/confirm     │
└──────────┬───────────────┘
           │ HTTP REST
           ▼
┌──────────────────────────┐
│  Cashdrop Gateway        │
│  (Flask - localhost:5000)│
│ GET /health              │
│ POST /pay                │
│ GET /payment/{id}/status │
│ POST /payment/{id}/confirm
└──────────┬───────────────┘
           │ HTTPS
           ▼
┌──────────────────────────┐
│  Cashdrop API            │
│  (10.0.1.140)           │
│ /Cashdro3WS/index.php    │
└──────────────────────────┘
```

---

## ✅ Checklist de Implementación

### Phase 1: Discovery
- [ ] Ejecutar `discover_payment_v2.py`
- [ ] Encontrar operación de pago
- [ ] Anotar parámetros exactos
- [ ] Actualizar CashdropAPI_v2.py con método `pay()`
- [ ] Probar método directamente
- [ ] Actualizar gateway para usar operación real

### Phase 2: Backend Odoo
- [ ] Crear modelos (Gateway, Transaction)
- [ ] Registrar métodos de pago
- [ ] Crear service para comunicación con gateway
- [ ] Tests unitarios
- [ ] Probar integración completa

### Phase 3: Controllers POS
- [ ] Crear endpoints `/pos/payment/*`
- [ ] Implementar lógica de transacciones
- [ ] Manejo de errores
- [ ] Tests de integración

### Phase 4: Frontend
- [ ] Crear widget de pago
- [ ] Integrar con ticket
- [ ] UX para polling de estado
- [ ] Manejo de confirmación/cancelación
- [ ] Tests E2E

### QA General
- [ ] Pruebas de múltiples montos
- [ ] Pruebas de cancelación
- [ ] Pruebas de errores de conexión
- [ ] Pruebas de timeout
- [ ] Documentación de usuario

---

## 🆘 Troubleshooting Común

| Problema | Solución |
|----------|----------|
| "Connection refused" gateway | Asegúrate que `python cashdrop_gateway.py` está corriendo |
| "Unknown operation" en discovery | Inspecciona tráfico del navegador de Cashdrop UI |
| Tests fallando | Verifica que gateway está en /health ✅ |
| Cashdrop API no responde | Verifica IP 10.0.1.140 y credenciales (admin/3428) |
| Gateway crashea en pago | Implementar método `pay()` en CashdropAPI_v2.py |

---

## 📞 Contacto y Escalamientos

**Si discovers la operación de pago:**
1. Actualizar `PAYMENT_OPERATION` en la parte superior de `discover_payment_v2.py`
2. Commitear cambios
3. Proceder a Phase 2

**Si necesitas inspeccionar tráfico del navegador:**
1. Abrir DevTools en Cashdrop UI (F12)
2. Network tab
3. Hacer pago manual
4. Buscar peticiones a `/Cashdro3WS/`
5. Copiar exactamente operación y parámetros

---

## 📚 Referencias

- **Gateway Docs:** `GATEWAY_DOCS.md`
- **README:** `README.md`
- **Cliente API:** `CashdropAPI_v2.py`
- **Discovery Script:** `discover_payment_v2.py`
- **Tests:** `test_gateway.py`

---

*Última actualización: 2024-03-03*
*Estado: Fase 1 Activa - Esperando descubrimiento de operación de pago*
