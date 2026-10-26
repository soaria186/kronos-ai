"""SOAR-CONSOLE: panel web del equipo (FastAPI, HTML simple sin JavaScript).

Pantallas: inicio de sesión (contraseña + TOTP) y panel por inquilino con
- niveles 3 que esperan aprobación (aprobar, o rechazar con motivo; D-32, CU-02),
- medidas de nivel 2 vigentes con su plazo de revisión y botón de revertir (RF-19),
- fallas y triage manual de los últimos días,
- estado del cortacircuito y su cierre con motivo.

Seguridad:
- Sólo escucha en NetBird (lo fija el despliegue) y con TLS.
- Cookie de sesión HttpOnly, Secure y SameSite=Strict; token CSRF en cada formulario.
- 5 intentos fallidos por cuenta o por IP bloquean 15 minutos; un código TOTP no se
  reutiliza. El mensaje de error no dice qué dato falló.
- CSP sin scripts; ninguna página se guarda en caché ni se muestra en un iframe.
- Quien actúa queda como actor en la bitácora («consola:<usuario>»).
"""

from __future__ import annotations

import hmac
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import (
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.templating import Jinja2Templates

from consola.datos import AccionRechazada
from consola.sesiones import CodigosUsados, Intentos, Sesiones
from consola.usuarios import Cuenta, hash_clave, verificar_clave, verificar_totp

COOKIE = "kronos_sesion"
PLANTILLAS = Path(__file__).resolve().parent / "plantillas"
# Para que una cuenta inexistente tarde lo mismo que una con contraseña equivocada.
_HASH_SEÑUELO = hash_clave("señuelo-para-igualar-tiempos")

AVISOS = {
    "aprobado": "Aprobado: SOAR-EXECUTE lo ejecutará en su próximo ciclo.",
    "rechazado": "Rechazado: no se ejecutará.",
    "revertir": "Reversión pedida: SOAR-EXECUTE la hará en su próximo ciclo.",
    "cortacircuito": "Cortacircuito cerrado: la ejecución automática vuelve a funcionar.",
}

CSP = (
    "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self'; "
    "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
)


def crear_app(
    datos: Any,
    cuentas: Mapping[str, Cuenta],
    inquilinos: Sequence[int],
    reloj: Callable[[], float] | None = None,
    cookie_segura: bool = True,
) -> FastAPI:
    reloj = reloj or time.time
    sesiones = Sesiones(reloj=reloj)
    intentos = Intentos(reloj=reloj)
    usados = CodigosUsados()
    plantillas = Jinja2Templates(directory=PLANTILLAS)
    plantillas.env.filters["fecha"] = _fecha
    plantillas.env.globals["ahora"] = lambda: datetime.fromtimestamp(reloj(), UTC)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def cabeceras(request: Request, call_next):
        respuesta: Response = await call_next(request)
        respuesta.headers["Content-Security-Policy"] = CSP
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        respuesta.headers["Cache-Control"] = "no-store"
        respuesta.headers["X-Frame-Options"] = "DENY"
        if cookie_segura:
            respuesta.headers["Strict-Transport-Security"] = "max-age=31536000"
        return respuesta

    def sesion_de(request: Request):
        return sesiones.obtener(request.cookies.get(COOKIE))

    def al_login() -> RedirectResponse:
        return RedirectResponse("/login", status_code=303)

    # ------------------------------------------------------------- sesión

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request, error: str = ""):
        return plantillas.TemplateResponse(
            request, "login.html", {"error": error == "1", "bloqueado": error == "b"}
        )

    @app.post("/login")
    def login(
        request: Request,
        usuario: str = Form(""),
        clave: str = Form(""),
        codigo: str = Form(""),
    ):
        ip = request.client.host if request.client else "?"
        usuario = usuario.strip().lower()
        if intentos.bloqueado(f"u:{usuario}") or intentos.bloqueado(f"ip:{ip}"):
            return RedirectResponse("/login?error=b", status_code=303)
        cuenta = cuentas.get(usuario)
        clave_ok = verificar_clave(clave, cuenta.clave if cuenta else _HASH_SEÑUELO)
        contador = (
            verificar_totp(cuenta.totp, codigo.strip(), reloj()) if cuenta else None
        )
        if not (
            cuenta
            and clave_ok
            and contador is not None
            and usados.aceptar(usuario, contador)
        ):
            intentos.fallo(f"u:{usuario}")
            intentos.fallo(f"ip:{ip}")
            return RedirectResponse("/login?error=1", status_code=303)
        intentos.exito(f"u:{usuario}")
        intentos.exito(f"ip:{ip}")
        respuesta = RedirectResponse("/", status_code=303)
        respuesta.set_cookie(
            COOKIE,
            sesiones.crear(usuario),
            httponly=True,
            secure=cookie_segura,
            samesite="strict",
            path="/",
        )
        return respuesta

    @app.post("/salir")
    def salir(request: Request, csrf: str = Form("")):
        sesion = sesion_de(request)
        if sesion and hmac.compare_digest(csrf, sesion.csrf):
            sesiones.cerrar(request.cookies.get(COOKIE))
        respuesta = al_login()
        respuesta.delete_cookie(COOKIE, path="/")
        return respuesta

    # ------------------------------------------------------------- panel

    @app.get("/", response_class=HTMLResponse)
    def panel(
        request: Request, inquilino: int | None = None, aviso: str = "", error: str = ""
    ):
        sesion = sesion_de(request)
        if sesion is None:
            return al_login()
        tenant = inquilino if inquilino in inquilinos else inquilinos[0]
        return plantillas.TemplateResponse(
            request,
            "panel.html",
            {
                "usuario": sesion.usuario,
                "csrf": sesion.csrf,
                "inquilinos": inquilinos,
                "inquilino": tenant,
                "panel": datos.panel(tenant),
                "aviso": AVISOS.get(aviso, ""),
                "error": error[:200],
            },
        )

    def actuar(
        request: Request, inquilino: int, csrf: str, accion: str, hacer: Callable
    ):
        sesion = sesion_de(request)
        if sesion is None:
            return al_login()
        if not hmac.compare_digest(csrf, sesion.csrf) or inquilino not in inquilinos:
            return PlainTextResponse("Solicitud rechazada", status_code=403)
        destino = f"/?inquilino={inquilino}"
        try:
            hacer(f"consola:{sesion.usuario}")
        except (AccionRechazada, ValueError) as exc:
            return RedirectResponse(
                f"{destino}&error={quote(str(exc)[:200])}", status_code=303
            )
        return RedirectResponse(f"{destino}&aviso={accion}", status_code=303)

    @app.post("/tickets/{ticket_id}/aprobar")
    def aprobar(
        request: Request, ticket_id: int, inquilino: int = Form(), csrf: str = Form("")
    ):
        return actuar(
            request,
            inquilino,
            csrf,
            "aprobado",
            lambda p: datos.aprobar(inquilino, ticket_id, p),
        )

    @app.post("/tickets/{ticket_id}/rechazar")
    def rechazar(
        request: Request,
        ticket_id: int,
        inquilino: int = Form(),
        csrf: str = Form(""),
        motivo: str = Form(""),
    ):
        return actuar(
            request,
            inquilino,
            csrf,
            "rechazado",
            lambda p: datos.denegar(inquilino, ticket_id, p, motivo),
        )

    @app.post("/tickets/{ticket_id}/revertir")
    def revertir(
        request: Request, ticket_id: int, inquilino: int = Form(), csrf: str = Form("")
    ):
        return actuar(
            request,
            inquilino,
            csrf,
            "revertir",
            lambda p: datos.revertir(inquilino, ticket_id, p),
        )

    @app.post("/cortacircuito/cerrar")
    def cerrar_cortacircuito(
        request: Request,
        inquilino: int = Form(),
        csrf: str = Form(""),
        motivo: str = Form(""),
    ):
        return actuar(
            request,
            inquilino,
            csrf,
            "cortacircuito",
            lambda p: datos.cerrar_cortacircuito(inquilino, p, motivo),
        )

    @app.get("/estilo.css")
    def estilo():
        return Response(
            (PLANTILLAS / "estilo.css").read_text(encoding="utf-8"),
            media_type="text/css",
        )

    return app


def _fecha(valor: Any) -> str:
    if not isinstance(valor, datetime):
        return "—"
    return valor.astimezone(UTC).strftime("%d-%m-%Y %H:%M UTC")
