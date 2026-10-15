"""Cliente mínimo de la API de Ollama que cumple el protocolo decision.inferencia.Modelo.

Usa /api/generate sin streaming, con temperature = 0, num_ctx = 4096 y el esquema JSON en
el campo "format", igual que la medición de la etapa 1, y pide keep_alive = -1 para que el
modelo no se descargue de la memoria entre alertas. Traduce los errores de red a las
excepciones de la falla segura: timeout -> TiempoExcedido; servidor caído, error HTTP o
respuesta ilegible -> MotorNoDisponible. Va directo al servidor, sin proxies.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from decision.inferencia import MotorNoDisponible, TiempoExcedido

URL_POR_DEFECTO = "http://127.0.0.1:11435"
OPCIONES = {"temperature": 0, "num_ctx": 4096}
# -1 = el modelo queda cargado en memoria indefinidamente. En frío el 7B tarda unos 58 s
# por alerta y en tibio unos 20 s (medición del 14-10); el límite es 60 s.
KEEP_ALIVE = -1

_ABRIDOR = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class ClienteOllama:
    def __init__(self, modelo: str, url: str = URL_POR_DEFECTO) -> None:
        self.modelo = modelo
        self.url = url.rstrip("/") + "/api/generate"

    def generar(self, prompt: str, esquema: dict, plazo: float) -> str:
        cuerpo = {
            "model": self.modelo,
            "prompt": prompt,
            "stream": False,
            "format": esquema,
            "options": OPCIONES,
            "keep_alive": KEEP_ALIVE,
        }
        peticion = urllib.request.Request(
            self.url,
            data=json.dumps(cuerpo).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with _ABRIDOR.open(peticion, timeout=plazo) as respuesta:
                datos = json.load(respuesta)
        except urllib.error.HTTPError as exc:
            raise MotorNoDisponible(f"Ollama respondió {exc.code}") from exc
        except TimeoutError as exc:
            raise TiempoExcedido(f"sin respuesta en {plazo:.1f} s") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise TiempoExcedido(f"sin respuesta en {plazo:.1f} s") from exc
            raise MotorNoDisponible(
                f"no se pudo contactar con Ollama: {exc.reason}"
            ) from exc
        except (OSError, ValueError) as exc:
            raise MotorNoDisponible(f"respuesta ilegible de Ollama: {exc}") from exc
        texto = datos.get("response") if isinstance(datos, dict) else None
        if not isinstance(texto, str):
            raise MotorNoDisponible("la respuesta de Ollama no trae el campo response")
        return texto
