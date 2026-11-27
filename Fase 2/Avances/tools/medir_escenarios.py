"""Mide qué medida elige la IA en los escenarios E1 a E4 y si VALIDATE la aprobaría.

Para cada escenario arma una alerta con la forma real de Wazuh, la pasa por el ciclo
completo de VALIDATE (``Validador.procesar``: dos pasos del modelo y chequeos 2 a 6) con el
Ollama real y una base falsa en memoria, y anota qué salió. No escribe en ninguna base ni
toca ningún equipo. Cada escenario se repite varias veces para ver si la respuesta es
estable (con temperature = 0 debería serlo).

Escenarios:
  E1  fuerza bruta SSH desde una IP externa contra el servidor Linux
  E2  fuerza bruta SSH desde una IP interna
  E3  inicios de sesión fallidos en Windows (EP-WKS-01)
  E4  registro de auditoría borrado en Windows (EP-WKS-01)

Los datos son de ejemplo (IP de documentación 192.0.2.0/24, 198.51.100.0/24 y
203.0.113.0/24 y un rango privado genérico). Si hay alertas reales capturadas, se pasan
con --alertas, sin IP ni nombres reales.

Por cada repetición imprime: familia, playbook, confianza de cada paso, nivel, acción, si
la acción tiene script de Active Response en la v1.0 (actuadores_v1, según el sistema del
agente) y el resultado de VALIDATE. Al final, un resumen por escenario.

NO se ajusta el prompt con estos casos: si E3 o E4 no eligen la medida esperada, se avisa
al equipo con el resultado para decidir.

Uso (con el túnel a Ollama abierto):
    python tools/medir_escenarios.py [--url URL] [--modelo MODELO] [--repeticiones N]
        [--plazo SEGUNDOS] [--alertas ARCHIVO_JSON] [--csv ARCHIVO.csv]

Formato de --alertas: lista de objetos {"escenario": "E3", "sistema": "windows",
"esperada": "PB-F1-05", "alerta": {...alerta de Wazuh...}}.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from decision.ollama import URL_POR_DEFECTO, ClienteOllama
from decision.plantillas import Plantillas
from validacion.catalogo import RUTA_CATALOGO, cargar_catalogo
from validacion.ciclo import PLAZO_POR_OMISION, Validador
from validacion.configuracion import cargar_configuracion

COLUMNAS = (
    "escenario",
    "repeticion",
    "familia",
    "playbook",
    "confianza_paso1",
    "confianza_paso2",
    "nivel",
    "accion",
    "tiene_script",
    "resultado",
    "motivo",
    "segundos",
)


def _alerta(
    regla: str,
    nivel: int,
    descripcion: str,
    grupos: list[str],
    agente: dict[str, str],
    datos: dict[str, Any],
    ubicacion: str,
    full_log: str | None = None,
) -> dict[str, Any]:
    alerta: dict[str, Any] = {
        "timestamp": "2026-10-29T15:00:00.000+0000",
        "rule": {
            "level": nivel,
            "description": descripcion,
            "id": regla,
            "firedtimes": 1,
            "groups": grupos,
        },
        "agent": agente,
        "id": "0",
        "location": ubicacion,
        "data": datos,
    }
    if full_log:
        alerta["full_log"] = full_log
    return alerta


SERVIDOR = {"id": "001", "name": "EP-SRV-01", "ip": "192.0.2.10"}
PUESTO = {"id": "002", "name": "EP-WKS-01", "ip": "192.0.2.20"}


def escenarios_por_omision() -> list[dict[str, Any]]:
    def ssh(ip: str) -> dict[str, Any]:
        return _alerta(
            "100101",
            10,
            f"Kronos F1: fuerza bruta por SSH desde {ip}",
            ["syslog", "sshd", "kronos", "kronos_f1"],
            SERVIDOR,
            {"srcip": ip, "srcport": "51122", "dstuser": "root"},
            "/var/log/auth.log",
            f"sshd[2211]: Failed password for root from {ip} port 51122 ssh2",
        )

    return [
        {
            "escenario": "E1",
            "sistema": "linux",
            "esperada": "PB-F1-02",
            "alerta": ssh("203.0.113.50"),
        },
        {
            "escenario": "E2",
            "sistema": "linux",
            "esperada": "PB-F1-03",
            "alerta": ssh("192.168.50.20"),
        },
        {
            "escenario": "E3",
            "sistema": "windows",
            "esperada": "PB-F1-05",
            "alerta": _alerta(
                "100103",
                10,
                "Kronos F1: fallos repetidos de inicio de sesión en Windows o cuenta bloqueada",
                ["windows", "kronos", "kronos_f1"],
                PUESTO,
                {
                    "win": {
                        "system": {"eventID": "4625", "channel": "Security"},
                        "eventdata": {
                            "targetUserName": "usuario.ejemplo",
                            "ipAddress": "-",
                            "logonType": "2",
                            "status": "0xc000006d",
                            "subStatus": "0xc000006a",
                            "workstationName": "EP-WKS-01",
                        },
                    }
                },
                "EventChannel",
            ),
        },
        {
            "escenario": "E4",
            "sistema": "windows",
            "esperada": "PB-F5-04",
            "alerta": _alerta(
                "100113",
                12,
                "Kronos F5: registro de auditoría borrado",
                ["windows", "kronos", "kronos_f5"],
                PUESTO,
                {
                    "win": {
                        "system": {"eventID": "1102", "channel": "Security"},
                        "eventdata": {
                            "subjectUserName": "usuario.ejemplo",
                            "subjectDomainName": "EJEMPLO",
                        },
                    }
                },
                "EventChannel",
            ),
        },
    ]


@dataclass(frozen=True)
class DecisionRegistrada:
    familia: str | None
    playbook_id: str | None
    confianza: float | None
    nivel: int | None
    motivo: str | None = None
    detalle: str = ""
    equipo: str | None = None


class Almacen:
    """Base falsa en memoria: guarda la decisión y no limita nada."""

    def __init__(self, usos: dict[str, int]) -> None:
        self._usos = usos
        self.decisiones: list[DecisionRegistrada] = []
        self._n = 0

    def registrar_alerta(self, tenant_id, alerta_ref, titulo, severidad, detalle=None):
        self._n += 1
        return _Ticket(self._n, True)

    def agrupar_alerta(self, tenant_id, ticket_id, detalle):  # pragma: no cover
        raise AssertionError("no debería agrupar")

    def registrar_decision(self, tenant_id, ticket_id, decision):
        self.decisiones.append(decision)
        return len(self.decisiones)

    def usos(self, tenant_id, definiciones, equipo=None, playbook_id=None):
        return dict(self._usos)

    def alertas_en_ventana(self, tenant_id, ventana_minutos):
        return 0

    def cortacircuito_abierto(self, tenant_id):
        return False

    def abrir_cortacircuito(self, tenant_id, motivo):  # pragma: no cover
        return True


@dataclass(frozen=True)
class _Ticket:
    ticket_id: int
    nuevo: bool


class ModeloRegistrado:
    """Envuelve al modelo y guarda la confianza que declaró en cada paso."""

    def __init__(self, interno) -> None:
        self._interno = interno
        self.confianzas: list[float | None] = []

    def generar(self, prompt: str, esquema: dict, plazo: float) -> str:
        texto = self._interno.generar(prompt, esquema, plazo)
        try:
            self.confianzas.append(float(json.loads(texto).get("confianza")))
        except (TypeError, ValueError, json.JSONDecodeError):
            self.confianzas.append(None)
        return texto

    def nuevo_caso(self) -> None:
        self.confianzas = []


def cargar_acciones() -> dict[str, dict[str, Any]]:
    """Por playbook: acción y sistemas con script de Active Response (actuadores_v1)."""
    datos = json.loads(RUTA_CATALOGO.read_text(encoding="utf-8"))
    actuadores = datos.get("actuadores_v1", {})
    salida = {}
    for p in datos["playbooks"]:
        sistemas = [
            so for so, acciones in actuadores.items() if p["accion"] in acciones
        ]
        salida[p["id"]] = {"accion": p["accion"], "sistemas": sistemas}
    return salida


def medir(
    modelo,
    casos: list[dict[str, Any]],
    repeticiones: int,
    plazo: float,
    mostrar: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    plantillas = Plantillas.cargar()
    catalogo = cargar_catalogo()
    config = cargar_configuracion()
    acciones = cargar_acciones()
    registrado = ModeloRegistrado(modelo)
    filas: list[dict[str, Any]] = []
    for caso in casos:
        for i in range(1, repeticiones + 1):
            alerta = copy.deepcopy(caso["alerta"])
            alerta["id"] = f"{caso['escenario']}-{i}"
            almacen = Almacen({c.nombre: 0 for c in config.contadores})
            validador = Validador(
                almacen,
                registrado,
                plantillas,
                catalogo,
                config,
                DecisionRegistrada,
                plazo=plazo,
            )
            registrado.nuevo_caso()
            t0 = time.monotonic()
            resultado = validador.procesar(1, alerta)
            segundos = time.monotonic() - t0
            decision = almacen.decisiones[-1] if almacen.decisiones else None
            playbook = decision.playbook_id if decision else None
            accion = acciones.get(playbook or "", {}).get("accion")
            sistemas = acciones.get(playbook or "", {}).get("sistemas", [])
            conf = registrado.confianzas + [None, None]
            fila = {
                "escenario": caso["escenario"],
                "repeticion": i,
                "familia": decision.familia if decision else None,
                "playbook": playbook,
                "confianza_paso1": conf[0],
                "confianza_paso2": conf[1],
                "nivel": decision.nivel if decision else None,
                "accion": accion,
                "tiene_script": (
                    None if accion is None else caso["sistema"] in sistemas
                ),
                "resultado": resultado.destino.value,
                "motivo": resultado.motivo,
                "segundos": round(segundos, 1),
            }
            filas.append(fila)
            if mostrar:
                mostrar(fila)
    return filas


def resumen(filas: list[dict[str, Any]], casos: list[dict[str, Any]]) -> str:
    lineas = ["", "RESUMEN POR ESCENARIO", "-" * 21]
    for caso in casos:
        propias = [f for f in filas if f["escenario"] == caso["escenario"]]
        elegidas = Counter(f["playbook"] or f["motivo"] for f in propias)
        niveles = sorted({f["nivel"] for f in propias if f["nivel"] is not None})
        resultados = Counter(
            f["resultado"] + (f"/{f['motivo']}" if f["motivo"] else "") for f in propias
        )
        esperada = caso.get("esperada")
        aciertos = sum(1 for f in propias if f["playbook"] == esperada)
        lineas.append(
            f"{caso['escenario']}: esperada {esperada}; eligió {dict(elegidas)}; "
            f"niveles {niveles}; resultado {dict(resultados)}; "
            f"coincide con la esperada {aciertos}/{len(propias)}"
        )
    return "\n".join(lineas)


def imprimir(fila: dict[str, Any]) -> None:
    def n(v: Any) -> str:
        return "-" if v is None else str(v)

    print(
        f"{fila['escenario']} #{fila['repeticion']}: {n(fila['familia'])} "
        f"{n(fila['playbook'])} conf {n(fila['confianza_paso1'])}/{n(fila['confianza_paso2'])} "
        f"nivel {n(fila['nivel'])} {n(fila['accion'])} script={n(fila['tiene_script'])} "
        f"-> {fila['resultado']} {n(fila['motivo'])} ({fila['segundos']} s)",
        flush=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", default=URL_POR_DEFECTO)
    parser.add_argument("--modelo", default="qwen2.5:7b")
    parser.add_argument("--repeticiones", type=int, default=5)
    parser.add_argument("--plazo", type=float, default=PLAZO_POR_OMISION)
    parser.add_argument(
        "--alertas", type=Path, help="alertas reales (sin IP ni nombres)"
    )
    parser.add_argument("--csv", type=Path, help="guarda las filas en este CSV")
    args = parser.parse_args(argv)
    if args.repeticiones < 1:
        parser.error("--repeticiones debe ser al menos 1")

    casos = (
        json.loads(args.alertas.read_text(encoding="utf-8"))
        if args.alertas
        else escenarios_por_omision()
    )
    modelo = ClienteOllama(args.modelo, args.url)
    print(
        f"Modelo {args.modelo} en {args.url}; {args.repeticiones} repeticiones",
        flush=True,
    )
    filas = medir(modelo, casos, args.repeticiones, args.plazo, imprimir)
    print(resumen(filas, casos))
    if args.csv:
        with args.csv.open("w", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
            escritor.writeheader()
            escritor.writerows(filas)
        print(f"CSV guardado en {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
