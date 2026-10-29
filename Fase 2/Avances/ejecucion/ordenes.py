"""Traducción de una medida del catálogo a una orden de Active Response.

Esta es la frontera con el equipo del cliente, así que todo es cerrado:

- El nombre del comando sale de una tabla fija por acción, nunca de la alerta.
- Los argumentos se toman de campos fijos de la alerta y se validan con reglas
  estrictas (una IP se parsea con ``ipaddress``; una cuenta sólo admite letras,
  dígitos, punto, guion y guion bajo). Un valor que no calza se rechaza: no se
  limpia ni se recorta.
- Los argumentos viajan como lista, nunca como texto de shell.
- Nunca se actúa sobre el manager (agente 000) ni sobre la IP del propio equipo.
- Cada orden lleva el sistema operativo del agente («linux» o «windows»): el actuador
  lo usa para el nombre del script, y EXECUTE para no enviar una medida que no tiene
  script en ese sistema. Si no se puede saber con certeza, no se actúa (ver
  ``sistema_operativo``).

Los campos de la alerta se buscan en el mismo orden que usa la lista de exclusión de
VALIDATE (validacion/alerta.py), para que EXECUTE actúe sobre lo que VALIDATE revisó.
Los nombres de los comandos deben coincidir con los scripts de Active Response que
se instalen en los agentes.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# Acción del catálogo -> (comando de Active Response, operación inversa o None si la
# medida no se revierte desde Kronos).
COMANDOS: dict[str, tuple[str, str | None]] = {
    "bloquear_ip": ("kronos-bloquear-ip", "quitar"),
    "aislar_equipo": ("kronos-aislar-equipo", "quitar"),
    "deshabilitar_cuenta": ("kronos-deshabilitar-cuenta", "habilitar"),
    "detener_servicio": ("kronos-detener-servicio", "iniciar"),
    "cerrar_sesion": ("kronos-cerrar-sesion", None),
    "terminar_proceso": ("kronos-terminar-proceso", None),
}
# Sin comando en la v1.0: consulta (sólo lectura, nivel 0), cuarentena, bloquear_destino,
# limitar_conexiones y revertir_tarea. EXECUTE las rechaza con ACCION_NO_IMPLEMENTADA
# (falla segura, con aviso).

_CAMPOS_IP = (("data", "srcip"), ("data", "win", "eventdata", "ipAddress"))
_CAMPOS_CUENTA = (
    ("data", "dstuser"),
    ("data", "win", "eventdata", "targetUserName"),
    ("data", "srcuser"),
)
_CAMPOS_PID = (("data", "win", "eventdata", "processId"), ("data", "audit", "pid"))
_CAMPOS_SERVICIO = (("data", "win", "eventdata", "serviceName"),)

_AGENTE = re.compile(r"^\d{3,8}$")
_CUENTA = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SERVICIO = re.compile(r"^[A-Za-z0-9._@-]{1,128}$")
_PID = re.compile(r"^\d{1,10}$")

# Defensa adicional a la lista de exclusión: cuentas que nunca se tocan.
CUENTAS_PROTEGIDAS = frozenset(
    {"root", "administrator", "administrador", "system", "localsystem", "kronos"}
)
PID_MINIMO = 5  # 0 a 4 son del sistema en Windows y Linux


SISTEMAS = frozenset({"linux", "windows"})
_UNIDAD_WINDOWS = re.compile(r"^[A-Za-z]:\\")


class OrdenInvalida(ValueError):
    """La alerta no trae un objetivo válido para la medida."""


class AccionNoImplementada(ValueError):
    """La acción del catálogo todavía no tiene comando de Active Response."""


@dataclass(frozen=True)
class Orden:
    agente: str
    comando: str
    argumentos: tuple[str, ...]
    sistema: str

    def __post_init__(self) -> None:
        if self.sistema not in SISTEMAS:
            raise ValueError(f"sistema operativo desconocido: {self.sistema!r}")

    def como_detalle(self) -> dict[str, Any]:
        return {
            "agente": self.agente,
            "sistema": self.sistema,
            "comando": self.comando,
            "argumentos": list(self.argumentos),
        }


def construir(accion: str, alerta: Mapping[str, Any], *, sistema: str) -> Orden:
    """Orden que aplica la medida en un agente del sistema operativo indicado."""
    comando, _ = _comando(accion)
    return Orden(
        _agente(alerta), comando, ("aplicar", *_objetivo(accion, alerta)), sistema
    )


def construir_reversion(
    accion: str, alerta: Mapping[str, Any], *, sistema: str
) -> Orden:
    """Orden que deshace la medida, con el mismo objetivo que la original."""
    comando, inversa = _comando(accion)
    if inversa is None:
        raise AccionNoImplementada(f"{accion}: no se revierte desde Kronos")
    return Orden(
        _agente(alerta), comando, (inversa, *_objetivo(accion, alerta)), sistema
    )


def leer_mapa_agentes(texto: str) -> dict[str, str]:
    """Lee el mapa «agente:sistema» de KRONOS_AGENTES_SO, por ejemplo
    «001:linux,002:windows». Vacío es válido (se deduce de cada alerta).

    Un formato inválido lanza ValueError: EXECUTE no arranca con un mapa dudoso.
    """
    mapa: dict[str, str] = {}
    for parte in texto.split(","):
        parte = parte.strip()
        if not parte:
            continue
        agente, separador, sistema = parte.partition(":")
        agente, sistema = agente.strip(), sistema.strip()
        if not separador or not _AGENTE.match(agente) or sistema not in SISTEMAS:
            raise ValueError(
                f"KRONOS_AGENTES_SO: {parte!r} no tiene la forma agente:linux o "
                "agente:windows (agente de 3 a 8 dígitos)"
            )
        if int(agente) == 0:
            raise ValueError("KRONOS_AGENTES_SO: el manager (agente 000) no va en el mapa")
        if agente in mapa:
            raise ValueError(f"KRONOS_AGENTES_SO: el agente {agente} está repetido")
        mapa[agente] = sistema
    return mapa


def sistema_operativo(
    alerta: Mapping[str, Any], mapa: Mapping[str, str]
) -> str | None:
    """Sistema operativo del agente de la alerta, o None si no se puede saber.

    1. El mapa explícito de la configuración manda.
    2. Si el agente no está en el mapa, se deduce de campos de la alerta.
    3. Si la alerta no dice nada claro, o el mapa y la alerta se contradicen, None:
       EXECUTE no actúa.
    """
    agente = _valor(alerta, ("agent", "id"))
    deducido = _deducir_sistema(alerta)
    declarado = mapa.get(agente) if agente is not None else None
    if declarado is not None and deducido is not None and declarado != deducido:
        return None
    return declarado or deducido


def _deducir_sistema(alerta: Mapping[str, Any]) -> str | None:
    ubicacion = _valor(alerta, ("location",)) or ""
    decodificador = _valor(alerta, ("decoder", "name")) or ""
    ruta = _valor(alerta, ("syscheck", "path")) or ""
    datos = alerta.get("data") if isinstance(alerta, Mapping) else None
    windows = (
        (isinstance(datos, Mapping) and isinstance(datos.get("win"), Mapping))
        or ubicacion == "EventChannel"
        or decodificador.lower().startswith("windows")
        or bool(_UNIDAD_WINDOWS.match(ruta))
    )
    linux = ruta.startswith("/") or ubicacion.startswith("/") or ubicacion == "journald"
    if windows == linux:  # ninguna señal, o señales de los dos sistemas
        return None
    return "windows" if windows else "linux"


def _comando(accion: str) -> tuple[str, str | None]:
    if accion not in COMANDOS:
        raise AccionNoImplementada(f"{accion}: sin comando de Active Response")
    return COMANDOS[accion]


def _objetivo(accion: str, alerta: Mapping[str, Any]) -> tuple[str, ...]:
    if accion == "bloquear_ip":
        return (_ip(alerta),)
    if accion in ("deshabilitar_cuenta", "cerrar_sesion"):
        return (_cuenta(alerta),)
    if accion == "terminar_proceso":
        return (_pid(alerta),)
    if accion == "detener_servicio":
        return (_validado(alerta, _CAMPOS_SERVICIO, _SERVICIO, "servicio"),)
    return ()  # aislar_equipo: actúa sobre el propio equipo


def agente(alerta: Mapping[str, Any]) -> str:
    """Agente de la alerta, validado (nunca el 000); si no sirve, OrdenInvalida."""
    return _agente(alerta)


def _agente(alerta: Mapping[str, Any]) -> str:
    agente = _valor(alerta, ("agent", "id"))
    if agente is None or not _AGENTE.match(agente):
        raise OrdenInvalida("la alerta no trae un agent.id válido")
    if int(agente) == 0:
        raise OrdenInvalida("nunca se actúa sobre el manager (agente 000)")
    return agente


def _ip(alerta: Mapping[str, Any]) -> str:
    texto = _primero(alerta, _CAMPOS_IP, "IP")
    try:
        ip = ipaddress.ip_address(texto)
    except ValueError as exc:
        raise OrdenInvalida(f"IP inválida: {texto!r}") from exc
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
        raise OrdenInvalida(f"no se bloquea la IP {ip}")
    propia = _valor(alerta, ("agent", "ip"))
    if propia is not None and propia == str(ip):
        raise OrdenInvalida("la IP a bloquear es la del propio equipo")
    return str(ip)


def _cuenta(alerta: Mapping[str, Any]) -> str:
    cuenta = _validado(alerta, _CAMPOS_CUENTA, _CUENTA, "cuenta")
    if cuenta.lower() in CUENTAS_PROTEGIDAS or cuenta.endswith("$"):
        raise OrdenInvalida(f"la cuenta {cuenta!r} está protegida")
    return cuenta


def _pid(alerta: Mapping[str, Any]) -> str:
    pid = _validado(alerta, _CAMPOS_PID, _PID, "PID")
    if int(pid) < PID_MINIMO:
        raise OrdenInvalida(f"PID del sistema: {pid}")
    return str(int(pid))


def _validado(
    alerta: Mapping[str, Any],
    campos: tuple[tuple[str, ...], ...],
    patron: re.Pattern,
    que: str,
) -> str:
    texto = _primero(alerta, campos, que)
    if not patron.match(texto):
        raise OrdenInvalida(f"{que} con caracteres no permitidos: {texto!r}")
    return texto


def _primero(
    alerta: Mapping[str, Any], campos: tuple[tuple[str, ...], ...], que: str
) -> str:
    for ruta in campos:
        valor = _valor(alerta, ruta)
        if valor is not None:
            return valor
    raise OrdenInvalida(f"la alerta no trae {que}")


def _valor(alerta: Mapping[str, Any], ruta: tuple[str, ...]) -> str | None:
    actual: Any = alerta
    for clave in ruta:
        if not isinstance(actual, Mapping) or clave not in actual:
            return None
        actual = actual[clave]
    if isinstance(actual, bool) or not isinstance(actual, (str, int)):
        return None
    texto = str(actual)
    return texto if texto else None
