# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

import json
from unittest.mock import Mock, patch, MagicMock
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from ..controllers.gateway_integration import CashdropGatewayIntegration


class TestCashdropGatewayIntegration(TransactionCase):
    """Tests para CashdropGatewayIntegration"""
    
    def setUp(self):
        super().setUp()
        self.gateway = CashdropGatewayIntegration(
            gateway_url='https://10.0.1.140',
            timeout=10,
            verify_ssl=False,
            log_level='INFO'
        )
    
    @patch('requests.get')
    def test_login_success(self, mock_get):
        """Test login exitoso"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'result': 'success'}
        mock_get.return_value = mock_response
        
        result = self.gateway.login('user', 'password')
        
        self.assertEqual(result['result'], 'success')
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_login_timeout(self, mock_get):
        """Test login con timeout"""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        with self.assertRaises(UserError):
            self.gateway.login('user', 'password')
    
    @patch('requests.get')
    def test_login_connection_error(self, mock_get):
        """Test login con error de conexión"""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        
        with self.assertRaises(UserError):
            self.gateway.login('user', 'password')
    
    @patch('requests.get')
    def test_start_operation(self, mock_get):
        """Test iniciar operación"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'operation_id': '12345'}
        mock_get.return_value = mock_response
        
        result = self.gateway.start_operation(9999, operation_type=4)
        
        self.assertEqual(result['operation_id'], '12345')
        mock_get.assert_called_once()
        
        # Verificar que se llamó con los parámetros correctos
        call_kwargs = mock_get.call_args[1]
        self.assertEqual(call_kwargs['params']['operation'], 'startOperation')
        self.assertEqual(call_kwargs['params']['type'], 4)
        self.assertEqual(call_kwargs['params']['amount'], 9999)
    
    @patch('requests.get')
    def test_start_operation_no_operation_id(self, mock_get):
        """Test start_operation sin retornar operation_id"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'result': 'error'}
        mock_get.return_value = mock_response
        
        with self.assertRaises(UserError):
            self.gateway.start_operation(9999)
    
    @patch('requests.get')
    def test_acknowledge_operation_id(self, mock_get):
        """Test reconocer operación"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'acknowledged'}
        mock_get.return_value = mock_response
        
        result = self.gateway.acknowledge_operation_id('12345')
        
        self.assertEqual(result['status'], 'acknowledged')
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_ask_operation(self, mock_get):
        """Test preguntar operación"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                'operation': {
                    'state': 'P'
                }
            }
        }
        mock_get.return_value = mock_response
        
        result = self.gateway.ask_operation('12345')
        
        self.assertIn('data', result)
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_finish_operation(self, mock_get):
        """Test finalizar operación"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'finished'}
        mock_get.return_value = mock_response
        
        result = self.gateway.finish_operation('12345', operation_type=2)
        
        self.assertEqual(result['status'], 'finished')
        call_kwargs = mock_get.call_args[1]
        self.assertEqual(call_kwargs['params']['operation'], 'finishOperation')
        self.assertEqual(call_kwargs['params']['type'], 2)
    
    @patch('requests.get')
    def test_ask_operation_with_polling_success(self, mock_get):
        """Test polling exitoso"""
        # Primera llamada: estado P (processing)
        # Segunda llamada: estado F (finished)
        response_processing = Mock()
        response_processing.status_code = 200
        response_processing.json.return_value = {
            'data': {
                'operation': {
                    'state': 'P'
                }
            }
        }
        
        response_finished = Mock()
        response_finished.status_code = 200
        response_finished.json.return_value = {
            'data': {
                'operation': {
                    'state': 'F',
                    'totalin': 9999
                }
            }
        }
        
        mock_get.side_effect = [response_processing, response_finished]
        
        result = self.gateway.ask_operation_with_polling(
            '12345',
            polling_timeout=10,
            polling_interval=100
        )
        
        self.assertEqual(result['data']['operation']['state'], 'F')
        self.assertGreaterEqual(mock_get.call_count, 2)
    
    @patch('requests.get')
    def test_ask_operation_with_polling_timeout(self, mock_get):
        """Test polling con timeout"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                'operation': {
                    'state': 'P'  # Siempre processing
                }
            }
        }
        mock_get.return_value = mock_response
        
        with self.assertRaises(UserError):
            self.gateway.ask_operation_with_polling(
                '12345',
                polling_timeout=1,  # Timeout muy corto
                polling_interval=100
            )
    
    def test_parse_response_valid_json(self):
        """Test parsear respuesta JSON válida"""
        mock_response = Mock()
        mock_response.json.return_value = {'key': 'value'}
        
        result = self.gateway._parse_response(mock_response)
        
        self.assertEqual(result['key'], 'value')
    
    def test_parse_response_invalid_json(self):
        """Test parsear respuesta JSON inválida"""
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError('msg', 'doc', 0)
        mock_response.text = 'invalid json'
        
        with self.assertRaises(ValueError):
            self.gateway._parse_response(mock_response)
    
    @patch('requests.get')
    def test_get_connection_status_success(self, mock_get):
        """Test estado de conexión exitoso"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'result': 'success'}
        mock_get.return_value = mock_response
        
        status = self.gateway.get_connection_status()
        
        self.assertTrue(status['connected'])
        self.assertIn('timestamp', status)
    
    @patch('requests.get')
    def test_get_connection_status_failure(self, mock_get):
        """Test estado de conexión fallido"""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        
        status = self.gateway.get_connection_status()
        
        self.assertFalse(status['connected'])
        self.assertIn('message', status)
    
    @patch('requests.get')
    def test_test_full_payment_flow(self, mock_get):
        """Test flujo completo de pago"""
        # Mock de respuestas para cada operación
        responses = [
            # start_operation
            Mock(status_code=200, json=Mock(return_value={'operation_id': '12345'})),
            # acknowledge_operation_id
            Mock(status_code=200, json=Mock(return_value={'status': 'acknowledged'})),
            # ask_operation (first polling)
            Mock(status_code=200, json=Mock(return_value={
                'data': {'operation': {'state': 'F', 'totalin': 10000}}
            })),
        ]
        
        mock_get.side_effect = responses
        
        result = self.gateway.test_full_payment_flow(amount_eur=100.0)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['operation_id'], '12345')


class TestGatewayUrlConstruction(TransactionCase):
    """Tests para construcción de URLs"""
    
    def test_gateway_url_with_trailing_slash(self):
        """Test URL con slash final"""
        gateway = CashdropGatewayIntegration(
            gateway_url='https://10.0.1.140/',
            timeout=10,
            verify_ssl=False
        )
        
        self.assertEqual(gateway.endpoint, 'https://10.0.1.140/Cashdro3WS/index.php')
    
    def test_gateway_url_without_trailing_slash(self):
        """Test URL sin slash final"""
        gateway = CashdropGatewayIntegration(
            gateway_url='https://10.0.1.140',
            timeout=10,
            verify_ssl=False
        )
        
        self.assertEqual(gateway.endpoint, 'https://10.0.1.140/Cashdro3WS/index.php')
