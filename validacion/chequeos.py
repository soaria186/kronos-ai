"""Chequeos deterministas de SOAR-VALIDATE sobre la propuesta del modelo.

El chequeo 1 (la respuesta cumple el esquema JSON) ya ocurrió en validacion.contrato. Aquí
van los otros cinco, en este orden; el primero que falla decide el motivo del rechazo, con
los mismos códigos que tickets.rechazo_motivo:

    2. confianza >= 0,70                          CONFIANZA_BAJA
    3. el playbook existe en el catálogo cerrado
       y pertenece a la familia clasificada       PLAYBOOK_FUERA_DE_CATALOGO
    4. el objetivo no está en la lista de
       exclusión                                  ACTIVO_EXCLUIDO
    5. cortacircuito cerrado                      CORTACIRCUITO_ABIERTO
       y ningún contador de tasa en su tope       LIMITE_DE_TASA
    6. el nivel del playbook está permitido
       para la severidad de la alerta             NIVEL_NO_PERMITIDO_POR_SEVERIDAD

El nivel de autonomía lo fija el catálogo, nunca el modelo. Lo que el equipo todavía no
decidió (el mapa de severidad, las categorías de exclusión y los topes de cada contador)
no tiene valores por defecto: entra como datos. El estado de los contadores y del
cortacircuito también entra como datos, porque vive en SOAR-AUDIT; esta capa no lee la base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from validacion.contrato import FAMILIAS

UMBRAL_CONFIANZA = 0.70
NIVELES = (0, 1, 2, 3)
SEVERIDAD_MINIMA = 0
SEVERIDAD_MAXIMA = 15  # niveles de regla de Wazuh


class MotivoRechazo(StrEnum):
    CONFIANZA_BAJA = "CONFIANZA_BAJA"
    PLAYBOOK_FUERA_DE_CATALOGO = "PLAYBOOK_FUERA_DE_CATALOGO"
    ACTIVO_EXCLUIDO = "ACTIVO_EXCLUIDO"
    CORTACIRCUITO_ABIERTO = "CORTACIRCUITO_ABIERTO"
    LIMITE_DE_TASA = "LIMITE_DE_TASA"
    NIVEL_NO_PERMITIDO_POR_SEVERIDAD = "NIVEL_NO_PERMITIDO_POR_SEVERIDAD"


@dataclass(frozen=True)
class Playbook:
    id: str
    familia: str
    nivel: int

    def __post_init__(self) -> None:
        if self.familia not in FAMILIAS:
            raise ValueError(f"{self.id}: familia desconocida {self.familia!r}")
        if self.nivel not in NIVELES:
            raise ValueError(f"{self.id}: nivel fuera de 0 a 3")


@dataclass(frozen=True)
class Catalogo:
    playbooks: dict[str, Playbook]

    @classmethod
    def desde(cls, playbooks: list[Playbook]) -> Catalogo:
        ids = [p.id for p in playbooks]
        if len(set(ids)) != len(ids):
            raise ValueError("el catálogo tiene identificadores repetidos")
        return cls({p.id: p for p in playbooks})


@dataclass(frozen=True)
class ListaExclusion:
    """Pares (categoría, valor) sobre los que Kronos nunca actúa, sea cual sea el nivel.

    Las categorías las define el equipo (equipo, cuenta, programa, servicio...). La
    comparación ignora mayúsculas y espacios en los extremos.
    """

    entradas: frozenset[tuple[str, str]] = frozenset()

    @classmethod
    def desde(cls, pares: list[tuple[str, str]]) -> ListaExclusion:
        return cls(frozenset((_normalizar(c), _normalizar(v)) for c, v in pares))

    def coincidencia(self, objetivo: dict[str, str]) -> tuple[str, str] | None:
        for categoria, valor in sorted(objetivo.items()):
            par = (_normalizar(categoria), _normalizar(valor))
            if par in self.entradas:
                return par
        return None


@dataclass(frozen=True)
class MapaSeveridad:
    """Tramos (severidad mínima, severidad máxima, nivel máximo permitido).

    Debe cubrir de 0 a 15 sin huecos ni solapes, y el nivel permitido no puede bajar
    cuando sube la severidad.
    """

    tramos: tuple[tuple[int, int, int], ...]

    def __post_init__(self) -> None:
        esperado = SEVERIDAD_MINIMA
        nivel_anterior = NIVELES[0]
        for desde, hasta, nivel in sorted(self.tramos):
            if desde != esperado or hasta < desde:
                raise ValueError(f"mapa de severidad con hueco o solape en {desde}")
            if nivel not in NIVELES or nivel < nivel_anterior:
                raise ValueError(
                    f"nivel inválido o decreciente en el tramo {desde}-{hasta}"
                )
            esperado, nivel_anterior = hasta + 1, nivel
        if esperado != SEVERIDAD_MAXIMA + 1:
            raise ValueError("el mapa de severidad debe cubrir de 0 a 15")

    def nivel_maximo(self, severidad: int) -> int:
        for desde, hasta, nivel in self.tramos:
            if desde <= severidad <= hasta:
                return nivel
        raise ValueError(f"severidad fuera de 0 a 15: {severidad}")


@dataclass(frozen=True)
class Contador:
    """Un contador de tasa con su uso actual en la ventana vigente y su tope."""

    nombre: str
    usados: int
    tope: int


@dataclass(frozen=True)
class EstadoOperacion:
    cortacircuito_abierto: bool
    contadores: tuple[Contador, ...] = ()


@dataclass(frozen=True)
class Propuesta:
    familia: str
    playbook_id: str
    confianza: float
    severidad: int
    objetivo: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Aprobada:
    playbook_id: str
    nivel: int


@dataclass(frozen=True)
class Rechazo:
    motivo: MotivoRechazo
    detalle: str


def validar(
    propuesta: Propuesta,
    catalogo: Catalogo,
    exclusion: ListaExclusion,
    mapa: MapaSeveridad,
    estado: EstadoOperacion,
) -> Aprobada | Rechazo:
    if not propuesta.confianza >= UMBRAL_CONFIANZA:
        return Rechazo(
            MotivoRechazo.CONFIANZA_BAJA,
            f"confianza {propuesta.confianza:.2f} < {UMBRAL_CONFIANZA:.2f}",
        )

    playbook = catalogo.playbooks.get(propuesta.playbook_id)
    if playbook is None or playbook.familia != propuesta.familia:
        return Rechazo(
            MotivoRechazo.PLAYBOOK_FUERA_DE_CATALOGO,
            f"{propuesta.playbook_id} no está en el catálogo para {propuesta.familia}",
        )

    excluido = exclusion.coincidencia(propuesta.objetivo)
    if excluido is not None:
        return Rechazo(MotivoRechazo.ACTIVO_EXCLUIDO, f"{excluido[0]} = {excluido[1]}")

    if estado.cortacircuito_abierto:
        return Rechazo(MotivoRechazo.CORTACIRCUITO_ABIERTO, "cortacircuito abierto")
    for contador in estado.contadores:
        if contador.usados >= contador.tope:
            return Rechazo(
                MotivoRechazo.LIMITE_DE_TASA,
                f"{contador.nombre}: {contador.usados} de {contador.tope}",
            )

    permitido = mapa.nivel_maximo(propuesta.severidad)
    if playbook.nivel > permitido:
        return Rechazo(
            MotivoRechazo.NIVEL_NO_PERMITIDO_POR_SEVERIDAD,
            f"nivel {playbook.nivel} con severidad {propuesta.severidad} "
            f"(máximo {permitido})",
        )

    return Aprobada(playbook.id, playbook.nivel)


def _normalizar(texto: str) -> str:
    return texto.strip().casefold()
