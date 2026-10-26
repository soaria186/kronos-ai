"""Respuestas del equipo en Telegram: aprobar o rechazar un nivel 3 (RF-16, CU-02).

Sólo cuentan los mensajes del chat del equipo y de las cuentas de Telegram de la
lista ``equipo`` (identificador numérico -> nombre). Cualquier otra cosa se ignora.

- Botón «Aprobar»: el ticket pasa a PENDING y EXECUTE lo ejecuta.
- Botón «Rechazar»: el bot pide el motivo; la respuesta a ese mensaje rechaza el
  ticket con ese motivo (CU-02 exige justificación).

Quién decidió queda como actor del evento («telegram:<nombre>»). Si el ticket ya
no espera aprobación (otro integrante respondió o venció el plazo), se informa y no
cambia nada.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from notificacion.mensajes import (
    LARGO_MOTIVO,
    Mensaje,
    leer_callback,
    leer_pedido_de_motivo,
    limpio,
    pedido_de_motivo,
)
from notificacion.telegram import ClienteTelegram

if TYPE_CHECKING:
    from persistencia.repositorio import Repositorio

registro = logging.getLogger("soar-notify")


class Atendedor:
    def __init__(
        self,
        repositorio: Repositorio,
        cliente: ClienteTelegram,
        chat_id: int,
        equipo: Mapping[int, str],
        bot_id: int,
        estado_invalido: type[Exception],
    ) -> None:
        self._repo = repositorio
        self._cliente = cliente
        self._chat = chat_id
        self._equipo = dict(equipo)
        self._bot = bot_id
        self._estado_invalido = estado_invalido

    def procesar(self, actualizacion: dict[str, Any]) -> None:
        if "callback_query" in actualizacion:
            self._boton(actualizacion["callback_query"])
        elif "message" in actualizacion:
            self._mensaje(actualizacion["message"])

    def _boton(self, cq: dict[str, Any]) -> None:
        nombre = self._integrante(cq.get("from"))
        mensaje = cq.get("message") or {}
        if nombre is None or _chat(mensaje) != self._chat:
            registro.warning("botón de una cuenta o chat no autorizados; ignorado")
            self._cliente.contestar_boton(cq.get("id", ""), "No autorizado")
            return
        respuesta = leer_callback(cq.get("data"))
        if respuesta is None:
            self._cliente.contestar_boton(cq["id"], "Botón no válido")
            return
        if respuesta.accion == "rechazar":
            self._cliente.contestar_boton(cq["id"], "Escribe el motivo")
            self._cliente.pedir_respuesta(
                self._chat, pedido_de_motivo(respuesta.tenant_id, respuesta.ticket_id)
            )
            return
        try:
            self._repo.aprobar(
                respuesta.tenant_id, respuesta.ticket_id, f"telegram:{nombre}"
            )
        except self._estado_invalido:
            self._cliente.contestar_boton(cq["id"], "Ya no espera aprobación")
            return
        self._cliente.contestar_boton(cq["id"], "Aprobado")
        if "message_id" in mensaje:
            self._cliente.quitar_botones(self._chat, mensaje["message_id"])
        self._avisar(
            f"Ticket #{respuesta.ticket_id} aprobado por {nombre}. Se ejecutará en breve."
        )

    def _mensaje(self, mensaje: dict[str, Any]) -> None:
        nombre = self._integrante(mensaje.get("from"))
        original = mensaje.get("reply_to_message") or {}
        if (
            nombre is None
            or _chat(mensaje) != self._chat
            or (original.get("from") or {}).get("id") != self._bot
        ):
            return
        objetivo = leer_pedido_de_motivo(original.get("text"))
        motivo = limpio(str(mensaje.get("text") or ""), LARGO_MOTIVO)
        if objetivo is None or not motivo:
            return
        tenant_id, ticket_id = objetivo
        try:
            self._repo.denegar(tenant_id, ticket_id, f"telegram:{nombre}", motivo)
        except self._estado_invalido:
            self._avisar(
                f"Ticket #{ticket_id}: ya no espera aprobación; no se cambió nada."
            )
            return
        self._avisar(f"Ticket #{ticket_id} rechazado por {nombre}. No se ejecutará.")

    def _integrante(self, usuario: Any) -> str | None:
        if not isinstance(usuario, dict) or usuario.get("is_bot"):
            return None
        return self._equipo.get(usuario.get("id"))

    def _avisar(self, texto: str) -> None:
        self._cliente.enviar(self._chat, Mensaje(texto))


def _chat(mensaje: dict[str, Any]) -> Any:
    return (mensaje.get("chat") or {}).get("id")
