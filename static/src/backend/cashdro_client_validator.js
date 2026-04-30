/**
 * Cliente de validación CashDro desde navegador
 * Ejecuta fetch directamente desde el cliente para validar conexión
 */

odoo.define('cs_pos_smart_cash_cashdro.client_validator', function(require) {
    'use strict';

    var rpc = require('web.rpc');
    
    // Exponer la función globalmente para que pueda ser llamada desde el botón
    window.cashdroValidateFromClient = function(host, user, password, recordId) {
        console.log('🚀 Iniciando validación CashDro desde navegador');
        console.log('📡 Conectando a: https://' + host + '/Cashdro3WS/index.php');

        var url = 'https://' + host + '/Cashdro3WS/index.php';
        var credentials = btoa(user + ':' + password); // Base64 encoding

        return fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': 'Basic ' + credentials,
                'Content-Type': 'application/json'
            },
            mode: 'cors',
            credentials: 'omit'
        })
        .then(function(response) {
            console.log('📡 Respuesta HTTP:', response.status, response.statusText);
            
            if (response.ok) {
                console.log('✅ Conexión exitosa');
                alert('✅ ÉXITO: Conexión exitosa a CashDro en ' + host);
                
                // Actualizar estado en el servidor
                return rpc.query({
                    model: 'pos.payment.method',
                    method: 'update_cashdro_status_from_client',
                    args: [recordId, true, null]
                });
            } else {
                console.log('❌ Error HTTP:', response.status);
                alert('❌ Error: HTTP ' + response.status + ' - ' + response.statusText);
            }
        })
        .catch(function(error) {
            console.error('❌ Error de conexión:', error);
            
            // Diagnóstico
            var diagnostic = 'Error: ' + error.message;
            if (error.message.includes('Failed to fetch')) {
                diagnostic += '\n\nPosibles causas:\n' +
                    '1. CashDro no está en línea\n' +
                    '2. No hay conexión de red a ' + host + '\n' +
                    '3. CORS bloqueado por CashDro\n' +
                    '4. Certificado SSL inválido (si usas HTTPS)\n\n' +
                    'Abre la consola (F12) para ver más detalles';
            }
            
            alert('❌ No se pudo conectar:\n' + diagnostic);
            
            // Actualizar estado en servidor
            return rpc.query({
                model: 'pos.payment.method',
                method: 'update_cashdro_status_from_client',
                args: [recordId, false, error.message]
            });
        });
    };
    
    return {
        validateFromClient: window.cashdroValidateFromClient
    };
});
