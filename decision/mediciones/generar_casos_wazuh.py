"""Convierte alertas con la forma de alerts.json en casos para medir_inferencia.py.

Cada alerta de alertas_formato_wazuh.json pasa por validacion.alerta.preparar(), la misma
función que usa SOAR-VALIDATE, así que el texto de cada caso es exactamente el que vería
el modelo en producción: sin la etiqueta kronos_fX, con la descripción de la regla de
sobre sin su prefijo "Kronos Fx:" y con los campos recortados.

Uso, desde la raíz del repositorio:
    python -m decision.mediciones.generar_casos_wazuh
"""

from __future__ import annotations

import json
from pathlib import Path

from validacion.alerta import preparar

DIR = Path(__file__).resolve().parent
ENTRADA = DIR / "alertas_formato_wazuh.json"
SALIDA = DIR / "casos_formato_wazuh.json"


def generar_casos(alertas: list[dict]) -> list[dict]:
    casos = []
    for dato in alertas:
        alerta = preparar(dato["alerta"])
        if alerta is None:
            raise ValueError(f"{dato['id']}: la alerta no pasó por una regla de sobre")
        casos.append(
            {
                "id": dato["id"],
                "texto": alerta.texto,
                "familia_esperada": dato["familia_esperada"],
                "familia_candidata": alerta.familia_candidata,
                "regla": dato["alerta"]["rule"]["id"],
            }
        )
    return casos


def main() -> None:
    alertas = json.loads(ENTRADA.read_text(encoding="utf-8"))
    casos = generar_casos(alertas)
    with SALIDA.open("w", encoding="utf-8", newline="\n") as archivo:
        json.dump(casos, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")
    print(f"{len(casos)} casos escritos en {SALIDA.name}")


if __name__ == "__main__":
    main()
