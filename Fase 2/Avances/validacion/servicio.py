"""Registro de la alerta en SOAR-AUDIT: primer paso del ciclo de SOAR-VALIDATE.

Por cada alerta de alerts.json que pasó por una regla de sobre, VALIDATE crea el ticket y
deja en la bitácora el evento ALERTA_RECIBIDA con la alerta COMPLETA en
detalle["alerta"]. SOAR-EXECUTE lee exactamente esa clave (ejecucion/ejecutor.py) para
sacar el agente (agent.id) y el objetivo de la medida; sin ella no puede ejecutar nada.

Lo que se guarda es lo que llegó, no el texto recortado que ve el modelo. Es también lo
que revisa la lista de exclusión (validacion/alerta.py, objetivo), de modo que EXECUTE
actúa sobre lo que VALIDATE revisó.

Leer dos veces la misma alerta (rotación del archivo, reinicio) no crea dos tickets:
UNIQUE (tenant_id, alerta_ref) en la base, y registrar_alerta devuelve nuevo=False.

Este módulo no importa persistencia (ni, por tanto, psycopg): recibe el repositorio, igual
que SOAR-EXECUTE, y se prueba con uno falso.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from validacion.alerta import (
    AlertaKronos,
    detalle_alerta_agrupada,
    detalle_alerta_recibida,
    preparar,
)


class TicketRegistrado(Protocol):
    @property
    def ticket_id(self) -> int: ...

    @property
    def nuevo(self) -> bool: ...


class RegistroDeAlertas(Protocol):
    """La parte de persistencia.repositorio.Repositorio que usa este paso."""

    def registrar_alerta(
        self,
        tenant_id: int,
        alerta_ref: str,
        titulo: str,
        severidad: int,
        detalle: Mapping[str, Any] | None = None,
    ) -> TicketRegistrado: ...

    def agrupar_alerta(
        self, tenant_id: int, ticket_id: int, detalle: Mapping[str, Any]
    ) -> None: ...


@dataclass(frozen=True)
class AlertaRegistrada:
    ticket_id: int
    # False si la alerta ya había creado un ticket: no hay que volver a procesarla.
    nuevo: bool
    alerta: AlertaKronos


def registrar(
    repositorio: RegistroDeAlertas,
    tenant_id: int,
    alerta_wazuh: dict,
    preparada: AlertaKronos | None = None,
) -> AlertaRegistrada | None:
    """Crea el ticket de la alerta y guarda la alerta completa. None si no es de Kronos.

    Lanza AlertaInvalida, sin tocar la base, si la alerta no trae los campos mínimos o no
    se puede guardar; quien llama la cuenta como descartada y sigue con la siguiente.
    ``preparada`` es la misma alerta ya pasada por ``preparar`` (el ciclo la prepara antes
    para decidir si se agrupa); sin ella, se prepara aquí.
    """
    alerta = preparada if preparada is not None else preparar(alerta_wazuh)
    if alerta is None:
        return None
    ticket = repositorio.registrar_alerta(
        tenant_id,
        alerta.id,
        alerta.titulo,
        alerta.severidad,
        detalle_alerta_recibida(alerta_wazuh),
    )
    return AlertaRegistrada(ticket.ticket_id, ticket.nuevo, alerta)


def agrupar(
    repositorio: RegistroDeAlertas,
    tenant_id: int,
    ticket_id: int,
    alerta_wazuh: dict,
    alerta: AlertaKronos,
) -> None:
    """Anota en el ticket que decidió que esta alerta es del mismo ataque.

    No crea un ticket nuevo: una sola decisión por ataque. Lanza AlertaInvalida, sin tocar
    la base, si los datos no se pueden guardar.
    """
    repositorio.agrupar_alerta(
        tenant_id, ticket_id, detalle_alerta_agrupada(alerta_wazuh, alerta)
    )
