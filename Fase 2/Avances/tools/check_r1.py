"""Chequeo de la regla R1: el código de decision/ no puede depender de la capa de efectos.

Falla si algún archivo Python dentro de decision/ importa ejecucion, persistencia o
conectores, ya sea con "import x", "from x import y", "from x.y import z", imports
relativos que suban hasta esos paquetes, o imports dinámicos con un nombre literal
(__import__("x") / importlib.import_module("x")).

Uso:
    python tools/check_r1.py [raíz del repositorio]

Código de salida: 0 si no hay violaciones, 1 si las hay o si algún archivo no se
puede analizar.
"""

from __future__ import annotations

import ast
import os
import sys
from collections.abc import Iterator
from pathlib import Path

PAQUETE_AISLADO = "decision"
PAQUETES_PROHIBIDOS = frozenset({"ejecucion", "persistencia", "conectores"})
FUNCIONES_IMPORT_DINAMICO = frozenset({"__import__", "import_module"})


def es_prohibido(modulo: str) -> bool:
    return modulo.split(".", 1)[0] in PAQUETES_PROHIBIDOS


def resolver_relativo(
    archivo: Path, raiz: Path, modulo: str | None, nivel: int
) -> str | None:
    """Convierte "from ..x import y" en el nombre absoluto del módulo, o None si sale del repo."""
    paquete = list(archivo.relative_to(raiz).parent.parts)
    subir = nivel - 1
    if subir > len(paquete):
        return None
    base = paquete[: len(paquete) - subir]
    if modulo:
        base.extend(modulo.split("."))
    return ".".join(base)


def nombre_funcion(llamada: ast.Call) -> str | None:
    if isinstance(llamada.func, ast.Name):
        return llamada.func.id
    if isinstance(llamada.func, ast.Attribute):
        return llamada.func.attr
    return None


def modulos_importados(
    arbol: ast.AST, archivo: Path, raiz: Path
) -> Iterator[tuple[int, str]]:
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                yield nodo.lineno, alias.name
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                modulo = resolver_relativo(archivo, raiz, nodo.module, nodo.level)
                if modulo is None:
                    continue
            else:
                modulo = nodo.module or ""
            if modulo:
                yield nodo.lineno, modulo
            else:
                # "from .. import persistencia" resuelto a la raíz: cada nombre es un paquete.
                for alias in nodo.names:
                    yield nodo.lineno, alias.name
        elif (
            isinstance(nodo, ast.Call)
            and nombre_funcion(nodo) in FUNCIONES_IMPORT_DINAMICO
            and nodo.args
            and isinstance(nodo.args[0], ast.Constant)
            and isinstance(nodo.args[0].value, str)
        ):
            yield nodo.lineno, nodo.args[0].value


def reportar(archivo: str, linea: int, mensaje: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::error file={archivo},line={linea},title=R1::{mensaje}")
    print(f"{archivo}:{linea}: {mensaje}")


def main(argv: list[str]) -> int:
    raiz = (
        Path(argv[1]).resolve()
        if len(argv) > 1
        else Path(__file__).resolve().parent.parent
    )
    carpeta = raiz / PAQUETE_AISLADO
    if not carpeta.is_dir():
        print(f"R1: no existe {PAQUETE_AISLADO}/, nada que revisar.")
        return 0

    archivos = sorted(p for patron in ("*.py", "*.pyi") for p in carpeta.rglob(patron))
    errores = 0
    for archivo in archivos:
        ruta = archivo.relative_to(raiz).as_posix()
        try:
            arbol = ast.parse(archivo.read_bytes(), filename=ruta)
        except (SyntaxError, ValueError) as exc:
            reportar(
                ruta, getattr(exc, "lineno", None) or 1, f"no se pudo analizar: {exc}"
            )
            errores += 1
            continue
        for linea, modulo in modulos_importados(arbol, archivo, raiz):
            if es_prohibido(modulo):
                reportar(
                    ruta, linea, f"{PAQUETE_AISLADO}/ no puede importar '{modulo}' (R1)"
                )
                errores += 1

    if errores:
        print(
            f"R1: FALLA, {errores} problema(s) en {len(archivos)} archivo(s) de {PAQUETE_AISLADO}/."
        )
        return 1
    print(f"R1: OK, {len(archivos)} archivo(s) revisado(s) en {PAQUETE_AISLADO}/.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
