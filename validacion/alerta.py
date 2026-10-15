"""Preparación de una alerta de Wazuh para SOAR-VALIDATE y para el modelo.

De cada alerta de alerts.json se obtiene:

- la familia candidata, de la etiqueta kronos_f1 a kronos_f6 que pone la regla de sobre
  en rule.groups. Una alerta sin etiqueta no la procesa VALIDATE;
- la severidad, de rule.level;
- el texto que verá el modelo, SIN la etiqueta de familia: se quitan rule.groups y el
  prefijo "Kronos Fx:" de la descripción. Si el modelo viera la familia candidata la
  copiaría, y el chequeo de coincidencia dejaría de comparar dos opiniones
  independientes;
- los identificadores del objetivo (equipo, IP, cuentas, programa, servicio, destino)
  para la lista de exclusión.

El texto se arma con valores recortados (LARGO_CAMPO por campo y LARGO_TEXTO en total) y
sin saltos de línea. Los valores los controla el atacante: un campo enorme dejaba al 7B
en más de 100 s (caso INY-10 del 14-10-2026), y un salto de línea permite simular
secciones del prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from validacion.contrato import FAMILIAS

LARGO_CAMPO = 300
LARGO_TEXTO = 2000
MARCA_RECORTE = "…[recortado]"

_ETIQUETA = re.compile(r"^kronos_f([1-6])$")
_PREFIJO_KRONOS = re.compile(r"^\s*Kronos F[1-6]\s*:\s*", re.IGNORECASE)
_ESPACIOS = re.compile(r"\s+")

# Campos de la alerta que identifican sobre qué se actuaría, por categoría de exclusión.
_OBJETIVO = {
    "equipo": (("agent", "name"),),
    "ip": (
        ("agent", "ip"),
        ("data", "srcip"),
        ("data", "dstip"),
        ("data", "win", "eventdata", "ipAddress"),
    ),
    "cuenta": (
        ("syscheck", "audit", "user", "name"),
        ("data", "srcuser"),
        ("data", "dstuser"),
        ("data", "win", "eventdata", "targetUserName"),
        ("data", "win", "eventdata", "subjectUserName"),
        ("data", "win", "eventdata", "user"),
    ),
    "programa": (
        ("syscheck", "path"),
        ("data", "win", "eventdata", "image"),
        ("data", "audit", "exe"),
    ),
    "servicio": (("data", "win", "eventdata", "serviceName"),),
    "destino": (("data", "dsthost"), ("data", "url")),
}


class AlertaInvalida(ValueError):
    """La alerta no trae los campos mínimos o trae una etiqueta de familia ambigua."""


@dataclass(frozen=True)
class AlertaKronos:
    id: str
    familia_candidata: str
    severidad: int
    texto: str
    objetivo: dict[str, tuple[str, ...]]


def preparar(alerta: dict) -> AlertaKronos | None:
    """Devuelve la alerta preparada, o None si no pasó por una regla de sobre."""
    regla = alerta.get("rule")
    if not isinstance(regla, dict):
        raise AlertaInvalida("la alerta no trae rule")
    etiquetas = {
        f"F{m.group(1)}"
        for grupo in regla.get("groups") or []
        if isinstance(grupo, str) and (m := _ETIQUETA.match(grupo))
    }
    if not etiquetas:
        return None
    if len(etiquetas) > 1:
        raise AlertaInvalida(f"varias familias candidatas: {sorted(etiquetas)}")
    familia = etiquetas.pop()
    assert familia in FAMILIAS

    identificador = alerta.get("id")
    if not isinstance(identificador, str) or not identificador:
        raise AlertaInvalida("la alerta no trae id")
    severidad = regla.get("level")
    if isinstance(severidad, bool) or not isinstance(severidad, int):
        raise AlertaInvalida("rule.level no es un entero")
    if not 0 <= severidad <= 15:
        raise AlertaInvalida(f"rule.level fuera de 0 a 15: {severidad}")

    return AlertaKronos(
        id=identificador,
        familia_candidata=familia,
        severidad=severidad,
        texto=_texto_para_el_modelo(alerta),
        objetivo=_objetivo(alerta),
    )


def _limpio(valor: object, largo: int = LARGO_CAMPO) -> str:
    texto = _ESPACIOS.sub(" ", str(valor)).strip()
    if len(texto) > largo:
        texto = texto[:largo] + MARCA_RECORTE
    return texto


def _aplanar(datos: dict, prefijo: str) -> list[tuple[str, object]]:
    pares = []
    for clave, valor in datos.items():
        nombre = f"{prefijo}.{clave}"
        if isinstance(valor, dict):
            pares += _aplanar(valor, nombre)
        elif isinstance(valor, list):
            pares.append((nombre, ", ".join(str(v) for v in valor)))
        elif valor not in (None, ""):
            pares.append((nombre, valor))
    return pares


def _texto_para_el_modelo(alerta: dict) -> str:
    regla = alerta["rule"]
    descripcion = _PREFIJO_KRONOS.sub("", str(regla.get("description", "")))
    agente = alerta.get("agent") or {}
    partes = [
        (
            f"Rule: {_limpio(regla.get('id', ''))} (level {regla['level']}) -> "
            f"'{_limpio(descripcion)}'"
        ),
        f"Agent: {_limpio(agente.get('name', ''))} ({_limpio(agente.get('ip', ''))})",
    ]
    if alerta.get("location"):
        partes.append(f"Location: {_limpio(alerta['location'])}")
    # data: campos decodificados; syscheck: integridad de archivos (ruta, diff, quién).
    for seccion in ("data", "syscheck"):
        datos = alerta.get(seccion)
        if isinstance(datos, dict):
            partes += [
                f"{clave}: {_limpio(valor)}"
                for clave, valor in _aplanar(datos, seccion)
            ]
    if alerta.get("full_log"):
        partes.append(f"full_log: {_limpio(alerta['full_log'])}")
    return _limpio(" | ".join(partes), LARGO_TEXTO)


def _valor(alerta: dict, ruta: tuple[str, ...]) -> str | None:
    actual: object = alerta
    for clave in ruta:
        if not isinstance(actual, dict):
            return None
        actual = actual.get(clave)
    if isinstance(actual, str) and actual.strip():
        return actual.strip()
    return None


def _objetivo(alerta: dict) -> dict[str, tuple[str, ...]]:
    objetivo = {}
    for categoria, rutas in _OBJETIVO.items():
        valores = tuple(dict.fromkeys(v for r in rutas if (v := _valor(alerta, r))))
        if valores:
            objetivo[categoria] = valores
    return objetivo
