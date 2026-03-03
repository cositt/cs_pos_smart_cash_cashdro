#!/usr/bin/env python3
"""
Cashdrop API Client v2
Cliente Python para interactuar con la API de Cashdrop

Uso:
    from CashdropAPI_v2 import CashdropAPI
    
    with CashdropAPI(
        base_url="https://10.0.1.140",
        username="admin",
        password="****"
    ) as client:
        # Obtener piezas de divisa
        pieces = client.get_pieces_currency("EUR")
        print(pieces)
"""

import requests
import json
import logging
from typing import Dict, Any, List
from urllib.parse import urljoin, urlencode
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CashdropAPIError(Exception):
    """Excepción base para errores de API"""
    pass

class CashdropAuthError(CashdropAPIError):
    """Error de autenticación"""
    pass

class CashdropAPI:
    """Cliente para la API de Cashdrop v2"""
    
    def __init__(self, base_url: str = "https://10.0.1.140", 
                 username: str = "admin", 
                 password: str = "3428",
                 verify_ssl: bool = False,
                 timeout: int = 10):
        """Inicializa cliente de Cashdrop"""
        self.base_url = base_url
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        
        self.session = requests.Session()
        self.session.verify = verify_ssl
        
        self._authenticated = False
        self.auth_token = None
        
    def _build_url(self, operation: str, **params) -> str:
        """Construye URL con parámetros"""
        query_params = {
            'name': self.username,
            'password': self.password,
            'operation': operation
        }
        query_params.update(params)
        
        query_string = urlencode(query_params)
        return f"{self.base_url}/Cashdro3WS/index.php?{query_string}"
    
    def _request(self, operation: str, method: str = "GET", **params) -> Dict[str, Any]:
        """Realiza petición a la API"""
        url = self._build_url(operation, **params)
        
        try:
            logger.info(f"[{method}] {operation} con parámetros {params}")
            
            if method == "GET":
                response = self.session.get(url, timeout=self.timeout)
            elif method == "POST":
                response = self.session.post(url, timeout=self.timeout)
            else:
                raise ValueError(f"Método HTTP no soportado: {method}")
            
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Respuesta: code={data.get('code')}")
            
            code = data.get('code')
            
            if code == 1:
                return data.get('data', data)
            elif code == 0:
                error_msg = data.get('data', 'Unknown operation')
                raise CashdropAPIError(f"Operación no reconocida: {error_msg}")
            elif code == -3:
                raise CashdropAPIError(f"Usuario no especificado: {data.get('data')}")
            else:
                raise CashdropAPIError(f"Error en API (código {code}): {data.get('data')}")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión: {e}")
            raise CashdropAPIError(f"Error de conexión: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Respuesta no es JSON válido: {e}")
            raise CashdropAPIError(f"Respuesta inválida: {e}")
    
    def login(self) -> bool:
        """Realiza login a Cashdrop"""
        try:
            result = self._request('login', method='POST')
            self._authenticated = True
            logger.info(f"Login exitoso para usuario {self.username}")
            return True
        except CashdropAPIError as e:
            logger.error(f"Error en login: {e}")
            raise CashdropAuthError(f"Login fallido: {e}")
    
    def get_user(self, user_id: str = "0") -> Dict[str, Any]:
        """Obtiene información de un usuario"""
        return self._request('getUser', userId=user_id)
    
    def get_pieces_currency(self, currency_id: str = "EUR", 
                           include_images: bool = False, 
                           include_levels: bool = True) -> List[Dict[str, Any]]:
        """
        Obtiene información de monedas y billetes para una divisa
        
        Args:
            currency_id: ID de la divisa (ej: EUR, USD)
            include_images: Incluir imágenes de las piezas
            include_levels: Incluir información de niveles
            
        Returns:
            Lista de piezas (monedas/billetes) con sus características
        """
        return self._request(
            'getPiecesCurrency',
            currencyId=currency_id,
            includeImages='1' if include_images else '0',
            includeLevels='1' if include_levels else '0'
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Obtiene estado de la máquina"""
        return self._request('getStatus')
    
    def get_balance(self, device_id: str = "0") -> Dict[str, Any]:
        """Obtiene balance de la máquina"""
        return self._request('getBalance', deviceId=device_id)
    
    def get_transactions(self, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """Obtiene historial de transacciones"""
        return self._request('getTransactions', limit=str(limit), offset=str(offset))
    
    def get_machine(self, device_id: str = "0") -> Dict[str, Any]:
        """Obtiene información de la máquina"""
        return self._request('getMachine', deviceId=device_id)
    
    def get_config(self, section: str = "general") -> Dict[str, Any]:
        """Obtiene configuración"""
        return self._request('getConfig', section=section)
    
    def get_cash(self, device_id: str = "0") -> Dict[str, Any]:
        """Obtiene información de efectivo"""
        return self._request('getCash', deviceId=device_id)
    
    def get_info(self) -> Dict[str, Any]:
        """Obtiene información general"""
        return self._request('getInfo')
    
    def get_version(self) -> Dict[str, Any]:
        """Obtiene versión del sistema"""
        return self._request('getVersion')
    
    def is_authenticated(self) -> bool:
        """Verifica si está autenticado"""
        return self._authenticated
    
    def close(self):
        """Cierra la sesión"""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry"""
        self.login()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


if __name__ == '__main__':
    import sys
    
    print("🚀 Prueba de Cashdrop API Client v2")
    print("="*60)
    
    try:
        with CashdropAPI(
            base_url="https://10.0.1.140",
            username="admin",
            password="3428"
        ) as client:
            print("✅ Conectado a Cashdrop\n")
            
            # Obtener usuario
            print("📋 Obteniendo información del usuario...")
            user = client.get_user()
            print(json.dumps(user, indent=2, default=str))
            
            # Obtener piezas de divisa
            print("\n📋 Obteniendo piezas de divisa EUR...")
            pieces = client.get_pieces_currency("EUR")
            print(f"Total de piezas: {len(pieces) if isinstance(pieces, list) else 1}")
            if isinstance(pieces, list) and len(pieces) > 0:
                print(f"Primeras piezas: {json.dumps(pieces[:2], indent=2, default=str)}")
    
    except CashdropAuthError as e:
        print(f"❌ Error de autenticación: {e}")
        sys.exit(1)
    except CashdropAPIError as e:
        print(f"❌ Error en API: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        sys.exit(1)
    
    print("\n✅ Pruebas completadas")
