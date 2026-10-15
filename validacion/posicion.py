"""Dónde quedó VALIDATE en alerts.json, guardado en un archivo para retomar tras un reinicio.

Se guarda después de procesar cada lote. Si el servicio se cae a la mitad de un lote, al
volver relee el lote entero: las alertas que ya tenían ticket se omiten (UNIQUE
(tenant_id, alerta_ref)), así que releer no duplica nada. Un archivo ausente o ilegible
equivale a no tener posición: el lector empieza por el final de alerts.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from conectores.alertas_wazuh import Posicion


def cargar(ruta: Path) -> Posicion | None:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        inodo, desplazamiento = datos["inodo"], datos["desplazamiento"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    for valor in (inodo, desplazamiento):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
            return None
    return Posicion(inodo, desplazamiento)


def guardar(ruta: Path, posicion: Posicion) -> None:
    """Escribe en un archivo temporal y lo renombra: nunca queda a medias."""
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(
        json.dumps(
            {"inodo": posicion.inodo, "desplazamiento": posicion.desplazamiento}
        ),
        encoding="utf-8",
    )
    os.replace(temporal, ruta)
