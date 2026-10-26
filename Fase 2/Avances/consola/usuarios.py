"""Cuentas del equipo para SOAR-CONSOLE: contraseña (scrypt) y TOTP (RFC 6238).

Sólo biblioteca estándar. Las cuentas viven en un archivo JSON fuera del repositorio
(secreto de Docker), con este formato:

    {"usuarios": {"nicolas": {"clave": "scrypt$16384$8$1$<sal>$<hash>",
                              "totp": "<secreto base32>"}}}

Alta de una cuenta (pide la contraseña sin mostrarla y entrega el secreto TOTP para
la app de autenticación una sola vez):

    python -m consola.usuarios agregar nicolas --archivo secrets/consola_usuarios.json
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import struct
import sys
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1
LARGO_MINIMO_CLAVE = 12
UID_SERVICIO = 10001
PASO_TOTP = 30
VENTANA_TOTP = 1  # acepta el código anterior y el siguiente (relojes desfasados)
_NOMBRE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")


@dataclass(frozen=True)
class Cuenta:
    nombre: str
    clave: str  # hash scrypt
    totp: str  # secreto base32


def hash_clave(clave: str) -> str:
    sal = secrets.token_bytes(16)
    derivada = hashlib.scrypt(
        clave.encode(), salt=sal, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${base64.b64encode(sal).decode()}${base64.b64encode(derivada).decode()}"


def verificar_clave(clave: str, almacenado: str) -> bool:
    try:
        tipo, n, r, p, sal, esperado = almacenado.split("$")
        if tipo != "scrypt":
            return False
        derivada = hashlib.scrypt(
            clave.encode(),
            salt=base64.b64decode(sal),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=32,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derivada, base64.b64decode(esperado))


def nuevo_secreto_totp() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def codigo_totp(secreto: str, contador: int) -> str:
    clave = base64.b32decode(secreto.upper() + "=" * (-len(secreto) % 8))
    resumen = hmac.new(clave, struct.pack(">Q", contador), hashlib.sha1).digest()
    desplazamiento = resumen[-1] & 0x0F
    valor = (
        struct.unpack(">I", resumen[desplazamiento : desplazamiento + 4])[0]
        & 0x7FFFFFFF
    )
    return f"{valor % 1_000_000:06d}"


def verificar_totp(secreto: str, codigo: str, ahora: float | None = None) -> int | None:
    """Devuelve el contador que coincidió (para impedir reutilizarlo) o None."""
    if not re.fullmatch(r"\d{6}", codigo or ""):
        return None
    actual = int((time.time() if ahora is None else ahora) // PASO_TOTP)
    for contador in range(actual - VENTANA_TOTP, actual + VENTANA_TOTP + 1):
        if hmac.compare_digest(codigo_totp(secreto, contador), codigo):
            return contador
    return None


def uri_totp(nombre: str, secreto: str, emisor: str = "Kronos AI") -> str:
    etiqueta = urllib.parse.quote(f"{emisor}:{nombre}")
    parametros = urllib.parse.urlencode({"secret": secreto, "issuer": emisor})
    return f"otpauth://totp/{etiqueta}?{parametros}"


def cargar(ruta: Path) -> dict[str, Cuenta]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    cuentas = {}
    for nombre, c in datos.get("usuarios", {}).items():
        if not _NOMBRE.match(nombre) or not c.get("clave") or not c.get("totp"):
            raise ValueError(f"cuenta inválida en {ruta.name}: {nombre!r}")
        cuentas[nombre] = Cuenta(nombre, c["clave"], c["totp"])
    if not cuentas:
        raise ValueError(f"{ruta.name} no tiene cuentas")
    return cuentas


def agregar(ruta: Path, nombre: str, clave: str) -> str:
    """Agrega (o reemplaza) una cuenta y devuelve su secreto TOTP nuevo."""
    if not _NOMBRE.match(nombre):
        raise ValueError("nombre: minúsculas, dígitos, «-» o «_», de 2 a 32 caracteres")
    if len(clave) < LARGO_MINIMO_CLAVE:
        raise ValueError(
            f"la contraseña debe tener al menos {LARGO_MINIMO_CLAVE} caracteres"
        )
    datos = (
        json.loads(ruta.read_text(encoding="utf-8"))
        if ruta.exists()
        else {"usuarios": {}}
    )
    secreto = nuevo_secreto_totp()
    datos.setdefault("usuarios", {})[nombre] = {
        "clave": hash_clave(clave),
        "totp": secreto,
    }
    ruta.write_text(json.dumps(datos, indent=2) + "\n", encoding="utf-8")
    # Lo lee el servicio, que corre como uid 10001 (servicios/Dockerfile). Si el alta se
    # hizo como root (docker run --user root), se le da el grupo de ese usuario.
    ruta.chmod(0o640)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        os.chown(ruta, 0, UID_SERVICIO)
    return secreto


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m consola.usuarios")
    sub = parser.add_subparsers(dest="orden", required=True)
    alta = sub.add_parser("agregar", help="agrega o reemplaza una cuenta")
    alta.add_argument("nombre")
    alta.add_argument("--archivo", type=Path, required=True)
    args = parser.parse_args(argv)

    clave = getpass.getpass("Contraseña: ")
    if clave != getpass.getpass("Repítela: "):
        print("Las contraseñas no coinciden.", file=sys.stderr)
        return 1
    try:
        secreto = agregar(args.archivo, args.nombre, clave)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Cuenta {args.nombre} guardada en {args.archivo}.")
    print("Agrega esta cuenta en la app de autenticación (se muestra una sola vez):")
    print(f"  secreto: {secreto}")
    print(f"  enlace:  {uri_totp(args.nombre, secreto)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
