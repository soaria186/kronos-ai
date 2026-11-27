"""Mide el efecto de no aceptar en el paso 2 las medidas cuyo dato no viene en la alerta.

Sólo cambian los casos de casos_150 en los que VALIDATE quita al menos un candidato de la
familia esperada y deja alguno (en los demás el esquema es idéntico y, con temperature = 0,
también la respuesta). Este script arma ese subconjunto en el formato de
``tools/medir_escenarios.py --alertas`` y después compara los dos CSV, el de antes
(``develop`` sin el cambio) y el de después: cuántas veces el modelo eligió una medida que
EXECUTE no podría aplicar, y qué eligió en su lugar.

Uso:
    python tools/medir_sin_datos.py subconjunto ARCHIVO.json
    python tools/medir_escenarios.py --alertas ARCHIVO.json --repeticiones 1 --csv ANTES.csv   (en develop)
    python tools/medir_escenarios.py --alertas ARCHIVO.json --repeticiones 1 --csv DESPUES.csv (con el cambio)
    python tools/medir_sin_datos.py comparar ARCHIVO.json ANTES.csv DESPUES.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ejecucion.ordenes import _deducir_sistema, falta_argumento
from validacion.catalogo import cargar_catalogo

CASOS = RAIZ / "decision" / "mediciones" / "casos_150" / "alertas.json"


def subconjunto() -> list[dict]:
    catalogo = cargar_catalogo()
    salida = []
    for caso in json.loads(CASOS.read_text(encoding="utf-8")):
        alerta = caso["alerta"]
        familia = {p.id for p in catalogo.playbooks.values() if p.familia == caso["familia_esperada"]}
        fuera = {
            p.id for p in catalogo.playbooks.values()
            if p.id in familia and p.accion and falta_argumento(p.accion, alerta)
        }
        if fuera and familia - fuera:
            salida.append({
                "escenario": caso["id"],
                "sistema": _deducir_sistema(alerta) or "linux",
                "esperada": caso["playbook_esperado"],
                "excluidos": sorted(fuera),
                "alerta": alerta,
            })
    return salida


def leer(ruta: Path) -> dict[str, str]:
    with ruta.open(encoding="utf-8", newline="") as f:
        return {fila["escenario"]: fila["playbook"] for fila in csv.DictReader(f)}


def comparar(casos: list[dict], antes: dict[str, str], despues: dict[str, str]) -> str:
    total = len(casos)
    acierto_antes = sum(1 for c in casos if antes.get(c["escenario"]) == c["esperada"])
    acierto_despues = sum(1 for c in casos if despues.get(c["escenario"]) == c["esperada"])
    imposibles = sum(1 for c in casos if antes.get(c["escenario"]) in c["excluidos"])
    cambios = Counter(
        (antes.get(c["escenario"]), despues.get(c["escenario"]))
        for c in casos
        if antes.get(c["escenario"]) != despues.get(c["escenario"])
    )
    lineas = [f"Casos afectados: {total}"]
    if any(c["esperada"] for c in casos):  # casos_150 todavía no trae el esperado
        lineas.append(
            f"Coinciden con el esperado: antes {acierto_antes}/{total}, después {acierto_despues}/{total}"
        )
    sin_dato = sum(1 for c in casos if despues.get(c["escenario"]) in c["excluidos"])
    lineas += [
        f"Antes eligió una medida sin su dato (ARGUMENTO_FALTANTE): {imposibles}/{total}",
        f"Después: {sin_dato}/{total} (debe ser 0)",
        "Cambios (antes -> después):",
    ]
    lineas += [f"  {a} -> {d}: {n}" for (a, d), n in cambios.most_common()]
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("subconjunto")
    s.add_argument("salida", type=Path)
    c = sub.add_parser("comparar")
    c.add_argument("casos", type=Path)
    c.add_argument("antes", type=Path)
    c.add_argument("despues", type=Path)
    args = parser.parse_args(argv)
    if args.orden == "subconjunto":
        casos = subconjunto()
        args.salida.write_text(json.dumps(casos, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(casos)} casos en {args.salida}")
        return 0
    casos = json.loads(args.casos.read_text(encoding="utf-8"))
    print(comparar(casos, leer(args.antes), leer(args.despues)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
