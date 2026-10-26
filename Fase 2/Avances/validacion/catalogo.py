"""Carga y validación del catálogo KRO-CAT-01 (decision/catalogo/kro-cat-01.json).

El catálogo es datos versionados: cambiarlo es publicar una versión nueva del archivo,
nunca modificarlo en caliente (R2). Al cargarlo se rechaza el archivo entero si no cumple
las reglas que el propio catálogo declara:

- identificadores únicos con la forma PB-Fx-NN, donde Fx es la familia del playbook;
- acción declarada en la lista de acciones, nivel de 0 a 3 y arquetipos conocidos;
- nivel 0 = consulta de sólo lectura, sin reversión;
- sólo el nivel 1 puede revertirse solo al vencer un plazo; los niveles 2 y 3 nunca.

Desde la versión 1.0 (D-60), "actuadores_v1" dice qué acciones tienen script de Active
Response en cada sistema operativo; "puntos_abiertos" y el campo "pendiente" de cada
playbook guardan lo que queda como trabajo futuro.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from validacion.chequeos import AMBITOS_IP, NIVELES, Catalogo, Playbook

RUTA_CATALOGO = (
    Path(__file__).resolve().parent.parent / "decision" / "catalogo" / "kro-cat-01.json"
)
CODIGO = "KRO-CAT-01"
ARQUETIPOS = frozenset({"puesto", "servidor"})
REVERSIONES = frozenset(
    {"no_aplica", "automatica_al_vencer", "manual", "accion_de_la_persona"}
)
_ID = re.compile(r"^PB-(F[1-6])-\d{2}$")


class CatalogoInvalido(ValueError):
    """El archivo del catálogo no cumple sus reglas."""


def cargar_catalogo(ruta: Path = RUTA_CATALOGO) -> Catalogo:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogoInvalido(f"no se pudo leer {ruta.name}: {exc}") from exc
    if not isinstance(datos, dict) or datos.get("codigo") != CODIGO:
        raise CatalogoInvalido(f"{ruta.name} no es el catálogo {CODIGO}")
    acciones = datos.get("acciones")
    playbooks = datos.get("playbooks")
    if (
        not isinstance(acciones, dict)
        or not isinstance(playbooks, list)
        or not playbooks
    ):
        raise CatalogoInvalido("faltan las acciones o los playbooks")

    leidos = [_leer_playbook(p, acciones) for p in playbooks]
    try:
        return Catalogo.desde(leidos)
    except ValueError as exc:
        raise CatalogoInvalido(str(exc)) from exc


def _leer_playbook(dato: object, acciones: dict) -> Playbook:
    if not isinstance(dato, dict):
        raise CatalogoInvalido("un playbook no es un objeto")
    identificador = dato.get("id")
    coincidencia = _ID.match(identificador) if isinstance(identificador, str) else None
    if not coincidencia or coincidencia.group(1) != dato.get("familia"):
        raise CatalogoInvalido(f"{identificador!r}: identificador o familia inválidos")

    nivel = dato.get("nivel")
    if isinstance(nivel, bool) or nivel not in NIVELES:
        raise CatalogoInvalido(f"{identificador}: nivel fuera de 0 a 3")
    accion = dato.get("accion")
    if not isinstance(accion, str) or accion not in acciones:
        raise CatalogoInvalido(f"{identificador}: acción no declarada {accion!r}")
    arquetipos = dato.get("arquetipos")
    if (
        not isinstance(arquetipos, list)
        or not arquetipos
        or not all(isinstance(a, str) for a in arquetipos)
        or not set(arquetipos) <= ARQUETIPOS
    ):
        raise CatalogoInvalido(f"{identificador}: arquetipos inválidos")
    reversion = dato.get("reversion")
    tipo = reversion.get("tipo") if isinstance(reversion, dict) else None
    if tipo not in REVERSIONES:
        raise CatalogoInvalido(f"{identificador}: tipo de reversión inválido")

    if (nivel == 0) != (accion == "consulta") or (nivel == 0) != (tipo == "no_aplica"):
        raise CatalogoInvalido(
            f"{identificador}: el nivel 0 es sólo para consultas, sin reversión"
        )
    if tipo == "automatica_al_vencer" and nivel != 1:
        raise CatalogoInvalido(
            f"{identificador}: sólo el nivel 1 puede revertirse solo"
        )
    condicion = dato.get("condicion_de_uso")
    if not isinstance(condicion, str) or not condicion.strip():
        raise CatalogoInvalido(f"{identificador}: sin condición de uso")
    medida = dato.get("medida")
    if not isinstance(medida, str) or not medida.strip():
        raise CatalogoInvalido(f"{identificador}: sin nombre de la medida")
    ambito = dato.get("ambito_ip")
    if ambito is not None and (ambito not in AMBITOS_IP or accion != "bloquear_ip"):
        raise CatalogoInvalido(
            f"{identificador}: ámbito de IP {ambito!r} inválido (sólo bloquear_ip)"
        )
    return Playbook(identificador, dato["familia"], nivel, medida.strip(), ambito)
