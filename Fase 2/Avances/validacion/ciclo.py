"""Ciclo de SOAR-VALIDATE para una alerta: registrar, clasificar, validar, decidir.

Orden de cada alerta de alerts.json (``Validador.procesar``):

 0. Si es del mismo ataque que otra que ya se resolvió hace poco (misma regla, misma IP de
    origen y mismo equipo, dentro de la ventana de validate.json), no crea ticket ni llama
    al modelo: queda anotada como ALERTA_AGRUPADA en el ticket que decidió. Un fallo de la
    IA o un tope pasajero no cierra el grupo, para que la alerta siguiente se reintente.
 1. Se crea el ticket y se guarda la alerta completa (validacion.servicio). Una alerta
    sin etiqueta kronos_fX se omite; una inválida se descarta sin tocar la base; una ya
    vista (rotación del archivo, reinicio) no se vuelve a procesar.
 2. Cortacircuito: si las alertas RECIBIDAS en la ventana llegan al disparo, se abre; si
    está abierto, la alerta se rechaza ahí mismo, sin llamar al modelo (lo que importa en
    una inundación es no gastar 20 s de inferencia por alerta). El disparo mide las que
    llegaron, no las que alcanzaron a procesarse: ``anotar_llegadas`` cuenta un lote
    completo antes de procesar la primera, y el cortacircuito toma el MAYOR entre esas
    llegadas y lo que SOAR-AUDIT tiene registrado en la ventana (tickets más alertas
    agrupadas). Se usa el máximo y no la suma para no contar dos veces una misma alerta.
    Limitación: las llegadas viven en memoria; si VALIDATE se reinicia se pierden y sólo
    queda lo registrado en la base. Una alerta releída tras una rotación del archivo
    también cuenta como llegada.
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
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from decision.inferencia import FallaSegura, Modelo, MotivoFalla, clasificar
from decision.plantillas import Plantillas
from validacion.alerta import AlertaInvalida, AlertaKronos, preparar
from validacion.chequeos import (
    Aprobada,
    Catalogo,
    MotivoRechazo,
    Propuesta,
    ip_canonica,
    normalizar,
    validar,
)
from validacion.configuracion import Configuracion
from validacion.servicio import RegistroDeAlertas, agrupar, registrar

registro = logging.getLogger("soar-validate")

AGENTE_MANAGER = 0
# Plazo total de los dos pasos del modelo. Era 60 s: en la prueba del 20-10 el modelo
# estaba frío y una alerta terminó en TIEMPO_EXCEDIDO (el 7B en frío tarda unos 58 s por
# alerta). Con 120 s esa alerta se clasifica; en tibio siguen siendo unos 20 s.
PLAZO_POR_OMISION = 120.0

# Motivos de rechazo que NO cierran un grupo de alertas: dependen del momento (el modelo
# estaba caído o frío, un tope de tasa, el cortacircuito) y la alerta siguiente del mismo
# ataque puede resolverse distinto. Los demás rechazos son del contenido de la alerta y se
# repetirían igual, así que sí cierran el grupo.
MOTIVOS_TRANSITORIOS = frozenset(
    {
        *(m.value for m in MotivoFalla),
        MotivoRechazo.LIMITE_DE_TASA.value,
        MotivoRechazo.CORTACIRCUITO_ABIERTO.value,
    }
)


class PromptDistintoDelCatalogo(ValueError):
    """El prompt del paso 2 no describe las medidas del catálogo KRO-CAT-01."""


class Almacen(RegistroDeAlertas, Protocol):  # incluye registrar_alerta y agrupar_alerta
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
    AGRUPADA = "agrupada"  # mismo ataque que una alerta ya resuelta: sin ticket nuevo
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


def clave_de_grupo(alerta: AlertaKronos, equipo: str | None) -> tuple[str, str, str] | None:
    """(regla, IP de origen, equipo) que identifica «el mismo ataque»; None si no se puede.

    Sin IP de origen no hay «origen» que comparar (dos procesos distintos en un equipo
    disparan la misma regla sin ser el mismo ataque): esas alertas no se agrupan.
    """
    if alerta.regla is None or alerta.ip_origen is None or equipo is None:
        return None
    return (alerta.regla, ip_canonica(alerta.ip_origen), equipo)


@dataclass(frozen=True)
class _Grupo:
    ticket_id: int  # el ticket que decidió por todo el grupo
    vence: float  # instante (del reloj del validador) en que se cierra el grupo


class Validador:
    def __init__(
        self,
        almacen: Almacen,
        modelo: Modelo,
        plantillas: Plantillas,
        catalogo: Catalogo,
        configuracion: Configuracion,
        tipo_decision: type,
        plazo: float = PLAZO_POR_OMISION,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        comprobar_prompt(plantillas, catalogo)
        self._almacen = almacen
        self._modelo = modelo
        self._plantillas = plantillas
        self._catalogo = catalogo
        self._config = configuracion
        self._decision = tipo_decision
        self._plazo = plazo
        self._reloj = reloj
        # Grupos abiertos, en memoria: si VALIDATE se reinicia se pierden y, a lo más, el
        # ataque en curso recibe una decisión más.
        self._grupos: dict[tuple[str, str, str], _Grupo] = {}
        # Instantes de llegada de las alertas de cada inquilino, para el disparo del
        # cortacircuito. También en memoria: tras un reinicio manda lo que dice la base.
        self._llegadas: dict[int, deque[float]] = {}

    def anotar_llegadas(self, tenant_id: int, alertas: Sequence[Mapping]) -> int:
        """Cuenta las alertas de un lote que llegaron, antes de procesar ninguna.

        Cuentan las que pasaron por una regla de sobre (las mismas que ``procesar`` llevaría
        a un ticket o a una agrupación). No cuentan las omitidas (sin etiqueta kronos_fX)
        ni las inválidas. Devuelve cuántas anotó.
        """
        ahora = self._reloj()
        cola = self._llegadas.setdefault(tenant_id, deque())
        anotadas = 0
        for alerta_wazuh in alertas:
            try:
                if preparar(dict(alerta_wazuh)) is None:
                    continue
            except AlertaInvalida:
                continue
            cola.append(ahora)
            anotadas += 1
        self._podar_llegadas(tenant_id)
        return anotadas

    def _podar_llegadas(self, tenant_id: int) -> int:
        """Descarta las llegadas fuera de la ventana y devuelve las que quedan."""
        cola = self._llegadas.get(tenant_id)
        if cola is None:
            return 0
        limite = self._reloj() - self._config.disparo_cortacircuito.ventana_minutos * 60
        while cola and cola[0] <= limite:
            cola.popleft()
        return len(cola)

    def procesar(self, tenant_id: int, alerta_wazuh: dict) -> Resultado:
        try:
            alerta = preparar(alerta_wazuh)
        except AlertaInvalida as exc:
            registro.warning("alerta descartada: %s", exc)
            return Resultado(Destino.DESCARTADA, motivo=str(exc))
        if alerta is None:
            return Resultado(Destino.OMITIDA)

        equipo = equipo_de(alerta)
        clave = self._clave_de_grupo(alerta, equipo)
        grupo = self._grupo_vigente(clave)
        try:
            if grupo is not None:
                agrupar(self._almacen, tenant_id, grupo.ticket_id, alerta_wazuh, alerta)
                return Resultado(Destino.AGRUPADA, grupo.ticket_id)
            registrada = registrar(self._almacen, tenant_id, alerta_wazuh, alerta)
        except AlertaInvalida as exc:
            registro.warning("alerta descartada: %s", exc)
            return Resultado(Destino.DESCARTADA, motivo=str(exc))
        if registrada is None:  # no ocurre: la alerta ya está preparada
            return Resultado(Destino.OMITIDA)
        if not registrada.nuevo:
            return Resultado(Destino.REPETIDA, registrada.ticket_id)

        resultado = self._resolver(
            tenant_id, alerta_wazuh, alerta, registrada.ticket_id, equipo
        )
        self._abrir_grupo(clave, resultado)
        return resultado

    def _clave_de_grupo(
        self, alerta: AlertaKronos, equipo: str | None
    ) -> tuple[str, str, str] | None:
        if self._config.ventana_agrupacion_minutos <= 0:
            return None
        return clave_de_grupo(alerta, equipo)

    def _grupo_vigente(self, clave: tuple[str, str, str] | None) -> _Grupo | None:
        ahora = self._reloj()
        for vencida in [k for k, g in self._grupos.items() if g.vence <= ahora]:
            del self._grupos[vencida]
        return self._grupos.get(clave) if clave is not None else None

    def _abrir_grupo(
        self, clave: tuple[str, str, str] | None, resultado: Resultado
    ) -> None:
        """Las alertas siguientes del mismo ataque quedan cubiertas por esta decisión."""
        if clave is None or resultado.ticket_id is None:
            return
        if resultado.destino is Destino.RECHAZADA and (
            resultado.motivo in MOTIVOS_TRANSITORIOS
        ):
            return
        vence = self._reloj() + self._config.ventana_agrupacion_minutos * 60
        self._grupos[clave] = _Grupo(resultado.ticket_id, vence)

    def _resolver(
        self,
        tenant_id: int,
        alerta_wazuh: Mapping[str, Any],
        alerta: AlertaKronos,
        ticket_id: int,
        equipo: str | None,
    ) -> Resultado:
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
            alerta.texto,
            self._modelo,
            self._plantillas,
            self._plazo,
            ambito_ip=self._ambito_ip(alerta),
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

    def _ambito_ip(self, alerta: AlertaKronos) -> str | None:
        """«interna» o «externa» para el prompt del paso 2; None si no hay una IP válida."""
        if alerta.ip_origen is None:
            return None
        return self._config.redes_internas.ambito(alerta.ip_origen)

    def _cortacircuito_abierto(self, tenant_id: int) -> bool:
        """Abre el cortacircuito si las alertas recibidas en la ventana llegan al disparo.

        Toma el mayor entre las llegadas anotadas en memoria y lo registrado en la base:
        las primeras no existen tras un reinicio; la segunda sólo sabe de las alertas ya
        procesadas. El máximo, y no la suma, evita contar dos veces la misma alerta.
        """
        if self._almacen.cortacircuito_abierto(tenant_id):
            return True  # ya abierto: sólo una persona lo cierra, no se vuelve a abrir
        disparo = self._config.disparo_cortacircuito
        registradas = self._almacen.alertas_en_ventana(tenant_id, disparo.ventana_minutos)
        alertas = max(registradas, self._podar_llegadas(tenant_id))
        if self._config.debe_abrir_cortacircuito(alertas):
            self._almacen.abrir_cortacircuito(
                tenant_id,
                f"{alertas} alertas recibidas en {disparo.ventana_minutos} min",
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
