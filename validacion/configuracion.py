"""Carga de la configuración de SOAR-VALIDATE (validacion/configuracion/validate.json).

Reúne los valores que los chequeos reciben como datos: el mapa de severidad a niveles,
la lista de exclusión con sus seis categorías, los cuatro contadores de tasa de acciones
y el quinto contador, el de alertas, que abre el cortacircuito. El archivo se rechaza
entero si algo no cuadra: un mapa con huecos, una entrada de exclusión con una categoría
no declarada, un contador repetido o un tope no positivo.

Los contadores aquí son definiciones (nombre, ventana y tope). Cuántas acciones lleva
cada uno en su ventana lo sabe SOAR-AUDIT; quien llama lo entrega a estado_operacion().
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from validacion.chequeos import (
    Contador,
    EstadoOperacion,
    ListaExclusion,
    MapaSeveridad,
    RedesInternas,
)

RUTA_CONFIGURACION = Path(__file__).resolve().parent / "configuracion" / "validate.json"
CODIGO = "KRO-VAL-CONF"
CATEGORIAS_EXCLUSION = frozenset(
    {"equipo", "cuenta", "programa", "servicio", "ip", "destino"}
)


class ConfiguracionInvalida(ValueError):
    """El archivo de configuración de VALIDATE no cumple sus reglas."""


@dataclass(frozen=True)
class DefinicionContador:
    nombre: str
    ventana_minutos: int
    tope: int


@dataclass(frozen=True)
class Configuracion:
    version: str
    mapa: MapaSeveridad
    exclusion: ListaExclusion
    redes_internas: RedesInternas
    contadores: tuple[DefinicionContador, ...]
    disparo_cortacircuito: DefinicionContador

    def estado_operacion(
        self, usos: dict[str, int], cortacircuito_abierto: bool
    ) -> EstadoOperacion:
        """Arma el estado que revisa el chequeo 5 con los usos que informa SOAR-AUDIT.

        Un contador sin dato se trata como en su tope: sin saber cuántas acciones van,
        no se ejecuta nada automático (falla segura).
        """
        return EstadoOperacion(
            cortacircuito_abierto=cortacircuito_abierto,
            contadores=tuple(
                Contador(d.nombre, usos.get(d.nombre, d.tope), d.tope)
                for d in self.contadores
            ),
        )

    def debe_abrir_cortacircuito(self, alertas_en_ventana: int) -> bool:
        return alertas_en_ventana >= self.disparo_cortacircuito.tope


def cargar_configuracion(ruta: Path = RUTA_CONFIGURACION) -> Configuracion:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfiguracionInvalida(f"no se pudo leer {ruta.name}: {exc}") from exc
    if not isinstance(datos, dict) or datos.get("codigo") != CODIGO:
        raise ConfiguracionInvalida(f"{ruta.name} no es la configuración {CODIGO}")
    try:
        return Configuracion(
            version=str(datos["version"]),
            mapa=_leer_mapa(datos["mapa_severidad"]),
            exclusion=_leer_exclusion(datos["exclusion"]),
            redes_internas=_leer_redes(datos["redes_internas"]),
            contadores=_leer_contadores(datos["contadores"]),
            disparo_cortacircuito=_leer_contador(datos["disparo_cortacircuito"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ConfiguracionInvalida):
            raise
        raise ConfiguracionInvalida(f"{ruta.name}: {exc}") from exc


def _entero(valor: object, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ConfiguracionInvalida(f"{campo} debe ser un entero")
    return valor


def _leer_mapa(tramos: list) -> MapaSeveridad:
    return MapaSeveridad(
        tuple(
            (
                _entero(t["desde"], "desde"),
                _entero(t["hasta"], "hasta"),
                _entero(t["nivel_maximo"], "nivel_maximo"),
            )
            for t in tramos
        )
    )


def _leer_redes(dato: list) -> RedesInternas:
    if not isinstance(dato, list) or not dato:
        raise ConfiguracionInvalida(
            "redes_internas debe ser una lista con al menos una red"
        )
    if not all(isinstance(r, str) for r in dato):
        raise ConfiguracionInvalida(
            "cada red interna debe ser un texto, por ejemplo 10.0.0.0/8"
        )
    return RedesInternas.desde(
        dato
    )  # ValueError (red mal escrita) lo recoge cargar_configuracion


def _leer_exclusion(dato: dict) -> ListaExclusion:
    categorias = set(dato["categorias"])
    if categorias != CATEGORIAS_EXCLUSION:
        raise ConfiguracionInvalida(
            f"categorías de exclusión {sorted(categorias)}, "
            f"se esperaban {sorted(CATEGORIAS_EXCLUSION)}"
        )
    pares = []
    for entrada in dato["entradas"]:
        categoria, valor = entrada["categoria"], entrada["valor"]
        if categoria not in CATEGORIAS_EXCLUSION:
            raise ConfiguracionInvalida(
                f"categoría de exclusión desconocida: {categoria!r}"
            )
        if not isinstance(valor, str) or not valor.strip():
            raise ConfiguracionInvalida(f"valor vacío en la exclusión de {categoria}")
        pares.append((categoria, valor))
    return ListaExclusion.desde(pares)


def _leer_contador(dato: dict) -> DefinicionContador:
    nombre = dato["nombre"]
    if not isinstance(nombre, str) or not nombre:
        raise ConfiguracionInvalida("contador sin nombre")
    ventana = _entero(dato["ventana_minutos"], f"{nombre}.ventana_minutos")
    tope = _entero(dato["tope"], f"{nombre}.tope")
    if ventana <= 0 or tope <= 0:
        raise ConfiguracionInvalida(f"{nombre}: ventana y tope deben ser positivos")
    return DefinicionContador(nombre, ventana, tope)


def _leer_contadores(datos: list) -> tuple[DefinicionContador, ...]:
    contadores = tuple(_leer_contador(d) for d in datos)
    nombres = [c.nombre for c in contadores]
    if len(set(nombres)) != len(nombres):
        raise ConfiguracionInvalida("hay contadores con el mismo nombre")
    return contadores
