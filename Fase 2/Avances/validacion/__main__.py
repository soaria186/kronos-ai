"""Servicio SOAR-VALIDATE: ``python -m validacion``.

Lee alerts.json de Wazuh (en sólo lectura) y, por cada alerta que pasó por una regla de
sobre, corre el ciclo de validacion.ciclo. Una alerta a la vez.

Variables de entorno:
    KRONOS_DSN                  conexión a SOAR-AUDIT como kronos_worker, SIN contraseña
    KRONOS_DB_CLAVE_ARCHIVO     archivo con la contraseña de kronos_worker (secreto de Docker)
    KRONOS_INQUILINO            inquilino al que se asignan todas las alertas (un entero)
    KRONOS_ALERTAS              ruta de alerts.json (por omisión, el volumen de logs de Wazuh)
    KRONOS_POSICION_ARCHIVO     donde guardar la posición de lectura; sin él, cada arranque
                                empieza por el final de alerts.json
    KRONOS_OLLAMA_URL           servidor de Ollama (por omisión, el túnel de las mediciones)
    KRONOS_MODELO               modelo (por omisión, qwen2.5:7b)
    KRONOS_PLAZO_SEGUNDOS       plazo total de los dos pasos del modelo (por omisión, 120)
                                (al arrancar, además, se precarga el modelo en memoria)
    KRONOS_INTERVALO_SEGUNDOS   pausa entre lecturas (por omisión, 2)

Si falta la configuración, el catálogo o la configuración de VALIDATE no son válidos, o el
prompt del paso 2 no describe el catálogo KRO-CAT-01, el servicio no arranca.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

from psycopg.conninfo import make_conninfo

from conectores.alertas_wazuh import LectorAlertas
from decision.inferencia import MotorNoDisponible, TiempoExcedido
from decision.ollama import URL_POR_DEFECTO, ClienteOllama
from decision.plantillas import Plantillas
from persistencia.repositorio import ACTOR_VALIDATE, Decision, Repositorio
from validacion import posicion
from validacion.catalogo import cargar_catalogo
from validacion.ciclo import PLAZO_POR_OMISION, Validador
from validacion.configuracion import cargar_configuracion

registro = logging.getLogger("soar-validate")

ALERTAS_POR_DEFECTO = "/var/ossec/logs/alerts/alerts.json"


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
        inquilino = int(os.environ["KRONOS_INQUILINO"])
        if inquilino <= 0:
            raise ValueError("KRONOS_INQUILINO debe ser un entero positivo")
        intervalo = float(os.environ.get("KRONOS_INTERVALO_SEGUNDOS", "2"))
        modelo = ClienteOllama(
            os.environ.get("KRONOS_MODELO", "qwen2.5:7b"),
            os.environ.get("KRONOS_OLLAMA_URL", URL_POR_DEFECTO),
        )
        validador = Validador(
            Repositorio(dsn, actor=ACTOR_VALIDATE),
            modelo,
            Plantillas.cargar(),
            cargar_catalogo(),
            cargar_configuracion(),
            Decision,
            plazo=float(
                os.environ.get("KRONOS_PLAZO_SEGUNDOS", str(PLAZO_POR_OMISION))
            ),
        )
        archivo_posicion = (
            Path(os.environ["KRONOS_POSICION_ARCHIVO"])
            if "KRONOS_POSICION_ARCHIVO" in os.environ
            else None
        )
        lector = LectorAlertas(
            Path(os.environ.get("KRONOS_ALERTAS", ALERTAS_POR_DEFECTO)),
            posicion.cargar(archivo_posicion) if archivo_posicion else None,
        )
    except (KeyError, ValueError, OSError) as exc:
        motivo = (
            f"falta la variable {exc.args[0]}" if isinstance(exc, KeyError) else exc
        )
        registro.error("no arranca: %s", motivo)
        return 2

    # Con el modelo en frío una alerta tarda más de 60 s. Se carga ahora, no con la primera
    # alerta real. Si Ollama aún no responde, el servicio arranca igual: la falla segura
    # (TIEMPO_EXCEDIDO, MOTOR_INFERENCIA_NO_DISPONIBLE) ya cubre ese caso.
    try:
        registro.info("cargando el modelo en memoria")
        modelo.precalentar()
    except (MotorNoDisponible, TiempoExcedido) as exc:
        registro.warning(
            "no se pudo precargar el modelo (%s); se cargará con la primera alerta", exc
        )

    registro.info("en marcha para el inquilino %s", inquilino)
    while True:
        alertas = lector.leer()
        resumen: Counter[str] = Counter()
        for alerta in alertas:
            try:
                resultado = validador.procesar(inquilino, alerta)
            except Exception:  # noqa: BLE001 - una alerta con error no detiene a las demás
                registro.exception("error al procesar la alerta %s", alerta.get("id"))
                resumen["error"] += 1
                continue
            resumen[resultado.motivo or resultado.destino.value] += 1
        if alertas:
            registro.info("lote de %d alertas: %s", len(alertas), dict(resumen))
            if archivo_posicion:
                try:
                    posicion.guardar(archivo_posicion, lector.posicion)
                except OSError:
                    registro.exception("no se pudo guardar la posición de lectura")
        time.sleep(intervalo)


if __name__ == "__main__":
    sys.exit(main())
