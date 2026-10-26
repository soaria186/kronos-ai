"""Interfaz del actuador: quien entrega la orden al equipo.

El actuador real envía la orden como Active Response por la API de Wazuh (55000, por
NetBird) con un usuario de permisos mínimos; va en un PR aparte. Las pruebas usan un
actuador falso.
"""

from __future__ import annotations

from typing import Protocol

from ejecucion.ordenes import Orden


class ErrorActuador(RuntimeError):
    """La orden no se pudo entregar (API caída, agente desconectado, respuesta inválida)."""


class Actuador(Protocol):
    def enviar(self, orden: Orden) -> str:
        """Entrega la orden y devuelve una referencia para la bitácora; si falla, lanza ErrorActuador."""
        ...
