"""Lo que SOAR-EXECUTE necesita saber de cada playbook del catálogo KRO-CAT-01.

El catálogo se valida con ``validacion.catalogo`` (la misma carga que usa VALIDATE) y
de cada playbook se toman la acción, el nivel y cómo se revierte. Si el archivo no
pasa la validación, EXECUTE no arranca.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from validacion.catalogo import RUTA_CATALOGO, cargar_catalogo


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
