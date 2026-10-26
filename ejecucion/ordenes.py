"""Traducción de una medida del catálogo a una orden de Active Response.

Esta es la frontera con el equipo del cliente, así que todo es cerrado:

- El nombre del comando sale de una tabla fija por acción, nunca de la alerta.
- Los argumentos se toman de campos fijos de la alerta y se validan con reglas
  estrictas (una IP se parsea con ``ipaddress``; una cuenta sólo admite letras,
  dígitos, punto, guion y guion bajo). Un valor que no calza se rechaza: no se
  limpia ni se recorta.
- Los argumentos viajan como lista, nunca como texto de shell.
- Nunca se actúa sobre el manager (agente 000) ni sobre la IP del propio equipo.

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


class OrdenInvalida(ValueError):
    """La alerta no trae un objetivo válido para la medida."""


class AccionNoImplementada(ValueError):
    """La acción del catálogo todavía no tiene comando de Active Response."""


@dataclass(frozen=True)
class Orden:
    agente: str
    comando: str
    argumentos: tuple[str, ...]

    def como_detalle(self) -> dict[str, Any]:
        return {
            "agente": self.agente,
            "comando": self.comando,
            "argumentos": list(self.argumentos),
        }


def construir(accion: str, alerta: Mapping[str, Any]) -> Orden:
    """Orden que aplica la medida."""
    comando, _ = _comando(accion)
    return Orden(_agente(alerta), comando, ("aplicar", *_objetivo(accion, alerta)))


def construir_reversion(accion: str, alerta: Mapping[str, Any]) -> Orden:
    """Orden que deshace la medida, con el mismo objetivo que la original."""
    comando, inversa = _comando(accion)
    if inversa is None:
        raise AccionNoImplementada(f"{accion}: no se revierte desde Kronos")
    return Orden(_agente(alerta), comando, (inversa, *_objetivo(accion, alerta)))


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
