"""Qué base de datos usan las pruebas de integración: nunca la real.

Estas pruebas escriben filas que no se pueden borrar (la bitácora es de sólo inserción,
ni siquiera para el superusuario). Si corrieran contra la base de SOAR-CORE-01 dejarían
tickets y eventos de prueba mezclados con los de los clientes: eso pasó con los tickets
#1, #2 y #5 de las pruebas del 16-10.

Por eso KRONOS_DSN (y KRONOS_DSN_CONSOLA) tienen que apuntar a una base cuyo nombre termine
en «_pruebas». Si apuntan a otra, el módulo de pruebas no se importa y unittest lo informa
como error, en vez de omitir las pruebas en silencio: así una variable mal puesta no pasa
por una ejecución «verde».

``tests/integracion/ejecutar.sh`` crea esa base (kronos_pruebas) con el esquema de la real,
corre las pruebas y la borra.
"""

from __future__ import annotations

import os

SUFIJO = "_pruebas"


class BaseNoEsDePruebas(RuntimeError):
    """La variable de conexión apunta a una base que no es de pruebas."""


def dsn_de_pruebas(variable: str = "KRONOS_DSN") -> str | None:
    """El valor de la variable de entorno, o None si no está puesta (pruebas omitidas).

    Lanza BaseNoEsDePruebas si apunta a una base cuyo nombre no termina en «_pruebas».
    El mensaje nombra la base, nunca la cadena de conexión (puede traer la contraseña).
    """
    dsn = os.environ.get(variable)
    if not dsn:
        return None
    from psycopg.conninfo import conninfo_to_dict

    try:
        base = conninfo_to_dict(dsn).get("dbname") or os.environ.get("PGDATABASE") or ""
    except Exception as exc:  # psycopg lanza varios tipos según el defecto
        raise BaseNoEsDePruebas(
            f"{variable} no es una cadena de conexión válida"
        ) from exc
    if not base.endswith(SUFIJO):
        raise BaseNoEsDePruebas(
            f"{variable} apunta a la base {base!r}, que no es de pruebas "
            f"(su nombre debe terminar en {SUFIJO!r}). Las pruebas de integración dejan "
            "filas que no se pueden borrar: úsese tests/integracion/ejecutar.sh"
        )
    return dsn
