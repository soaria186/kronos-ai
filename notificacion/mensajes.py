"""Textos de los avisos de SOAR-NOTIFY y formato de los botones de Telegram.

Los lee el encargado de TI de la PyME, que no es especialista en seguridad. Cada aviso
dice en palabras simples qué pasó, en qué equipo, qué hizo Kronos y qué tiene que hacer
la persona. No lleva códigos internos (PB-…, D-…) ni la palabra «inquilino»: la medida
se nombra como en el catálogo y la PyME por su nombre.

Lógica pura (sin red ni base). Los avisos se envían como texto plano, sin formato:
el título de la alerta lo puede controlar un atacante, así que se recorta y se le
quitan los saltos de línea, y nunca se interpreta como Markdown o HTML.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

LARGO_TITULO = 120
LARGO_DETALLE = 200
LARGO_MOTIVO = 500
LARGO_NOMBRE = 60

_CALLBACK = re.compile(r"^([ar]):(\d{1,10}):(\d{1,19})$")
_PEDIDO_MOTIVO = re.compile(r"ticket #(\d{1,19}) \(inquilino (\d{1,10})\)")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
# Las reglas de sobre describen la alerta como «Kronos F1: fuerza bruta por SSH…».
_PREFIJO_FAMILIA = re.compile(r"^Kronos (F[1-6]):\s*")

FAMILIAS = {
    "F1": "abuso de credenciales",
    "F2": "programa sospechoso",
    "F3": "acceso remoto o movimiento entre equipos",
    "F4": "salida de datos anómala",
    "F5": "cambio en el sistema",
    "F6": "servicio caído o degradado",
}

# Por qué no se aplicó una medida (motivo de EXECUTE), dicho para el encargado de TI.
POR_QUE_FALLO = {
    "ACCION_NO_IMPLEMENTADA": "esta medida no está disponible en esta versión de Kronos",
    "ORDEN_INVALIDA": "la alerta no trae un objetivo válido (IP, cuenta o equipo)",
    "ACTUADOR_FALLO": "la orden no llegó al equipo; puede estar apagado o sin conexión",
    "PLAYBOOK_SIN_MEDIDA": "la medida no está en el catálogo cargado",
    "PLAZO_DE_REVERSION_SIN_DEFINIR": "la medida no tiene plazo de reversión en el catálogo",
}
# Por qué no se pudo revertir (tipo de error que deja EXECUTE).
POR_QUE_NO_SE_REVIRTIO = {
    "ErrorActuador": "la orden no llegó al equipo; puede estar apagado o sin conexión",
    "OrdenInvalida": "ya no se conoce el objetivo de la medida",
    "AccionNoImplementada": "esta medida no se puede deshacer desde Kronos",
}


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


@dataclass(frozen=True)
class TextoMedida:
    """Cómo se nombra una medida del catálogo KRO-CAT-01 en los avisos."""

    nombre: str  # «Bloquear la IP externa que intenta entrar»
    efecto: str = ""  # «Nada, salvo que alguien legítimo use esa dirección»


def componer(
    tenant_id: int,
    ev: Any,
    medidas: Mapping[str, TextoMedida] | None = None,
    pyme: str | None = None,
) -> Mensaje:
    """Aviso para un evento de ``Repositorio.eventos_para_avisar``.

    ``medidas`` da el nombre de cada medida del catálogo y ``pyme`` el nombre de la PyME
    (si falta, «PyME <número>»).
    """
    nombre_pyme = limpio(pyme or "", LARGO_NOMBRE) or f"PyME {tenant_id}"
    equipo = limpio(str(getattr(ev, "equipo", None) or ""), LARGO_NOMBRE)
    cabecera = " · ".join(
        parte
        for parte in (
            nombre_pyme,
            f"ticket #{ev.ticket_id}",
            f"equipo {equipo}" if equipo else "",
        )
        if parte
    )
    que_paso = "Qué pasó: " + _que_paso(ev.titulo)
    texto = (medidas or {}).get(ev.playbook_id or "")
    medida = _medida(ev.playbook_id, texto)
    efecto = f"Efecto: {_inicial_minuscula(texto.efecto)}." if texto and texto.efecto else ""
    d = ev.detalle or {}
    objetivo = _objetivo(d)

    if ev.evento == "DECISION":
        return Mensaje(
            _lineas(
                "[APROBACIÓN] Kronos necesita una decisión",
                cabecera,
                que_paso,
                f"Kronos propone: {medida}.",
                efecto,
                "Qué hacer: aprobar o rechazar con los botones o en la consola. Si nadie"
                " responde en 2 días, no se ejecuta y queda en revisión manual.",
            ),
            (
                ("Aprobar", f"a:{tenant_id}:{ev.ticket_id}"),
                ("Rechazar", f"r:{tenant_id}:{ev.ticket_id}"),
            ),
        )
    if ev.evento == "EJECUCION_OK":
        return Mensaje(
            _lineas(
                "[MEDIDA APLICADA] Kronos actuó en un equipo",
                cabecera,
                que_paso,
                f"Kronos aplicó: {medida}{objetivo}.",
                efecto,
                "Qué hacer: avisar por correo a la persona afectada y revisar la medida en"
                " la consola; si no corresponde, revertirla ahí. No se revierte sola: desde"
                " los 2 días llega un recordatorio diario.",
            )
        )
    if ev.evento == "EJECUCION_FALLIDA":
        motivo = str(d.get("motivo", ""))
        if motivo == "ACTUADOR_FALLO":
            hacer = "revisar que el equipo esté encendido y conectado, y ver el caso en la consola"
        elif motivo == "ACCION_NO_IMPLEMENTADA":
            hacer = "ver el caso en la consola y, si corresponde, actuar a mano"
        else:
            hacer = "ver el caso en la consola"
        return Mensaje(
            _lineas(
                "[NO SE APLICÓ] Kronos no pudo aplicar una medida",
                cabecera,
                que_paso,
                f"Medida: {medida}{objetivo}.",
                f"Por qué: {_por_que(motivo, POR_QUE_FALLO)}.",
                _detalle_tecnico(d),
                f"Qué hacer: {hacer}. Kronos no lo vuelve a intentar solo.",
            )
        )
    if ev.evento == "REVERSION_FALLIDA":
        return Mensaje(
            _lineas(
                "[NO SE REVIRTIÓ] Una medida sigue aplicada",
                cabecera,
                que_paso,
                f"Sigue aplicada: {medida}{objetivo}.",
                f"Por qué: {_por_que(str(d.get('motivo', '')), POR_QUE_NO_SE_REVIRTIO)}.",
                _detalle_tecnico(d),
                "Qué hacer: comprobar que el equipo esté encendido y conectado, y quitar la"
                " medida a mano o volver a pedir la reversión desde la consola.",
            )
        )
    if ev.evento == "RECORDATORIO_REVISION":
        return Mensaje(
            _lineas(
                "[RECORDATORIO] Hay una medida sin revisar",
                cabecera,
                que_paso,
                f"Sigue vigente: {medida}.",
                "Qué hacer: revisarla en la consola y decidir si se mantiene o se revierte."
                " No se revierte sola.",
            )
        )
    if ev.evento == "APROBACION_VENCIDA":
        return Mensaje(
            _lineas(
                "[VENCIDA] Nadie aprobó la medida a tiempo",
                cabecera,
                que_paso,
                f"Kronos proponía: {medida}. No se ejecutó.",
                "Qué hacer: el caso quedó en revisión manual; verlo en la consola y actuar"
                " a mano si corresponde.",
            )
        )
    if ev.evento == "TICKET_SIN_DECISION":
        plazo = limpio(str(d.get("plazo_minutos", "")), 6)
        return Mensaje(
            _lineas(
                "[SIN DECISIÓN] Kronos no alcanzó a decidir",
                cabecera,
                que_paso,
                f"Kronos no registró una decisión en {plazo} min y no hizo nada en el equipo.",
                "Qué hacer: revisar la alerta en la consola (quedó en revisión manual). Si"
                " se repite, avisar al equipo Kronos.",
            )
        )
    if ev.evento == "CORTACIRCUITO_ABIERTO":
        return Mensaje(
            _lineas(
                "[DETENIDO] Kronos dejó de actuar solo",
                nombre_pyme,
                f"Por qué: {limpio(str(d.get('motivo', '')), LARGO_DETALLE)}.",
                "Mientras siga así, cada alerta queda en revisión manual y no se aplica"
                " ninguna medida automática.",
                "Qué hacer: revisar qué está pasando (puede ser un ataque o una falla). Para"
                " que Kronos vuelva a actuar solo, cerrar el cortacircuito en la consola,"
                " con un motivo.",
            )
        )
    raise ValueError(f"evento sin aviso: {ev.evento}")


def _que_paso(titulo: str | None) -> str:
    """El título de la alerta sin el prefijo «Kronos Fx:», con la familia en palabras."""
    texto = limpio(titulo or "", LARGO_TITULO)
    m = _PREFIJO_FAMILIA.match(texto)
    if not m:
        return texto or "alerta sin descripción"
    resto = texto[m.end():] or "alerta sin descripción"
    return f"{resto} ({FAMILIAS[m.group(1)]})"


def _medida(playbook_id: str | None, texto: TextoMedida | None) -> str:
    if texto is not None and texto.nombre:
        return _inicial_minuscula(limpio(texto.nombre, LARGO_TITULO))
    if playbook_id:
        return f"medida {limpio(playbook_id, 16)} del catálogo"
    return "sin medida"


def _objetivo(detalle: Mapping[str, Any]) -> str:
    """« (203.0.113.50)»: el objetivo de la orden que envió EXECUTE, si la hubo."""
    orden = detalle.get("orden")
    argumentos = orden.get("argumentos") if isinstance(orden, Mapping) else None
    if not isinstance(argumentos, list) or len(argumentos) < 2:
        return ""
    objetivo = limpio(" ".join(str(a) for a in argumentos[1:]), LARGO_NOMBRE)
    return f" ({objetivo})" if objetivo else ""


def _por_que(motivo: str, explicaciones: Mapping[str, str]) -> str:
    return explicaciones.get(motivo) or limpio(motivo, 60) or "sin motivo registrado"


def _detalle_tecnico(detalle: Mapping[str, Any]) -> str:
    error = limpio(str(detalle.get("error", "")), LARGO_DETALLE)
    return f"Detalle técnico: {error}" if error else ""


def _inicial_minuscula(texto: str) -> str:
    texto = texto.strip()
    return texto[:1].lower() + texto[1:]


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
