# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

from unittest.mock import Mock, patch, MagicMock
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from ..controllers.payment_method_integration import PaymentMethodIntegration


class TestPaymentMethodIntegration(TransactionCase):
    """Tests para PaymentMethodIntegration"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env
        cls.transaction_model = cls.env['cashdro.transaction']
        cls.payment_method_model = cls.env['pos.payment.method']
        cls.order_model = cls.env['sale.order']
        cls.partner_model = cls.env['res.partner']
        cls.config_model = cls.env['res.config.settings']
        
        # Crear partner
        cls.partner = cls.partner_model.create({
            'name': 'Test Partner',
            'email': 'test@example.com'
        })
        
        # Crear orden
        cls.order = cls.order_model.create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.env.ref('product.product_product_1').id,
                'product_qty': 1,
                'price_unit': 99.99
            })]
        })
        
        # Crear método de pago Cashdrop
        cls.payment_method = cls.payment_method_model.create({
            'name': 'Cashdrop Payment',
            'payment_method_type': 'bank_transfer',
            'cashdro_enabled': True,
            'cashdro_host': '10.0.1.140',
            'cashdro_user': 'testuser',
            'cashdro_password': 'testpass',
            'cashdro_gateway_url': 'https://10.0.1.140'
        })
    
    def test_init_without_payment_method_id(self):
        """Test inicializar sin payment_method_id"""
        integration = PaymentMethodIntegration(self.env)
        
        self.assertIsNone(integration.payment_method)
        self.assertIsNone(integration.gateway)
    
    def test_init_with_payment_method_id(self):
        """Test inicializar con payment_method_id"""
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=self.payment_method.id
        )
        
        self.assertIsNotNone(integration.payment_method)
        self.assertIsNotNone(integration.gateway)
    
    def test_load_payment_method_not_found(self):
        """Test cargar método de pago no encontrado"""
        integration = PaymentMethodIntegration(self.env)
        
        with self.assertRaises(UserError):
            integration.load_payment_method(999999)
    
    def test_load_payment_method_cashdrop_disabled(self):
        """Test cargar método de pago con Cashdrop deshabilitado"""
        # Crear método de pago sin Cashdrop
        payment_method = self.payment_method_model.create({
            'name': 'Regular Payment',
            'payment_method_type': 'bank_transfer',
            'cashdro_enabled': False
        })
        
        integration = PaymentMethodIntegration(self.env)
        
        with self.assertRaises(UserError):
            integration.load_payment_method(payment_method.id)
    
    def test_create_transaction(self):
        """Test crear transacción"""
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=self.payment_method.id
        )
        
        transaction = integration.create_transaction(
            order_id=self.order.id,
            amount=99.99
        )
        
        self.assertEqual(transaction.amount, 99.99)
        self.assertEqual(transaction.status, 'processing')
        self.assertEqual(transaction.order_id.id, self.order.id)
    
    def test_create_transaction_invalid_amount(self):
        """Test crear transacción con monto inválido"""
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=self.payment_method.id
        )
        
        with self.assertRaises(UserError):
            integration.create_transaction(
                order_id=self.order.id,
                amount=-10.0
            )
    
    @patch('requests.get')
    def test_start_payment(self, mock_get):
        """Test iniciar pago"""
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=self.payment_method.id
        )
        
        transaction = integration.create_transaction(
            order_id=self.order.id,
            amount=99.99
        )
        
        # Mock de respuesta
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'operation_id': '12345'}
        mock_get.return_value = mock_response
        
        result = integration.start_payment(transaction)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['operation_id'], '12345')
        self.assertEqual(transaction.operation_id, '12345')
    
    @patch('requests.get')
    def test_start_payment_with_credentials(self, mock_get):
        """Test iniciar pago con credenciales"""
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=self.payment_method.id
        )
        
        transaction = integration.create_transaction(
            order_id=self.order.id,
            amount=99.99
        )
        
        # Mock de respuestas
        responses = [
            # login
            Mock(status_code=200, json=Mock(return_value={'result': 'success'})),
            # start_operation
            Mock(status_code=200, json=Mock(return_value={'operation_id': '12345'}))
        ]
        mock_get.side_effect = responses
        
        credentials = {'user': 'testuser', 'password': 'testpass'}
        result = integration.start_payment(transaction, user_credentials=credentials)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['operation_id'], '12345')
    
    @patch('requests.get')
    def test_confirm_payment(self, mock_get):
        """Test confirmar pago"""
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=self.payment_method.id
        )
        
        transaction = integration.create_transaction(
            order_id=self.order.id,
            amount=99.99
        )
        transaction.write({'operation_id': '12345'})
        
        # Mock de respuestas
        responses = [
            # acknowledge
            Mock(status_code=200, json=Mock(return_value={'status': 'acknowledged'})),
            # ask_operation
            Mock(status_code=200, json=Mock(return_value={
                'data': {'operation': {'state': 'F', 'totalin': 9999}}
            }))
        ]
        mock_get.side_effect = responses
        
        result = integration.confirm_payment(transaction)
        
        self.assertTrue(result['success'])
        self.assertEqual(transaction.status, 'confirmed')
        self.assertEqual(transaction.amount_received, 99.99)
    
    def test_confirm_payment_no_operation(self):
        """Test confirmar pago sin operación en progreso"""
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=self.payment_method.id
        )
        
        transaction = integration.create_transaction(
            order_id=self.order.id,
            amount=99.99
        )
        
        with self.assertRaises(UserError):
            integration.confirm_payment(transaction)
    
    @patch('requests.get')
    def test_cancel_payment(self, mock_get):
        """Test cancelar pago"""
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=self.payment_method.id
        )
        
        transaction = integration.create_transaction(
            order_id=self.order.id,
            amount=99.99
        )
        transaction.write({'operation_id': '12345'})
        
        # Mock de respuesta
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'finished'}
        mock_get.return_value = mock_response
        
        result = integration.cancel_payment(transaction)
        
        self.assertTrue(result['success'])
        self.assertEqual(transaction.status, 'cancelled')
    
    def test_cancel_payment_no_operation(self):
        """Test cancelar pago sin operación"""
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=self.payment_method.id
        )
        
        transaction = integration.create_transaction(
            order_id=self.order.id,
            amount=99.99
        )
        
        with self.assertRaises(UserError):
            integration.cancel_payment(transaction)
    
    @patch('requests.get')
    def test_get_payment_status(self, mock_get):
        """Test obtener estado del pago"""
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=self.payment_method.id
        )
        
        transaction = integration.create_transaction(
            order_id=self.order.id,
            amount=99.99
        )
        transaction.write({'operation_id': '12345'})
        
        # Mock de respuesta
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {'operation': {'state': 'P', 'totalin': 0}}
        }
        mock_get.return_value = mock_response
        
        result = integration.get_payment_status(transaction)
        
        self.assertIn('status', result)
        self.assertIn('operation_id', result)
        self.assertEqual(result['operation_id'], '12345')
    
    def test_validate_configuration_valid(self):
        """Test validar configuración correcta"""
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=self.payment_method.id
        )
        
        result = integration.validate_configuration()
        
        self.assertTrue(result['valid'])
        self.assertEqual(len(result['errors']), 0)
    
    def test_validate_configuration_invalid(self):
        """Test validar configuración incompleta"""
        # Crear método de pago sin host
        payment_method = self.payment_method_model.create({
            'name': 'Incomplete Payment',
            'payment_method_type': 'bank_transfer',
            'cashdro_enabled': True,
            'cashdro_user': 'testuser',
            'cashdro_password': 'testpass'
        })
        
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=payment_method.id
        )
        
        result = integration.validate_configuration()
        
        self.assertFalse(result['valid'])
        self.assertGreater(len(result['errors']), 0)
    
    @patch('requests.get')
    def test_test_gateway_connection_success(self, mock_get):
        """Test probar conexión exitosa"""
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=self.payment_method.id
        )
        
        # Mock de respuesta
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'result': 'success'}
        mock_get.return_value = mock_response
        
        result = integration.test_gateway_connection()
        
        self.assertTrue(result['connected'])
    
    @patch('requests.get')
    def test_test_gateway_connection_failure(self, mock_get):
        """Test probar conexión fallida"""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        
        integration = PaymentMethodIntegration(
            self.env,
            payment_method_id=self.payment_method.id
        )
        
        result = integration.test_gateway_connection()
        
        self.assertFalse(result['connected'])
