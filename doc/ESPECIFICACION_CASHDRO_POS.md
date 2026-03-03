# Especificación: Módulo CashDro POS SmartCash (recreación)

Documento de análisis y requisitos para recrear la funcionalidad del módulo [CashDro POS SmartCash](https://apps.odoo.com/apps/modules/19.0/pos_smart_cash_cashdro) (Next Level Digital Solutions) en nuestro addon custom.

---

## 1. Referencia del módulo original

| Campo | Valor |
|-------|--------|
| **Nombre técnico** | `pos_smart_cash_cashdro` |
| **Nombre comercial** | CashDro POS SmartCash |
| **Versión Odoo** | 19.0 (también 17.0, 18.0) |
| **Autor original** | Next Level Digital Solutions, LLC |
| **Web** | https://www.nextlevel-digitalsolutions.com/ |
| **Líneas de código (original)** | ~1238 |
| **Dependencia comunitaria** | CashDro POS SmartCash (Terminal) – `pos_payment_config_cashdro` (~37 LOC) |

---

## 2. Dependencias Odoo

- **point_of_sale** – Punto de venta
- **mail** – Discuss
- **stock** – Inventario
- **account** – Facturación

Nuestro módulo puede implementar todo en uno (sin depender de un “Terminal” externo) o dividir en dos módulos más adelante.

---

## 3. Objetivo del módulo

Conectar Odoo POS con **cajas inteligentes CashDro** (recyclers) para:

- Usar CashDro como **método de pago** en el POS.
- Gestionar **entrada/salida de efectivo** (Cash In / Cash Out) desde Odoo.
- Coordinar el **arqueo de caja** de Odoo con el estado del drawer.

La comunicación se hace a través de un **gateway** (software local) entre el navegador/POS y el hardware. No se usa IOT Box.

---

## 4. Funcionalidades a implementar

### 4.1 Método de pago CashDro

- Definir un **nuevo método de pago** “CashDro” (o “SMARTCASH”) en el POS.
- El método debe poder **configurarse por sesión/configuración** del POS (URL/parámetros del gateway, etc.).
- Al pulsar el método de pago en el POS:
  - Se envía la petición al **gateway** (comunicación asíncrona).
  - El usuario puede seguir usando el POS mientras la caja procesa.
- Cuando la caja confirma el pago, Odoo recibe la notificación y **valida el pago** en el ticket.
- Posibilidad de **ir al ticket** una vez pagado (flujo directo).

### 4.2 Cancelación y reintento

- **Cancelar** un pago CashDro en curso desde el POS en cualquier momento.
- **Reintentar** el pago después de cancelar.

### 4.3 Cash In / Cash Out

- **Cash Out:** retirar efectivo de la caja CashDro desde Odoo.
- **Cash In:** ingresar efectivo en la caja CashDro desde Odoo.

(Ambos vía el gateway, con órdenes y respuestas que habrá que definir según documentación o reversión del protocolo.)

### 4.4 Arqueo de caja (opening control)

- Coordinar el **control de apertura/cierre de caja** de Odoo con el estado de la caja CashDro.
- Objetivo: que el arqueo del POS y el estado físico del drawer estén alineados.

### 4.5 Configuración

- Configuración del **gateway** (URL, puerto, credenciales si aplica).
- Asignación del método CashDro a los **Puntos de venta** donde se use.
- Posible configuración por **terminal** (si se replica el concepto del módulo “Terminal”).

---

## 5. Cómo funciona (flujo descrito en la app)

1. **Instalación:** se crea/configura el método de pago “CashDro” en el POS.
2. **Gateway:** software local en el equipo del POS (p. ej. Windows) que habla con la caja CashDro y expone una interfaz (REST, WebSocket, etc.) a Odoo.
3. **Comunicación:** desde el **navegador** (POS en Odoo) se habla con el gateway; no hace falta IOT Box.
4. **Pago:**  
   - Usuario elige pago “CashDro” → se envía mensaje al gateway (importe, etc.).  
   - Gateway/caja procesan.  
   - Respuesta asíncrona: notificación a Odoo → validación del pago en el ticket.
5. **Cancelación:** en cualquier momento se puede cancelar desde Odoo; el gateway/caja deben soportar la cancelación.
6. **Cash In/Out y arqueo:** se implementan como acciones adicionales que envían comandos al gateway y actualizan/consultan estado según diseño.

---

## 6. Hardware compatible (según ficha)

- CashDro 2, 3, 4, 5, 7 (recyclers).
- Web fabricante: [cashdro.com](https://www.cashdro.com/).

El protocolo concreto (API del gateway) no está público; habrá que obtenerlo de CashDro o del gateway que uses, o definirlo en nuestro módulo como “configurable” (URL, método, payload) para adaptarlo cuando tengas la documentación.

---

## 7. Enfoque técnico sugerido en Odoo 19

### 7.1 Backend (Python)

- **pos.config / pos.payment.method:** extensión o configuración para marcar el método “CashDro” y guardar parámetros del gateway (URL, etc.).
- **Modelos/acciones para Cash In / Cash Out:** registros o wizards que generen las órdenes al gateway y, si aplica, movimientos de caja/diario en Odoo.
- **Integración con flujo de caja:** enlazar con el control de apertura/cierre del POS (arqueo).

### 7.2 Frontend POS (JavaScript / OWL)

- **PaymentInterface (o equivalente en 19):** implementar la interfaz del método de pago CashDro:
  - Enviar petición de pago (por ejemplo `send_payment_request(cid)`).
  - Cancelar pago (`send_payment_cancel`).
  - Reintento si la API lo permite.
- Comunicación con el gateway desde el navegador (fetch/WebSocket al localhost o IP del gateway).
- **Botones/acciones Cash In y Cash Out** en la interfaz del POS (navbar o popup).
- Mostrar estado del pago (esperando, confirmado, error, cancelado).

### 7.3 Gateway

- Asumir un gateway local que:
  - Recibe órdenes desde Odoo (pago, cancelación, cash in, cash out).
  - Se comunica con la caja CashDro (protocolo propietario).
  - Devuelve respuestas/eventos a Odoo (éxito, error, importe contado, etc.).
- Nuestro módulo debe estar preparado para:
  - Configurar URL/puerto (y opcionalmente auth).
  - Definir formato de petición/respuesta (JSON u otro) cuando se conozca el protocolo.

---

## 8. Estructura sugerida del addon

```
cashdro_custom/   (o pos_cashdro si quieres nombre más estándar)
├── __manifest__.py    # depends: ['point_of_sale', 'mail', 'stock', 'account']
├── models/
│   ├── pos_config.py       # configuración gateway + método CashDro
│   ├── pos_payment_method.py  # si extendemos el método de pago
│   └── ...                 # Cash In/Out, arqueo si aplica
├── static/
│   └── src/
│       ├── js/             # PaymentInterface, servicios al gateway
│       ├── xml/            # botones Cash In/Out, UI de pago
│       └── scss/
├── views/
│   └── pos_config_views.xml
├── security/
└── controllers/            # si hay endpoints para el gateway (callback, etc.)
```

---

## 9. Resumen de entregables

| Entregable | Descripción |
|------------|-------------|
| Método de pago CashDro en POS | Crear y configurar método de pago que use el gateway |
| Comunicación con gateway | Cliente JS (y/o Python) para enviar/recibir pago, cancelación |
| Pago asíncrono | Flujo: solicitud → respuesta → validación del ticket |
| Cancelar / Reintentar | Desde el POS |
| Cash In / Cash Out | Acciones en POS + lógica backend si aplica |
| Arqueo coordinado | Integración con control de apertura/cierre de caja |
| Configuración | Parámetros del gateway y asignación a POS/terminales |

---

## 10. Notas

- El módulo original depende de **pos_payment_config_cashdro** (Terminal). Para la recreación podemos hacer un solo módulo que incluya configuración de terminal/gateway, o dos módulos si quieres separar “configuración por terminal” y “lógica de pago”.
- La **licencia del original** es propietaria; esta especificación está basada solo en la descripción pública de la app y en buenas prácticas de integración POS. No se copia código ni documentación propietaria.
- Para implementar el protocolo real hace falta documentación o acceso al gateway/CashDro (API, mensajes, estados). Mientras tanto se puede definir una **interfaz/cliente genérico** (URL, método HTTP, payload) y rellenar después el formato concreto.

Cuando tengas definido el protocolo del gateway (o un mock), se puede bajar esto a tareas concretas (modelos, campos, JS, endpoints) e implementar por fases (primero pago, luego Cash In/Out, luego arqueo).
