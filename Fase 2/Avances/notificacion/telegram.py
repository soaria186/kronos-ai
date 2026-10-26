"""Cliente mínimo de la API de bots de Telegram (sólo biblioteca estándar).

Sólo conexiones salientes: los mensajes nuevos se leen con ``getUpdates`` (consulta
larga), así que el servidor no publica ningún puerto para Telegram.
El token va en la URL de la API; por eso ningún error lo incluye.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from notificacion.mensajes import Mensaje

API = "https://api.telegram.org"


class ErrorTelegram(RuntimeError):
    """La API de Telegram no respondió o rechazó la petición."""


class ClienteTelegram:
    def __init__(self, token: str, api: str = API, plazo: float = 15.0) -> None:
        if not token or "/" in token:
            raise ValueError("token de Telegram inválido")
        self._base = f"{api}/bot{token}/"
        self._plazo = plazo

    def enviar(self, chat_id: int, mensaje: Mensaje) -> int:
        datos: dict[str, Any] = {
            "chat_id": chat_id,
            "text": mensaje.texto,
            "disable_web_page_preview": True,
        }
        if mensaje.botones:
            datos["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": t, "callback_data": c} for t, c in mensaje.botones]
                ]
            }
        return self.llamar("sendMessage", datos)["message_id"]

    def pedir_respuesta(self, chat_id: int, texto: str) -> int:
        datos = {
            "chat_id": chat_id,
            "text": texto,
            "reply_markup": {"force_reply": True},
        }
        return self.llamar("sendMessage", datos)["message_id"]

    def contestar_boton(self, callback_id: str, texto: str) -> None:
        self.llamar(
            "answerCallbackQuery", {"callback_query_id": callback_id, "text": texto}
        )

    def quitar_botones(self, chat_id: int, message_id: int) -> None:
        self.llamar(
            "editMessageReplyMarkup",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": {"inline_keyboard": []},
            },
        )

    def mi_id(self) -> int:
        return self.llamar("getMe", {})["id"]

    def actualizaciones(self, desde: int, espera: int) -> list[dict]:
        return self.llamar(
            "getUpdates",
            {
                "offset": desde,
                "timeout": espera,
                "allowed_updates": ["message", "callback_query"],
            },
            plazo=self._plazo + espera,
        )

    def llamar(self, metodo: str, datos: dict, plazo: float | None = None) -> Any:
        peticion = urllib.request.Request(
            self._base + metodo,
            data=json.dumps(datos).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(peticion, timeout=plazo or self._plazo) as r:
                cuerpo = json.loads(r.read(2_000_000))
        except urllib.error.HTTPError as exc:
            try:
                cuerpo = json.loads(exc.read(10_000))
            except ValueError:
                raise ErrorTelegram(f"{metodo}: HTTP {exc.code}") from None
        except (OSError, ValueError) as exc:
            # Sin el mensaje original: podría incluir la URL con el token.
            raise ErrorTelegram(f"{metodo}: {type(exc).__name__}") from None
        if not isinstance(cuerpo, dict) or not cuerpo.get("ok"):
            descripcion = (
                cuerpo.get("description", "") if isinstance(cuerpo, dict) else ""
            )
            raise ErrorTelegram(f"{metodo}: {str(descripcion)[:200]}")
        return cuerpo.get("result")
