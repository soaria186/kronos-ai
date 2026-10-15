"""Envío de avisos: recorre la bitácora y avisa al equipo por Telegram (D-31).

Cada ciclo, por inquilino:
1. Genera los recordatorios diarios de los niveles 2 vencidos (D-33).
2. Toma los eventos a avisar en orden y los envía uno a uno. Tras cada envío deja
   AVISO_ENVIADO en la bitácora. Si Telegram falla, se detiene: ese evento y los
   siguientes se vuelven a intentar en el próximo ciclo (mejor un aviso repetido
   que uno perdido).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from notificacion.mensajes import componer
from notificacion.telegram import ClienteTelegram, ErrorTelegram

if TYPE_CHECKING:
    from persistencia.repositorio import Repositorio


class Avisador:
    def __init__(
        self, repositorio: Repositorio, cliente: ClienteTelegram, chat_id: int
    ) -> None:
        self._repo = repositorio
        self._cliente = cliente
        self._chat = chat_id

    def ciclo(self, tenant_id: int) -> int:
        """Devuelve cuántos avisos se enviaron."""
        self._repo.tomar_recordatorios(tenant_id)
        enviados = 0
        for ev in self._repo.eventos_para_avisar(tenant_id):
            try:
                message_id = self._cliente.enviar(self._chat, componer(tenant_id, ev))
            except ErrorTelegram:
                break
            self._repo.registrar_aviso(
                tenant_id, ev.seq, f"telegram:{self._chat}:{message_id}"
            )
            enviados += 1
        return enviados
