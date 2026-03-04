# Flujo de Pagos - Cashdrop + Redsys

## Opción 1: Pago en Kiosko (Quiosco Físico)

### Flujo de Usuario
1. Cliente se acerca al kiosko
2. Realiza su pedido en la pantalla táctil
3. Selecciona método de pago:
   - **Cashdrop (Efectivo)**: Inserta dinero, máquina devuelve cambio automáticamente
   - **TPV (Tarjeta)**: Pasa tarjeta por terminal
4. Pago confirmado
5. Pedido se envía a cocina automáticamente
6. **FIN**

### Integración Técnica - Cashdrop
- Cliente inserta dinero en máquina física (10.0.1.140)
- POS envía orden de pago a Cashdrop mediante API
- Máquina procesa el pago
- Devuelve cambio automáticamente
- Confirma a Odoo el monto recibido
- Transacción se registra en `cashdro.transaction`
- Pedido va a cocina

### Integración Técnica - TPV
- Cliente pasa tarjeta por terminal física
- Terminal procesa pago
- Confirma a Odoo
- Pedido va a cocina

---

## Opción 2: Pago Online (Web/Mobile)

### Flujo de Usuario
1. Cliente accede a web o app mobile
2. Realiza su pedido online
3. Procede al checkout
4. Selecciona **Redsys (Tarjeta de Crédito)**
5. Redirigido a pasarela Redsys
6. Completa datos de tarjeta
7. Pago confirmado
8. Pedido se envía a cocina automáticamente
9. **FIN**

### Integración Técnica - Redsys
- Formulario de pago en web
- Gateway Redsys (banco)
- Confirmación de pago IPN/Webhook
- Registro en Odoo
- Pedido automáticamente a cocina

---

## Estado Actual
- ✅ Módulo Cashdrop desarrollado e instalado
- ✅ Conexión a máquina Cashdrop verificada
- ⏳ Habilitación de pago en efectivo en Kiosko (SIGUIENTE)
- ⏳ Integración Cashdrop con flujo de pago
- ⏳ Implementación de Redsys
- ⏳ Integración web/mobile con Redsys

---

## Próximos Pasos
1. Habilitar pago en efectivo en Kiosko
2. Configurar Cashdrop como método de pago en caja
3. Probar flujo completo Kiosko + Cashdrop
4. Implementar Redsys para pagos online
5. Integrar web/mobile con Redsys
