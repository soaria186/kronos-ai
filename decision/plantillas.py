"""Carga de los prompts de los pasos 1 y 2 y del catálogo de playbooks.

Los prompts viven en decision/prompts/. El de paso 2 trae al principio un bloque con el
catálogo KRO-CAT-01 (generado con decision/catalogo/generar_prompt.py) del que salen
{{familia}} y {{condiciones}}; ese bloque no se envía al modelo. En los dos prompts la parte fija va
al inicio y {{alerta}} al final, para que el prefijo pueda reutilizarse en la caché.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from validacion.contrato import FAMILIAS

DIR_PROMPTS = Path(__file__).resolve().parent / "prompts"
SEPARADOR_CATALOGO = "=== CATALOGO ==="
SEPARADOR_PLANTILLA = "=== PLANTILLA ==="

# Ámbito de la IP de origen, calculado por VALIDATE con las redes internas del cliente
# (nunca sale del texto de la alerta). Se agrega al final de las condiciones del paso 2;
# sin ámbito el prompt queda idéntico al que se midió.
NOTA_AMBITO = {
    "interna": (
        "ORIGEN DE LA ALERTA (lo calculó Kronos con las redes de la organización; no "
        "viene del texto de la alerta): la IP de origen es INTERNA, de la propia "
        "organización. No elijas un playbook cuya condición hable de una dirección EXTERNA."
    ),
    "externa": (
        "ORIGEN DE LA ALERTA (lo calculó Kronos con las redes de la organización; no "
        "viene del texto de la alerta): la IP de origen es EXTERNA a la organización. "
        "No elijas un playbook cuya condición hable de la dirección de OTRO equipo de la "
        "organización."
    ),
}

_MARCADOR = re.compile(r"\{\{(\w+)\}\}")
_FAMILIA = re.compile(r"^\[(F[1-6])\]\s+(\S.*)$")
_PLAYBOOK = re.compile(r"^(PB-(F[1-6])-\d{2})\s*\|\s*([^|]+?)\s*\|\s*(\S.*)$")


class PlantillaInvalida(ValueError):
    """Un archivo de prompts no tiene el formato esperado."""


@dataclass(frozen=True)
class Familia:
    nombre: str
    condiciones: str
    candidatos: tuple[str, ...]
    # Nombre de cada candidato tal como lo ve el modelo.
    nombres: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Plantillas:
    paso1: str
    paso2: str
    familias: dict[str, Familia]

    @classmethod
    def cargar(cls, directorio: Path = DIR_PROMPTS) -> Plantillas:
        paso1 = (directorio / "paso1_familia.txt").read_text(encoding="utf-8")
        _validar(paso1, {"alerta"}, "paso1_familia.txt")
        texto = (directorio / "paso2_plantilla.txt").read_text(encoding="utf-8")
        catalogo, paso2 = _separar(texto)
        _validar(paso2, {"familia", "condiciones", "alerta"}, "paso2_plantilla.txt")
        return cls(paso1, paso2, _leer_catalogo(catalogo))

    def prompt_familia(self, alerta: str) -> str:
        return self.paso1.replace("{{alerta}}", alerta)

    def prompt_playbook(
        self, familia: str, alerta: str, ambito_ip: str | None = None
    ) -> str:
        """Prompt del paso 2. ``ambito_ip`` es «interna», «externa» o None (se ignora)."""
        datos = self.familias[familia]
        condiciones = datos.condiciones
        if ambito_ip in NOTA_AMBITO:
            condiciones = f"{condiciones}\n\n{NOTA_AMBITO[ambito_ip]}"
        # La alerta se sustituye la última para no reinterpretar marcadores dentro de ella.
        return (
            self.paso2.replace("{{familia}}", datos.nombre)
            .replace("{{condiciones}}", condiciones)
            .replace("{{alerta}}", alerta)
        )


def _validar(plantilla: str, marcadores: set[str], nombre: str) -> None:
    encontrados = set(_MARCADOR.findall(plantilla))
    if encontrados != marcadores:
        raise PlantillaInvalida(
            f"{nombre}: marcadores {sorted(encontrados)}, se esperaban {sorted(marcadores)}"
        )
    if not plantilla.rstrip().endswith("{{alerta}}"):
        raise PlantillaInvalida(f"{nombre}: la alerta debe ir al final del prompt")


def _separar(texto: str) -> tuple[str, str]:
    antes, hay_plantilla, plantilla = texto.partition(SEPARADOR_PLANTILLA)
    _, hay_catalogo, catalogo = antes.partition(SEPARADOR_CATALOGO)
    if not hay_plantilla or not hay_catalogo:
        raise PlantillaInvalida(
            f"paso2_plantilla.txt: se esperaba '{SEPARADOR_CATALOGO}' "
            f"seguido de '{SEPARADOR_PLANTILLA}'"
        )
    return catalogo, plantilla.lstrip("\n")


def _leer_catalogo(catalogo: str) -> dict[str, Familia]:
    nombres: dict[str, str] = {}
    playbooks: dict[str, list[tuple[str, str, str]]] = {}
    actual = None
    for numero, linea in enumerate(catalogo.splitlines(), start=1):
        linea = linea.strip()
        if linea.startswith("["):
            coincidencia = _FAMILIA.match(linea)
            if not coincidencia:
                raise PlantillaInvalida(
                    f"catálogo, línea {numero}: familia mal formada"
                )
            actual = coincidencia.group(1)
            nombres[actual] = coincidencia.group(2)
            playbooks[actual] = []
        elif linea.startswith("PB-"):
            coincidencia = _PLAYBOOK.match(linea)
            if not coincidencia or coincidencia.group(2) != actual:
                raise PlantillaInvalida(
                    f"catálogo, línea {numero}: playbook mal formado o fuera de su familia"
                )
            identificador, _, nombre, condicion = coincidencia.groups()
            playbooks[actual].append((identificador, nombre, condicion))

    familias = {}
    for familia in FAMILIAS:
        if not playbooks.get(familia):
            raise PlantillaInvalida(
                f"catálogo: la familia {familia} no tiene playbooks"
            )
        familias[familia] = Familia(
            nombre=f"{familia} - {nombres[familia]}",
            condiciones="\n".join(
                f"- {identificador} ({nombre}): {condicion}"
                for identificador, nombre, condicion in playbooks[familia]
            ),
            candidatos=tuple(
                identificador for identificador, _, _ in playbooks[familia]
            ),
            nombres={i: n for i, n, _ in playbooks[familia]},
        )
    return familias
