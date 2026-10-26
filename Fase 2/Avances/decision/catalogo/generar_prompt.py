"""Escribe en decision/prompts/paso2_plantilla.txt el bloque de candidatos de KRO-CAT-01.

El modelo del paso 2 elige un identificador y lo que se ejecuta es la medida que ese
identificador tiene en el catálogo. Para que no puedan separarse, el bloque de candidatos
del prompt (identificador, nombre de la medida y condición de uso) se genera desde
kro-cat-01.json y nunca se edita a mano. Una prueba falla si el archivo no coincide con lo
que este script produce.

    python decision/catalogo/generar_prompt.py

Dentro de cada familia los candidatos van de menos a más intrusivos (nivel del catálogo).
"""

from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CATALOGO = RAIZ / "decision" / "catalogo" / "kro-cat-01.json"
PROMPT = RAIZ / "decision" / "prompts" / "paso2_plantilla.txt"
SEPARADOR_CATALOGO = "=== CATALOGO ==="
SEPARADOR_PLANTILLA = "=== PLANTILLA ==="
FAMILIAS = {
    "F1": "Abuso de credenciales",
    "F2": "Proceso sospechoso en ejecución",
    "F3": "Movimiento lateral o acceso remoto",
    "F4": "Exfiltración o salida anómala",
    "F5": "Alteración de integridad o persistencia",
    "F6": "Disponibilidad del servicio",
}


def bloque(catalogo: dict) -> str:
    lineas = [
        (
            f"Candidatos tomados de {catalogo['codigo']} versión {catalogo['version']}; "
            "generado por decision/catalogo/generar_prompt.py, no se edita a mano."
        ),
        "Este bloque no se envía al modelo tal cual: de él se obtienen el nombre de la familia",
        "y los playbooks candidatos con sus condiciones de uso, que rellenan la plantilla.",
        'Formato: "[Fx] nombre de la familia" y debajo "PB-Fx-0y | nombre | condición de uso".',
        "En cada familia van de menos a más intrusivo (nivel del catálogo).",
        "",
    ]
    for familia, nombre in FAMILIAS.items():
        lineas.append(f"[{familia}] {nombre}")
        playbooks = sorted(
            (p for p in catalogo["playbooks"] if p["familia"] == familia),
            key=lambda p: (p["nivel"], p["id"]),
        )
        for p in playbooks:
            for campo in ("medida", "condicion_de_uso"):
                if "|" in p[campo] or "\n" in p[campo]:
                    raise ValueError(f"{p['id']}: {campo} con «|» o salto de línea")
            lineas.append(f"{p['id']} | {p['medida']} | {p['condicion_de_uso']}")
        lineas.append("")
    return "\n".join(lineas)


def prompt_generado(catalogo: dict, actual: str) -> str:
    """El archivo del prompt con el bloque de candidatos regenerado."""
    _, _, plantilla = actual.partition(SEPARADOR_PLANTILLA)
    return f"{SEPARADOR_CATALOGO}\n{bloque(catalogo)}\n{SEPARADOR_PLANTILLA}{plantilla}"


def main() -> None:
    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    PROMPT.write_text(
        prompt_generado(catalogo, PROMPT.read_text(encoding="utf-8")), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
