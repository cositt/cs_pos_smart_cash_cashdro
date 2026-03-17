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

    def __init__(self, gateway_url, timeout=10, verify_ssl=False, log_level='INFO', user=None, password=None):
        self.gateway_url = gateway_url.rstrip('/')
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.log_level = log_level
        # index3.php: pagos (type=3). index.php: consultas y operaciones admin (getInfoDevices, type=12, setDepositLevels)
        self.endpoint = f"{self.gateway_url}/Cashdro3WS/index3.php"
        self.endpoint_admin = f"{self.gateway_url}/Cashdro3WS/index.php"
        self.user = user
        self.password = password
        # Canal de control usado por la UI web oficial de Cashdro.
        # Tráfico capturado: name=Exchange_Machine&password=-99
        self.exchange_user = "Exchange_Machine"
        self.exchange_password = "-99"
        # movimientos_funcionan: posid=1 (entero), posuser="odoo" para que la máquina active
        self.posid = 1
        self.posuser = "odoo"
        _logger.setLevel(getattr(logging, log_level, logging.INFO))

    def login(self, user, password):
        """Login en index3.php (mismo flujo que cobro_20centimos_FUNCIONA.py)."""
        try:
            _logger.info("CashDro LOGIN: endpoint=%s user=%s", self.endpoint, user)
            params = {'operation': 'login', 'name': user, 'password': password}
            response = requests.get(
                self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            data = self._parse_response(response)
            _logger.info("CashDro LOGIN OK: code=%s", data.get('code'))
            return data
        except requests.exceptions.Timeout:
            _logger.error("CashDro LOGIN TIMEOUT: %s", self.endpoint)
            raise UserError(_('Timeout conectando a CashDro. Comprueba que Odoo pueda alcanzar %s (ej. desde Docker).') % self.gateway_url)
        except requests.exceptions.ConnectionError as e:
            _logger.error("CashDro LOGIN CONNECTION ERROR: %s -> %s", self.endpoint, e)
            raise UserError(_('No hay conexión con CashDro en %s. Comprueba la IP y que Odoo (p. ej. contenedor Docker) pueda alcanzar la máquina.') % self.gateway_url)
        except Exception as e:
            _logger.exception("CashDro LOGIN error")
            raise UserError(_('Error en login: %s') % str(e))

    def start_operation(self, amount_eur, operation_type=4):
        """
        Inicia operación en la máquina.
        amount_eur: monto en euros (ej. 0.20 para 20 céntimos). Se envía en céntimos dentro de parameters.
        operation_type=4: VENTA/cobro (movimientos_funcionan/cobro_20centimos_FUNCIONA.py). type=3 también válido.
        """
        try:
            # Flujo idéntico a cobro_20centimos_FUNCIONA.py: index3.php, login → startOperation → acknowledge
            self.login(self.user, self.password)
            _logger.debug("Iniciando operación Cashdro: tipo=%s, monto=%.2f EUR", operation_type, amount_eur)
            amount_cents = str(int(round(float(amount_eur) * 100)))
            params = {
                'operation': 'startOperation',
                'name': self.user,
                'password': self.password,
                'type': operation_type,
                'posid': self.posid,
                'parameters': json.dumps({'amount': amount_cents}),
                'startnow': 'true',
                'posuser': self.posuser,
            }
            log_params = params.copy()
            # No loguear la contraseña en claro
            if 'password' in log_params:
                log_params['password'] = '***'
            _logger.info(
                "CashDro startOperation REQUEST: endpoint=%s type=%s (%s) amount_eur=%s amount_cents=%s params=%s",
                self.endpoint,
                operation_type,
                "PAGO/dispensa" if operation_type == 3 else "VENTA/cobro",
                amount_eur,
                amount_cents,
                log_params,
            )
            response = requests.get(
                self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            data = self._parse_response(response)
            operation_id = None
            if data.get('code') == 1:
                response_obj = data.get('response', {})
                if isinstance(response_obj, dict):
                    operation_id = response_obj.get('operation', {}).get('operationId')
                if not operation_id and data.get('data'):
                    resp_data = data.get('data')
                    if isinstance(resp_data, str) and resp_data.isdigit():
                        operation_id = resp_data
            if not operation_id:
                _logger.error("CashDro startOperation SIN operation_id: code=%s response=%s", data.get('code'), data)
                raise ValueError('No se recibió operation_id en la respuesta')
            _logger.info("CashDro startOperation OK: operation_id=%s", operation_id)
            # Acknowledge obligatorio para que la máquina muestre pantalla de pago (cobro_20centimos_FUNCIONA.py)
            try:
                self.acknowledge_operation_id(operation_id)
            except Exception as ack_err:
                _logger.warning("acknowledgeOperationId tras start: %s", ack_err)
            result = data.copy()
            result['operation_id'] = operation_id
            return result
        except requests.exceptions.Timeout:
            _logger.error("CashDro startOperation TIMEOUT: %s (no llega señal a la máquina)", self.endpoint)
            raise UserError(_('Timeout: la máquina CashDro no responde. Comprueba IP y que el contenedor pueda alcanzar %s') % self.gateway_url)
        except requests.exceptions.ConnectionError as e:
            _logger.error("CashDro startOperation CONNECTION ERROR: %s -> %s (no llega señal)", self.endpoint, e)
            raise UserError(_('No hay conexión con CashDro en %s. Comprueba la IP y que Odoo (Docker) pueda alcanzar la máquina.') % self.gateway_url)
        except Exception as e:
            _logger.exception("CashDro startOperation error")
            raise UserError(_('Error iniciando operación: %s') % str(e))

    def acknowledge_operation_id(self, operation_id):
        """DEPRECATED: acknowledgeOperationId causes premature operation termination.
        This method is kept for backwards compatibility but should not be used in payment flows.
        """
        try:
            _logger.debug("[DEPRECATED] Reconociendo operación: %s", operation_id)
            params = {
                'operation': 'acknowledgeOperationId',
                'name': self.user,
                'password': self.password,
                'operationId': operation_id,
                'includeImages': 1,
            }
            response = requests.get(
                self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            data = self._parse_response(response)
            if data.get('code') == 1:
                _logger.info("[DEPRECATED] Operación reconocida: %s", operation_id)
            else:
                _logger.warning("[DEPRECATED] Acknowledge returned code %s", data.get('code'))
            return data
        except Exception as e:
            raise UserError(_('Error en acknowledgeOperationId: %s') % str(e))

    def ask_operation(self, operation_id):
        """Consulta el estado detallado de una operación (askOperation).

        Según el manual v4.15, la respuesta viene como:
        {
            "code": <code>,
            "response": {
                "errorMessage": "none",
                "operation": {
                    "operation": {
                        "operationid": "<operationId>",
                        "state": "<state>",
                        ...
                    },
                    "devices": [...],
                    "messages": [],
                    "withError": "<withError>",
                    ...
                }
            }
        }
        """
        try:
            _logger.debug("Consultando estado de operación: %s", operation_id)
            params = {
                'operation': 'askOperation',
                'name': self.exchange_user,
                'password': self.exchange_password,
                'operationId': operation_id,  # Nota: operationId (con Id mayúscula)
                'includeImages': 1,
            }
            response = requests.get(
                self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            data = self._parse_response(response)

            # Normalizar estructura de respuesta (response / data + operation / operation.operation)
            normalized_operation = {}
            try:
                container = data.get('response')
                if not container and data.get('data') is not None:
                    container = data.get('data')
                    if isinstance(container, str):
                        container = json.loads(container)
                if isinstance(container, dict):
                    op_wrapper = container.get('operation') or {}
                    if isinstance(op_wrapper, dict) and 'operation' in op_wrapper:
                        normalized_operation = op_wrapper.get('operation') or {}
                    else:
                        normalized_operation = op_wrapper
            except Exception as norm_err:
                _logger.warning("No se pudo normalizar respuesta askOperation %s: %s", operation_id, norm_err)

            state = normalized_operation.get('state', '?') if isinstance(normalized_operation, dict) else '?'
            _logger.debug("Estado actual de operación %s: %s", operation_id, state)

            # Adjuntar operación normalizada para que capas superiores puedan reutilizarla
            if isinstance(data, dict):
                data.setdefault('normalized_operation', normalized_operation)

            return data
        except Exception as e:
            raise UserError(_('Error consultando operación: %s') % str(e))

    def ask_operation_executing(self):
        """Consulta operación en ejecución usando credenciales del canal web."""
        try:
            params = {
                'operation': 'askOperationExecuting',
                'name': self.exchange_user,
                'password': self.exchange_password,
            }
            response = requests.get(
                self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            return self._parse_response(response)
        except Exception as e:
            raise UserError(_('Error consultando operación en ejecución: %s') % str(e))

    def get_main_currency(self):
        """Obtiene moneda principal usando credenciales del canal web."""
        try:
            params = {
                'operation': 'getMainCurrency',
                'name': self.exchange_user,
                'password': self.exchange_password,
            }
            response = requests.get(
                self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            return self._parse_response(response)
        except Exception as e:
            raise UserError(_('Error obteniendo moneda principal: %s') % str(e))

    def finish_operation(self, operation_id, operation_type=1):
        """Finaliza una operación.
        
        Args:
            operation_id: ID de la operación a finalizar
            operation_type: 1 = finalización exitosa, 2 = cancelación
        """
        try:
            _logger.debug("Finalizando operación: %s, tipo=%s", operation_id, operation_type)
            params = {
                'operation': 'finishOperation',
                'name': self.user,
                'password': self.password,
                'operationId': operation_id,  # Nota: operationId (con Id mayúscula)
                'type': operation_type  # 1 = finalizar, 2 = cancelar
            }
            response = requests.get(
                self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            data = self._parse_response(response)
            if data.get('code') == 1:
                finish_type = 'finalizada' if operation_type == 1 else 'cancelada'
                _logger.info("Operación %s: %s", finish_type, operation_id)
            return data
        except Exception as e:
            raise UserError(_('Error finalizando operación: %s') % str(e))

    def ask_operation_with_polling(self, operation_id, polling_timeout=180,
                                   polling_interval=500, max_retries=3):
        start_time = time.time()
        polling_interval_sec = polling_interval / 1000.0
        retry_count = 0
        _logger.info("Iniciando polling para operation_id=%s, timeout=%ss", operation_id, polling_timeout)
        while time.time() - start_time < polling_timeout:
            try:
                response = self.ask_operation(operation_id)
                # Usar operación normalizada si está presente (añadida en ask_operation)
                op = None
                if isinstance(response, dict):
                    op = response.get('normalized_operation')
                    if not op:
                        container = response.get('response') or response.get('data')
                        if isinstance(container, str):
                            try:
                                container = json.loads(container)
                            except Exception:
                                container = None
                        if isinstance(container, dict):
                            op_wrapper = container.get('operation') or {}
                            if isinstance(op_wrapper, dict) and 'operation' in op_wrapper:
                                op = op_wrapper.get('operation')
                            else:
                                op = op_wrapper

                state = op.get('state') if isinstance(op, dict) else None
                _logger.debug("Estado operación (polling): %s", state)
                if state == 'F':
                    _logger.info("Operación completada: %s", operation_id)
                    return response

                # Modo investigación: log completo de la respuesta de la máquina cuando no está finalizada
                _logger.info(
                    "[CASHDRO INVESTIGACIÓN] askOperation response (state=%s): %s",
                    state or '?',
                    json.dumps(response, default=str, ensure_ascii=False)[:2000],
                )

                time.sleep(polling_interval_sec)
                retry_count = 0
            except UserError:
                retry_count += 1
                if retry_count >= max_retries:
                    raise
                _logger.warning("Error en polling, reintentando (%s/%s)", retry_count, max_retries)
                time.sleep(polling_interval_sec)
        raise UserError(_('Timeout esperando pago (operación_id=%s)') % operation_id)

    def _request_post(self, params, use_admin=True):
        """Petición POST al endpoint admin (index.php) para getInfoDevices, getActiveCurrencies, etc."""
        url = self.endpoint_admin if use_admin else self.endpoint
        response = requests.post(
            url, params=params, timeout=self.timeout, verify=self.verify_ssl
        )
        response.raise_for_status()
        return self._parse_response(response)

    def get_info_devices(self):
        """Información de dispositivos (billetes/monedas, estado). Usa index.php POST."""
        try:
            params = {
                'operation': 'getInfoDevices',
                'name': self.user,
                'password': self.password,
            }
            return self._request_post(params)
        except Exception as e:
            raise UserError(_('Error getInfoDevices: %s') % str(e))

    def get_active_currencies(self):
        """Monedas/denominaciones activas y niveles. Usa index.php POST."""
        try:
            params = {
                'operation': 'getActiveCurrencies',
                'name': self.user,
                'password': self.password,
                'includeImages': '0',
            }
            return self._request_post(params)
        except Exception as e:
            raise UserError(_('Error getActiveCurrencies: %s') % str(e))

    def get_pieces_currency(self, currency_id='EUR', include_images='0', include_levels='1'):
        """
        Estado de fianza: piezas por denominación (getPiecesCurrency).
        URL: index.php?operation=getPiecesCurrency&currencyId=EUR&includeImages=0&includeLevels=1&name=...&password=...
        """
        try:
            params = {
                'operation': 'getPiecesCurrency',
                'name': self.user,
                'password': self.password,
                'currencyId': currency_id,
                'includeImages': include_images,
                'includeLevels': include_levels,
            }
            return self._request_post(params)
        except Exception as e:
            _logger.warning("get_pieces_currency: %s", e)
            return {'code': 0, 'data': []}

    def get_consult_levels(self):
        """
        Consulta de niveles (monedas/billetes en reciclador y casete).
        Ejecuta type=12 + acknowledge + espera 3s + askOperation + finish y extrae devices[].pieces.
        Devuelve (result_dict, debug_snippet) para guardar en state_raw.
        """
        import time
        moneda_denom = [2.0, 1.0, 0.5, 0.2, 0.1, 0.05]
        billete_denom = [100, 50, 20, 10, 5]
        result = {
            'moneda': [(v, 0, 0.0, 0, 0.0) for v in moneda_denom],
            'billete': [(v, 0, 0.0, 0, 0.0) for v in billete_denom],
        }
        debug_snippet = {}
        operation_id = None
        try:
            start_res = self.start_operation_admin(operation_type=12, alias_id='', is_manual='0', parameters='')
            operation_id = start_res.get('operation_id')
            if not operation_id:
                return result, debug_snippet
            time.sleep(0.5)
            self._request_post({
                'operation': 'acknowledgeOperationId',
                'name': self.user,
                'password': self.password,
                'operationId': operation_id,
            })
            time.sleep(3)
            ask_res = self._request_post({
                'operation': 'askOperation',
                'name': self.user,
                'password': self.password,
                'operationId': operation_id,
                'includeImages': '0',
            })
            debug_snippet['askOperation_code'] = ask_res.get('code')
            debug_snippet['askOperation_data_keys'] = list(ask_res.keys())
            data = ask_res.get('data')
            if data is None:
                resp_op = (ask_res.get('response') or {}).get('operation') or ask_res.get('response')
                if isinstance(resp_op, dict):
                    data = resp_op
                elif isinstance(resp_op, str):
                    try:
                        data = json.loads(resp_op)
                    except Exception:
                        data = {}
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    data = {}
            if isinstance(data, dict):
                debug_snippet['data_keys'] = list(data.keys())
            devices = []
            if isinstance(data, dict):
                devices = data.get('devices') or data.get('Devices') or []
            for dev in devices:
                typ = str(dev.get('Type') or dev.get('type') or '')
                pieces = dev.get('pieces') or dev.get('Pieces') or []
                for p in pieces:
                    if not isinstance(p, dict):
                        continue
                    val_raw = p.get('value') or p.get('Value') or 0
                    try:
                        val_int = int(float(val_raw))
                    except Exception:
                        continue
                    rec = int(float(p.get('finishlevelrecycler') or p.get('startlevelrecycler') or p.get('unitsinrecycler') or p.get('unitsInRecycler') or 0))
                    cas = int(float(p.get('finishlevelcassette') or p.get('startlevelcassette') or p.get('unitsincassette') or p.get('unitsInCassette') or 0))
                    if typ == '2':
                        val_eur = val_int / 100.0
                        idx = next((i for i, d in enumerate(moneda_denom) if abs(d - val_eur) < 0.01), None)
                        if idx is not None:
                            total_rec = rec * val_eur
                            total_cas = cas * val_eur
                            result['moneda'][idx] = (moneda_denom[idx], rec, total_rec, cas, total_cas)
                    elif typ == '3':
                        val_eur = (val_int / 100.0) if val_int >= 100 else val_int
                        if val_eur not in billete_denom and val_int in (5, 10, 20, 50, 100, 200):
                            val_eur = val_int
                        if val_eur in billete_denom:
                            idx = billete_denom.index(val_eur)
                            total_rec = rec * val_eur
                            total_cas = cas * val_eur
                            result['billete'][idx] = (val_eur, rec, total_rec, cas, total_cas)
            if isinstance(data, dict) and devices:
                debug_snippet['devices_count'] = len(devices)
                debug_snippet['devices_types'] = [str(d.get('Type') or d.get('type')) for d in devices]
        except Exception as e:
            _logger.warning("get_consult_levels: %s", e)
            debug_snippet['error'] = str(e)
        finally:
            if operation_id:
                try:
                    self._request_post({
                        'operation': 'finishOperation',
                        'name': self.user,
                        'password': self.password,
                        'operationId': operation_id,
                        'type': 1,
                    })
                except Exception as e2:
                    _logger.warning("get_consult_levels finish: %s", e2)
        return result, debug_snippet

    def initialize_levels(self, posid='Terminal3', posuser='OdooInit', alias_id='INITLEVELS'):
        """
        Inicializa niveles de la máquina (operación administrativa type=12).

        Flujo probado contra la máquina real y descrito en la documentación:
        - startOperation (type=12) en index3.php
        - acknowledgeOperationId
        - askOperation (para forzar la ejecución y loguear el estado)
        - finishOperation
        """
        try:
            # START type=12 en index3.php
            params_start = {
                'operation': 'startOperation',
                'name': self.user,
                'password': self.password,
                'type': 12,
                'posid': posid,
                'posuser': posuser,
                'aliasid': alias_id,
            }
            _logger.info("CashDro initialize_levels: startOperation type=12 posid=%s posuser=%s", posid, posuser)
            import requests as _requests
            resp = _requests.get(self.endpoint, params=params_start, timeout=self.timeout, verify=self.verify_ssl)
            resp.raise_for_status()
            start_data = self._parse_response(resp)
            operation_id = (start_data.get('response') or {}).get('operation', {}).get('operationId') or start_data.get('data')
            if not operation_id:
                _logger.error("initialize_levels: sin operation_id en respuesta %s", start_data)
                raise UserError(_('No se pudo iniciar la operación de inicializar niveles (type=12).'))

            _logger.info("CashDro initialize_levels: operation_id=%s", operation_id)

            # ACKNOWLEDGE
            try:
                self.acknowledge_operation_id(operation_id)
            except Exception as ack_err:
                _logger.warning("initialize_levels acknowledge error: %s", ack_err)

            # ASK (solo para registrar estado, no es crítico)
            try:
                ask_res = self.ask_operation(operation_id)
                _logger.debug("initialize_levels askOperation: %s", ask_res)
            except Exception as ask_err:
                _logger.warning("initialize_levels askOperation error: %s", ask_err)

            # FINISH
            try:
                finish_res = self.finish_operation(operation_id, operation_type=1)
                _logger.info("CashDro initialize_levels finishOperation code=%s", finish_res.get('code'))
            except Exception as fin_err:
                _logger.warning("initialize_levels finishOperation error: %s", fin_err)

            return {'start': start_data}
        except Exception as e:
            _logger.exception("initialize_levels error")
            raise UserError(_('Error inicializando niveles (type=12): %s') % str(e))

    def ask_operation_executing_admin(self):
        """Estado global (operación en ejecución). Credenciales Exchange_Machine/-99."""
        try:
            params = {
                'operation': 'askOperationExecuting',
                'name': self.exchange_user,
                'password': self.exchange_password,
            }
            return self._request_post(params)
        except Exception as e:
            raise UserError(_('Error askOperationExecuting: %s') % str(e))

    def start_operation_admin(self, operation_type, alias_id='', is_manual='0', parameters=''):
        """
        Inicia operación administrativa. Usa index.php POST.
        operation_type: 16=ingresar genérico (carga dinero), 1=carga manual, 12=inicializar niveles.
        """
        try:
            _logger.info("CashDro start_operation_admin: endpoint=%s type=%s", self.endpoint_admin, operation_type)
            params = {
                'operation': 'startOperation',
                'name': self.user,
                'password': self.password,
                'type': operation_type,
                'aliasId': alias_id,
                'isManual': is_manual,
                'startnow': 'true',
                'parameters': parameters,
            }
            data = self._request_post(params)
            operation_id = data.get('data') or (data.get('response') or {}).get('operation') or {}
            if isinstance(operation_id, dict):
                operation_id = operation_id.get('operationId')
            if not operation_id and data.get('response', {}).get('operation', {}).get('operationId'):
                operation_id = data['response']['operation']['operationId']
            if not operation_id or operation_id == 'Operation not queued':
                msg = data.get('data') if isinstance(data.get('data'), str) else 'No se recibió operation_id'
                if data.get('code') == -2:
                    msg = _('Máquina ocupada u operación no encolada (code=-2). Espere a que termine la operación actual.')
                raise ValueError(msg or 'No se recibió operation_id')
            result = data.copy()
            result['operation_id'] = operation_id
            return result
        except Exception as e:
            raise UserError(_('Error startOperation (admin): %s') % str(e))

    def start_load_money(self, alias_id='', is_manual='0', parameters=''):
        """
        Carga de dinero (INGRESAR genérico).

        Basado en movimientos_funcionan/ingresar_generico.py y la doc:
        - startOperation(type=16, isManual=0, startnow=true)
        - acknowledgeOperationId(operationId)
        - La máquina entra en modo 'cargando' y espera a que el operario ingrese dinero.
        No hacemos polling ni finishOperation desde Odoo; se gestionan desde la propia interfaz/máquina.
        """
        # START type=16 vía index.php (mismo flujo que start_operation_admin)
        start_res = self.start_operation_admin(operation_type=16, alias_id=alias_id, is_manual=is_manual, parameters=parameters)
        operation_id = start_res.get('operation_id')
        if not operation_id:
            return start_res
        # ACKNOWLEDGE vía index.php (POST), como en ingresar_generico.py
        try:
            ack_params = {
                'operation': 'acknowledgeOperationId',
                'name': self.user,
                'password': self.password,
                'operationId': operation_id,
            }
            ack_res = self._request_post(ack_params)
            _logger.info("CashDro start_load_money: acknowledge code=%s", ack_res.get('code'))
        except Exception as e:
            _logger.warning("start_load_money acknowledge error: %s", e)
        return start_res

    def start_carga(self, alias_id=''):
        """
        Carga (doc 5.7): startOperation type=1 sin importe, acknowledge.
        La máquina permanece en pantalla de carga hasta que se llame a finish_operation + set_operation_imported.
        """
        self.login(self.user, self.password)
        params = {
            'operation': 'startOperation',
            'name': self.user,
            'password': self.password,
            'type': 1,
            'posid': self.posid,
            'posuser': self.posuser,
            'startnow': 'true',
        }
        if alias_id:
            params['aliasid'] = alias_id
        _logger.info("CashDro start_carga: endpoint=%s type=1", self.endpoint)
        response = requests.get(
            self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
        )
        response.raise_for_status()
        data = self._parse_response(response)
        operation_id = None
        if data.get('code') == 1:
            resp = data.get('response', {}) or {}
            operation_id = (resp.get('operation') or {}).get('operationId')
            if not operation_id and data.get('data'):
                operation_id = data.get('data')
        if not operation_id:
            raise ValueError(data.get('response', {}).get('errorMessage') or 'No operationId')
        try:
            self.acknowledge_operation_id(operation_id)
        except Exception as e:
            _logger.warning("start_carga acknowledge: %s", e)
        return {'code': 1, 'operation_id': operation_id}

    def start_cambio(self, alias_id=''):
        """
        Cambio (doc 5.4): startOperation type=18 sin importe, acknowledge.
        La gestión del cambio (importe introducido/devuelto) se realiza desde la interfaz web (pantalla splash).
        """
        self.login(self.user, self.password)
        params = {
            'operation': 'startOperation',
            'name': self.user,
            'password': self.password,
            'type': 18,
            'posid': self.posid,
            'posuser': self.posuser,
            'startnow': 'true',
        }
        if alias_id:
            params['aliasid'] = alias_id
        _logger.info("CashDro start_cambio: endpoint=%s type=18", self.endpoint)
        response = requests.get(
            self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
        )
        response.raise_for_status()
        data = self._parse_response(response)
        operation_id = None
        if data.get('code') == 1:
            resp = data.get('response', {}) or {}
            operation_id = (resp.get('operation') or {}).get('operationId')
            if not operation_id and data.get('data'):
                operation_id = data.get('data')
        if not operation_id:
            raise ValueError(data.get('response', {}).get('errorMessage') or 'No operationId')
        try:
            self.acknowledge_operation_id(operation_id)
        except Exception as e:
            _logger.warning("start_cambio acknowledge: %s", e)
        return {'code': 1, 'operation_id': operation_id}
    def start_retirada(self, alias_id=''):
        """
        Retirada (doc 5.8): startOperation type=2 sin importe, acknowledge.
        La máquina muestra la pantalla de retirada; completar el proceso y aceptar en la máquina.
        """
        self.login(self.user, self.password)
        params = {
            'operation': 'startOperation',
            'name': self.user,
            'password': self.password,
            'type': 2,
            'posid': self.posid,
            'posuser': self.posuser,
            'startnow': 'true',
        }
        if alias_id:
            params['aliasid'] = alias_id
        _logger.info("CashDro start_retirada: endpoint=%s type=2", self.endpoint)
        response = requests.get(
            self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
        )
        response.raise_for_status()
        data = self._parse_response(response)
        operation_id = None
        if data.get('code') == 1:
            resp = data.get('response', {}) or {}
            operation_id = (resp.get('operation') or {}).get('operationId')
            if not operation_id and data.get('data'):
                operation_id = data.get('data')
        if not operation_id:
            raise ValueError(data.get('response', {}).get('errorMessage') or 'No operationId')
        try:
            self.acknowledge_operation_id(operation_id)
        except Exception as e:
            _logger.warning("start_retirada acknowledge: %s", e)
        return {'code': 1, 'operation_id': operation_id}

    def start_retirada_casete_monedas(self, alias_id=''):
        """
        Retirada casete de monedas (doc 5.13): startOperation type=11, acknowledge.
        El software registra que el dinero del casete ha sido retirado; completar en la máquina.
        """
        self.login(self.user, self.password)
        params = {
            'operation': 'startOperation',
            'name': self.user,
            'password': self.password,
            'type': 11,
            'posid': self.posid,
            'posuser': self.posuser,
            'startnow': 'true',
        }
        if alias_id:
            params['aliasid'] = alias_id
        _logger.info("CashDro start_retirada_casete_monedas: endpoint=%s type=11", self.endpoint)
        response = requests.get(
            self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
        )
        response.raise_for_status()
        data = self._parse_response(response)
        operation_id = None
        if data.get('code') == 1:
            resp = data.get('response', {}) or {}
            operation_id = (resp.get('operation') or {}).get('operationId')
            if not operation_id and data.get('data'):
                operation_id = data.get('data')
        if not operation_id:
            raise ValueError(data.get('response', {}).get('errorMessage') or 'No operationId')
        try:
            self.acknowledge_operation_id(operation_id)
        except Exception as e:
            _logger.warning("start_retirada_casete_monedas acknowledge: %s", e)
        return {'code': 1, 'operation_id': operation_id}

    def start_retirada_casete_billetes(self, alias_id=''):
        """
        Retirada casete de billetes (doc 5.12): startOperation type=10, acknowledge.
        Completar en la máquina y aceptar.
        """
        self.login(self.user, self.password)
        params = {
            'operation': 'startOperation',
            'name': self.user,
            'password': self.password,
            'type': 10,
            'posid': self.posid,
            'posuser': self.posuser,
            'startnow': 'true',
        }
        if alias_id:
            params['aliasid'] = alias_id
        _logger.info("CashDro start_retirada_casete_billetes: endpoint=%s type=10", self.endpoint)
        response = requests.get(
            self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
        )
        response.raise_for_status()
        data = self._parse_response(response)
        operation_id = None
        if data.get('code') == 1:
            resp = data.get('response', {}) or {}
            operation_id = (resp.get('operation') or {}).get('operationId')
            if not operation_id and data.get('data'):
                operation_id = data.get('data')
        if not operation_id:
            raise ValueError(data.get('response', {}).get('errorMessage') or 'No operationId')
        try:
            self.acknowledge_operation_id(operation_id)
        except Exception as e:
            _logger.warning("start_retirada_casete_billetes acknowledge: %s", e)
        return {'code': 1, 'operation_id': operation_id}

    def get_retirada_web_url(self, operation_id):
        """
        URL de la interfaz web para indicar las piezas a retirar (doc 5.8.3).
        Obligatorio en retirada: sin abrir esta pantalla la máquina puede quedarse en "Retirando...".
        """
        from urllib.parse import urlencode
        params = urlencode({'username': self.user, 'password': self.password})
        base = self.gateway_url.rstrip('/')
        return f"{base}/Cashdro3Web/#/unload/{operation_id}/true/?{params}"

    def get_cambio_web_url(self, operation_id=None):
        """
        URL de la interfaz web para gestionar la transacción de cambio (doc 5.4.3).
        Doc: https://<ip>/Cashdro3Web/index.html#/splash/true
        Si la web acepta operationId en la ruta (como retirada con unload), se usa para mostrar la operación.
        """
        base = self.gateway_url.rstrip('/')
        if operation_id:
            return f"{base}/Cashdro3Web/index.html#/splash/{operation_id}/true"
        return f"{base}/Cashdro3Web/index.html#/splash/true"

    def set_operation_imported(self, operation_id):
        """Indica al CashDro que la transacción ha sido recibida y procesada por el Host (doc 5.7.6)."""
        try:
            params = {
                'operation': 'setOperationImported',
                'name': self.user,
                'password': self.password,
                'operationId': operation_id,
            }
            response = requests.get(
                self.endpoint, params=params, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            data = self._parse_response(response)
            _logger.info("CashDro setOperationImported: operation_id=%s code=%s", operation_id, data.get('code'))
            return data
        except Exception as e:
            raise UserError(_('Error setOperationImported: %s') % str(e))

    def set_deposit_levels(self, levels_config):
        """Configura fianza/depósito. levels_config: dict con limitRecyclerCheck y config (lista de niveles)."""
        try:
            params = {
                'operation': 'setDepositLevels',
                'name': self.user,
                'password': self.password,
                'levels': json.dumps(levels_config),
            }
            return self._request_post(params)
        except Exception as e:
            raise UserError(_('Error setDepositLevels: %s') % str(e))

    def apply_deposit_levels(self):
        """
        Aplica en la máquina la fianza configurada con setDepositLevels.
        Flujo observado en la web oficial:
        - startOperation type=36
        - acknowledgeOperationId
        - askOperation (opcional, solo para logging)
        - finishOperation
        """
        import time
        try:
            # START type=36
            start_params = {
                'operation': 'startOperation',
                'name': self.user,
                'password': self.password,
                'type': 36,
                'aliasId': '',
                'isManual': '0',
                'startnow': 'true',
                'parameters': '',
            }
            start_res = self._request_post(start_params)
            operation_id = start_res.get('data') or (start_res.get('response') or {}).get('operation', {}).get('operationId')
            _logger.info("CashDro apply_deposit_levels: start type=36 operation_id=%s code=%s", operation_id, start_res.get('code'))
            if not operation_id:
                raise UserError(_('No se pudo iniciar operación administrativa type=36 (aplicar fianza).'))

            # ACKNOWLEDGE
            ack_params = {
                'operation': 'acknowledgeOperationId',
                'name': self.user,
                'password': self.password,
                'operationId': operation_id,
            }
            ack_res = self._request_post(ack_params)
            _logger.info("CashDro apply_deposit_levels: acknowledge code=%s", ack_res.get('code'))

            # Pequeña espera y ASK (solo para forzar ejecución y para debug)
            time.sleep(2)
            ask_params = {
                'operation': 'askOperation',
                'name': self.user,
                'password': self.password,
                'operationId': operation_id,
                'includeImages': '0',
            }
            ask_res = self._request_post(ask_params)
            _logger.debug("CashDro apply_deposit_levels: askOperation response keys=%s", list(ask_res.keys()))

            # FINISH (puede devolver code=-2 si ya no está en ejecución; lo consideramos no fatal)
            finish_params = {
                'operation': 'finishOperation',
                'name': self.user,
                'password': self.password,
                'operationId': operation_id,
                'type': 1,
            }
            finish_res = self._request_post(finish_params)
            _logger.info("CashDro apply_deposit_levels: finishOperation code=%s", finish_res.get('code'))
            return {
                'start': start_res,
                'ack': ack_res,
                'ask': ask_res,
                'finish': finish_res,
            }
        except Exception as e:
            raise UserError(_('Error aplicando fianza (type=36): %s') % str(e))

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
        """Prueba el flujo de pago alineado con la web: start → acknowledge → askExecuting → getMainCurrency → ask."""
        try:
            # PASO 1: Iniciar operación
            start_resp = self.start_operation(amount_eur, operation_type=3)
            operation_id = start_resp.get('operation_id')
            _logger.info("✅ Operación iniciada: %s", operation_id)
            
            time.sleep(0.5)
            
            # PASO 2: Reconocer operación (muestra pantalla en la máquina)
            ack_resp = self.acknowledge_operation_id(operation_id)
            _logger.info("✅ Operación reconocida")
            
            time.sleep(0.5)
            
            # PASO 3: Secuencia observada en la web oficial
            executing_resp = self.ask_operation_executing()
            _logger.info("✅ askOperationExecuting consultado")

            currency_resp = self.get_main_currency()
            _logger.info("✅ getMainCurrency consultado")

            # PASO 4: Consultar estado detallado de la operación
            ask_resp = self.ask_operation(operation_id)
            _logger.info("✅ Estado consultado")
            
            return {
                'success': True,
                'operation_id': operation_id,
                'start_response': start_resp,
                'acknowledge_response': ack_resp,
                'executing_response': executing_resp,
                'currency_response': currency_resp,
                'ask_response': ask_resp
            }
        except Exception as e:
            _logger.error("Error en flujo de pago: %s", str(e))
            return {'success': False, 'error': str(e)}
