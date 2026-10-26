"""Comprueba que el repositorio esté listo para la entrega (versión 1.0).

Uso, desde la raíz de un clon actualizado (`git fetch --all --tags --prune` antes):

    python tools/verificar_entrega.py                      # rama actual, origin/main y ramas
    python tools/verificar_entrega.py --pruebas            # además, pruebas unitarias y R1
    python tools/verificar_entrega.py --antes-de-publicar  # sin mirar main ni la etiqueta

--antes-de-publicar es para el PR de versión (develop → main): la etiqueta y el contenido
de main sólo existen después de mezclarlo. El CI lo corre así en los PR hacia main.

Sólo usa la biblioteca estándar y git. No modifica nada. Termina con código 1 si alguna
comprobación obligatoria falla.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# Históricos: pueden mencionar la farmacia.
EXCLUIDAS = ("docs/archivo/", "docs/registro/")
# Nombran la farmacia para buscarla.
PROPIOS = ("tools/verificar_entrega.py", "tools/README.md")
TEXTO = (
    ".md", ".mmd", ".py", ".sh", ".yml", ".yaml", ".json", ".sql", ".example", ".txt",
)
MARCAS_DESACTUALIZADAS = re.compile(
    r"\(pendiente\)|pendiente de verificar|por verificar|\[POR CONFIRMAR|\[PENDIENTE",
    re.IGNORECASE,
)
# Una IP de NetBird (100.64.0.0/10) escrita como dirección, no como rango.
IP_NETBIRD = re.compile(r"\b100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+\b(?!/)")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.]|/\d)")
# 9 dígitos o más, sueltos: el formato de los identificadores de Telegram.
NUMERO_LARGO = re.compile(r"(?<![\w.-])-?\d{9,}(?![\w.])")

resultados: list[tuple[bool, bool, str, str]] = []  # (ok, obligatoria, nombre, detalle)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=RAIZ, capture_output=True, text=True, check=False
    ).stdout.strip()


def anotar(ok: bool, nombre: str, detalle: str = "", obligatoria: bool = True) -> None:
    resultados.append((ok, obligatoria, nombre, detalle))


def archivos() -> list[str]:
    return [a for a in git("ls-files").splitlines() if not a.startswith(EXCLUIDAS)]


def leer(ruta: str) -> str:
    try:
        return (RAIZ / ruta).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def texto_docx(ruta: str) -> str:
    try:
        with zipfile.ZipFile(RAIZ / ruta) as z:
            return re.sub(r"<[^>]+>", " ", z.read("word/document.xml").decode("utf-8"))
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""


def comprobar_portada(publicada: bool = True) -> None:
    if publicada:
        en_main = git("ls-tree", "-r", "--name-only", "origin/main").splitlines()
        anotar(len(en_main) > 50, "main tiene el proyecto",
               f"{len(en_main)} archivos en origin/main")
        etiquetas = git("tag", "-l", "v1.*").splitlines()
        anotar(bool(etiquetas), "existe una etiqueta v1.x",
               ", ".join(etiquetas) or "ninguna")
    readme = leer("README.md")
    lineas = len(readme.splitlines())
    titulos = re.findall(r"^#{2,3} ", readme, re.MULTILINE)
    anotar(lineas >= 60 and len(titulos) >= 6, "README completo",
           f"{lineas} líneas, {len(titulos)} secciones")
    ingles = re.search(
        r"(?i)^#{2,3} .*(english|summary|abstract)", readme, re.MULTILINE
    )
    anotar(bool(ingles), "README con resumen en inglés")
    anotar((RAIZ / "LICENSE").exists(), "LICENSE", obligatoria=False)
    anotar((RAIZ / "CHANGELOG.md").exists(), "CHANGELOG.md")


def comprobar_documentacion(lista: list[str]) -> None:
    cortos = [a for a in lista
              if a.endswith("README.md") and len(leer(a).splitlines()) <= 2]
    anotar(not cortos, "ningún README de una línea", ", ".join(cortos))
    partes = sorted({m.group(1) for a in lista
                     if (m := re.match(r"docs/instalacion/(\d\d)-", a))})
    anotar(len(partes) == 15, "guía de instalación en 15 partes",
           f"partes: {', '.join(partes)}")
    farmacia = []
    for a in lista:
        if a in PROPIOS:
            continue
        if a.endswith(".docx"):
            txt = texto_docx(a)
        else:
            txt = leer(a) if a.endswith(TEXTO) else ""
        n = len(re.findall(r"(?i)farmacia", txt))
        if n:
            farmacia.append(f"{a} ({n})")
    anotar(not farmacia, "sin menciones a la farmacia (fuera de archivo y registro)",
           "; ".join(farmacia[:8]) + (" …" if len(farmacia) > 8 else ""))
    marcas = []
    for a in lista:
        if a.endswith((".md", ".mmd")):
            n = len(MARCAS_DESACTUALIZADAS.findall(leer(a)))
            if n:
                marcas.append(f"{a} ({n})")
    anotar(not marcas, "sin marcas de pendiente o por confirmar", "; ".join(marcas[:8]))


def comprobar_coherencia() -> None:
    usadas: set[str] = set()
    for f in ("infra/docker/servicios.yml", "infra/docker/docker-compose.yml"):
        usadas |= set(re.findall(r"\$\{([A-Z0-9_]+)", leer(f)))
    env = leer("infra/docker/servicios/.env.example")
    ejemplo = set(re.findall(r"^\s*#?\s*([A-Z0-9_]+)=", env, re.MULTILINE))
    faltan = sorted(usadas - ejemplo)
    anotar(not faltan, ".env.example con todas las variables", ", ".join(faltan))
    try:
        cat = json.loads(leer("decision/catalogo/kro-cat-01.json"))
        anotar(cat.get("estado") != "version_de_trabajo", "catálogo aprobado",
               f"versión {cat.get('version')}, estado {cat.get('estado')}")
    except json.JSONDecodeError:
        anotar(False, "catálogo aprobado", "JSON inválido")
    try:
        val = json.loads(leer("validacion/configuracion/validate.json"))
        anotar(val.get("estado") != "propuesta", "configuración de VALIDATE aprobada",
               f"versión {val.get('version')}, estado {val.get('estado')}")
    except json.JSONDecodeError:
        anotar(False, "configuración de VALIDATE aprobada", "JSON inválido")
    servicios = leer("infra/docker/servicios.yml")
    anotar(servicios.count("build:") <= 1,
           "la imagen de servicios se construye una vez",
           f"{servicios.count('build:')} bloques build", obligatoria=False)
    ip_netbird = [a for a in archivos() if IP_NETBIRD.search(leer(a))]
    anotar(not ip_netbird, "sin IP de NetBird reales (antes de hacerlo público)",
           ", ".join(ip_netbird), obligatoria=False)


def publicable(texto: str) -> bool:
    try:
        ip = ipaddress.ip_address(texto)
    except ValueError:
        return True
    return not (ip.is_global or ip in ipaddress.ip_network("100.64.0.0/10"))


def comprobar_registro_y_evidencia() -> None:
    """Registro y evidencia: copias de trabajo que pueden arrastrar datos del servidor.

    Es un aviso: los números largos pueden ser otra cosa, así que se revisa a mano.
    """
    hallazgos = []
    for a in git("ls-files", "docs/registro", "docs/evidencia").splitlines():
        if not a.endswith(TEXTO):
            continue
        texto = leer(a)
        ips = {m for m in IPV4.findall(texto) if not publicable(m)}
        largos = set(NUMERO_LARGO.findall(texto))
        if ips or largos:
            hallazgos.append(f"{a} ({len(ips)} IP, {len(largos)} números largos)")
    anotar(not hallazgos,
           "registro y evidencia sin IP reales ni posibles identificadores de Telegram",
           "; ".join(hallazgos[:6]), obligatoria=False)


def comprobar_ramas() -> None:
    remotas = [r for r in git("branch", "-r", "--format=%(refname:short)").splitlines()
               if r not in ("origin", "origin/HEAD")]
    mezcladas = [r for r in git("branch", "-r", "--merged", "origin/develop",
                                "--format=%(refname:short)").splitlines()
                 if r not in ("origin", "origin/HEAD", "origin/develop", "origin/main")]
    anotar(not mezcladas, "sin ramas ya mezcladas",
           f"{len(mezcladas)} de {len(remotas)} remotas")


def comprobar_pruebas() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests/unit"],
        cwd=RAIZ, capture_output=True, text=True, check=False,
    )
    ultima = (r.stderr.strip().splitlines() or [""])[-1]
    anotar(r.returncode == 0, "pruebas unitarias", ultima)
    r = subprocess.run([sys.executable, "tools/check_r1.py"], cwd=RAIZ,
                       capture_output=True, text=True, check=False)
    anotar(r.returncode == 0, "regla R1", (r.stdout.strip().splitlines() or [""])[-1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pruebas", action="store_true",
                        help="corre también las pruebas")
    parser.add_argument("--antes-de-publicar", action="store_true",
                        help="no exige main con el proyecto ni la etiqueta v1.x")
    args = parser.parse_args()
    lista = archivos()
    comprobar_portada(publicada=not args.antes_de_publicar)
    comprobar_documentacion(lista)
    comprobar_coherencia()
    comprobar_registro_y_evidencia()
    comprobar_ramas()
    if args.pruebas:
        comprobar_pruebas()
    fallas = 0
    for ok, obligatoria, nombre, detalle in resultados:
        marca = "OK  " if ok else ("FALTA" if obligatoria else "aviso")
        fallas += (not ok) and obligatoria
        print(f"[{marca}] {nombre}" + (f" — {detalle}" if detalle and not ok else ""))
    total = sum(1 for r in resultados if r[1])
    print(f"\n{total - fallas} de {total} comprobaciones obligatorias en orden.")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
