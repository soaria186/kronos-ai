"""Contrato JSON de las respuestas del modelo y su validación determinista.

El modelo sólo puede responder con uno de estos dos objetos, sin texto alrededor:

    paso 1: {"familia": "F1".."F6", "confianza": número entre 0 y 1}
    paso 2: {"playbook_id": uno de los candidatos de la familia, "confianza": número entre 0 y 1}

Cualquier otra cosa es ESQUEMA_INVALIDO: texto que no es JSON, claves de más, de menos
o repetidas, tipos distintos, NaN o infinito, confianza fuera de rango, una familia que
no existe o un playbook que no está entre los candidatos. La respuesta se rechaza
entera; no se intenta reparar ni completar.

Los esquemas se envían también a Ollama en el campo "format", pero la validación de aquí
no confía en que el servidor los haya respetado.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

FAMILIAS = ("F1", "F2", "F3", "F4", "F5", "F6")
LARGO_MAXIMO_RESPUESTA = 1000


class EsquemaInvalido(ValueError):
    """La respuesta del modelo no cumple el contrato."""


@dataclass(frozen=True)
class RespuestaFamilia:
    familia: str
    confianza: float


@dataclass(frozen=True)
class RespuestaPlaybook:
    playbook_id: str
    confianza: float


def esquema_familia() -> dict:
    return _esquema("familia", FAMILIAS)


def esquema_playbook(candidatos: tuple[str, ...]) -> dict:
    if not candidatos:
        raise ValueError("el paso 2 necesita al menos un playbook candidato")
    return _esquema("playbook_id", candidatos)


def leer_familia(texto: str) -> RespuestaFamilia:
    datos = _leer_objeto(texto, "familia", FAMILIAS)
    return RespuestaFamilia(datos["familia"], datos["confianza"])


def leer_playbook(texto: str, candidatos: tuple[str, ...]) -> RespuestaPlaybook:
    datos = _leer_objeto(texto, "playbook_id", candidatos)
    return RespuestaPlaybook(datos["playbook_id"], datos["confianza"])


def _esquema(campo: str, permitidos: tuple[str, ...]) -> dict:
    return {
        "type": "object",
        "properties": {
            campo: {"type": "string", "enum": list(permitidos)},
            "confianza": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [campo, "confianza"],
        "additionalProperties": False,
    }


def _sin_repetidas(pares: list[tuple[str, object]]) -> dict:
    datos = {}
    for clave, valor in pares:
        if clave in datos:
            raise EsquemaInvalido(f"clave repetida: {clave}")
        datos[clave] = valor
    return datos


def _sin_constantes(nombre: str) -> float:
    raise EsquemaInvalido(f"valor no permitido: {nombre}")


def _leer_objeto(texto: str, campo: str, permitidos: tuple[str, ...]) -> dict:
    if not isinstance(texto, str):
        raise EsquemaInvalido("la respuesta no es texto")
    if len(texto) > LARGO_MAXIMO_RESPUESTA:
        raise EsquemaInvalido(f"respuesta de {len(texto)} caracteres")
    try:
        datos = json.loads(
            texto, object_pairs_hook=_sin_repetidas, parse_constant=_sin_constantes
        )
    except json.JSONDecodeError as exc:
        raise EsquemaInvalido(f"no es JSON: {exc.msg}") from exc
    if not isinstance(datos, dict):
        raise EsquemaInvalido("la respuesta no es un objeto JSON")
    if set(datos) != {campo, "confianza"}:
        raise EsquemaInvalido(
            f"claves {sorted(datos)}, se esperaban {campo} y confianza"
        )
    if datos[campo] not in permitidos:
        raise EsquemaInvalido(f"{campo} fuera del contrato: {datos[campo]!r}")
    confianza = datos["confianza"]
    if isinstance(confianza, bool) or not isinstance(confianza, (int, float)):
        raise EsquemaInvalido("confianza no es un número")
    if not math.isfinite(confianza) or not 0.0 <= confianza <= 1.0:
        raise EsquemaInvalido(f"confianza fuera de rango: {confianza}")
    return {campo: datos[campo], "confianza": float(confianza)}
