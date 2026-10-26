"""Actuador real: entrega la orden como Active Response por la API de Wazuh.

    PUT /active-response?agents_list=<agente>
    {"command": "!kronos-bloquear-ip", "arguments": ["aplicar", "203.0.113.7"]}

- Sólo biblioteca estándar. HTTPS con verificación de certificado obligatoria: no hay
  opción para desactivarla. La API de Wazuh usa un certificado propio, así que se
  entrega su CA (o el propio certificado) y, si el nombre del certificado no es el
  del host al que se conecta, ``nombre_servidor`` indica cuál verificar.
- Usuario de API de permisos mínimos (sólo ``active-response:command``). La
  contraseña se lee de un archivo de secreto y nunca aparece en errores ni en la
  bitácora.
- La orden se envía una sola vez. Si no llega respuesta, el error lo dice: la orden
  pudo haber llegado al equipo, y por eso el ticket queda en FAILED para que una
  persona lo revise, sin reintento.

Verificado con Wazuh 4.14.8 el 20-10-2026: la API acepta el prefijo «!» sin declarar un
<command> en el manager, y el script del agente recibe «arguments» en
parameters.extra_args. En Windows el agente sólo encuentra el script con su extensión
(«!kronos-bloquear-ip.cmd»; prueba del 21-10-2026 en EP-WKS-01).
"""

from __future__ import annotations

import base64
import http.client
import json
import os
import ssl
import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ejecucion.actuador import ErrorActuador
from ejecucion.ordenes import Orden

PLAZO_SEGUNDOS = 10.0
# El token de la API dura 900 s por omisión; se renueva antes.
VIGENCIA_TOKEN_SEGUNDOS = 600.0
PREFIJO_COMANDO = "!"

Conectar = Callable[[], http.client.HTTPConnection]


