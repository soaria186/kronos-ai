"""Tope de tamaño de la alerta completa antes de guardarla en alertas_guardadas.

La tabla rechaza una alerta de más de 64 KiB (CHECK en initdb/06_alertas_guardadas.sql).
Quien controla un campo de la alerta controla su tamaño, así que antes de guardarla:

1. Si cabe, se guarda tal cual.
2. Si no cabe, se recorta cada texto a LARGO_TEXTO caracteres.
3. Si aún no cabe (por ejemplo, miles de claves), se guardan sólo los CAMPOS_ESENCIALES:
   los que usan SOAR-EXECUTE (ejecucion/ordenes.py) y la lista de exclusión de VALIDATE
   (validacion/alerta.py), con sus textos recortados a LARGO_ESENCIAL.

Los valores que EXECUTE usa como objetivo son cortos y se validan con reglas estrictas
(una cuenta, hasta 64 caracteres; un servicio, hasta 128), así que el recorte no cambia
una orden válida: un valor que necesitara recortarse ya era inválido.

Sólo biblioteca estándar: VALIDATE y EXECUTE lo usan a través de persistencia.repositorio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

# Margen bajo los 65536 bytes del CHECK: el tamaño se mide con el mismo formato que
# jsonb::text (separadores ", " y ": "), pero jsonb puede escapar distinto algunos
# caracteres de control.
TOPE_BYTES = 60_000
LARGO_TEXTO = 4_096
LARGO_ESENCIAL = 1_024
MARCA_RECORTE = "…[recortado]"
CLAVE_RECORTE = "kronos_recorte"

CAMPOS_ESENCIALES: tuple[tuple[str, ...], ...] = (
    ("id",),
    ("timestamp",),
    ("rule", "id"),
    ("rule", "level"),
    ("rule", "description"),
    ("rule", "groups"),
    ("agent", "id"),
    ("agent", "name"),
    ("agent", "ip"),
    ("data", "srcip"),
    ("data", "dstip"),
    ("data", "srcuser"),
    ("data", "dstuser"),
    ("data", "audit", "pid"),
    ("data", "audit", "exe"),
    ("data", "win", "eventdata", "ipAddress"),
    ("data", "win", "eventdata", "targetUserName"),
    ("data", "win", "eventdata", "subjectUserName"),
    ("data", "win", "eventdata", "processId"),
    ("data", "win", "eventdata", "image"),
    ("data", "win", "eventdata", "hashes"),
    ("data", "win", "eventdata", "serviceName"),
    ("data", "win", "eventdata", "destinationIp"),
    ("data", "win", "eventdata", "queryName"),
    ("syscheck", "path"),
)


@dataclass(frozen=True)
class AlertaParaGuardar:
    alerta: dict[str, Any]
    bytes_original: int
    recortada: bool


def tamano(valor: Any) -> int:
    """Bytes de ``valor`` en el formato de texto de jsonb."""
    return len(
        json.dumps(valor, ensure_ascii=False, separators=(", ", ": ")).encode("utf-8")
    )


def preparar(alerta: dict[str, Any]) -> AlertaParaGuardar:
    """La alerta que se guarda, siempre bajo TOPE_BYTES. No modifica la original."""
    original = tamano(alerta)
    if original <= TOPE_BYTES:
        return AlertaParaGuardar(alerta, original, False)

    recortada = _recortar(alerta, LARGO_TEXTO)
    if tamano(recortada) <= TOPE_BYTES:
        recortada[CLAVE_RECORTE] = f"textos de más de {LARGO_TEXTO} caracteres recortados"
        return AlertaParaGuardar(recortada, original, True)

    esencial = _esenciales(alerta)
    esencial[CLAVE_RECORTE] = "alerta demasiado grande: sólo se guardaron los campos esenciales"
    if tamano(esencial) > TOPE_BYTES:  # no debería ocurrir: campos fijos y recortados
        esencial = {CLAVE_RECORTE: esencial[CLAVE_RECORTE]}
    return AlertaParaGuardar(esencial, original, True)


def _recortar(valor: Any, largo: int) -> Any:
    if isinstance(valor, dict):
        return {_texto(k, largo): _recortar(v, largo) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_recortar(v, largo) for v in valor]
    if isinstance(valor, str):
        return _texto(valor, largo)
    return valor


def _texto(texto: str, largo: int) -> str:
    return texto if len(texto) <= largo else texto[:largo] + MARCA_RECORTE


def _esenciales(alerta: dict[str, Any]) -> dict[str, Any]:
    resultado: dict[str, Any] = {}
    for ruta in CAMPOS_ESENCIALES:
        actual: Any = alerta
        for clave in ruta:
            if not isinstance(actual, dict) or clave not in actual:
                break
            actual = actual[clave]
        else:
            if isinstance(actual, list):
                actual = actual[:20]
            elif isinstance(actual, dict):
                continue
            destino = resultado
            for clave in ruta[:-1]:
                destino = destino.setdefault(clave, {})
            destino[ruta[-1]] = _recortar(actual, LARGO_ESENCIAL)
    return resultado
