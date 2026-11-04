"""Pruebas de kronos-aislar-equipo, el script de Active Response para Linux.

El script se ejecuta completo en el mismo proceso (runpy), con `iptables`, `ip6tables` e `ip`
simulados (las cadenas quedan en memoria), `socket.getaddrinfo`, ossec.conf y el archivo de
permitidos simulados, y el registro capturado: no toca el firewall ni necesita root.
"""

from __future__ import annotations

import builtins
import io
import json
import runpy
import socket
import subprocess
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "infra" / "wazuh" / "active-response" / "linux" / "kronos-aislar-equipo"
)

LOG = "/var/ossec/logs/active-responses.log"
OSSEC_CONF = "/var/ossec/etc/ossec.conf"
PERMITIDOS = "/var/ossec/etc/kronos-aislar.permitidos"
CADENA = "KRONOS-AISLAR"
MANAGER = "203.0.113.10"

CONF_IP = f"""<ossec_config>
  <client>
    <server>
      <address>{MANAGER}</address>
      <port>1514</port>
      <protocol>tcp</protocol>
    </server>
  </client>
</ossec_config>
"""

# Una regla ajena que ya estaba (por ejemplo, un bloqueo de kronos-bloquear-ip).
AJENA = ["-s", "203.0.113.50", "-m", "comment", "--comment", "kronos", "-j", "DROP"]


class Equipo:
    """Simula el firewall, la red y los archivos, y guarda lo que pasa."""

    def __init__(self, conf=CONF_IP, permitidos=None, netbird=True, resolver=None, falla=None):
        self.tablas = {fam: {"INPUT": [list(AJENA)], "OUTPUT": []} for fam in ("iptables", "ip6tables")}
        self.archivos = {OSSEC_CONF: conf} if conf is not None else {}
        if permitidos is not None:
            self.archivos[PERMITIDOS] = permitidos
        self.netbird = netbird
        self.resolver = resolver or {}
        self.falla = falla  # función(cmd) -> True si ese comando debe fallar
        self.comandos = []
        self.log = []

    def run(self, cmd, **opciones):
        assert isinstance(cmd, list), f"el comando debe ser una lista: {cmd!r}"
        assert not opciones.get("shell"), "nunca shell=True"
        self.comandos.append(cmd)
        if self.falla and self.falla(cmd):
            return subprocess.CompletedProcess(cmd, 1, "", "fallo simulado")
        if cmd[:3] == ["ip", "link", "show"]:
            return subprocess.CompletedProcess(cmd, 0 if self.netbird else 1, "", "")
        if cmd[0] not in self.tablas:
            raise AssertionError(f"comando inesperado: {cmd}")
        t = self.tablas[cmd[0]]
        accion, cadena, resto = cmd[1], cmd[2], cmd[3:]

        def r(codigo):
            return subprocess.CompletedProcess(cmd, codigo, "", "" if codigo == 0 else "no existe")

        if accion == "-S":
            return r(0 if cadena in t else 1)
        if accion == "-N":
            if cadena in t:
                return r(1)
            t[cadena] = []
            return r(0)
        if cadena not in t:
            return r(1)
        if accion == "-A":
            t[cadena].append(resto)
        elif accion == "-I":
            t[cadena].insert(int(resto[0]) - 1, resto[1:])
        elif accion == "-C":
            return r(0 if resto in t[cadena] else 1)
        elif accion == "-D":
            if resto not in t[cadena]:
                return r(1)
            t[cadena].remove(resto)
        elif accion == "-F":
            t[cadena].clear()
        elif accion == "-X":
            if any(["-j", cadena] == regla[-2:] for c in t.values() for regla in c):
                return r(1)  # todavía la usa un gancho
            del t[cadena]
        else:
            raise AssertionError(f"acción inesperada: {cmd}")
        return r(0)

    def getaddrinfo(self, nombre, puerto, familia=0, tipo=0, *a, **k):
        assert familia == socket.AF_INET, "el manager se resuelve sólo a IPv4"
        if nombre not in self.resolver:
            raise socket.gaierror(-2, "Name or service not known")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in self.resolver[nombre]]

    def abrir(self, ruta, modo="r", *a, **k):
        ruta = str(ruta)
        if ruta == LOG:
            equipo = self

            class Registro(io.StringIO):
                def close(self):
                    equipo.log.append(self.getvalue())
                    super().close()

            return Registro()
        if ruta in (OSSEC_CONF, PERMITIDOS):
            assert modo == "r", f"{ruta} sólo se lee"
            if ruta not in self.archivos:
                raise FileNotFoundError(ruta)
            return io.StringIO(self.archivos[ruta])
        return _ABRIR(ruta, modo, *a, **k)

    # Consultas para las pruebas
    def cadena(self, fam="iptables"):
        return self.tablas[fam].get(CADENA)

    def aislado(self, fam):
        t = self.tablas[fam]
        return CADENA in t and ["-j", CADENA] in t["INPUT"] and ["-j", CADENA] in t["OUTPUT"]

    def limpio(self):
        """Sin cadena ni ganchos de Kronos, y con la regla ajena intacta."""
        return all(CADENA not in t and t["INPUT"] == [AJENA] and t["OUTPUT"] == [] for t in self.tablas.values())

    def cambios(self):
        return [c for c in self.comandos if c[0] in self.tablas and c[1] in ("-N", "-A", "-I", "-D", "-F", "-X")]


