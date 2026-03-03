# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)

import requests
import json
import time
import logging
from datetime import datetime
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CashdropGatewayIntegration:
    """
    Clase para manejar comunicación con máquinas Cashdrop
    
    Encapsula todos los endpoints y lógica de comunicación con el gateway.
    """
    
    def __init__(self, gateway_url, timeout=10, verify_ssl=False, log_level='INFO'):
        """
        Inicializar integración con gateway
        
        Args:
            gateway_url (str): URL base del gateway (ej: https://10.0.1.140)
            timeout (int): Timeout en segundos
            verify_ssl (bool): Verificar certificado SSL
            log_level (str): Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.gateway_url = gateway_url.rstrip('/')
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.log_level = log_level
        self.endpoint = f"{self.gateway_url}/Cashdro3WS/index.php"
        
        # Configurar logger
        _logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # ========================
    # OPERACIONES BÁSICAS
    # ========================
    
    def login(self, user, password):
        """
        Operación de login en Cashdrop
        
        Args:
            user (str): Usuario
            password (str): Contraseña
            
        Returns:
            dict: Respuesta del gateway
            
        Raises:
            UserError: Si falla la conexión o autenticación
        """
        try:
            _logger.debug(f"Intentando login en {self.gateway_url} con usuario {user}")
            
            params = {
                'operation': 'login',
                'user': user,
                'password': password
            }
            
            response = requests.get(
                self.endpoint,
                params=params,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            data = self._parse_response(response)
            _logger.info(f"Login exitoso en {self.gateway_url}")
            return data
        
        except requests.exceptions.Timeout:
            msg = _('Timeout conectando a Cashdrop')
            _logger.error(msg)
            raise UserError(msg)
        
        except requests.exceptions.ConnectionError as e:
            msg = _('Error de conexión a Cashdrop: %s') % str(e)
            _logger.error(msg)
            raise UserError(msg)
        
        except Exception as e:
            msg = _('Error en login: %s') % str(e)
            _logger.error(msg)
            raise UserError(msg)
    
    def start_operation(self, amount_centavos, operation_type=4):
        """
        Iniciar operación de pago en Cashdrop
        
        Args:
            amount_centavos (int): Monto en centavos (EUR * 100)
            operation_type (int): Tipo de operación (4=venta, default)
            
        Returns:
            dict: Respuesta con operation_id
            
        Raises:
            UserError: Si falla la operación
        """
        try:
            _logger.debug(f"Iniciando operación: tipo={operation_type}, monto={amount_centavos}ct")
            
            params = {
                'operation': 'startOperation',
                'type': operation_type,
                'amount': amount_centavos
            }
            
            response = requests.get(
                self.endpoint,
                params=params,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            data = self._parse_response(response)
            operation_id = data.get('operation_id')
            
            if not operation_id:
                raise ValueError('No se recibió operation_id')
            
            _logger.info(f"Operación iniciada: operation_id={operation_id}")
            return data
        
        except Exception as e:
            msg = _('Error iniciando operación: %s') % str(e)
            _logger.error(msg)
            raise UserError(msg)
    
    def acknowledge_operation_id(self, operation_id):
        """
        Reconocer operación en Cashdrop
        
        Args:
            operation_id (str): ID de operación
            
        Returns:
            dict: Respuesta del gateway
            
        Raises:
            UserError: Si falla
        """
        try:
            _logger.debug(f"Reconociendo operación: {operation_id}")
            
            params = {
                'operation': 'acknowledgeOperationId',
                'operationid': operation_id
            }
            
            response = requests.get(
                self.endpoint,
                params=params,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            data = self._parse_response(response)
            _logger.info(f"Operación reconocida: {operation_id}")
            return data
        
        except Exception as e:
            msg = _('Error reconociendo operación: %s') % str(e)
            _logger.error(msg)
            raise UserError(msg)
    
    def ask_operation(self, operation_id):
        """
        Preguntar estado de operación (sin polling)
        
        Args:
            operation_id (str): ID de operación
            
        Returns:
            dict: Respuesta con estado de operación
            
        Raises:
            UserError: Si falla
        """
        try:
            _logger.debug(f"Consultando operación: {operation_id}")
            
            params = {
                'operation': 'askOperation',
                'operationid': operation_id
            }
            
            response = requests.get(
                self.endpoint,
                params=params,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            data = self._parse_response(response)
            return data
        
        except Exception as e:
            msg = _('Error consultando operación: %s') % str(e)
            _logger.error(msg)
            raise UserError(msg)
    
    def finish_operation(self, operation_id, operation_type=2):
        """
        Finalizar/Cancelar operación
        
        Args:
            operation_id (str): ID de operación
            operation_type (int): Tipo (2=cancelación, default)
            
        Returns:
            dict: Respuesta del gateway
            
        Raises:
            UserError: Si falla
        """
        try:
            _logger.debug(f"Finalizando operación: {operation_id}, tipo={operation_type}")
            
            params = {
                'operation': 'finishOperation',
                'operationid': operation_id,
                'type': operation_type
            }
            
            response = requests.get(
                self.endpoint,
                params=params,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            data = self._parse_response(response)
            _logger.info(f"Operación finalizada: {operation_id}")
            return data
        
        except Exception as e:
            msg = _('Error finalizando operación: %s') % str(e)
            _logger.error(msg)
            raise UserError(msg)
    
    # ========================
    # POLLING CON REINTENTOS
    # ========================
    
    def ask_operation_with_polling(self, operation_id, polling_timeout=60, 
                                    polling_interval=500, max_retries=3):
        """
        Preguntar operación con polling hasta que se complete
        
        Args:
            operation_id (str): ID de operación
            polling_timeout (int): Timeout total en segundos
            polling_interval (int): Intervalo entre intentos en ms
            max_retries (int): Máximo de reintentos en error
            
        Returns:
            dict: Respuesta final con estado y monto
            
        Raises:
            UserError: Si timeout o error crítico
        """
        start_time = time.time()
        polling_interval_sec = polling_interval / 1000.0
        retry_count = 0
        
        _logger.info(f"Iniciando polling para operation_id={operation_id}, timeout={polling_timeout}s")
        
        while time.time() - start_time < polling_timeout:
            try:
                response = self.ask_operation(operation_id)
                
                # Parsear respuesta
                if 'data' in response:
                    data = response['data']
                    if isinstance(data, str):
                        data = json.loads(data)
                    
                    if isinstance(data, dict) and 'operation' in data:
                        operation = data['operation']
                        state = operation.get('state')
                        
                        _logger.debug(f"Estado operación: {state}")
                        
                        # 'F' = finished
                        if state == 'F':
                            _logger.info(f"Operación completada: {operation_id}")
                            return response
                
                # Esperar antes de reintentar
                time.sleep(polling_interval_sec)
                retry_count = 0  # Reset retry counter en éxito
            
            except UserError:
                # Reintentar en error de conexión
                retry_count += 1
                if retry_count >= max_retries:
                    msg = _('Máximo de reintentos alcanzado')
                    _logger.error(msg)
                    raise
                
                _logger.warning(f"Error en polling, reintentando ({retry_count}/{max_retries})")
                time.sleep(polling_interval_sec)
        
        # Timeout
        msg = _('Timeout esperando pago (operación_id=%s)') % operation_id
        _logger.error(msg)
        raise UserError(msg)
    
    # ========================
    # UTILIDADES
    # ========================
    
    def _parse_response(self, response):
        """
        Parsear respuesta de Cashdrop
        
        Args:
            response: requests.Response object
            
        Returns:
            dict: Datos parseados
            
        Raises:
            ValueError: Si no se puede parsear
        """
        try:
            # Cashdrop retorna JSON
            data = response.json()
            
            if self.log_level == 'DEBUG':
                _logger.debug(f"Respuesta Cashdrop: {json.dumps(data, indent=2)}")
            
            return data
        
        except json.JSONDecodeError as e:
            msg = f"Error parseando respuesta: {response.text}"
            _logger.error(msg)
            raise ValueError(msg) from e
    
    def get_connection_status(self):
        """
        Obtener estado de conexión
        
        Returns:
            dict: {'connected': bool, 'message': str, 'timestamp': str}
        """
        try:
            self.login('test', 'test')  # Intento sin credenciales válidas
            return {
                'connected': True,
                'message': 'Gateway accesible',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'connected': False,
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def test_full_payment_flow(self, amount_eur=1.0):
        """
        Probar flujo completo de pago (requiere intervención manual)
        
        Args:
            amount_eur (float): Monto en EUR
            
        Returns:
            dict: Resultado de prueba
        """
        try:
            amount_cents = int(amount_eur * 100)
            
            # 1. Iniciar operación
            start_resp = self.start_operation(amount_cents)
            operation_id = start_resp.get('operation_id')
            
            # 2. Reconocer
            self.acknowledge_operation_id(operation_id)
            
            # 3. Polling (esperar a que usuario inserte dinero)
            result = self.ask_operation_with_polling(
                operation_id,
                polling_timeout=60,
                polling_interval=500
            )
            
            return {
                'success': True,
                'operation_id': operation_id,
                'result': result
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
