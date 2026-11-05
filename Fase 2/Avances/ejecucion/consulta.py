"""Interfaz de la consulta de nivel 0 (D-72): inventario del agente desde el servidor.

La consulta no pasa por Active Response ni corre nada en el equipo: EXECUTE le pide a
la API de Wazuh (syscollector: procesos, puertos y red) un resumen del agente, con el
usuario de permisos mínimos de EXECUTE, y lo guarda en el detalle del ticket. El ticket
termina en SUCCESS y no se avisa (D-50: el nivel 0 sólo reúne contexto).

La implementación real está en ``ejecucion.consulta_wazuh.ConsultaWazuh``, que EXECUTE
conecta en ``__main__``; las pruebas del ejecutor usan una falsa.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class ErrorConsulta(RuntimeError):
    """La API no respondió o la respuesta no sirve. EXECUTE deja el ticket en FAILED
    con CONSULTA_FALLIDA, sin reintento."""


class Consulta(Protocol):
    def consultar(self, agente: str) -> Mapping[str, Any]:
        """Resumen corto del inventario del agente (no el inventario completo), apto
        para la bitácora: sin secretos. Si falla, lanza ErrorConsulta."""
        ...
