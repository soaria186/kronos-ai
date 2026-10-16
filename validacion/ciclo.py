"""Ciclo de SOAR-VALIDATE para una alerta: registrar, clasificar, validar, decidir.

Orden de cada alerta de alerts.json (``Validador.procesar``):

 1. Se crea el ticket y se guarda la alerta completa (validacion.servicio). Una alerta
    sin etiqueta kronos_fX se omite; una inválida se descarta sin tocar la base; una ya
    vista (rotación del archivo, reinicio) no se vuelve a procesar.
 2. Cortacircuito: si las alertas de la ventana llegan al disparo, se abre; si está
    abierto, la alerta se rechaza ahí mismo, sin llamar al modelo (lo que importa en una
    inundación es no gastar 20 s de inferencia por alerta).
 3. El agente 000 es el manager: nunca se actúa sobre él (EXECUTE tampoco lo haría);
    la alerta se rechaza como ACTIVO_EXCLUIDO sin llamar al modelo.
 4. El modelo clasifica en dos pasos (decision.inferencia). Si falla, la alerta pasa a
    revisión humana con el motivo de la falla segura.
 5. Los chequeos 2 a 6 (validacion.chequeos), con los contadores y el cortacircuito que
    informa SOAR-AUDIT.
 6. La decisión se registra en la bitácora ANTES de que nadie actúe: SOAR-EXECUTE sólo
    toma tickets que ya tienen decisión.

Una alerta a la vez: los contadores de tasa se leen de la bitácora, así que dos alertas
en paralelo podrían pasar bajo el mismo tope. Con ~20 s por alerta el cuello de botella
es el modelo, no la concurrencia.

Este módulo no importa persistencia (ni psycopg): recibe el repositorio y el tipo
``Decision`` de Rodrigo, y se prueba con falsos. ``DefinicionContador`` tiene los mismos
atributos que ``DefinicionUso``, por eso ``usos`` recibe las definiciones tal cual.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from decision.inferencia import FallaSegura, Modelo, clasificar
from decision.plantillas import Plantillas
from validacion.alerta import AlertaInvalida, AlertaKronos
from validacion.chequeos import (
    Aprobada,
    Catalogo,
    MotivoRechazo,
    Propuesta,
    normalizar,
    validar,
)
from validacion.configuracion import Configuracion
from validacion.servicio import RegistroDeAlertas, registrar

registro = logging.getLogger("soar-validate")

AGENTE_MANAGER = 0


class PromptDistintoDelCatalogo(ValueError):
    """El prompt del paso 2 no describe las medidas del catálogo KRO-CAT-01."""


class Almacen(RegistroDeAlertas, Protocol):
    """La parte de persistencia.repositorio.Repositorio que usa el ciclo."""

    def registrar_decision(
        self, tenant_id: int, ticket_id: int, decision: Any
    ) -> int: ...

    def usos(
        self,
        tenant_id: int,
        definiciones: Sequence[Any],
        equipo: str | None = None,
        playbook_id: str | None = None,
    ) -> dict[str, int]: ...

    def alertas_en_ventana(self, tenant_id: int, ventana_minutos: int) -> int: ...

    def cortacircuito_abierto(self, tenant_id: int) -> bool: ...

    def abrir_cortacircuito(self, tenant_id: int, motivo: str) -> bool: ...


class Destino(StrEnum):
    OMITIDA = "omitida"  # no pasó por una regla de sobre
    DESCARTADA = "descartada"  # inválida: no se registró
    REPETIDA = "repetida"  # ya tenía ticket
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"


@dataclass(frozen=True)
class Resultado:
    destino: Destino
    ticket_id: int | None = None
    motivo: str | None = None


def comprobar_prompt(plantillas: Plantillas, catalogo: Catalogo) -> None:
    """Falla si los candidatos del paso 2 no son las medidas del catálogo.

    El modelo elige un identificador; lo que se ejecuta es la medida que ese identificador
    tiene en KRO-CAT-01. Si el prompt le describe otra medida con el mismo identificador
    (el catálogo provisional de medición reutiliza los PB-Fx-0y con otro significado), la
    elección del modelo no tiene nada que ver con lo que se ejecutaría.
    """
    errores = []
    for familia, datos in sorted(plantillas.familias.items()):
        for identificador in datos.candidatos:
            playbook = catalogo.playbooks.get(identificador)
            if playbook is None or playbook.familia != familia:
                errores.append(
                    f"{identificador}: no está en el catálogo para {familia}"
                )
            elif normalizar(datos.nombres.get(identificador, "")) != normalizar(
                playbook.medida
            ):
                errores.append(
                    f"{identificador}: el prompt dice «{datos.nombres.get(identificador)}»"
                    f" y el catálogo, «{playbook.medida}»"
                )
    if errores:
        raise PromptDistintoDelCatalogo(
            "el prompt del paso 2 no describe el catálogo KRO-CAT-01: "
            + "; ".join(errores[:3])
            + (f" (y {len(errores) - 3} más)" if len(errores) > 3 else "")
        )


def equipo_de(alerta: AlertaKronos) -> str | None:
    """Nombre del equipo, normalizado: el mismo valor para el contador y la bitácora."""
    for nombre in alerta.objetivo.get("equipo", ()):
        if normalizar(nombre):
            return normalizar(nombre)
    return None


def es_manager(alerta_wazuh: Mapping[str, Any]) -> bool:
    agente = alerta_wazuh.get("agent")
    identificador = agente.get("id") if isinstance(agente, Mapping) else None
    if isinstance(identificador, bool) or not isinstance(identificador, (str, int)):
        return False
    texto = str(identificador).strip()
    return texto.isdigit() and int(texto) == AGENTE_MANAGER


class Validador:
    def __init__(
        self,
        almacen: Almacen,
        modelo: Modelo,
        plantillas: Plantillas,
        catalogo: Catalogo,
        configuracion: Configuracion,
        tipo_decision: type,
        plazo: float = 60.0,
    ) -> None:
        comprobar_prompt(plantillas, catalogo)
        self._almacen = almacen
        self._modelo = modelo
        self._plantillas = plantillas
        self._catalogo = catalogo
        self._config = configuracion
        self._decision = tipo_decision
        self._plazo = plazo

    def procesar(self, tenant_id: int, alerta_wazuh: dict) -> Resultado:
        try:
            registrada = registrar(self._almacen, tenant_id, alerta_wazuh)
        except AlertaInvalida as exc:
            registro.warning("alerta descartada: %s", exc)
            return Resultado(Destino.DESCARTADA, motivo=str(exc))
        if registrada is None:
            return Resultado(Destino.OMITIDA)
        if not registrada.nuevo:
            return Resultado(Destino.REPETIDA, registrada.ticket_id)

        alerta, ticket_id = registrada.alerta, registrada.ticket_id
        equipo = equipo_de(alerta)

        if self._cortacircuito_abierto(tenant_id):
            return self._rechazar(
                tenant_id,
                ticket_id,
                MotivoRechazo.CORTACIRCUITO_ABIERTO,
                "cortacircuito abierto",
                equipo,
            )
        if es_manager(alerta_wazuh):
            return self._rechazar(
                tenant_id,
                ticket_id,
                MotivoRechazo.ACTIVO_EXCLUIDO,
                "agente 000 (el manager)",
                equipo,
            )

        clasificacion = clasificar(
            alerta.texto, self._modelo, self._plantillas, self._plazo
        )
        if isinstance(clasificacion, FallaSegura):
            return self._rechazar(
                tenant_id,
                ticket_id,
                clasificacion.motivo.value,
                f"paso {clasificacion.paso}: {clasificacion.detalle}",
                equipo,
            )

        usos = self._almacen.usos(
            tenant_id, self._config.contadores, equipo, clasificacion.playbook_id
        )
        estado = self._config.estado_operacion(usos, cortacircuito_abierto=False)
        veredicto = validar(
            Propuesta(
                familia=clasificacion.familia,
                playbook_id=clasificacion.playbook_id,
                confianza=clasificacion.confianza,
                severidad=alerta.severidad,
                objetivo=alerta.objetivo,
                familia_candidata=alerta.familia_candidata,
                ip_origen=alerta.ip_origen,
            ),
            self._catalogo,
            self._config.exclusion,
            self._config.mapa,
            estado,
            self._config.redes_internas,
        )
        if isinstance(veredicto, Aprobada):
            self._almacen.registrar_decision(
                tenant_id,
                ticket_id,
                self._decision(
                    familia=clasificacion.familia,
                    playbook_id=veredicto.playbook_id,
                    confianza=clasificacion.confianza,
                    nivel=veredicto.nivel,
                    equipo=equipo,
                ),
            )
            return Resultado(Destino.APROBADA, ticket_id)
        return self._rechazar(
            tenant_id,
            ticket_id,
            veredicto.motivo,
            veredicto.detalle,
            equipo,
            clasificacion=clasificacion,
        )

    def _cortacircuito_abierto(self, tenant_id: int) -> bool:
        """Abre el cortacircuito si las alertas de la ventana llegan al disparo."""
        disparo = self._config.disparo_cortacircuito
        alertas = self._almacen.alertas_en_ventana(tenant_id, disparo.ventana_minutos)
        if self._config.debe_abrir_cortacircuito(alertas):
            self._almacen.abrir_cortacircuito(
                tenant_id, f"{alertas} alertas en {disparo.ventana_minutos} min"
            )
        return self._almacen.cortacircuito_abierto(tenant_id)

    def _rechazar(
        self,
        tenant_id: int,
        ticket_id: int,
        motivo: str,
        detalle: str,
        equipo: str | None,
        clasificacion: Any = None,
    ) -> Resultado:
        self._almacen.registrar_decision(
            tenant_id,
            ticket_id,
            self._decision(
                familia=getattr(clasificacion, "familia", None),
                playbook_id=getattr(clasificacion, "playbook_id", None),
                confianza=getattr(clasificacion, "confianza", None),
                nivel=None,
                motivo=str(motivo),
                detalle=detalle,
                equipo=equipo,
            ),
        )
        return Resultado(Destino.RECHAZADA, ticket_id, str(motivo))
