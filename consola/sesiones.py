"""Sesiones, límite de intentos y códigos TOTP ya usados. Todo en memoria.

Reiniciar SOAR-CONSOLE cierra todas las sesiones: es aceptable para un equipo de tres
personas y evita guardar sesiones en disco.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

DURACION_SESION = 8 * 3600
MAX_FALLOS = 5
VENTANA_FALLOS = 15 * 60


@dataclass(frozen=True)
class Sesion:
    usuario: str
    csrf: str
    vence: float


class Sesiones:
    def __init__(
        self, duracion: float = DURACION_SESION, reloj: Callable[[], float] = time.time
    ):
        self._duracion = duracion
        self._reloj = reloj
        self._activas: dict[str, Sesion] = {}

    def crear(self, usuario: str) -> str:
        token = secrets.token_urlsafe(32)
        self._activas[token] = Sesion(
            usuario, secrets.token_urlsafe(32), self._reloj() + self._duracion
        )
        return token

    def obtener(self, token: str | None) -> Sesion | None:
        sesion = self._activas.get(token or "")
        if sesion is None:
            return None
        if sesion.vence <= self._reloj():
            del self._activas[token]
            return None
        return sesion

    def cerrar(self, token: str | None) -> None:
        self._activas.pop(token or "", None)


class Intentos:
    """Bloquea una clave (usuario o IP) tras MAX_FALLOS en VENTANA_FALLOS segundos."""

    def __init__(self, reloj: Callable[[], float] = time.time) -> None:
        self._reloj = reloj
        self._fallos: dict[str, list[float]] = {}

    def bloqueado(self, clave: str) -> bool:
        return len(self._recientes(clave)) >= MAX_FALLOS

    def fallo(self, clave: str) -> None:
        self._fallos[clave] = [*self._recientes(clave), self._reloj()]

    def exito(self, clave: str) -> None:
        self._fallos.pop(clave, None)

    def _recientes(self, clave: str) -> list[float]:
        limite = self._reloj() - VENTANA_FALLOS
        return [t for t in self._fallos.get(clave, []) if t > limite]


class CodigosUsados:
    """Un código TOTP sirve una sola vez por cuenta (RFC 6238, sección 5.2)."""

    def __init__(self) -> None:
        self._ultimo: dict[str, int] = {}

    def aceptar(self, usuario: str, contador: int) -> bool:
        if contador <= self._ultimo.get(usuario, -1):
            return False
        self._ultimo[usuario] = contador
        return True
