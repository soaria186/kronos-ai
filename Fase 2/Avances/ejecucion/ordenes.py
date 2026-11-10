"""Traducción de una medida del catálogo a una orden de Active Response.

Esta es la frontera con el equipo del cliente, así que todo es cerrado:

- El nombre del comando sale de una tabla fija por acción, nunca de la alerta.
- Los argumentos se toman de campos fijos de la alerta y se validan con reglas
  estrictas (una IP se parsea con ``ipaddress``; una cuenta sólo admite letras,
  dígitos, punto, guion y guion bajo). Un valor que no calza se rechaza: no se
  limpia ni se recorta.
- Los argumentos viajan como lista, nunca como texto de shell.
- Nunca se actúa sobre el manager (agente 000), sobre la IP del propio equipo ni sobre
  las IP protegidas de la configuración (``KRONOS_IP_PROTEGIDAS``: el manager y la
  puerta de enlace).
- Si la alerta no trae el campo que la medida necesita, se rechaza con
  ``ArgumentoFaltante`` (ARGUMENTO_FALTANTE en la bitácora): nunca se adivina.
- Cada orden lleva el sistema operativo del agente («linux» o «windows»): el actuador
  lo usa para el nombre del script, y EXECUTE para no enviar una medida que no tiene
  script en ese sistema. Si no se puede saber con certeza, no se actúa (ver
  ``sistema_operativo``).

Los campos de la alerta se buscan en el mismo orden que usa la lista de exclusión de
VALIDATE (validacion/alerta.py), para que EXECUTE actúe sobre lo que VALIDATE revisó.
Los nombres de los comandos deben coincidir con los scripts de Active Response que
se instalen en los agentes.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# Acción del catálogo -> (comando de Active Response, operación inversa o None si la
# medida no se revierte desde Kronos).
COMANDOS: dict[str, tuple[str, str | None]] = {
    "bloquear_ip": ("kronos-bloquear-ip", "quitar"),
    "aislar_equipo": ("kronos-aislar-equipo", "quitar"),
    "deshabilitar_cuenta": ("kronos-deshabilitar-cuenta", "habilitar"),
    "detener_servicio": ("kronos-detener-servicio", "iniciar"),
    "cerrar_sesion": ("kronos-cerrar-sesion", None),
    "terminar_proceso": ("kronos-terminar-proceso", None),
    "cuarentena": ("kronos-cuarentena", "restaurar"),
    "bloquear_destino": ("kronos-bloquear-destino", "quitar"),
    "limitar_conexiones": ("kronos-limitar-conexiones", "quitar"),
    "revertir_tarea": ("kronos-revertir-tarea", "habilitar"),
}
# La consulta (nivel 0) no tiene comando: no pasa por Active Response, sino por la
# API de Wazuh desde el servidor (D-72; ver ejecucion/consulta.py). Tener comando aquí
# no basta para actuar: la acción tiene que estar además en actuadores_v1 del catálogo
# para el sistema del agente (D-69 y D-70); si no, ACCION_NO_IMPLEMENTADA.

_CAMPOS_IP = (("data", "srcip"), ("data", "win", "eventdata", "ipAddress"))
_CAMPOS_CUENTA = (
    ("data", "dstuser"),
    ("data", "win", "eventdata", "targetUserName"),
    ("data", "srcuser"),
)
_CAMPOS_PID = (("data", "win", "eventdata", "processId"), ("data", "audit", "pid"))
# Ejecutable del proceso a terminar (Sysmon y auditd): el script confirma que el PID siga
# siendo ese programa antes de terminarlo, para no matar otro proceso que heredó el PID.
_CAMPOS_IMAGEN = (("data", "win", "eventdata", "image"), ("data", "audit", "exe"))
_CAMPOS_SERVICIO = (("data", "win", "eventdata", "serviceName"),)
# Sin serviceName, el servicio se obtiene de otra parte de la alerta (cobertura de F6, 10-11-2026):
# - Windows, eventos 7031/7034 del Service Control Manager: param1 es el nombre que se muestra
#   (traducido, con espacios); el nombre real viene en «binary», en UTF-16LE y en hexadecimal.
# - Linux: el registro de acceso del servidor web dice qué servicio es (/var/log/nginx/...).
_CAMPO_BINARIO = ("data", "win", "eventdata", "binary")
_SERVICIOS_WEB_LINUX = frozenset({"nginx", "apache2", "httpd", "lighttpd"})
_REGISTRO_WEB = re.compile(r"^/var/log/([a-z0-9]+)/[^/]+$")
# IP de destino (F4): Linux y Sysmon (evento 3).
_CAMPOS_IP_DESTINO = (("data", "dstip"), ("data", "win", "eventdata", "destinationIp"))
# Archivo a poner en cuarentena: el mismo orden que la categoría «programa» de la lista
# de exclusión (integridad de archivos en F5, Sysmon en F2 y auditd).
_CAMPOS_RUTA = (
    ("syscheck", "path"),
    # Sysmon 11 (archivo creado): el archivo es targetFilename; image es quien lo creó
    # (prueba integral 2, ticket 147: se intentaba poner en cuarentena powershell.exe).
    ("data", "win", "eventdata", "targetFilename"),
    ("data", "win", "eventdata", "image"),
    ("data", "audit", "exe"),
)
# Tarea programada: en Windows, el evento 4698 (nombre de la tarea); en Linux, el
# archivo de cron o la unidad de systemd que cambió (integridad de archivos).
_CAMPOS_TAREA_WINDOWS = (("data", "win", "eventdata", "taskName"),)
_CAMPOS_TAREA_LINUX = (("syscheck", "path"),)

_AGENTE = re.compile(r"^\d{3,8}$")
_CUENTA = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SERVICIO = re.compile(r"^[A-Za-z0-9._@-]{1,128}$")
_PID = re.compile(r"^\d{1,10}$")

# Rutas y tareas: lista blanca de caracteres por tramo. Fuera quedan los de shell y de
# comodines ($ % ` ' " ; & | < > * ? [ ] { } ! ^ =), «~» (en Windows abre los nombres
# cortos, como PROGRA~2, que esquivarían las carpetas protegidas) y «:» fuera de la
# unidad (flujos alternativos de NTFS).
_TRAMO = r"[\w .()+#@,-]{1,255}"
_RUTA_WINDOWS = re.compile(rf"^[A-Za-z]:\\(?:{_TRAMO}\\)*{_TRAMO}$")
_RUTA_LINUX = re.compile(rf"^/(?:{_TRAMO}/)*{_TRAMO}$")
_TAREA_WINDOWS = re.compile(rf"^\\(?:{_TRAMO}\\)*{_TRAMO}$")
LARGO_RUTA_WINDOWS = 260
LARGO_RUTA_LINUX = 1024
LARGO_TAREA = 238

# Defensa adicional a la lista de exclusión y a la del script: carpetas del sistema
# operativo, del agente y de Kronos, donde nunca se pone nada en cuarentena.
CARPETAS_PROTEGIDAS_WINDOWS = (
    "c:\\windows",
    "c:\\program files (x86)\\ossec-agent",
    "c:\\program files\\ossec-agent",
    "c:\\program files\\netbird",
    "c:\\programdata\\kronos",
)
CARPETAS_PROTEGIDAS_LINUX = (
    "/bin", "/boot", "/dev", "/etc", "/lib", "/lib32", "/lib64", "/libx32", "/proc",
    "/run", "/sbin", "/sys", "/usr", "/var/lib", "/var/ossec",
)
# En Linux sólo se revierten tareas de cron o temporizadores de systemd.
TAREAS_LINUX = (
    "/etc/crontab",
    "/etc/cron.d/",
    "/etc/cron.hourly/",
    "/etc/cron.daily/",
    "/etc/cron.weekly/",
    "/etc/cron.monthly/",
    "/var/spool/cron/",
    "/etc/systemd/system/",
)

# Defensa adicional a la lista de exclusión: cuentas que nunca se tocan.
CUENTAS_PROTEGIDAS = frozenset(
    {"root", "administrator", "administrador", "system", "localsystem", "kronos"}
)
PID_MINIMO = 5  # 0 a 4 son del sistema en Windows y Linux


SISTEMAS = frozenset({"linux", "windows"})
_UNIDAD_WINDOWS = re.compile(r"^[A-Za-z]:\\")


class OrdenInvalida(ValueError):
    """La alerta no trae un objetivo válido para la medida."""


class ArgumentoFaltante(OrdenInvalida):
    """La alerta no trae el campo que la medida necesita (ARGUMENTO_FALTANTE)."""


class AccionNoImplementada(ValueError):
    """La acción del catálogo todavía no tiene comando de Active Response."""


@dataclass(frozen=True)
class Orden:
    agente: str
    comando: str
    argumentos: tuple[str, ...]
    sistema: str

    def __post_init__(self) -> None:
        if self.sistema not in SISTEMAS:
            raise ValueError(f"sistema operativo desconocido: {self.sistema!r}")

    def como_detalle(self) -> dict[str, Any]:
        return {
            "agente": self.agente,
            "sistema": self.sistema,
            "comando": self.comando,
            "argumentos": list(self.argumentos),
        }


def construir(
    accion: str,
    alerta: Mapping[str, Any],
    *,
    sistema: str,
    ip_protegidas: frozenset[str] = frozenset(),
) -> Orden:
    """Orden que aplica la medida en un agente del sistema operativo indicado."""
    comando, _ = _comando(accion)
    agente_id = _agente(alerta)
    objetivo = _objetivo(accion, alerta, sistema, ip_protegidas)
    return Orden(agente_id, comando, ("aplicar", *objetivo), sistema)


def construir_reversion(
    accion: str,
    alerta: Mapping[str, Any],
    *,
    sistema: str,
    ip_protegidas: frozenset[str] = frozenset(),
) -> Orden:
    """Orden que deshace la medida, con el mismo objetivo que la original."""
    comando, inversa = _comando(accion)
    if inversa is None:
        raise AccionNoImplementada(f"{accion}: no se revierte desde Kronos")
    agente_id = _agente(alerta)
    objetivo = _objetivo(accion, alerta, sistema, ip_protegidas)
    return Orden(agente_id, comando, (inversa, *objetivo), sistema)


def leer_ip_protegidas(texto: str) -> frozenset[str]:
    """Lee KRONOS_IP_PROTEGIDAS: IP separadas por coma (el manager, la puerta de enlace).

    Vacío es válido. Una IP inválida lanza ValueError: EXECUTE no arranca con una lista
    dudosa. Se guardan normalizadas (``::ffff:a.b.c.d`` cuenta como ``a.b.c.d``).
    """
    protegidas: set[str] = set()
    for parte in texto.split(","):
        parte = parte.strip()
        if not parte:
            continue
        try:
            protegidas.add(_normalizada(ipaddress.ip_address(parte)))
        except ValueError as exc:
            raise ValueError(f"KRONOS_IP_PROTEGIDAS: {parte!r} no es una IP") from exc
    return frozenset(protegidas)


def leer_mapa_agentes(texto: str) -> dict[str, str]:
    """Lee el mapa «agente:sistema» de KRONOS_AGENTES_SO, por ejemplo
    «001:linux,002:windows». Vacío es válido (se deduce de cada alerta).

    Un formato inválido lanza ValueError: EXECUTE no arranca con un mapa dudoso.
    """
    mapa: dict[str, str] = {}
    for parte in texto.split(","):
        parte = parte.strip()
        if not parte:
            continue
        agente, separador, sistema = parte.partition(":")
        agente, sistema = agente.strip(), sistema.strip()
        if not separador or not _AGENTE.match(agente) or sistema not in SISTEMAS:
            raise ValueError(
                f"KRONOS_AGENTES_SO: {parte!r} no tiene la forma agente:linux o "
                "agente:windows (agente de 3 a 8 dígitos)"
            )
        if int(agente) == 0:
            raise ValueError("KRONOS_AGENTES_SO: el manager (agente 000) no va en el mapa")
        if agente in mapa:
            raise ValueError(f"KRONOS_AGENTES_SO: el agente {agente} está repetido")
        mapa[agente] = sistema
    return mapa


def falta_argumento(accion: str, alerta: Mapping[str, Any]) -> bool:
    """True si la alerta no trae el campo que la medida necesita (ARGUMENTO_FALTANTE).

    Lo usa VALIDATE para no aceptar del modelo medidas que EXECUTE no podría aplicar con
    esta alerta. Sólo cuenta la falta del campo: un valor que está pero no es válido (una
    IP protegida, una ruta del sistema) no se decide aquí, sino en EXECUTE, como siempre.
    Si no se sabe el sistema operativo, o la acción no tiene comando, responde False.
    """
    if accion not in COMANDOS:
        return False
    sistema = _deducir_sistema(alerta)
    if sistema is None:
        return False
    try:
        _objetivo(accion, alerta, sistema, frozenset())
    except ArgumentoFaltante:
        return True
    except OrdenInvalida:
        return False
    return False


def no_aplicable(accion: str, alerta: Mapping[str, Any]) -> bool:
    """True si EXECUTE no podría aplicar la medida con esta alerta: le falta el dato o el
    dato no es válido (una IP local, la del propio equipo, una ruta del sistema...).

    Lo usa VALIDATE para no ofrecer al modelo medidas que terminarían en
    ARGUMENTO_FALTANTE u ORDEN_INVALIDA (prueba integral 2, tickets 147 y 148). Las IP
    protegidas de la configuración de EXECUTE no se conocen aquí: ésas las sigue
    rechazando EXECUTE. Si la alerta no dice el sistema operativo (por ejemplo, la 592 de
    logcollector), la medida es imposible sólo si lo es en Linux y en Windows (ticket 162).
    """
    if accion not in COMANDOS:
        return False
    sistema = _deducir_sistema(alerta)
    sistemas = (sistema,) if sistema is not None else ("linux", "windows")
    for candidato in sistemas:
        try:
            _objetivo(accion, alerta, candidato, frozenset())
        except OrdenInvalida:  # incluye ArgumentoFaltante
            continue
        return False
    return True


def sistema_operativo(
    alerta: Mapping[str, Any], mapa: Mapping[str, str]
) -> str | None:
    """Sistema operativo del agente de la alerta, o None si no se puede saber.

    1. El mapa explícito de la configuración manda.
    2. Si el agente no está en el mapa, se deduce de campos de la alerta.
    3. Si la alerta no dice nada claro, o el mapa y la alerta se contradicen, None:
       EXECUTE no actúa.
    """
    agente = _valor(alerta, ("agent", "id"))
    deducido = _deducir_sistema(alerta)
    declarado = mapa.get(agente) if agente is not None else None
    if declarado is not None and deducido is not None and declarado != deducido:
        return None
    return declarado or deducido


def _deducir_sistema(alerta: Mapping[str, Any]) -> str | None:
    ubicacion = _valor(alerta, ("location",)) or ""
    decodificador = _valor(alerta, ("decoder", "name")) or ""
    ruta = _valor(alerta, ("syscheck", "path")) or ""
    datos = alerta.get("data") if isinstance(alerta, Mapping) else None
    windows = (
        (isinstance(datos, Mapping) and isinstance(datos.get("win"), Mapping))
        or ubicacion == "EventChannel"
        or decodificador.lower().startswith("windows")
        or bool(_UNIDAD_WINDOWS.match(ruta))
    )
    linux = ruta.startswith("/") or ubicacion.startswith("/") or ubicacion == "journald"
    if windows == linux:  # ninguna señal, o señales de los dos sistemas
        return None
    return "windows" if windows else "linux"


def _comando(accion: str) -> tuple[str, str | None]:
    if accion not in COMANDOS:
        raise AccionNoImplementada(f"{accion}: sin comando de Active Response")
    return COMANDOS[accion]


def _objetivo(
    accion: str,
    alerta: Mapping[str, Any],
    sistema: str,
    ip_protegidas: frozenset[str],
) -> tuple[str, ...]:
    if accion in ("bloquear_ip", "limitar_conexiones"):
        return (_ip(alerta, _CAMPOS_IP, ip_protegidas),)
    if accion == "bloquear_destino":
        return (_ip(alerta, _CAMPOS_IP_DESTINO, ip_protegidas),)
    if accion == "cuarentena":
        return (_ruta(alerta, sistema, _CAMPOS_RUTA, protegidas=True),)
    if accion == "revertir_tarea":
        return (_tarea(alerta, sistema),)
    if accion in ("deshabilitar_cuenta", "cerrar_sesion"):
        return (_cuenta(alerta),)
    if accion == "terminar_proceso":
        return (_pid(alerta), _ruta(alerta, sistema, _CAMPOS_IMAGEN, protegidas=False))
    if accion == "detener_servicio":
        return (_servicio(alerta, sistema),)
    return ()  # aislar_equipo: actúa sobre el propio equipo


def agente(alerta: Mapping[str, Any]) -> str:
    """Agente de la alerta, validado (nunca el 000); si no sirve, OrdenInvalida."""
    return _agente(alerta)


def _agente(alerta: Mapping[str, Any]) -> str:
    agente = _valor(alerta, ("agent", "id"))
    if agente is None or not _AGENTE.match(agente):
        raise OrdenInvalida("la alerta no trae un agent.id válido")
    if int(agente) == 0:
        raise OrdenInvalida("nunca se actúa sobre el manager (agente 000)")
    return agente


def _ip(
    alerta: Mapping[str, Any],
    campos: tuple[tuple[str, ...], ...],
    ip_protegidas: frozenset[str],
) -> str:
    texto = _primero(alerta, campos, "IP")
    try:
        ip = ipaddress.ip_address(texto)
    except ValueError as exc:
        raise OrdenInvalida(f"IP inválida: {texto!r}") from exc
    real = ip.ipv4_mapped if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped else ip
    if real.is_loopback or real.is_unspecified or real.is_multicast or real.is_link_local:
        raise OrdenInvalida(f"no se bloquea la IP {ip}")
    propia = _valor(alerta, ("agent", "ip"))
    if propia is not None and propia == str(ip):
        raise OrdenInvalida("la IP a bloquear es la del propio equipo")
    if _normalizada(ip) in ip_protegidas:
        raise OrdenInvalida(f"la IP {ip} está protegida (manager o puerta de enlace)")
    return str(ip)


def _normalizada(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return str(ip.ipv4_mapped)
    return str(ip)


def _ruta(
    alerta: Mapping[str, Any],
    sistema: str,
    campos: tuple[tuple[str, ...], ...],
    *,
    protegidas: bool,
) -> str:
    """Ruta absoluta del archivo, con la forma del sistema del agente y, si ``protegidas``,
    fuera de las carpetas protegidas (cuarentena). Para terminar un proceso la ruta sólo
    identifica el programa: un powershell.exe de C:\\Windows se puede terminar, pero no
    poner en cuarentena. Nunca se normaliza: lo que no calza se rechaza."""
    ruta = _primero(alerta, campos, "la ruta del archivo")
    if sistema == "windows":
        if len(ruta) > LARGO_RUTA_WINDOWS or not _RUTA_WINDOWS.match(ruta):
            raise OrdenInvalida(f"ruta de Windows no permitida: {ruta!r}")
        _sin_puntos(ruta.split("\\")[1:], ruta)
        minuscula = ruta.lower()
        carpetas = CARPETAS_PROTEGIDAS_WINDOWS
        separador = "\\"
    else:
        if len(ruta) > LARGO_RUTA_LINUX or not _RUTA_LINUX.match(ruta):
            raise OrdenInvalida(f"ruta de Linux no permitida: {ruta!r}")
        _sin_puntos(ruta.split("/")[1:], ruta)
        minuscula = ruta
        carpetas = CARPETAS_PROTEGIDAS_LINUX
        separador = "/"
    if not protegidas:
        return ruta
    for carpeta in carpetas:
        if minuscula == carpeta or minuscula.startswith(carpeta + separador):
            raise OrdenInvalida(f"{ruta!r} está en una carpeta protegida ({carpeta})")
    return ruta


def _tarea(alerta: Mapping[str, Any], sistema: str) -> str:
    """Nombre de la tarea programada (Windows) o archivo de cron o de systemd (Linux)."""
    if sistema == "windows":
        tarea = _primero(alerta, _CAMPOS_TAREA_WINDOWS, "el nombre de la tarea")
        if len(tarea) > LARGO_TAREA or not _TAREA_WINDOWS.match(tarea):
            raise OrdenInvalida(f"nombre de tarea no permitido: {tarea!r}")
        _sin_puntos(tarea.split("\\")[1:], tarea)
        return tarea
    tarea = _primero(alerta, _CAMPOS_TAREA_LINUX, "el archivo de la tarea")
    if len(tarea) > LARGO_RUTA_LINUX or not _RUTA_LINUX.match(tarea):
        raise OrdenInvalida(f"ruta de tarea no permitida: {tarea!r}")
    _sin_puntos(tarea.split("/")[1:], tarea)
    if not any(
        tarea == prefijo or (prefijo.endswith("/") and tarea.startswith(prefijo))
        for prefijo in TAREAS_LINUX
    ):
        raise OrdenInvalida(f"{tarea!r} no es una tarea de cron ni de systemd")
    if tarea.startswith("/etc/systemd/system/") and not tarea.endswith(".timer"):
        raise OrdenInvalida(f"{tarea!r}: en systemd sólo se deshabilitan temporizadores")
    return tarea


def _sin_puntos(tramos: list[str], original: str) -> None:
    """Rechaza «.» y «..», y tramos que terminan en punto o espacio (Windows los
    recorta y la ruta apuntaría a otro archivo)."""
    for tramo in tramos:
        if tramo in (".", "..") or tramo != tramo.strip() or tramo.endswith("."):
            raise OrdenInvalida(f"ruta con tramos no permitidos: {original!r}")


def _servicio(alerta: Mapping[str, Any], sistema: str) -> str:
    if any(_valor(alerta, ruta) is not None for ruta in _CAMPOS_SERVICIO):
        return _validado(alerta, _CAMPOS_SERVICIO, _SERVICIO, "servicio")
    if sistema == "windows":
        binario = _valor(alerta, _CAMPO_BINARIO)
        if binario is not None:
            nombre = _nombre_desde_binario(binario)
            if nombre is None or not _SERVICIO.match(nombre):
                raise OrdenInvalida(f"servicio no válido en el evento: {binario[:80]!r}")
            return nombre
    else:
        registro = _REGISTRO_WEB.match(_valor(alerta, ("location",)) or "")
        if registro and registro.group(1) in _SERVICIOS_WEB_LINUX:
            return registro.group(1)
    raise ArgumentoFaltante("la alerta no trae servicio")


def _nombre_desde_binario(texto: str) -> str | None:
    """Nombre del servicio en el campo «binary» de 7031/7034 (hexadecimal de UTF-16LE)."""
    try:
        nombre = bytes.fromhex(texto).decode("utf-16-le")
    except ValueError:
        return None
    nombre = nombre.rstrip("\x00")
    return nombre or None


def _cuenta(alerta: Mapping[str, Any]) -> str:
    cuenta = _validado(alerta, _CAMPOS_CUENTA, _CUENTA, "cuenta")
    if cuenta.lower() in CUENTAS_PROTEGIDAS or cuenta.endswith("$"):
        raise OrdenInvalida(f"la cuenta {cuenta!r} está protegida")
    return cuenta


def _pid(alerta: Mapping[str, Any]) -> str:
    pid = _validado(alerta, _CAMPOS_PID, _PID, "PID")
    if int(pid) < PID_MINIMO:
        raise OrdenInvalida(f"PID del sistema: {pid}")
    return str(int(pid))


def _validado(
    alerta: Mapping[str, Any],
    campos: tuple[tuple[str, ...], ...],
    patron: re.Pattern,
    que: str,
) -> str:
    texto = _primero(alerta, campos, que)
    if not patron.match(texto):
        raise OrdenInvalida(f"{que} con caracteres no permitidos: {texto!r}")
    return texto


def _primero(
    alerta: Mapping[str, Any], campos: tuple[tuple[str, ...], ...], que: str
) -> str:
    for ruta in campos:
        valor = _valor(alerta, ruta)
        if valor is not None:
            return valor
    raise ArgumentoFaltante(f"la alerta no trae {que}")


def _valor(alerta: Mapping[str, Any], ruta: tuple[str, ...]) -> str | None:
    actual: Any = alerta
    for clave in ruta:
        if not isinstance(actual, Mapping) or clave not in actual:
            return None
        actual = actual[clave]
    if isinstance(actual, bool) or not isinstance(actual, (str, int)):
        return None
    texto = str(actual)
    return texto if texto else None
