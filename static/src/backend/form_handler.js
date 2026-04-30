/**
 * Manejador de formularios para métodos de pago POS
 * Intercepta clics en botones de validación CashDro
 */

odoo.define('cs_pos_smart_cash_cashdro.form_handler', function(require) {
    'use strict';

    var FormView = require('web.FormView');
    var clientValidator = require('cs_pos_smart_cash_cashdro.client_validator');

    // Extender FormController para interceptar acciones
    var FormController = require('web.FormController');
    
    FormController.include({
        _onButtonClicked: function(event) {
            var $button = $(event.target);
            var action = $button.attr('name');
            
            // Si es el botón de validación cliente, manejarlo especialmente
            if (action === 'action_test_connection_client') {
                event.preventDefault();
                event.stopPropagation();
                
                var recordId = this.dataManager.ids[0];
                var record = this.dataManager.getContext();
                
                var host = this.model.get(this.handle).data.cashdro_host;
                var user = this.model.get(this.handle).data.cashdro_user;
                var password = this.model.get(this.handle).data.cashdro_password;
                
                console.log('🎯 Botón validación CashDro clickeado');
                console.log('Host:', host, 'User:', user);
                
                if (host && user && password) {
                    clientValidator.validateFromClient(host, user, password, recordId);
                } else {
                    alert('⚠️ Por favor completa Host, Usuario y Contraseña');
                }
                
                return false;
            }
            
            // Para otros botones, usar comportamiento por defecto
            return this._super.apply(this, arguments);
        }
    });
});
