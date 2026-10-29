"""Servicio SOAR-EXECUTE: ``python -m ejecucion``.

Cada INTERVALO segundos corre un ciclo del ejecutor por cada inquilino configurado.

Variables de entorno:
    KRONOS_DSN                  conexión a SOAR-AUDIT como kronos_worker, SIN contraseña
    KRONOS_DB_CLAVE_ARCHIVO     archivo con la contraseña de kronos_worker (secreto de Docker)
    KRONOS_INQUILINOS           identificadores separados por coma, por ejemplo «1»
    KRONOS_INTERVALO_SEGUNDOS   pausa entre ciclos (por omisión, 10)
    KRONOS_AGENTES_SO           sistema operativo de cada agente, «001:linux,002:windows»
                                (opcional; si un agente no está, se deduce de la alerta)
    KRONOS_WAZUH_*              ver ejecucion/actuador_wazuh.py

Un error en un inquilino se registra y no detiene a los demás. Si falta la
configuración, el catálogo no es válido o el actuador no se puede crear, el servicio
no arranca.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from psycopg.conninfo import make_conninfo

from ejecucion.actuador_wazuh import ActuadorWazuh
from ejecucion.ejecutor import Ejecutor
from ejecucion.medidas import cargar_actuadores, cargar_medidas
from ejecucion.ordenes import leer_mapa_agentes
from persistencia.repositorio import ACTOR_EXECUTE, Repositorio

registro = logging.getLogger("soar-execute")


def _inquilinos(texto: str) -> list[int]:
    ids = [int(t) for t in texto.split(",") if t.strip()]
    if not ids or any(i <= 0 for i in ids):
        raise ValueError("KRONOS_INQUILINOS debe tener al menos un entero positivo")
    return ids


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    try:
        clave = (
            Path(os.environ["KRONOS_DB_CLAVE_ARCHIVO"])
            .read_text(encoding="utf-8")
            .strip()
        )
        dsn = make_conninfo(os.environ["KRONOS_DSN"], password=clave)
        inquilinos = _inquilinos(os.environ["KRONOS_INQUILINOS"])
        intervalo = float(os.environ.get("KRONOS_INTERVALO_SEGUNDOS", "10"))
        agentes_so = leer_mapa_agentes(os.environ.get("KRONOS_AGENTES_SO", ""))
        ejecutor = Ejecutor(
            Repositorio(dsn, actor=ACTOR_EXECUTE),
            ActuadorWazuh.desde_entorno(),
            cargar_medidas(),
            cargar_actuadores(),
            agentes_so,
        )
    except (KeyError, ValueError, OSError) as exc:
        motivo = (
            f"falta la variable {exc.args[0]}" if isinstance(exc, KeyError) else exc
        )
        registro.error("no arranca: %s", motivo)
        return 2

    registro.info(
        "en marcha para los inquilinos %s, cada %.0f s", inquilinos, intervalo
    )
    if agentes_so:
        registro.info("sistema operativo por agente: %s", agentes_so)
    else:
        registro.warning(
            "KRONOS_AGENTES_SO vacío: el sistema operativo se deduce de cada alerta"
        )
    while True:
        for tenant_id in inquilinos:
            try:
                resumen = ejecutor.ciclo(tenant_id)
            except Exception:  # noqa: BLE001 - un inquilino con error no detiene a los demás
                registro.exception("inquilino %s: error en el ciclo", tenant_id)
                continue
            if any(vars(resumen).values()):
                registro.info("inquilino %s: %s", tenant_id, vars(resumen))
        time.sleep(intervalo)


if __name__ == "__main__":
    sys.exit(main())
