"""Envío de avisos: recorre la bitácora y avisa por Telegram.

Los avisos nombran la medida como en el catálogo KRO-CAT-01 y la PyME por su nombre
(``KRONOS_NOMBRES_INQUILINOS``), para que los entienda el encargado de TI.

Cada ciclo, por inquilino:
1. Genera los recordatorios diarios de los niveles 2 vencidos (D-33).
2. Toma los eventos a avisar en orden y los envía uno a uno. Tras cada envío deja
   AVISO_ENVIADO en la bitácora. Si Telegram falla, se detiene: ese evento y los
   siguientes se vuelven a intentar en el próximo ciclo (mejor un aviso repetido
   que uno perdido).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from notificacion.mensajes import TextoMedida, componer
from notificacion.telegram import ClienteTelegram, ErrorTelegram
from validacion.catalogo import RUTA_CATALOGO, cargar_catalogo

if TYPE_CHECKING:
    from persistencia.repositorio import Repositorio


def textos_de_medidas(ruta: Path = RUTA_CATALOGO) -> dict[str, TextoMedida]:
    """Nombre y efecto de cada medida de KRO-CAT-01, para los avisos.

    El catálogo se valida igual que en VALIDATE y EXECUTE: si no cumple sus reglas,
    lanza CatalogoInvalido y el servicio no arranca.
    """
    cargar_catalogo(ruta)
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return {
        p["id"]: TextoMedida(
            p["medida"].strip(), str(p.get("efecto_en_la_persona") or "").strip()
        )
        for p in datos["playbooks"]
    }


def leer_nombres(texto: str) -> dict[int, str]:
    """Nombres de las PyME para los avisos: «1:PyME de demostración,2:Otra»."""
    nombres: dict[int, str] = {}
    for parte in texto.split(","):
        if not parte.strip():
            continue
        ident, _, nombre = parte.partition(":")
        if not ident.strip().isdigit() or not nombre.strip():
            raise ValueError(
                "KRONOS_NOMBRES_INQUILINOS debe ser «inquilino:nombre,inquilino:nombre»"
            )
        nombres[int(ident)] = nombre.strip()
    return nombres


class Avisador:
    def __init__(
        self,
        repositorio: Repositorio,
        cliente: ClienteTelegram,
        chat_id: int,
        medidas: Mapping[str, TextoMedida] | None = None,
        nombres: Mapping[int, str] | None = None,
    ) -> None:
        self._repo = repositorio
        self._cliente = cliente
        self._chat = chat_id
        self._medidas = dict(medidas or {})
        self._nombres = dict(nombres or {})

    def ciclo(self, tenant_id: int) -> int:
        """Devuelve cuántos avisos se enviaron."""
        self._repo.tomar_recordatorios(tenant_id)
        enviados = 0
        for ev in self._repo.eventos_para_avisar(tenant_id):
            try:
                mensaje = componer(
                    tenant_id, ev, self._medidas, self._nombres.get(tenant_id)
                )
                message_id = self._cliente.enviar(self._chat, mensaje)
            except ErrorTelegram:
                break
            self._repo.registrar_aviso(
                tenant_id, ev.seq, f"telegram:{self._chat}:{message_id}"
            )
            enviados += 1
        return enviados