class ActuadorWazuh:
    def __init__(
        self,
        url: str,
        usuario: str,
        clave: str,
        ca: str | None = None,
        nombre_servidor: str | None = None,
        plazo: float = PLAZO_SEGUNDOS,
        conectar: Conectar | None = None,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        partes = urllib.parse.urlsplit(url)
        if partes.scheme != "https" or not partes.hostname:
            raise ValueError("la URL de la API de Wazuh debe ser https://host:puerto")
        if not usuario or not clave:
            raise ValueError("faltan el usuario o la contraseña de la API de Wazuh")
        self._usuario = usuario
        self._clave = clave
        self._reloj = reloj
        self._token: str | None = None
        self._token_desde = 0.0
        if conectar is None:
            contexto = ssl.create_default_context(cafile=ca)
            conectar = _conectar_https(
                partes.hostname, partes.port or 55000, contexto, nombre_servidor, plazo
            )
        self._conectar = conectar

    @classmethod
    def desde_entorno(cls) -> ActuadorWazuh:
        """Configuración por variables de entorno (la contraseña, en un archivo)."""
        try:
            url = os.environ["KRONOS_WAZUH_URL"]
            usuario = os.environ["KRONOS_WAZUH_USUARIO"]
            archivo = os.environ["KRONOS_WAZUH_CLAVE_ARCHIVO"]
        except KeyError as exc:
            raise ValueError(f"falta la variable {exc.args[0]}") from exc
        clave = Path(archivo).read_text(encoding="utf-8").strip()
        return cls(
            url,
            usuario,
            clave,
            ca=os.environ.get("KRONOS_WAZUH_CA") or None,
            nombre_servidor=os.environ.get("KRONOS_WAZUH_NOMBRE_SERVIDOR") or None,
        )

    def enviar(self, orden: Orden) -> str:
        cuerpo = {
            "command": PREFIJO_COMANDO + orden.comando,
            "arguments": list(orden.argumentos),
        }
        ruta = "/active-response?" + urllib.parse.urlencode(
            {"agents_list": orden.agente}
        )
        estado, datos = self._con_token("PUT", ruta, cuerpo)
        if estado != 200:
            raise ErrorActuador(f"la API respondió {estado}: {_mensaje(datos)}")
        resultado = datos.get("data", {}) if isinstance(datos, dict) else {}
        afectados = resultado.get("affected_items") or []
        if orden.agente not in afectados:
            fallas = resultado.get("failed_items") or []
            raise ErrorActuador(
                f"el agente {orden.agente} no recibió la orden: {_fallas(fallas)}"
            )
        return f"wazuh-ar:{orden.agente}:{orden.comando}"

    # ------------------------------------------------------------------ interno

    def _con_token(self, metodo: str, ruta: str, cuerpo: dict) -> tuple[int, Any]:
        estado, datos = self._pedir(metodo, ruta, cuerpo, self._vigente())
        if estado == 401:
            # Token vencido o revocado: se pide uno nuevo y se reintenta UNA vez. Un 401
            # significa que la API rechazó la petición, así que la orden no se envió.
            self._token = None
            estado, datos = self._pedir(metodo, ruta, cuerpo, self._vigente())
        return estado, datos

    def _vigente(self) -> str:
        if (
            self._token is None
            or self._reloj() - self._token_desde > VIGENCIA_TOKEN_SEGUNDOS
        ):
            self._token = self._autenticar()
            self._token_desde = self._reloj()
        return self._token

    def _autenticar(self) -> str:
        credencial = base64.b64encode(
            f"{self._usuario}:{self._clave}".encode()
        ).decode()
        estado, datos = self._pedir(
            "POST",
            "/security/user/authenticate",
            None,
            autorizacion=f"Basic {credencial}",
        )
        token = datos.get("data", {}).get("token") if isinstance(datos, dict) else None
        if estado != 200 or not isinstance(token, str) or not token:
            raise ErrorActuador(f"la API de Wazuh rechazó la autenticación ({estado})")
        return token

    def _pedir(
        self,
        metodo: str,
        ruta: str,
        cuerpo: dict | None,
        token: str | None = None,
        autorizacion: str | None = None,
    ) -> tuple[int, Any]:
        cabeceras = {"Accept": "application/json"}
        datos = None
        if cuerpo is not None:
            datos = json.dumps(cuerpo).encode()
            cabeceras["Content-Type"] = "application/json"
        cabeceras["Authorization"] = autorizacion or f"Bearer {token}"
        conexion = self._conectar()
        try:
            conexion.request(metodo, ruta, body=datos, headers=cabeceras)
            respuesta = conexion.getresponse()
            crudo = respuesta.read(1_000_000)
            estado = respuesta.status
        except ssl.SSLError as exc:
            raise ErrorActuador(
                f"certificado de la API no válido: {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise ErrorActuador(
                "sin respuesta de la API a tiempo: la orden pudo haber llegado al equipo"
            ) from exc
        except (OSError, http.client.HTTPException) as exc:
            raise ErrorActuador(
                f"no se pudo hablar con la API: {type(exc).__name__}"
            ) from exc
        finally:
            conexion.close()
        try:
            return estado, json.loads(crudo) if crudo else {}
        except ValueError:
            return estado, {}


def _conectar_https(
    host: str,
    puerto: int,
    contexto: ssl.SSLContext,
    nombre_servidor: str | None,
    plazo: float,
) -> Conectar:
    def conectar() -> http.client.HTTPConnection:
        if nombre_servidor is None:
            return http.client.HTTPSConnection(
                host, puerto, context=contexto, timeout=plazo
            )
        return _HTTPSConNombre(host, puerto, contexto, nombre_servidor, plazo)

    return conectar


class _HTTPSConNombre(http.client.HTTPSConnection):
    """Conecta a ``host`` pero verifica el certificado contra ``nombre_servidor``."""

    def __init__(
        self,
        host: str,
        puerto: int,
        contexto: ssl.SSLContext,
        nombre: str,
        plazo: float,
    ) -> None:
        super().__init__(host, puerto, context=contexto, timeout=plazo)
        self._contexto_tls = contexto
        self._nombre = nombre

    def connect(self) -> None:
        http.client.HTTPConnection.connect(self)
        self.sock = self._contexto_tls.wrap_socket(
            self.sock, server_hostname=self._nombre
        )


def _mensaje(datos: Any) -> str:
    if isinstance(datos, dict):
        return str(
            datos.get("detail") or datos.get("title") or datos.get("message") or ""
        )[:200]
    return ""


def _fallas(fallas: list) -> str:
    textos = []
    for f in fallas[:3]:
        if isinstance(f, dict):
            error = f.get("error", {})
            textos.append(
                str(error.get("message", error) if isinstance(error, dict) else error)
            )
    return "; ".join(textos)[:300] or "sin detalle"