_ABRIR = builtins.open


def correr(entrada, equipo=None):
    """Corre el script con `entrada` en la entrada estándar. Devuelve (código, equipo)."""
    equipo = equipo or Equipo()
    if not isinstance(entrada, str):
        entrada = json.dumps({"version": 1, "command": "add", "parameters": {"extra_args": entrada}})
    with mock.patch("subprocess.run", equipo.run), \
         mock.patch("builtins.open", equipo.abrir), \
         mock.patch("socket.getaddrinfo", equipo.getaddrinfo), \
         mock.patch("sys.stdin", io.StringIO(entrada + "\n")):
        try:
            runpy.run_path(str(SCRIPT), run_name="__main__")
            codigo = 0
        except SystemExit as fin:
            codigo = fin.code
    return codigo, equipo


def aceptar_manager(ip):
    salida = [["-d", ip, "-p", "tcp", "--dport", p, "-j", "ACCEPT"] for p in ("1514", "1515")]
    respuesta = [["-s", ip, "-p", "tcp", "--sport", p, "-m", "conntrack", "--ctstate", "ESTABLISHED", "-j", "ACCEPT"]
                 for p in ("1514", "1515")]
    return salida + respuesta


LO = [["-i", "lo", "-j", "ACCEPT"], ["-o", "lo", "-j", "ACCEPT"]]
WT0 = [["-i", "wt0", "-j", "ACCEPT"], ["-o", "wt0", "-j", "ACCEPT"]]
DROP = [["-j", "DROP"]]


