"""Consulta de nivel 0 (D-72): resumen del inventario del agente por la API de Wazuh.

Implementa la interfaz ``ejecucion.consulta.Consulta``. No corre nada en el equipo: lee
lo que el agente ya reporta a Wazuh (syscollector) con el usuario de EXECUTE, que tiene
``syscollector:read`` sobre ``agent:id:*`` (política de fábrica 28, asociada el 03-11).

El resumen es corto a propósito, porque va al detalle del ticket en la bitácora:
- sistema operativo;
- cantidad de procesos y una muestra de sus nombres;
- puertos en escucha (protocolo, puerto y proceso);
- direcciones de red del equipo.

Cada parte se pide por separado. Si una falla, el resumen la marca como no disponible y
sigue con las demás; sólo si fallan todas se lanza ``ErrorConsulta``. Así un agente que
todavía no reportó, por ejemplo, sus puertos, igual deja contexto útil.
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Mapping
from typing import Any, Protocol

from ejecucion.actuador import ErrorActuador
from ejecucion.consulta import ErrorConsulta

MAX_PROCESOS = 15
MAX_PUERTOS = 20
MAX_DIRECCIONES = 10
_AGENTE = re.compile(r"^\d{3,8}$")


class LectorApi(Protocol):
    def leer(self, ruta: str) -> Any: ...


class ConsultaWazuh:
    def __init__(self, lector: LectorApi) -> None:
        self._lector = lector

    def consultar(self, agente: str) -> Mapping[str, Any]:
        if not isinstance(agente, str) or not _AGENTE.match(agente) or agente == "000":
            raise ErrorConsulta(f"agente no válido para la consulta: {agente!r}")
        partes = {
            "sistema": lambda: self._sistema(agente),
            "procesos": lambda: self._procesos(agente),
            "puertos": lambda: self._puertos(agente),
            "red": lambda: self._red(agente),
        }
        resumen: dict[str, Any] = {}
        errores: list[str] = []
        for nombre, leer in partes.items():
            try:
                resumen[nombre] = leer()
            except ErrorActuador as exc:
                resumen[nombre] = "no disponible"
                errores.append(f"{nombre}: {exc}")
        if len(errores) == len(partes):
            raise ErrorConsulta("syscollector no respondió: " + "; ".join(errores))
        resumen["fuente"] = "syscollector"
        return resumen

    # ------------------------------------------------------------------ partes

    def _items(self, agente: str, recurso: str, **parametros: Any) -> tuple[list, int]:
        consulta = urllib.parse.urlencode(parametros)
        ruta = f"/syscollector/{agente}/{recurso}" + (f"?{consulta}" if consulta else "")
        datos = self._lector.leer(ruta)
        cuerpo = datos.get("data", {}) if isinstance(datos, dict) else {}
        items = cuerpo.get("affected_items") or []
        total = cuerpo.get("total_affected_items", len(items))
        if not isinstance(items, list):
            items = []
        return [i for i in items if isinstance(i, dict)], int(total or 0)

    def _sistema(self, agente: str) -> str:
        items, _ = self._items(agente, "os")
        if not items:
            return "sin datos"
        so = items[0].get("os") or {}
        nombre = " ".join(str(so.get(k, "")) for k in ("name", "version") if so.get(k))
        return nombre or "sin datos"

    def _procesos(self, agente: str) -> dict[str, Any]:
        items, total = self._items(agente, "processes", limit=500)
        nombres = sorted({str(i["name"]) for i in items if i.get("name")})
        return {"total": total, "muestra": nombres[:MAX_PROCESOS]}

    def _puertos(self, agente: str) -> list[str]:
        items, _ = self._items(agente, "ports", limit=200)
        vistos: set[str] = set()
        for i in items:
            if str(i.get("state", "listening")).lower() not in ("listening", "listen"):
                continue
            local = i.get("local") or {}
            puerto = local.get("port")
            if puerto in (None, ""):
                continue
            proceso = i.get("process") or ""
            texto = f"{i.get('protocol', '?')}/{puerto}" + (f" ({proceso})" if proceso else "")
            vistos.add(texto)
        return sorted(vistos)[:MAX_PUERTOS]

    def _red(self, agente: str) -> list[str]:
        items, _ = self._items(agente, "netaddr", limit=50)
        direcciones = []
        for i in items:
            direccion = i.get("address")
            if not direccion:
                continue
            direcciones.append(f"{i.get('iface', '?')} {direccion}")
        return sorted(set(direcciones))[:MAX_DIRECCIONES]
