"""Lectura incremental de alerts.json de Wazuh, en sólo lectura.

El manager escribe una alerta por línea, en JSON, y a las 00:00 UTC rota el archivo:
lo renombra y empieza uno nuevo con el mismo nombre. SOAR-VALIDATE lo lee desde el
volumen de logs montado con :ro (ver el acuerdo con Nicolás del 14-10-2026).

- Sólo se procesan líneas completas: una línea a medio escribir queda para la próxima
  lectura y no avanza la posición.
- La posición (inodo y desplazamiento) se entrega para guardarla y retomar tras un
  reinicio. Sin posición guardada se empieza por el final del archivo, para no procesar
  de golpe todas las alertas del día.
- Rotación: si la ruta apunta a otro inodo, se termina de leer el archivo anterior con
  el descriptor que ya está abierto y recién entonces se abre el nuevo desde el
  principio, así no se pierden las alertas escritas justo antes de rotar.
- Si el archivo se trunca sin cambiar de inodo, se vuelve al principio.
- Si al arrancar la posición guardada es de un archivo que ya rotó, se empieza el
  archivo actual desde el principio; lo que quedó sin leer del anterior se pierde y
  queda contado en perdidas_por_rotacion.
- Una línea que no es un objeto JSON se descarta y se cuenta en descartadas.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Posicion:
    inodo: int
    desplazamiento: int


class LectorAlertas:
    def __init__(self, ruta: Path, posicion: Posicion | None = None) -> None:
        self.ruta = Path(ruta)
        self.descartadas = 0
        self.perdidas_por_rotacion = 0
        self._archivo = None
        self._inodo = 0
        self._pendiente = b""
        self._abrir(posicion)

    @property
    def posicion(self) -> Posicion:
        """Inodo y desplazamiento de la última línea completa entregada."""
        if self._archivo is None:
            return Posicion(self._inodo, 0)
        return Posicion(self._inodo, self._archivo.tell() - len(self._pendiente))

    def leer(self) -> list[dict]:
        """Devuelve las alertas nuevas desde la última lectura."""
        if self._archivo is None:
            self._abrir(None, desde_el_final=False)
            if self._archivo is None:
                return []
        alertas = self._leer_lineas()
        try:
            estado = os.stat(self.ruta)
        except FileNotFoundError:
            return alertas  # justo entre el renombre y la creación del archivo nuevo
        if estado.st_ino != self._inodo:
            alertas += self._leer_lineas()  # lo último del archivo anterior
            self._archivo.close()
            self._archivo = None
            self._pendiente = b""
            self._abrir(None, desde_el_final=False)
            if self._archivo is not None:
                alertas += self._leer_lineas()
        elif estado.st_size < self.posicion.desplazamiento:
            self._archivo.seek(0)
            self._pendiente = b""
            alertas += self._leer_lineas()
        return alertas

    def cerrar(self) -> None:
        if self._archivo is not None:
            self._archivo.close()
            self._archivo = None

    def _abrir(self, posicion: Posicion | None, desde_el_final: bool = True) -> None:
        try:
            archivo = open(self.ruta, "rb")  # noqa: SIM115 - queda abierto entre lecturas
        except FileNotFoundError:
            self._archivo = None
            return
        estado = os.fstat(archivo.fileno())
        if posicion is not None and posicion.inodo == estado.st_ino:
            archivo.seek(min(posicion.desplazamiento, estado.st_size))
        elif posicion is not None:
            self.perdidas_por_rotacion += 1
        elif desde_el_final:
            archivo.seek(0, os.SEEK_END)
        self._archivo = archivo
        self._inodo = estado.st_ino

    def _leer_lineas(self) -> list[dict]:
        datos = self._pendiente + self._archivo.read()
        *completas, self._pendiente = datos.split(b"\n")
        alertas = []
        for linea in completas:
            if not linea.strip():
                continue
            try:
                alerta = json.loads(linea)
            except (json.JSONDecodeError, UnicodeDecodeError):
                self.descartadas += 1
                continue
            if isinstance(alerta, dict):
                alertas.append(alerta)
            else:
                self.descartadas += 1
        return alertas
