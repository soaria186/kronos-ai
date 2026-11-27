"""Lo que SOAR-EXECUTE necesita saber de cada playbook del catálogo KRO-CAT-01.

El catálogo se valida con ``validacion.catalogo`` (la misma carga que usa VALIDATE) y
de cada playbook se toman la acción, el nivel y cómo se revierte. De la sección
"actuadores_v1" se toma qué acciones tienen script de Active Response en cada sistema
operativo (D-60). Si el archivo no pasa la validación, EXECUTE no arranca.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ejecucion.ordenes import COMANDOS, SISTEMAS
from validacion.catalogo import RUTA_CATALOGO, CatalogoInvalido, cargar_catalogo


@dataclass(frozen=True)
class Medida:
    playbook_id: str
    accion: str
    nivel: int
    # no_aplica, automatica_al_vencer, manual o accion_de_la_persona.
    reversion: str
    # Plazo de la reversión automática; None mientras el catálogo no lo fije.
    plazo_minutos: int | None


def cargar_medidas(ruta: Path = RUTA_CATALOGO) -> dict[str, Medida]:
    cargar_catalogo(ruta)  # lanza CatalogoInvalido si el archivo no cumple sus reglas
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    medidas: dict[str, Medida] = {}
    for p in datos["playbooks"]:
        plazo = p["reversion"].get("plazo_minutos")
        if plazo is not None and (
            isinstance(plazo, bool) or not isinstance(plazo, int) or plazo <= 0
        ):
            raise ValueError(
                f"{p['id']}: plazo_minutos debe ser un entero positivo o null"
            )
        medidas[p["id"]] = Medida(
            p["id"], p["accion"], p["nivel"], p["reversion"]["tipo"], plazo
        )
    return medidas


def cargar_actuadores(ruta: Path = RUTA_CATALOGO) -> dict[str, frozenset[str]]:
    """Acciones con script de Active Response por sistema operativo (``actuadores_v1``).

    Devuelve, por ejemplo, ``{"linux": {"bloquear_ip"}, "windows": {...}}``. Se exige
    la sección con los dos sistemas; un sistema desconocido, o una acción que no está
    declarada en el catálogo o no tiene comando en ``ordenes.COMANDOS``, es un error.
    """
    cargar_catalogo(ruta)
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    seccion = datos.get("actuadores_v1")
    if not isinstance(seccion, dict):
        raise CatalogoInvalido("falta la sección actuadores_v1")
    sistemas = {k: v for k, v in seccion.items() if k != "nota"}
    desconocidos = set(sistemas) - SISTEMAS
    if desconocidos:
        raise CatalogoInvalido(
            f"actuadores_v1: sistema desconocido {sorted(desconocidos)}"
        )
    faltan = SISTEMAS - set(sistemas)
    if faltan:
        raise CatalogoInvalido(f"actuadores_v1: falta {sorted(faltan)}")
    actuadores: dict[str, frozenset[str]] = {}
    for sistema, acciones in sistemas.items():
        if not isinstance(acciones, list) or not all(
            isinstance(a, str) for a in acciones
        ):
            raise CatalogoInvalido(f"actuadores_v1.{sistema}: debe ser una lista de acciones")
        for accion in acciones:
            if accion not in datos["acciones"] or accion not in COMANDOS:
                raise CatalogoInvalido(
                    f"actuadores_v1.{sistema}: {accion!r} no es una acción con comando"
                )
        actuadores[sistema] = frozenset(acciones)
    return actuadores
