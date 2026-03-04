# -*- coding: utf-8 -*-
# Copyright 2026 Juan Cositt
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl)
# Ubicado en raíz del addon para evitar import circular (models y controllers lo usan).

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
    Clase para manejar comunicación con máquinas Cashdrop.
    Encapsula todos los endpoints y lógica de comunicación con el gateway.
    """

    def __init__(self, gateway_url, timeout=10, verify_ssl=False, log_level='INFO'):
        self.gateway_url = gateway_url.rstrip('/')
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.log_level = log_level
        self.endpoint = f"{self.gateway_url}/Cashdro3WS/index.php"
        _logger.setLevel(getattr(logging, log_level, logging.INFO))

    def login(self, user, password):
        try:
            _logger.debug("Intentando login en %s con usuario %s", self.gateway_url, user)
            params = {'operation': 'login', 'user': user, 'password': password}
            response = requests.get(
                self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            data = self._parse_response(response)
            _logger.info("Login exitoso en %s", self.gateway_url)
            return data
        except requests.exceptions.Timeout:
            raise UserError(_('Timeout conectando a Cashdrop'))
        except requests.exceptions.ConnectionError as e:
            raise UserError(_('Error de conexión a Cashdrop: %s') % str(e))
        except Exception as e:
            raise UserError(_('Error en login: %s') % str(e))

    def start_operation(self, amount_centavos, operation_type=4):
        try:
            _logger.debug("Iniciando operación: tipo=%s, monto=%sct", operation_type, amount_centavos)
            params = {
                'operation': 'startOperation',
                'type': operation_type,
                'amount': amount_centavos
            }
            response = requests.get(
                self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            data = self._parse_response(response)
            operation_id = data.get('operation_id')
            if not operation_id:
                raise ValueError('No se recibió operation_id')
            _logger.info("Operación iniciada: operation_id=%s", operation_id)
            return data
        except Exception as e:
            raise UserError(_('Error iniciando operación: %s') % str(e))

    def acknowledge_operation_id(self, operation_id):
        try:
            _logger.debug("Reconociendo operación: %s", operation_id)
            params = {'operation': 'acknowledgeOperationId', 'operationid': operation_id}
            response = requests.get(
                self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            data = self._parse_response(response)
            _logger.info("Operación reconocida: %s", operation_id)
            return data
        except Exception as e:
            raise UserError(_('Error reconociendo operación: %s') % str(e))

    def ask_operation(self, operation_id):
        try:
            _logger.debug("Consultando operación: %s", operation_id)
            params = {'operation': 'askOperation', 'operationid': operation_id}
            response = requests.get(
                self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            return self._parse_response(response)
        except Exception as e:
            raise UserError(_('Error consultando operación: %s') % str(e))

    def finish_operation(self, operation_id, operation_type=2):
        try:
            _logger.debug("Finalizando operación: %s, tipo=%s", operation_id, operation_type)
            params = {
                'operation': 'finishOperation',
                'operationid': operation_id,
                'type': operation_type
            }
            response = requests.get(
                self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            data = self._parse_response(response)
            _logger.info("Operación finalizada: %s", operation_id)
            return data
        except Exception as e:
            raise UserError(_('Error finalizando operación: %s') % str(e))

    def ask_operation_with_polling(self, operation_id, polling_timeout=60,
                                   polling_interval=500, max_retries=3):
        start_time = time.time()
        polling_interval_sec = polling_interval / 1000.0
        retry_count = 0
        _logger.info("Iniciando polling para operation_id=%s, timeout=%ss", operation_id, polling_timeout)
        while time.time() - start_time < polling_timeout:
            try:
                response = self.ask_operation(operation_id)
                if 'data' in response:
                    data = response['data']
                    if isinstance(data, str):
                        data = json.loads(data)
                    if isinstance(data, dict) and 'operation' in data:
                        state = data['operation'].get('state')
                        _logger.debug("Estado operación: %s", state)
                        if state == 'F':
                            _logger.info("Operación completada: %s", operation_id)
                            return response
                time.sleep(polling_interval_sec)
                retry_count = 0
            except UserError:
                retry_count += 1
                if retry_count >= max_retries:
                    raise
                _logger.warning("Error en polling, reintentando (%s/%s)", retry_count, max_retries)
                time.sleep(polling_interval_sec)
        raise UserError(_('Timeout esperando pago (operación_id=%s)') % operation_id)

    def _parse_response(self, response):
        try:
            data = response.json()
            if self.log_level == 'DEBUG':
                _logger.debug("Respuesta Cashdrop: %s", json.dumps(data, indent=2))
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parseando respuesta: {response.text}") from e

    def get_connection_status(self):
        try:
            self.login('test', 'test')
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
        try:
            amount_cents = int(amount_eur * 100)
            start_resp = self.start_operation(amount_cents)
            operation_id = start_resp.get('operation_id')
            self.acknowledge_operation_id(operation_id)
            result = self.ask_operation_with_polling(
                operation_id, polling_timeout=60, polling_interval=500
            )
            return {'success': True, 'operation_id': operation_id, 'result': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}
