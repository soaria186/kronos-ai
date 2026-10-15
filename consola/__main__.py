"""Servicio SOAR-CONSOLE: ``python -m consola``.

Variables de entorno:
    KRONOS_DSN_CONSOLA            conexión como kronos_console, SIN contraseña
    KRONOS_CONSOLA_CLAVE_ARCHIVO  archivo con la contraseña de kronos_console
    KRONOS_CONSOLA_USUARIOS       archivo de cuentas (python -m consola.usuarios)
    KRONOS_INQUILINOS             inquilinos visibles, separados por coma
    KRONOS_CONSOLA_CERTIFICADO    certificado TLS (PEM)
    KRONOS_CONSOLA_LLAVE          llave privada TLS (PEM)
    KRONOS_CONSOLA_PUERTO         puerto dentro del contenedor (8443)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import uvicorn
from psycopg.conninfo import make_conninfo

from consola.app import crear_app
from consola.datos import Datos
from consola.usuarios import cargar

registro = logging.getLogger("soar-console")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    try:
        clave = (
            Path(os.environ["KRONOS_CONSOLA_CLAVE_ARCHIVO"])
            .read_text(encoding="utf-8")
            .strip()
        )
        dsn = make_conninfo(os.environ["KRONOS_DSN_CONSOLA"], password=clave)
        cuentas = cargar(Path(os.environ["KRONOS_CONSOLA_USUARIOS"]))
        inquilinos = [
            int(t) for t in os.environ["KRONOS_INQUILINOS"].split(",") if t.strip()
        ]
        if not inquilinos or any(t <= 0 for t in inquilinos):
            raise ValueError("KRONOS_INQUILINOS debe tener al menos un entero positivo")
        certificado = os.environ["KRONOS_CONSOLA_CERTIFICADO"]
        llave = os.environ["KRONOS_CONSOLA_LLAVE"]
        puerto = int(os.environ.get("KRONOS_CONSOLA_PUERTO", "8443"))
    except (KeyError, ValueError, OSError) as exc:
        motivo = (
            f"falta la variable {exc.args[0]}" if isinstance(exc, KeyError) else exc
        )
        registro.error("no arranca: %s", motivo)
        return 2

    registro.info("en marcha: %d cuentas, inquilinos %s", len(cuentas), inquilinos)
    uvicorn.run(
        crear_app(Datos(dsn), cuentas, inquilinos),
        host="0.0.0.0",
        port=puerto,
        ssl_certfile=certificado,
        ssl_keyfile=llave,
        server_header=False,
        proxy_headers=False,
        access_log=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
