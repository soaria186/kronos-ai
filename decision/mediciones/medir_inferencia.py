"""Mide la latencia y la calidad de la inferencia en dos pasos contra la API de Ollama.

Paso 1: clasifica la alerta en una familia (F1-F6) con prompts/paso1_familia.txt.
Paso 2: elige un playbook de esa familia con prompts/paso2_plantilla.txt.

Cada caso de casos_prueba.json se mide en dos condiciones, que quedan en filas separadas
del CSV e identificadas por la columna "condicion":
  - frio:  se antepone un identificador aleatorio al prompt, así que Ollama no puede
           reutilizar ningún prefijo que tenga en caché;
  - tibio: el prompt real, con la parte fija al inicio y la alerta al final, cuyo prefijo
           fijo sí puede reutilizarse entre llamadas.
Las condiciones se ejecutan en bloques (primero todos los casos en frío y después todos
en tibio), para que las llamadas en frío no desplacen de la caché el prefijo del bloque
tibio. Dentro de cada caso los pasos 1 y 2 se alternan: si el servidor mantiene un solo
hueco de caché (OLLAMA_NUM_PARALLEL=1), cada paso sustituye el prefijo del anterior y la
ventaja de la condición tibia será pequeña. Eso también es un resultado de la medición.

Todas las llamadas usan options.temperature = 0, options.num_ctx = 4096 y un esquema JSON
en el campo "format". Los tiempos son de reloj, medidos desde el cliente. Antes de medir
se hace una llamada de calentamiento que no cuenta. Si el paso 1 no devuelve un JSON
válido, el paso 2 no se ejecuta y el caso queda sin tiempo total. Las columnas
confianza_paso1 y confianza_paso2 guardan la confianza que declaró el modelo en cada paso.

El CSV se guarda en resultados/ y se escribe fila a fila, así que si la ejecución se
interrumpe se conservan los casos ya medidos. Las columnas json_valido y acierto_familia
valen 1 o 0; json_valido es 1 solo si los dos pasos devuelven un JSON que cumple el
esquema.

Solo usa la biblioteca estándar y no importa ejecucion, persistencia ni conectores (R1).

Uso:
    python decision/mediciones/medir_inferencia.py MODELO [--url URL] [--timeout SEGUNDOS]
        [--casos ARCHIVO_JSON]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import secrets
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

URL_POR_DEFECTO = "http://127.0.0.1:11435"
TIMEOUT_POR_DEFECTO = 600.0
OPCIONES = {"temperature": 0, "num_ctx": 4096}
LIMITE_TOKENS_PROMPT = 4000

FAMILIAS = ("F1", "F2", "F3", "F4", "F5", "F6")
CONDICIONES = ("frio", "tibio")

DIR_MEDICIONES = Path(__file__).resolve().parent
DIR_PROMPTS = DIR_MEDICIONES.parent / "prompts"
RUTA_PASO1 = DIR_PROMPTS / "paso1_familia.txt"
RUTA_PASO2 = DIR_PROMPTS / "paso2_plantilla.txt"
RUTA_CASOS = DIR_MEDICIONES / "casos_prueba.json"
DIR_RESULTADOS = DIR_MEDICIONES / "resultados"

SEPARADOR_CATALOGO = "=== CATALOGO PROVISIONAL ==="
SEPARADOR_PLANTILLA = "=== PLANTILLA ==="
PATRON_MARCADOR = re.compile(r"\{\{(\w+)\}\}")
PATRON_FAMILIA = re.compile(r"^\[(F[1-6])\]\s+(\S.*)$")
PATRON_PLAYBOOK = re.compile(r"^(PB-(F[1-6])-\d{2})\s*\|\s*([^|]+?)\s*\|\s*(\S.*)$")

COLUMNAS = (
    "caso",
    "modelo",
    "condicion",
    "t_paso1",
    "t_paso2",
    "t_total",
    "prompt_eval_count_paso1",
    "eval_count_paso1",
    "prompt_eval_count_paso2",
    "eval_count_paso2",
    "json_valido",
    "familia_obtenida",
    "confianza_paso1",
    "acierto_familia",
    "playbook_obtenido",
    "confianza_paso2",
)

ESQUEMA_PASO1 = {
    "type": "object",
    "properties": {
        "familia": {"type": "string", "enum": list(FAMILIAS)},
        "confianza": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["familia", "confianza"],
    "additionalProperties": False,
}

# Sin proxies: la medición debe ir directa al servidor de Ollama.
ABRIDOR = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class ErrorMedicion(Exception):
    """Error que impide seguir midiendo (servidor caído, modelo inexistente, datos mal formados)."""


@dataclass(frozen=True)
class Caso:
    id: str
    texto: str
    familia_esperada: str


@dataclass(frozen=True)
class Familia:
    nombre: str
    condiciones: str
    candidatos: tuple[str, ...]


@dataclass(frozen=True)
class Llamada:
    segundos: float
    prompt_eval_count: int | None
    eval_count: int | None
    datos: dict | None


# --- Carga de prompts y casos ---------------------------------------------------------


def validar_plantilla(plantilla: str, marcadores: set[str], ruta: Path) -> None:
    encontrados = set(PATRON_MARCADOR.findall(plantilla))
    if encontrados != marcadores:
        raise ErrorMedicion(
            f"{ruta.name}: marcadores {sorted(encontrados)}, se esperaban {sorted(marcadores)}"
        )
    if not plantilla.rstrip().endswith("{{alerta}}"):
        raise ErrorMedicion(f"{ruta.name}: la alerta debe ir al final del prompt")


def cargar_paso1() -> str:
    plantilla = RUTA_PASO1.read_text(encoding="utf-8")
    validar_plantilla(plantilla, {"alerta"}, RUTA_PASO1)
    return plantilla


def cargar_paso2() -> tuple[str, dict[str, Familia]]:
    texto = RUTA_PASO2.read_text(encoding="utf-8")
    antes, hay_plantilla, plantilla = texto.partition(SEPARADOR_PLANTILLA)
    _, hay_catalogo, catalogo = antes.partition(SEPARADOR_CATALOGO)
    if not hay_plantilla or not hay_catalogo:
        raise ErrorMedicion(
            f"{RUTA_PASO2.name}: se esperaba '{SEPARADOR_CATALOGO}' "
            f"seguido de '{SEPARADOR_PLANTILLA}'"
        )
    plantilla = plantilla.lstrip("\n")
    validar_plantilla(plantilla, {"familia", "condiciones", "alerta"}, RUTA_PASO2)

    nombres: dict[str, str] = {}
    playbooks: dict[str, list[tuple[str, str, str]]] = {}
    actual = None
    for numero, linea in enumerate(catalogo.splitlines(), start=1):
        linea = linea.strip()
        if linea.startswith("["):
            coincidencia = PATRON_FAMILIA.match(linea)
            if not coincidencia:
                raise ErrorMedicion(f"catálogo, línea {numero}: familia mal formada")
            actual = coincidencia.group(1)
            nombres[actual] = coincidencia.group(2)
            playbooks[actual] = []
        elif linea.startswith("PB-"):
            coincidencia = PATRON_PLAYBOOK.match(linea)
            if not coincidencia or coincidencia.group(2) != actual:
                raise ErrorMedicion(
                    f"catálogo, línea {numero}: playbook mal formado o fuera de su familia"
                )
            identificador, _, nombre, condicion = coincidencia.groups()
            playbooks[actual].append((identificador, nombre, condicion))

    familias = {}
    for familia in FAMILIAS:
        if not playbooks.get(familia):
            raise ErrorMedicion(f"catálogo: la familia {familia} no tiene playbooks")
        condiciones = "\n".join(
            f"- {identificador} ({nombre}): {condicion}"
            for identificador, nombre, condicion in playbooks[familia]
        )
        familias[familia] = Familia(
            nombre=f"{familia} - {nombres[familia]}",
            condiciones=condiciones,
            candidatos=tuple(
                identificador for identificador, _, _ in playbooks[familia]
            ),
        )
    return plantilla, familias


def cargar_casos(ruta: Path) -> list[Caso]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    casos = []
    for posicion, dato in enumerate(datos, start=1):
        try:
            caso = Caso(dato["id"], dato["texto"], dato["familia_esperada"])
        except (KeyError, TypeError) as exc:
            raise ErrorMedicion(f"{ruta.name}: caso {posicion} incompleto") from exc
        if caso.familia_esperada not in FAMILIAS:
            raise ErrorMedicion(f"{caso.id}: familia esperada desconocida")
        casos.append(caso)
    if len({caso.id for caso in casos}) != len(casos):
        raise ErrorMedicion(f"{ruta.name}: hay identificadores repetidos")
    return casos


def rellenar(plantilla: str, **valores: str) -> str:
    # La alerta se sustituye la última para no reinterpretar marcadores dentro de ella.
    alerta = valores.pop("alerta")
    for clave, valor in valores.items():
        plantilla = plantilla.replace("{{" + clave + "}}", valor)
    return plantilla.replace("{{alerta}}", alerta)


# --- Llamadas a Ollama ----------------------------------------------------------------


def esquema_paso2(candidatos: tuple[str, ...]) -> dict:
    return {
        "type": "object",
        "properties": {
            "playbook_id": {"type": "string", "enum": list(candidatos)},
            "confianza": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["playbook_id", "confianza"],
        "additionalProperties": False,
    }


def generar(
    url: str, modelo: str, prompt: str, esquema: dict, timeout: float
) -> tuple[dict, float]:
    cuerpo = {
        "model": modelo,
        "prompt": prompt,
        "stream": False,
        "format": esquema,
        "options": OPCIONES,
    }
    peticion = urllib.request.Request(
        url.rstrip("/") + "/api/generate",
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    inicio = time.perf_counter()
    try:
        with ABRIDOR.open(peticion, timeout=timeout) as respuesta:
            datos = json.load(respuesta)
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", errors="replace").strip()
        raise ErrorMedicion(f"Ollama respondió {exc.code}: {detalle}") from exc
    except OSError as exc:
        raise ErrorMedicion(f"no se pudo contactar con Ollama en {url}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ErrorMedicion(
            f"Ollama devolvió una respuesta que no es JSON: {exc}"
        ) from exc
    return datos, time.perf_counter() - inicio


def es_confianza(valor: object) -> bool:
    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and 0.0 <= valor <= 1.0
    )


def leer_salida(texto: str, campo: str, permitidos: tuple[str, ...]) -> dict | None:
    """Devuelve el JSON del modelo si cumple el esquema {campo, confianza}; si no, None."""
    try:
        datos = json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(datos, dict) or set(datos) != {campo, "confianza"}:
        return None
    if datos[campo] not in permitidos or not es_confianza(datos["confianza"]):
        return None
    return datos


def ejecutar_paso(
    url: str,
    modelo: str,
    prompt: str,
    esquema: dict,
    campo: str,
    permitidos: tuple[str, ...],
    frio: bool,
    timeout: float,
) -> Llamada:
    if frio:
        prompt = f"ID {secrets.token_hex(8)}\n\n{prompt}"
    respuesta, segundos = generar(url, modelo, prompt, esquema, timeout)
    return Llamada(
        segundos=segundos,
        prompt_eval_count=respuesta.get("prompt_eval_count"),
        eval_count=respuesta.get("eval_count"),
        datos=leer_salida(respuesta.get("response", ""), campo, permitidos),
    )


# --- Medición -------------------------------------------------------------------------


def segundos(valor: float | None) -> str:
    return "" if valor is None else f"{valor:.3f}"


def entero(valor: int | None) -> str:
    return "" if valor is None else str(valor)


def confianza(datos: dict | None) -> str:
    return "" if datos is None else f"{float(datos['confianza']):.2f}"


def medir_caso(
    caso: Caso,
    condicion: str,
    modelo: str,
    url: str,
    timeout: float,
    plantilla1: str,
    plantilla2: str,
    familias: dict[str, Familia],
    excesos: list[str],
) -> dict[str, str]:
    frio = condicion == "frio"
    paso1 = ejecutar_paso(
        url,
        modelo,
        rellenar(plantilla1, alerta=caso.texto),
        ESQUEMA_PASO1,
        "familia",
        FAMILIAS,
        frio,
        timeout,
    )
    familia = paso1.datos["familia"] if paso1.datos else None

    paso2 = None
    if familia is not None:
        datos_familia = familias[familia]
        paso2 = ejecutar_paso(
            url,
            modelo,
            rellenar(
                plantilla2,
                familia=datos_familia.nombre,
                condiciones=datos_familia.condiciones,
                alerta=caso.texto,
            ),
            esquema_paso2(datos_familia.candidatos),
            "playbook_id",
            datos_familia.candidatos,
            frio,
            timeout,
        )

    for nombre, llamada in (("paso1", paso1), ("paso2", paso2)):
        if llamada and (llamada.prompt_eval_count or 0) > LIMITE_TOKENS_PROMPT:
            excesos.append(
                f"{caso.id} [{condicion}] {nombre}: {llamada.prompt_eval_count} tokens"
            )

    json_valido = paso2 is not None and paso2.datos is not None
    return {
        "caso": caso.id,
        "modelo": modelo,
        "condicion": condicion,
        "t_paso1": segundos(paso1.segundos),
        "t_paso2": segundos(paso2.segundos if paso2 else None),
        "t_total": segundos(paso1.segundos + paso2.segundos if paso2 else None),
        "prompt_eval_count_paso1": entero(paso1.prompt_eval_count),
        "eval_count_paso1": entero(paso1.eval_count),
        "prompt_eval_count_paso2": entero(paso2.prompt_eval_count if paso2 else None),
        "eval_count_paso2": entero(paso2.eval_count if paso2 else None),
        "json_valido": "1" if json_valido else "0",
        "familia_obtenida": familia or "",
        "confianza_paso1": confianza(paso1.datos),
        "acierto_familia": "1" if familia == caso.familia_esperada else "0",
        "playbook_obtenido": paso2.datos["playbook_id"] if json_valido else "",
        "confianza_paso2": confianza(paso2.datos if paso2 else None),
    }


def percentil_90(valores: list[float]) -> float:
    if len(valores) == 1:
        return valores[0]
    return statistics.quantiles(valores, n=10, method="inclusive")[-1]


def porcentaje(filas: list[dict[str, str]], columna: str) -> float:
    return 100 * sum(fila[columna] == "1" for fila in filas) / len(filas)


def imprimir_resumen(
    modelo: str, filas: list[dict[str, str]], excesos: list[str]
) -> None:
    print(f"\nResumen del modelo {modelo}")
    for condicion in CONDICIONES:
        de_condicion = [fila for fila in filas if fila["condicion"] == condicion]
        if not de_condicion:
            continue
        tiempos = [float(fila["t_total"]) for fila in de_condicion if fila["t_total"]]
        if tiempos:
            tiempo = (
                f"t_total mediana {statistics.median(tiempos):.2f} s, "
                f"p90 {percentil_90(tiempos):.2f} s (n={len(tiempos)})"
            )
        else:
            tiempo = "t_total sin datos"
        print(
            f"  {condicion:<5}  {tiempo} | "
            f"JSON válido {porcentaje(de_condicion, 'json_valido'):.1f} % | "
            f"precisión paso 1 {porcentaje(de_condicion, 'acierto_familia'):.1f} % "
            f"({len(de_condicion)} casos)"
        )
    if excesos:
        print(
            f"\nADVERTENCIA: {len(excesos)} prompt(s) superan {LIMITE_TOKENS_PROMPT} tokens "
            f"con num_ctx={OPCIONES['num_ctx']}; Ollama puede haberlos truncado:"
        )
        for exceso in excesos:
            print(f"  - {exceso}")


def calentar(url: str, modelo: str, timeout: float) -> None:
    prompt = (
        f"ID {secrets.token_hex(8)}\n\n"
        'Calentamiento. Responde solo con {"familia": "F1", "confianza": 0.0}'
    )
    _, duracion = generar(url, modelo, prompt, ESQUEMA_PASO1, timeout)
    print(f"Calentamiento: {duracion:.2f} s (no cuenta)", flush=True)


def ruta_salida(modelo: str, casos: Path) -> Path:
    marca = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    nombre = re.sub(r"[^A-Za-z0-9._-]+", "_", modelo)
    prefijo = (
        "inferencia" if casos.resolve() == RUTA_CASOS else f"inferencia_{casos.stem}"
    )
    return DIR_RESULTADOS / f"{prefijo}_{nombre}_{marca}.csv"


def leer_argumentos(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mide la inferencia en dos pasos (familia y playbook) contra Ollama."
    )
    parser.add_argument("modelo", help="nombre del modelo en Ollama, p. ej. qwen2.5:7b")
    parser.add_argument(
        "--url",
        default=URL_POR_DEFECTO,
        help=f"URL base de la API de Ollama (por defecto {URL_POR_DEFECTO})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=TIMEOUT_POR_DEFECTO,
        help=f"segundos máximos por llamada (por defecto {TIMEOUT_POR_DEFECTO:.0f})",
    )
    parser.add_argument(
        "--casos",
        type=Path,
        default=RUTA_CASOS,
        help=f"archivo JSON de casos (por defecto {RUTA_CASOS.name})",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    argumentos = leer_argumentos(argv)
    modelo, url, timeout = argumentos.modelo, argumentos.url, argumentos.timeout
    filas: list[dict[str, str]] = []
    excesos: list[str] = []
    try:
        plantilla1 = cargar_paso1()
        plantilla2, familias = cargar_paso2()
        casos = cargar_casos(argumentos.casos)

        print(
            f"Modelo {modelo} en {url}: {len(casos)} casos x {len(CONDICIONES)} condiciones"
        )
        calentar(url, modelo, timeout)

        salida = ruta_salida(modelo, argumentos.casos)
        salida.parent.mkdir(parents=True, exist_ok=True)
        with salida.open("w", encoding="utf-8", newline="") as archivo:
            print(f"Resultados en {salida}", flush=True)
            escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
            escritor.writeheader()
            for condicion in CONDICIONES:
                for caso in casos:
                    fila = medir_caso(
                        caso,
                        condicion,
                        modelo,
                        url,
                        timeout,
                        plantilla1,
                        plantilla2,
                        familias,
                        excesos,
                    )
                    escritor.writerow(fila)
                    archivo.flush()
                    filas.append(fila)
                    print(
                        f"[{condicion}] {caso.id}: "
                        f"{fila['familia_obtenida'] or '-'} (esperada {caso.familia_esperada}) "
                        f"{fila['playbook_obtenido'] or '-'} "
                        f"t_total={fila['t_total'] or '-'} s",
                        flush=True,
                    )
        print(f"\nCSV completo en {salida}")
    except ErrorMedicion as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if filas:
            imprimir_resumen(modelo, filas, excesos)
        return 1
    except KeyboardInterrupt:
        print("\nInterrumpido.", file=sys.stderr)
        if filas:
            imprimir_resumen(modelo, filas, excesos)
        return 130

    imprimir_resumen(modelo, filas, excesos)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
