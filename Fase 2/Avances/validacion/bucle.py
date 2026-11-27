"""Bucle de lectura de SOAR-VALIDATE: leer, contar las llegadas y procesar de a una.

Antes (hallazgo H2 de la prueba integral del 03-11) el servicio leía un lote de
alerts.json y no volvía a leer hasta procesarlo entero. Cada alerta pasa por el modelo
(13 a 70 s), así que lo que llegaba mientras tanto quedaba sin leer y sin contar: la
ráfaga de E6 llegó en 16 s, la primera lectura alcanzó a ver 13 de las 40 alertas y las
otras 27 recién se contaron 4 minutos después, al terminar el lote. El cortacircuito se
abrió tarde y 13 alertas pasaron por la IA.

Ahora, antes de cada alerta, se vuelve a leer el archivo y lo nuevo se anota como
llegada (``Validador.anotar_llegadas``) y se pone a la cola. Así el disparo del
cortacircuito ve la ráfaga con, a lo más, una decisión de retraso.

La posición de lectura se guarda sólo cuando la cola queda vacía: la posición del lector
incluye lo leído y aún no procesado, y si el servicio se cae con alertas en la cola, al
volver se releen desde la última posición guardada (las que ya tenían ticket se omiten).

Este módulo no importa persistencia ni psycopg: recibe el lector y el validador.
"""

from __future__ import annotations

import logging
from collections import Counter, deque
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

registro = logging.getLogger("soar-validate")


class Lector(Protocol):
    def leer(self) -> list[dict]: ...

    @property
    def posicion(self) -> Any: ...


class Procesador(Protocol):
    def anotar_llegadas(self, tenant_id: int, alertas: Sequence[Mapping]) -> int: ...

    def procesar(self, tenant_id: int, alerta_wazuh: dict) -> Any: ...


class Bucle:
    def __init__(
        self,
        lector: Lector,
        validador: Procesador,
        inquilino: int,
        guardar_posicion: Callable[[Any], None] | None = None,
    ) -> None:
        self._lector = lector
        self._validador = validador
        self._inquilino = inquilino
        self._guardar_posicion = guardar_posicion
        self._cola: deque[dict] = deque()
        self._resumen: Counter[str] = Counter()
        self._leidas = 0

    @property
    def pendientes(self) -> int:
        return len(self._cola)

    def recoger(self) -> int:
        """Lee lo nuevo de alerts.json, lo anota como llegada y lo pone a la cola."""
        nuevas = self._lector.leer()
        if nuevas:
            # Se cuentan antes de procesar ninguna: el cortacircuito mide las que llegan.
            self._validador.anotar_llegadas(self._inquilino, nuevas)
            self._cola.extend(nuevas)
            self._leidas += len(nuevas)
        return len(nuevas)

    def vuelta(self) -> bool:
        """Lee lo nuevo y procesa a lo más una alerta. Devuelve True si quedan en la cola."""
        self.recoger()
        if self._cola:
            alerta = self._cola.popleft()
            try:
                resultado = self._validador.procesar(self._inquilino, alerta)
            except Exception:  # noqa: BLE001 - una alerta con error no detiene a las demás
                registro.exception("error al procesar la alerta %s", alerta.get("id"))
                self._resumen["error"] += 1
            else:
                self._resumen[resultado.motivo or resultado.destino.value] += 1
        if not self._cola and self._leidas:
            self._cerrar_tanda()
        return bool(self._cola)

    def _cerrar_tanda(self) -> None:
        """Con la cola vacía: deja el resumen en el registro y guarda la posición."""
        registro.info("lote de %d alertas: %s", self._leidas, dict(self._resumen))
        self._leidas = 0
        self._resumen = Counter()
        if self._guardar_posicion is not None:
            try:
                self._guardar_posicion(self._lector.posicion)
            except OSError:
                registro.exception("no se pudo guardar la posición de lectura")
