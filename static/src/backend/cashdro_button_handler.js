console.log("🔥 CASHDRO HANDLER CARGADO");

odoo.define('cs_pos_smart_cash_cashdro.button_handler', function(require) {
    'use strict';
    console.log("🔥 MODULO ODOO CASHDRO INICIADO");
    
    var FormController = require('web.FormController');
    var rpc = require('web.rpc');
    
    FormController.include({
        willStart: function() {
            var self = this;
            console.log("🔥 FormController willStart, contexto:", this.initialState.context);
            
            // Si el contexto tiene cashdro_validate, hacer el fetch
            if (this.initialState.context && this.initialState.context.cashdro_validate) {
                console.log("🚀 CASHDRO VALIDATION INICIADA");
                
                var host = this.initialState.context.cashdro_host;
                var user = this.initialState.context.cashdro_user;
                var password = this.initialState.context.cashdro_password;
                
                console.log('Host:', host, 'User:', user);
                
                if (host && user && password) {
                    var url = 'https://' + host + '/Cashdro3WS/index.php';
                    var credentials = btoa(user + ':' + password);
                    
                    console.log('📡 Fetch a:', url);
                    
                    fetch(url, {
                        method: 'GET',
                        headers: {
                            'Authorization': 'Basic ' + credentials,
                            'Content-Type': 'application/json'
                        },
                        mode: 'cors',
                        credentials: 'omit'
                    })
                    .then(function(response) {
                        console.log('✅ Respuesta:', response.status);
                        if (response.ok) {
                            alert('✅ ÉXITO: Conexión a CashDro exitosa');
                        } else {
                            alert('❌ Error HTTP ' + response.status);
                        }
                        self.do_action({
                            type: 'ir.actions.act_window_close'
                        });
                    })
                    .catch(function(error) {
                        console.error('❌ Error:', error);
                        alert('❌ No se pudo conectar: ' + error.message);
                        self.do_action({
                            type: 'ir.actions.act_window_close'
                        });
                    });
                }
            }
            
            return this._super.apply(this, arguments);
        }
    });
});
