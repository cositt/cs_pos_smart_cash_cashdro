# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

import json
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestCashdroTransaction(TransactionCase):
    """Tests para modelo cashdro.transaction"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transaction_model = cls.env['cashdro.transaction']
        cls.payment_method_model = cls.env['pos.payment.method']
        cls.order_model = cls.env['sale.order']
        cls.partner_model = cls.env['res.partner']
        cls.user_model = cls.env['res.users']
        
        # Crear partner de prueba
        cls.partner = cls.partner_model.create({
            'name': 'Test Partner',
            'email': 'test@example.com'
        })
        
        # Crear orden de prueba
        cls.order = cls.order_model.create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.env.ref('product.product_product_1').id,
                'product_qty': 1,
                'price_unit': 99.99
            })]
        })
    
    def test_create_transaction(self):
        """Test crear transacción básica"""
        transaction = self.transaction_model.create({
            'transaction_id': 'test-uuid-001',
            'order_id': self.order.id,
            'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
            'amount': 99.99,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'processing'
        })
        
        self.assertEqual(transaction.amount, 99.99)
        self.assertEqual(transaction.status, 'processing')
        self.assertFalse(transaction.operation_id)
    
    def test_transaction_name_generated(self):
        """Test que se genera nombre secuencial"""
        transaction = self.transaction_model.create({
            'transaction_id': 'test-uuid-002',
            'order_id': self.order.id,
            'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
            'amount': 50.00,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'processing'
        })
        
        # Debe tener nombre generado automáticamente
        self.assertTrue(transaction.name)
        self.assertNotEqual(transaction.name, '')
    
    def test_amount_validation(self):
        """Test validación de monto positivo"""
        with self.assertRaises(ValidationError):
            self.transaction_model.create({
                'transaction_id': 'test-uuid-003',
                'order_id': self.order.id,
                'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
                'amount': -10.00,  # Negativo
                'currency_id': self.env.ref('base.EUR').id,
                'status': 'processing'
            })
    
    def test_amount_received_validation(self):
        """Test validación de monto recibido"""
        transaction = self.transaction_model.create({
            'transaction_id': 'test-uuid-004',
            'order_id': self.order.id,
            'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
            'amount': 99.99,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'processing'
        })
        
        with self.assertRaises(ValidationError):
            transaction.write({'amount_received': -5.00})
    
    def test_action_confirm(self):
        """Test confirmar transacción"""
        transaction = self.transaction_model.create({
            'transaction_id': 'test-uuid-005',
            'order_id': self.order.id,
            'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
            'amount': 99.99,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'processing'
        })
        
        transaction.action_confirm()
        self.assertEqual(transaction.status, 'confirmed')
        self.assertTrue(transaction.confirmed_at)
    
    def test_action_cancel(self):
        """Test cancelar transacción"""
        transaction = self.transaction_model.create({
            'transaction_id': 'test-uuid-006',
            'order_id': self.order.id,
            'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
            'amount': 99.99,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'processing'
        })
        
        transaction.action_cancel()
        self.assertEqual(transaction.status, 'cancelled')
        self.assertTrue(transaction.cancelled_at)
    
    def test_action_retry(self):
        """Test reintentar transacción con error"""
        transaction = self.transaction_model.create({
            'transaction_id': 'test-uuid-007',
            'order_id': self.order.id,
            'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
            'amount': 99.99,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'error',
            'error_message': 'Test error'
        })
        
        transaction.action_retry()
        self.assertEqual(transaction.status, 'processing')
        self.assertFalse(transaction.error_message)
    
    def test_mark_error(self):
        """Test marcar como error"""
        transaction = self.transaction_model.create({
            'transaction_id': 'test-uuid-008',
            'order_id': self.order.id,
            'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
            'amount': 99.99,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'processing'
        })
        
        error_msg = 'Connection timeout'
        transaction.mark_error(error_msg)
        self.assertEqual(transaction.status, 'error')
        self.assertEqual(transaction.error_message, error_msg)
    
    def test_mark_timeout(self):
        """Test marcar como timeout"""
        transaction = self.transaction_model.create({
            'transaction_id': 'test-uuid-009',
            'order_id': self.order.id,
            'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
            'amount': 99.99,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'processing'
        })
        
        transaction.mark_timeout()
        self.assertEqual(transaction.status, 'timeout')
        self.assertTrue('Timeout' in transaction.error_message)
    
    def test_get_by_transaction_id(self):
        """Test búsqueda por transaction_id"""
        txn_id = 'test-uuid-010'
        transaction = self.transaction_model.create({
            'transaction_id': txn_id,
            'order_id': self.order.id,
            'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
            'amount': 99.99,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'processing'
        })
        
        found = self.transaction_model.get_by_transaction_id(txn_id)
        self.assertEqual(found.id, transaction.id)
    
    def test_get_by_operation_id(self):
        """Test búsqueda por operation_id"""
        op_id = '12345'
        transaction = self.transaction_model.create({
            'transaction_id': 'test-uuid-011',
            'operation_id': op_id,
            'order_id': self.order.id,
            'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
            'amount': 99.99,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'processing'
        })
        
        found = self.transaction_model.get_by_operation_id(op_id)
        self.assertEqual(found.id, transaction.id)
    
    def test_update_from_gateway_response(self):
        """Test actualizar desde respuesta del gateway"""
        transaction = self.transaction_model.create({
            'transaction_id': 'test-uuid-012',
            'order_id': self.order.id,
            'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
            'amount': 99.99,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'processing'
        })
        
        response = {
            'operation_id': '54321',
            'data': {
                'operation': {
                    'state': 'F',
                    'totalin': 9999
                }
            }
        }
        
        transaction.update_from_gateway_response(response)
        self.assertEqual(transaction.operation_id, '54321')
        self.assertEqual(transaction.amount_received, 99.99)
        self.assertEqual(transaction.status, 'confirmed')
    
    def test_is_confirmed(self):
        """Test estado confirmado"""
        transaction = self.transaction_model.create({
            'transaction_id': 'test-uuid-013',
            'order_id': self.order.id,
            'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
            'amount': 99.99,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'confirmed'
        })
        
        self.assertTrue(transaction.is_confirmed())
    
    def test_is_error(self):
        """Test estado error"""
        transaction = self.transaction_model.create({
            'transaction_id': 'test-uuid-014',
            'order_id': self.order.id,
            'payment_method_id': self.env.ref('point_of_sale.pos_payment_method_cash').id,
            'amount': 99.99,
            'currency_id': self.env.ref('base.EUR').id,
            'status': 'error'
        })
        
        self.assertTrue(transaction.is_error())


class TestPosPaymentMethodCashdro(TransactionCase):
    """Tests para extensión de pos.payment.method"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payment_method_model = cls.env['pos.payment.method']
    
    def test_payment_method_cashdro_fields(self):
        """Test que existen campos de Cashdro en payment method"""
        payment_method = self.env.ref('point_of_sale.pos_payment_method_cash')
        
        # Verificar que el modelo tiene los campos
        self.assertTrue(hasattr(payment_method, 'cashdro_enabled'))
        self.assertTrue(hasattr(payment_method, 'cashdro_host'))
        self.assertTrue(hasattr(payment_method, 'cashdro_user'))
        self.assertTrue(hasattr(payment_method, 'cashdro_password'))
        self.assertTrue(hasattr(payment_method, 'cashdro_gateway_url'))
        self.assertTrue(hasattr(payment_method, 'cashdro_connection_status'))


