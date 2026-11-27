"""Compara dos versiones del prompt del paso 2 sobre los 150 casos (experimento del 05-11).

Arma, a partir de decision/mediciones/casos_150, un archivo en el formato de
``tools/medir_escenarios.py --alertas`` con dos datos extra por caso: las medidas que no se
podrían aplicar porque la alerta no trae su dato (la misma regla de ARGUMENTO_FALTANTE de
EXECUTE) y si el equipo de la alerta es un servidor según su nombre. Después compara el CSV
de antes (prompt de develop) con el de después (prompt del experimento).

Uso:
    python tools/comparar_prompt.py casos ARCHIVO.json
    python tools/medir_escenarios.py --alertas ARCHIVO.json --repeticiones 1 --csv ANTES.csv    (prompt de develop)
    python tools/medir_escenarios.py --alertas ARCHIVO.json --repeticiones 1 --csv DESPUES.csv  (prompt nuevo)
    python tools/comparar_prompt.py comparar ARCHIVO.json ANTES.csv DESPUES.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ejecucion.ordenes import (
    COMANDOS,
    ArgumentoFaltante,
    OrdenInvalida,
    _deducir_sistema,
    _objetivo,
)

CASOS = RAIZ / "decision" / "mediciones" / "casos_150" / "alertas.json"
CATALOGO = RAIZ / "decision" / "catalogo" / "kro-cat-01.json"
# Sólo para medir: qué nombres de equipo se consideran servidor (la regla 5 del prompt).
_SERVIDOR = re.compile(r"srv|server|dc|db", re.IGNORECASE)


def _falta(accion: str, alerta: dict, sistema: str | None) -> bool:
    if accion not in COMANDOS or sistema is None:
        return False
    try:
        _objetivo(accion, alerta, sistema, frozenset())
    except ArgumentoFaltante:
        return True
    except OrdenInvalida:
        return False
    return False


def casos() -> list[dict]:
    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))["playbooks"]
    salida = []
    for caso in json.loads(CASOS.read_text(encoding="utf-8")):
        alerta = caso["alerta"]
        sistema = _deducir_sistema(alerta)
        equipo = str((alerta.get("agent") or {}).get("name", ""))
        salida.append({
            "escenario": caso["id"],
            "sistema": sistema or "linux",
            "esperada": caso.get("playbook_esperado") or "",
            "familia_esperada": caso["familia_esperada"],
            "servidor": bool(_SERVIDOR.search(equipo)),
            "imposibles": sorted(
                p["id"] for p in catalogo if _falta(p["accion"], alerta, sistema)
            ),
            "alerta": alerta,
        })
    return salida


def _leer(ruta: Path) -> dict[str, dict]:
    with ruta.open(encoding="utf-8", newline="") as f:
        return {fila["escenario"]: fila for fila in csv.DictReader(f)}


def comparar(lista: list[dict], antes: dict[str, dict], despues: dict[str, dict]) -> str:
    arquetipos = {
        p["id"]: set(p["arquetipos"])
        for p in json.loads(CATALOGO.read_text(encoding="utf-8"))["playbooks"]
    }
    total = len(lista)

    def pb(tabla, caso):
        return (tabla.get(caso["escenario"]) or {}).get("playbook") or ""

    def nivel(tabla, caso):
        valor = (tabla.get(caso["escenario"]) or {}).get("nivel") or ""
        return int(valor) if valor.isdigit() else None

    def imposibles(tabla):
        return sum(1 for c in lista if pb(tabla, c) in c["imposibles"])

    def tipo_errado(tabla):
        # Elige una medida sólo de puesto en un servidor, o sólo de servidor en un puesto.
        errados = 0
        for c in lista:
            tipos = arquetipos.get(pb(tabla, c), set())
            if tipos == {"servidor"} and not c["servidor"] or tipos == {"puesto"} and c["servidor"]:
                errados += 1
        return errados

    cambios = Counter(
        (pb(antes, c), pb(despues, c)) for c in lista if pb(antes, c) != pb(despues, c)
    )
    sube = sum(
        1 for c in lista
        if None not in (nivel(antes, c), nivel(despues, c)) and nivel(despues, c) > nivel(antes, c)
    )
    baja = sum(
        1 for c in lista
        if None not in (nivel(antes, c), nivel(despues, c)) and nivel(despues, c) < nivel(antes, c)
    )
    lineas = [
        f"Casos: {total}",
        f"Medida sin su dato (ARGUMENTO_FALTANTE): antes {imposibles(antes)}, después {imposibles(despues)}",
        f"Medida de puesto en servidor o al revés: antes {tipo_errado(antes)}, después {tipo_errado(despues)}",
        f"Casos con otra medida: {sum(cambios.values())} (sube de nivel {sube}, baja de nivel {baja})",
        "Cambios (antes -> después):",
    ]
    lineas += [f"  {a or '-'} -> {d or '-'}: {n}" for (a, d), n in cambios.most_common()]
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("casos")
    s.add_argument("salida", type=Path)
    c = sub.add_parser("comparar")
    c.add_argument("casos", type=Path)
    c.add_argument("antes", type=Path)
    c.add_argument("despues", type=Path)
    args = parser.parse_args(argv)
    if args.orden == "casos":
        lista = casos()
        args.salida.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(lista)} casos en {args.salida}")
        return 0
    lista = json.loads(args.casos.read_text(encoding="utf-8"))
    print(comparar(lista, _leer(args.antes), _leer(args.despues)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