class Aplicar(unittest.TestCase):
    def test_aplicar_arma_la_cadena_en_orden_y_la_engancha_primero(self):
        eq = Equipo(permitidos="10.0.2.2  # NAT de VirtualBox: SSH del laboratorio\n")
        codigo, eq = correr(["aplicar"], eq)
        self.assertEqual(codigo, 0)
        admin = [["-s", "10.0.2.2/32", "-j", "ACCEPT"], ["-d", "10.0.2.2/32", "-j", "ACCEPT"]]
        self.assertEqual(eq.cadena(), LO + aceptar_manager(MANAGER) + admin + WT0 + DROP)
        for base in ("INPUT", "OUTPUT"):
            self.assertEqual(eq.tablas["iptables"][base][0], ["-j", CADENA], f"el gancho va primero en {base}")
        self.assertEqual(eq.tablas["iptables"]["INPUT"][1], AJENA, "la regla ajena sigue ahí")
        self.assertIn("aplicar OK; manager permitido: 203.0.113.10 TCP/1514,1515; administracion: 10.0.2.2/32",
                      eq.log[-1])

    def test_el_manager_queda_antes_del_drop(self):
        _, eq = correr(["aplicar"])
        cadena = eq.cadena()
        self.assertEqual(cadena[-1], ["-j", "DROP"])
        for regla in aceptar_manager(MANAGER):
            self.assertLess(cadena.index(regla), cadena.index(["-j", "DROP"]))

    def test_los_ganchos_se_ponen_con_la_cadena_ya_completa(self):
        _, eq = correr(["aplicar"])
        cambios = eq.cambios()
        primer_gancho = next(i for i, c in enumerate(cambios) if c[1] == "-I")
        ultimo_drop = max(i for i, c in enumerate(cambios) if c[1] == "-A" and c[-2:] == ["-j", "DROP"])
        self.assertLess(ultimo_drop, primer_gancho)

    def test_ipv6_solo_loopback_y_drop(self):
        _, eq = correr(["aplicar"])
        self.assertEqual(eq.cadena("ip6tables"), LO + DROP)
        self.assertTrue(eq.aislado("ip6tables"))

    def test_sin_permitidos_ni_wt0(self):
        codigo, eq = correr(["aplicar"], Equipo(netbird=False))
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cadena(), LO + aceptar_manager(MANAGER) + DROP)
        self.assertNotIn("wt0", json.dumps(eq.cadena()))
        self.assertIn("administracion: ninguna", eq.log[-1])

    def test_ya_aislado(self):
        _, eq = correr(["aplicar"])
        antes = json.dumps(eq.tablas)
        eq.comandos.clear()
        codigo, eq = correr(["aplicar"], eq)
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [])
        self.assertEqual(json.dumps(eq.tablas), antes)
        self.assertIn("aplicar OK (ya estaba aislado)", eq.log[-1])

    def test_cadena_a_medias_de_un_intento_anterior_se_rearma(self):
        eq = Equipo()
        eq.tablas["iptables"][CADENA] = [["-j", "DROP"]]  # existe, pero sin ganchos
        codigo, eq = correr(["aplicar"], eq)
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cadena()[:2], LO)
        self.assertTrue(eq.aislado("iptables") and eq.aislado("ip6tables"))

    def test_manager_por_nombre(self):
        conf = CONF_IP.replace(MANAGER, "manager.ejemplo.test")
        eq = Equipo(conf=conf, resolver={"manager.ejemplo.test": ["203.0.113.11", "203.0.113.12"]})
        codigo, eq = correr(["aplicar"], eq)
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cadena()[2:10], aceptar_manager("203.0.113.11") + aceptar_manager("203.0.113.12"))
        self.assertIn("manager permitido: 203.0.113.11,203.0.113.12 TCP/1514,1515", eq.log[-1])

    def test_ossec_conf_con_varios_bloques_raiz(self):
        conf = "<!-- agente -->\n" + CONF_IP + "<ossec_config>\n  <labels/>\n</ossec_config>\n"
        codigo, eq = correr(["aplicar"], Equipo(conf=conf))
        self.assertEqual(codigo, 0)
        self.assertTrue(eq.aislado("iptables"))


class Quitar(unittest.TestCase):
    def test_quitar_desengancha_y_borra_solo_la_cadena(self):
        _, eq = correr(["aplicar"])
        codigo, eq = correr(["quitar"], eq)
        self.assertEqual(codigo, 0)
        self.assertTrue(eq.limpio())
        self.assertIn("quitar OK; aislamiento quitado", eq.log[-1])

    def test_quitar_sin_aislar(self):
        codigo, eq = correr(["quitar"])
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [])
        self.assertTrue(eq.limpio())
        self.assertIn("quitar OK (no estaba aislado)", eq.log[-1])

    def test_quitar_no_necesita_ossec_conf(self):
        _, eq = correr(["aplicar"])
        eq.archivos.clear()
        codigo, eq = correr(["quitar"], eq)
        self.assertEqual(codigo, 0)
        self.assertTrue(eq.limpio())

    def test_fallo_al_quitar(self):
        _, eq = correr(["aplicar"])
        eq.falla = lambda cmd: cmd[1] == "-X"
        codigo, eq = correr(["quitar"], eq)
        self.assertEqual(codigo, 1)
        self.assertIn("ERROR al quitar el aislamiento", eq.log[-1])


