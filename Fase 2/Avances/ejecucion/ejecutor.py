"""SOAR-EXECUTE: ejecuta las decisiones aprobadas y sus reversiones.

Un ciclo, por inquilino:

0. Pasa a revisión manual los tickets huérfanos: sin decisión de VALIDATE 10 minutos
   después de creados (DECISION_NO_REGISTRADA, con aviso).
1. Vence las aprobaciones de nivel 3 sin respuesta (D-34).
2. Toma los tickets PENDING con playbook, uno a la vez, y para cada uno:
   arma la orden, la envía y registra el resultado. La decisión ya está en la
   bitácora (R3) y EJECUCION_INICIADA queda escrita antes de enviar.
3. Toma las reversiones vencidas (nivel 1 al vencer su plazo, o pedidas por una
   persona) y las ejecuta.

Antes de armar cada orden (y cada reversión) se determina el sistema operativo del
agente (``ordenes.sistema_operativo``) y se comprueba que la acción tenga script en ese
sistema (``actuadores_v1`` del catálogo). Si no se sabe el sistema, o no hay script, no
se envía nada: la API de Wazuh confirmaría la entrega aunque el script no exista, y el
ticket quedaría en SUCCESS sin que nada pasara en el equipo.

Falla segura: si la orden no se puede armar o no se puede entregar, el ticket queda
en FAILED con el motivo y nada se reintenta solo. Una medida de reversión automática
sin plazo en el catálogo no se ejecuta: no se aplica algo que después no se sabría
cuándo deshacer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ejecucion.actuador import Actuador, ErrorActuador
from ejecucion.medidas import Medida
from ejecucion.ordenes import (
    AccionNoImplementada,
    OrdenInvalida,
    agente,
    construir,
    construir_reversion,
    sistema_operativo,
)

if TYPE_CHECKING:  # sin dependencia de psycopg al importar (pruebas unitarias)
    from persistencia.repositorio import Repositorio

MAX_POR_CICLO = 50

MOTIVO_SIN_MEDIDA = "PLAYBOOK_SIN_MEDIDA"
MOTIVO_NO_IMPLEMENTADA = "ACCION_NO_IMPLEMENTADA"
MOTIVO_ORDEN_INVALIDA = "ORDEN_INVALIDA"
MOTIVO_SIN_PLAZO = "PLAZO_DE_REVERSION_SIN_DEFINIR"
MOTIVO_ACTUADOR = "ACTUADOR_FALLO"


@dataclass
class Resumen:
    huerfanos: list[int] = field(default_factory=list)
    vencidas: list[int] = field(default_factory=list)
    exitosas: list[int] = field(default_factory=list)
    fallidas: list[int] = field(default_factory=list)
    revertidas: list[int] = field(default_factory=list)
    reversiones_fallidas: list[int] = field(default_factory=list)


class Ejecutor:
    def __init__(
        self,
        repositorio: Repositorio,
        actuador: Actuador,
        medidas: Mapping[str, Medida],
        actuadores: Mapping[str, frozenset[str]],
        agentes_so: Mapping[str, str] | None = None,
    ) -> None:
        self._repo = repositorio
        self._actuador = actuador
        self._medidas = medidas
        self._actuadores = actuadores
        self._agentes_so = agentes_so or {}

    def ciclo(self, tenant_id: int) -> Resumen:
        resumen = Resumen()
        resumen.huerfanos = self._repo.recuperar_huerfanos(tenant_id)
        resumen.vencidas = self._repo.vencer_aprobaciones(tenant_id)
        for _ in range(MAX_POR_CICLO):
            ticket = self._repo.tomar_para_ejecutar(tenant_id)
            if ticket is None:
                break
            exito = self._ejecutar(
                tenant_id, ticket.ticket_id, ticket.playbook_id, ticket.alerta
            )
            (resumen.exitosas if exito else resumen.fallidas).append(ticket.ticket_id)
        for _ in range(MAX_POR_CICLO):
            reversion = self._repo.tomar_reversion(tenant_id)
            if reversion is None:
                break
            exito = self._revertir(
                tenant_id, reversion.ticket_id, reversion.playbook_id, reversion.alerta
            )
            (resumen.revertidas if exito else resumen.reversiones_fallidas).append(
                reversion.ticket_id
            )
        return resumen

    def _ejecutar(
        self, tenant_id: int, ticket_id: int, playbook_id: str, alerta: dict
    ) -> bool:
        medida = self._medidas.get(playbook_id)
        if medida is None:
            return self._fallo(tenant_id, ticket_id, MOTIVO_SIN_MEDIDA, playbook_id)
        plazo = None
        if medida.reversion == "automatica_al_vencer":
            if medida.plazo_minutos is None:
                return self._fallo(tenant_id, ticket_id, MOTIVO_SIN_PLAZO, playbook_id)
            plazo = medida.plazo_minutos
        datos = alerta.get("alerta", {})
        try:
            sistema = self._sistema(medida.accion, datos)
            orden = construir(medida.accion, datos, sistema=sistema)
        except AccionNoImplementada as exc:
            return self._fallo(tenant_id, ticket_id, MOTIVO_NO_IMPLEMENTADA, str(exc))
        except OrdenInvalida as exc:
            return self._fallo(tenant_id, ticket_id, MOTIVO_ORDEN_INVALIDA, str(exc))
        try:
            referencia = self._actuador.enviar(orden)
        except ErrorActuador as exc:
            return self._fallo(
                tenant_id, ticket_id, MOTIVO_ACTUADOR, str(exc), orden.como_detalle()
            )
        self._repo.registrar_ejecucion(
            tenant_id,
            ticket_id,
            True,
            {"orden": orden.como_detalle(), "referencia": referencia},
            reversion_en_minutos=plazo,
        )
        return True

    def _revertir(
        self, tenant_id: int, ticket_id: int, playbook_id: str, alerta: dict
    ) -> bool:
        medida = self._medidas.get(playbook_id)
        detalle: dict = {}
        try:
            if medida is None:
                raise AccionNoImplementada(f"{playbook_id}: sin medida en el catálogo")
            datos = alerta.get("alerta", {})
            sistema = self._sistema(medida.accion, datos)
            orden = construir_reversion(medida.accion, datos, sistema=sistema)
            detalle["orden"] = orden.como_detalle()
            detalle["referencia"] = self._actuador.enviar(orden)
        except (AccionNoImplementada, OrdenInvalida, ErrorActuador) as exc:
            detalle["motivo"] = type(exc).__name__
            detalle["error"] = str(exc)
            self._repo.registrar_reversion(tenant_id, ticket_id, False, detalle)
            return False
        self._repo.registrar_reversion(tenant_id, ticket_id, True, detalle)
        return True

    def _sistema(self, accion: str, alerta: Mapping) -> str:
        """Sistema del agente, si la acción tiene script en él.

        Un agente inválido (o el 000) lanza OrdenInvalida, igual que al armar la orden;
        sin sistema conocido o sin script en ese sistema, AccionNoImplementada.
        """
        agente_id = agente(alerta)
        sistema = sistema_operativo(alerta, self._agentes_so)
        if sistema is None:
            raise AccionNoImplementada(
                f"no se pudo determinar el sistema operativo del agente {agente_id}"
            )
        if accion not in self._actuadores.get(sistema, frozenset()):
            raise AccionNoImplementada(f"{accion}: sin script en {sistema} en la v1.0")
        return sistema

    def _fallo(
        self,
        tenant_id: int,
        ticket_id: int,
        motivo: str,
        error: str,
        orden: dict | None = None,
    ) -> bool:
        detalle = {"motivo": motivo, "error": error}
        if orden is not None:
            detalle["orden"] = orden
        self._repo.registrar_ejecucion(tenant_id, ticket_id, False, detalle)
        return False
