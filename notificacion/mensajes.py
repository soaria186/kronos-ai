"""Textos de los avisos de SOAR-NOTIFY y formato de los botones de Telegram.

Lógica pura (sin red ni base). Los avisos se envían como texto plano, sin formato:
el título de la alerta lo puede controlar un atacante, así que se recorta y se le
quitan los saltos de línea, y nunca se interpreta como Markdown o HTML.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

LARGO_TITULO = 120
LARGO_DETALLE = 200
LARGO_MOTIVO = 500

_CALLBACK = re.compile(r"^([ar]):(\d{1,10}):(\d{1,19})$")
_PEDIDO_MOTIVO = re.compile(r"ticket #(\d{1,19}) \(inquilino (\d{1,10})\)")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")


@dataclass(frozen=True)
class Mensaje:
    texto: str
    # (texto del botón, callback_data)
    botones: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Respuesta:
    accion: str  # "aprobar" o "rechazar"
    tenant_id: int
    ticket_id: int


def componer(tenant_id: int, ev: Any) -> Mensaje:
    """Aviso para un evento de ``Repositorio.eventos_para_avisar``."""
    cabecera = f"Inquilino {tenant_id} · ticket #{ev.ticket_id}"
    titulo = limpio(ev.titulo or "", LARGO_TITULO)
    medida = f"Medida: {ev.playbook_id} (nivel {ev.nivel})"
    d = ev.detalle or {}

    if ev.evento == "DECISION":
        return Mensaje(
            _lineas(
                "[NIVEL 3] Se necesita aprobación",
                cabecera,
                titulo,
                medida,
                "Plazo: 2 días. Si nadie responde, pasa a revisión manual sin ejecutarse.",
            ),
            (
                ("Aprobar", f"a:{tenant_id}:{ev.ticket_id}"),
                ("Rechazar", f"r:{tenant_id}:{ev.ticket_id}"),
            ),
        )
    if ev.evento == "EJECUCION_OK":
        return Mensaje(
            _lineas(
                "[NIVEL 2] Medida aplicada",
                cabecera,
                titulo,
                medida,
                "Avisar por correo a la persona afectada (D-35).",
                "Revisar en 2 días; se revierte desde la consola.",
            )
        )
    if ev.evento == "EJECUCION_FALLIDA":
        return Mensaje(
            _lineas(
                "[FALLÓ] La medida no se aplicó",
                cabecera,
                titulo,
                medida,
                f"Motivo: {limpio(str(d.get('motivo', '')), 60)}",
                limpio(str(d.get("error", "")), LARGO_DETALLE),
                "No se reintenta sola: revisar en la consola.",
            )
        )
    if ev.evento == "REVERSION_FALLIDA":
        return Mensaje(
            _lineas(
                "[REVERSIÓN FALLIDA] La medida sigue aplicada",
                cabecera,
                titulo,
                medida,
                limpio(str(d.get("error", "")), LARGO_DETALLE),
                "Revisar el equipo y volver a pedir la reversión desde la consola.",
            )
        )
    if ev.evento == "RECORDATORIO_REVISION":
        return Mensaje(
            _lineas(
                "[RECORDATORIO] Medida de nivel 2 sin revisar",
                cabecera,
                titulo,
                medida,
                "Sigue vigente: no se revierte sola (D-33).",
            )
        )
    if ev.evento == "APROBACION_VENCIDA":
        return Mensaje(
            _lineas(
                "[VENCIDA] Nivel 3 sin respuesta en 2 días",
                cabecera,
                titulo,
                medida,
                "No se ejecutó; quedó en revisión manual (D-34).",
            )
        )
    if ev.evento == "TICKET_SIN_DECISION":
        return Mensaje(
            _lineas(
                "[SIN DECISIÓN] La alerta quedó sin clasificar",
                cabecera,
                titulo,
                f"VALIDATE no registró la decisión en {limpio(str(d.get('plazo_minutos', '')), 6)} min.",
                "No se ejecutó nada; quedó en revisión manual.",
                "Revisar la alerta en la consola y el registro de soar-validate.",
            )
        )
    if ev.evento == "CORTACIRCUITO_ABIERTO":
        return Mensaje(
            _lineas(
                "[CORTACIRCUITO] Ejecución automática detenida",
                f"Inquilino {tenant_id}",
                f"Motivo: {limpio(str(d.get('motivo', '')), LARGO_DETALLE)}",
                "Se reabre a mano desde la consola.",
            )
        )
    raise ValueError(f"evento sin aviso: {ev.evento}")


def _lineas(*partes: str) -> str:
    return "\n".join(p for p in partes if p)


def pedido_de_motivo(tenant_id: int, ticket_id: int) -> str:
    return (
        f"Motivo del rechazo del ticket #{ticket_id} (inquilino {tenant_id}). "
        "Responde a este mensaje con el motivo."
    )


def leer_callback(datos: Any) -> Respuesta | None:
    if not isinstance(datos, str):
        return None
    m = _CALLBACK.match(datos)
    if not m:
        return None
    accion = "aprobar" if m.group(1) == "a" else "rechazar"
    return Respuesta(accion, int(m.group(2)), int(m.group(3)))


def leer_pedido_de_motivo(texto: Any) -> tuple[int, int] | None:
    """(tenant_id, ticket_id) del mensaje del bot que pidió el motivo."""
    if not isinstance(texto, str):
        return None
    m = _PEDIDO_MOTIVO.search(texto)
    return (int(m.group(2)), int(m.group(1))) if m else None


def limpio(texto: str, largo: int) -> str:
    texto = _CONTROL.sub(" ", texto).strip()
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"
