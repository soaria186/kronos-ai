"""Servicio SOAR-NOTIFY: ``python -m notificacion``.

Alterna dos tareas: envía los avisos pendientes de cada inquilino y atiende las
respuestas del equipo en Telegram (consulta larga, que hace de pausa entre ciclos).

Variables de entorno:
    KRONOS_DSN, KRONOS_DB_CLAVE_ARCHIVO, KRONOS_INQUILINOS   como en SOAR-EXECUTE
    KRONOS_TELEGRAM_TOKEN_ARCHIVO   archivo con el token del bot
    KRONOS_TELEGRAM_CHAT            identificador del chat del equipo
    KRONOS_TELEGRAM_EQUIPO          cuentas que pueden aprobar: «id:nombre,id:nombre»
    KRONOS_ESPERA_SEGUNDOS          espera de la consulta larga (por omisión, 20)
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from psycopg.conninfo import make_conninfo

from notificacion.avisos import Avisador
from notificacion.respuestas import Atendedor
from notificacion.telegram import ClienteTelegram, ErrorTelegram
from persistencia.repositorio import ACTOR_NOTIFY, EstadoInvalido, Repositorio

registro = logging.getLogger("soar-notify")


def leer_equipo(texto: str) -> dict[int, str]:
    equipo: dict[int, str] = {}
    for parte in texto.split(","):
        if not parte.strip():
            continue
        ident, _, nombre = parte.partition(":")
        if not ident.strip().isdigit() or not nombre.strip():
            raise ValueError("KRONOS_TELEGRAM_EQUIPO debe ser «id:nombre,id:nombre»")
        equipo[int(ident)] = nombre.strip()
    if not equipo:
        raise ValueError("KRONOS_TELEGRAM_EQUIPO está vacío")
    return equipo


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
        inquilinos = [
            int(t) for t in os.environ["KRONOS_INQUILINOS"].split(",") if t.strip()
        ]
        token = (
            Path(os.environ["KRONOS_TELEGRAM_TOKEN_ARCHIVO"])
            .read_text(encoding="utf-8")
            .strip()
        )
        chat = int(os.environ["KRONOS_TELEGRAM_CHAT"])
        equipo = leer_equipo(os.environ["KRONOS_TELEGRAM_EQUIPO"])
        espera = int(os.environ.get("KRONOS_ESPERA_SEGUNDOS", "20"))
        if not inquilinos or any(t <= 0 for t in inquilinos):
            raise ValueError("KRONOS_INQUILINOS debe tener al menos un entero positivo")
        repo = Repositorio(dsn, actor=ACTOR_NOTIFY)
        cliente = ClienteTelegram(token)
        avisador = Avisador(repo, cliente, chat)
        atendedor = Atendedor(
            repo, cliente, chat, equipo, cliente.mi_id(), EstadoInvalido
        )
    except (KeyError, ValueError, OSError, ErrorTelegram) as exc:
        registro.error("no arranca: %s", exc)
        return 2

    registro.info(
        "en marcha para los inquilinos %s; equipo de %d cuentas",
        inquilinos,
        len(equipo),
    )
    desde = 0
    while True:
        for tenant_id in inquilinos:
            try:
                enviados = avisador.ciclo(tenant_id)
            except Exception:  # noqa: BLE001 - un inquilino con error no detiene a los demás
                registro.exception("inquilino %s: error al avisar", tenant_id)
                continue
            if enviados:
                registro.info("inquilino %s: %d avisos enviados", tenant_id, enviados)
        try:
            actualizaciones = cliente.actualizaciones(desde, espera)
        except ErrorTelegram as exc:
            registro.warning("Telegram: %s", exc)
            time.sleep(espera)  # sin consulta larga no hay pausa: se espera aquí
            continue
        for actualizacion in actualizaciones:
            desde = max(desde, actualizacion.get("update_id", 0) + 1)
            try:
                atendedor.procesar(actualizacion)
            except Exception:  # noqa: BLE001
                registro.exception("error al atender una respuesta de Telegram")


if __name__ == "__main__":
    sys.exit(main())
