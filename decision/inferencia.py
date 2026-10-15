"""Clasificación de una alerta en dos pasos con falla segura.

Paso 1: el modelo elige la familia (F1-F6). Paso 2: elige un playbook entre los
candidatos de esa familia. Si algo sale mal, no se adivina ni se reintenta: el resultado
es una FallaSegura y el caso pasa a triaje manual (MANUAL_TRIAGE). Los motivos usan los
mismos códigos que tickets.rechazo_motivo en el esquema de persistencia:

    MOTOR_INFERENCIA_NO_DISPONIBLE  el servidor del modelo no responde o devuelve error
    TIEMPO_EXCEDIDO                 los dos pasos juntos superan el plazo total
    ESQUEMA_INVALIDO                la respuesta no cumple validacion.contrato

El plazo es uno solo para los dos pasos: el paso 2 recibe lo que sobró del paso 1.
Una respuesta que llega después del plazo también es TIEMPO_EXCEDIDO, aunque sea válida.

El acceso al modelo se inyecta (protocolo Modelo), así esta lógica se prueba sin red.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from decision.plantillas import Plantillas
from validacion.contrato import (
    EsquemaInvalido,
    esquema_familia,
    esquema_playbook,
    leer_familia,
    leer_playbook,
)


class MotivoFalla(StrEnum):
    MOTOR_INFERENCIA_NO_DISPONIBLE = "MOTOR_INFERENCIA_NO_DISPONIBLE"
    TIEMPO_EXCEDIDO = "TIEMPO_EXCEDIDO"
    ESQUEMA_INVALIDO = "ESQUEMA_INVALIDO"


class MotorNoDisponible(Exception):
    """El servidor del modelo no responde o respondió con un error."""


class TiempoExcedido(Exception):
    """La llamada al modelo no terminó dentro del plazo."""


class Modelo(Protocol):
    def generar(self, prompt: str, esquema: dict, plazo: float) -> str:
        """Devuelve el texto generado o lanza MotorNoDisponible o TiempoExcedido."""


@dataclass(frozen=True)
class Clasificacion:
    familia: str
    confianza_familia: float
    playbook_id: str
    confianza_playbook: float

    @property
    def confianza(self) -> float:
        """Confianza que revisa el chequeo 2: la menor de los dos pasos.

        Una clasificación es tan confiable como su paso más dudoso: si el modelo dudó de
        la familia, el playbook elegido dentro de ella tampoco es seguro.
        """
        return min(self.confianza_familia, self.confianza_playbook)


@dataclass(frozen=True)
class FallaSegura:
    motivo: MotivoFalla
    paso: int
    detalle: str


def clasificar(
    alerta: str,
    modelo: Modelo,
    plantillas: Plantillas,
    plazo: float,
    reloj: Callable[[], float] = time.monotonic,
) -> Clasificacion | FallaSegura:
    if plazo <= 0:
        raise ValueError("el plazo debe ser positivo")
    limite = reloj() + plazo

    resultado = _paso(
        1,
        modelo,
        plantillas.prompt_familia(alerta),
        esquema_familia(),
        leer_familia,
        limite,
        reloj,
    )
    if isinstance(resultado, FallaSegura):
        return resultado
    familia = resultado

    candidatos = plantillas.familias[familia.familia].candidatos
    resultado = _paso(
        2,
        modelo,
        plantillas.prompt_playbook(familia.familia, alerta),
        esquema_playbook(candidatos),
        lambda texto: leer_playbook(texto, candidatos),
        limite,
        reloj,
    )
    if isinstance(resultado, FallaSegura):
        return resultado
    return Clasificacion(
        familia=familia.familia,
        confianza_familia=familia.confianza,
        playbook_id=resultado.playbook_id,
        confianza_playbook=resultado.confianza,
    )


def _paso(numero, modelo, prompt, esquema, leer, limite, reloj):
    restante = limite - reloj()
    if restante <= 0:
        return FallaSegura(
            MotivoFalla.TIEMPO_EXCEDIDO, numero, "sin tiempo para el paso"
        )
    try:
        texto = modelo.generar(prompt, esquema, restante)
    except TiempoExcedido as exc:
        return FallaSegura(MotivoFalla.TIEMPO_EXCEDIDO, numero, str(exc))
    except MotorNoDisponible as exc:
        return FallaSegura(MotivoFalla.MOTOR_INFERENCIA_NO_DISPONIBLE, numero, str(exc))
    if reloj() > limite:
        return FallaSegura(
            MotivoFalla.TIEMPO_EXCEDIDO, numero, "la respuesta llegó después del plazo"
        )
    try:
        return leer(texto)
    except EsquemaInvalido as exc:
        return FallaSegura(MotivoFalla.ESQUEMA_INVALIDO, numero, str(exc))