class Rechazos(unittest.TestCase):
    def assertRechazada(self, entrada, texto, equipo=None):
        codigo, eq = correr(entrada, equipo)
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.cambios(), [], "no se toca el firewall")
        self.assertTrue(eq.limpio())
        self.assertIn(texto, eq.log[-1])

    def test_sin_argumentos(self):
        self.assertRechazada([], "entrada invalida: se esperaba 1 argumento y llegaron 0")

    def test_dos_argumentos(self):
        self.assertRechazada(["aplicar", "203.0.113.50"], "entrada invalida: se esperaba 1 argumento y llegaron 2")

    def test_argumento_que_no_es_texto(self):
        self.assertRechazada([1], "entrada invalida: se esperaba 1 argumento")

    def test_operacion_desconocida(self):
        self.assertRechazada(["borrar"], "entrada invalida: operacion desconocida: borrar")

    def test_json_roto(self):
        self.assertRechazada("{roto", "entrada invalida")

    def test_ossec_conf_sin_manager(self):
        conf = "<ossec_config>\n  <client>\n    <config-profile>ubuntu</config-profile>\n  </client>\n</ossec_config>\n"
        self.assertRechazada(["aplicar"], "ERROR no se pudo leer el manager", Equipo(conf=conf))

    def test_sin_ossec_conf(self):
        self.assertRechazada(["aplicar"], "ERROR no se pudo leer el manager", Equipo(conf=None))

    def test_ossec_conf_roto(self):
        self.assertRechazada(["aplicar"], "ERROR no se pudo leer el manager", Equipo(conf="<ossec_config><client>"))

    def test_manager_por_nombre_que_no_resuelve(self):
        conf = CONF_IP.replace(MANAGER, "noexiste.ejemplo.test")
        self.assertRechazada(["aplicar"], "ERROR no se pudo leer el manager", Equipo(conf=conf))

    def test_manager_ipv6(self):
        conf = CONF_IP.replace(MANAGER, "2001:db8::10")
        self.assertRechazada(["aplicar"], "es IPv6", Equipo(conf=conf))

    def test_manager_con_caracteres_raros(self):
        conf = CONF_IP.replace(MANAGER, "manager;id")
        self.assertRechazada(["aplicar"], "direccion del manager no valida", Equipo(conf=conf))

    def test_permitidos_con_linea_invalida(self):
        eq = Equipo(permitidos="10.0.2.2  # NAT\nesto-no-es-una-ip\n")
        self.assertRechazada(["aplicar"], f"ERROR direcciones de administracion: {PERMITIDOS}, linea 2", eq)

    def test_permitidos_con_toda_la_red(self):
        self.assertRechazada(["aplicar"], "nunca /0", Equipo(permitidos="0.0.0.0/0\n"))

    def test_permitidos_ipv6(self):
        self.assertRechazada(["aplicar"], "solo redes IPv4", Equipo(permitidos="2001:db8::/64\n"))


class Fallos(unittest.TestCase):
    def test_fallo_a_mitad_de_aplicar_se_deshace(self):
        # Falla el gancho de OUTPUT en IPv6, el último paso: todo lo anterior ya estaba hecho.
        eq = Equipo(falla=lambda cmd: cmd[:3] == ["ip6tables", "-I", "OUTPUT"])
        codigo, eq = correr(["aplicar"], eq)
        self.assertEqual(codigo, 1)
        self.assertTrue(eq.limpio(), "sin cadenas ni ganchos de Kronos, y la regla ajena intacta")
        self.assertIn("ERROR al aislar: ip6tables -I OUTPUT 1 -j KRONOS-AISLAR (codigo 1)", eq.log[-1])
        self.assertIn("se deshizo lo aplicado", eq.log[-1])

    def test_fallo_al_armar_la_cadena_no_deja_ganchos(self):
        eq = Equipo(falla=lambda cmd: cmd[:2] == ["iptables", "-A"] and cmd[-1] == "DROP")
        codigo, eq = correr(["aplicar"], eq)
        self.assertEqual(codigo, 1)
        self.assertTrue(eq.limpio())
        self.assertFalse([c for c in eq.comandos if c[1] == "-I"], "nunca se llegó a enganchar")

    def test_si_no_se_puede_deshacer_lo_dice(self):
        eq = Equipo(falla=lambda cmd: cmd[:3] == ["ip6tables", "-I", "OUTPUT"] or (cmd[1] == "-X" and cmd[0] == "iptables"))
        codigo, eq = correr(["aplicar"], eq)
        self.assertEqual(codigo, 1)
        self.assertIn("NO se pudo deshacer", eq.log[-1])


if __name__ == "__main__":
    unittest.main()