class TestResConfigSettings(TransactionCase):
    """Tests para configuración global"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config_model = cls.env['res.config.settings']
    
    def test_get_cashdro_config(self):
        """Test obtener configuración completa"""
        config = self.config_model.get_cashdro_config()
        
        # Verificar que contiene las keys esperadas
        expected_keys = [
            'enabled', 'gateway_url', 'connection_timeout',
            'polling_timeout', 'polling_interval', 'verify_ssl',
            'max_retries', 'retry_delay', 'auto_confirm',
            'log_level', 'test_mode', 'keep_logs', 'retention_days'
        ]
        
        for key in expected_keys:
            self.assertIn(key, config)
    
    def test_config_defaults(self):
        """Test valores por defecto"""
        config = self.config_model.get_cashdro_config()
        
        self.assertEqual(config['connection_timeout'], 10)
        self.assertEqual(config['polling_timeout'], 180)
        self.assertEqual(config['polling_interval'], 500)
        self.assertEqual(config['max_retries'], 3)
        self.assertEqual(config['retry_delay'], 2)
        self.assertTrue(config['auto_confirm'])
        self.assertEqual(config['log_level'], 'INFO')
    
    def test_timeout_validation(self):
        """Test validación de timeouts"""
        with self.assertRaises(ValidationError):
            settings = self.config_model.create({
                'cashdro_connection_timeout': -1
            })
