"""Pruebas de kronos-limitar-conexiones para Linux (infra/wazuh/active-response/linux).

El script se ejecuta completo en el mismo proceso (runpy), con `ip`, `hostname`,
`iptables`, ossec.conf y la resolución de nombres simulados: no toca el
firewall ni necesita root.
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
    / "infra" / "wazuh" / "active-response" / "linux" / "kronos-limitar-conexiones"
)

PROPIA = "192.0.2.10"
PUERTA = "192.0.2.1"
DNS = "192.0.2.53"
MANAGER = "203.0.113.10"
IP = "198.51.100.66"

OSSEC = f"""<ossec_config>
  <client>
    <server>
      <address>{MANAGER}</address>
      <port>1514</port>
    </server>
  </client>
</ossec_config>
"""


class Equipo:
    """Simula los comandos y archivos que usa el script y guarda lo que pasa."""

    def __init__(self, reglas=(), ossec=OSSEC, resolv=f"nameserver {DNS}\n",
                 ruta4_falla=False, nombres=None):
        self.reglas = set(reglas)
        self.ossec = ossec
        self.resolv = resolv
        self.ruta4_falla = ruta4_falla
        self.nombres = nombres or {}
        self.comandos = []
        self.log = []

    def run(self, cmd, **_):
        self.comandos.append(cmd)
        ok = subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[:2] == ["hostname", "-I"]:
            return subprocess.CompletedProcess(cmd, 0, f"{PROPIA} \n", "")
        if cmd[:2] == ["ip", "-j"]:
            if cmd[2] == "-4":
                if self.ruta4_falla:
                    return subprocess.CompletedProcess(cmd, 1, "", "error")
                ruta = [{"dst": "default", "gateway": PUERTA}]
                return subprocess.CompletedProcess(cmd, 0, json.dumps(ruta), "")
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        if cmd[0] in ("iptables", "ip6tables"):
            self.cadena = cmd[2]
            ip = cmd[4]  # iptables -C|-I|-D INPUT -s <ip> ...
            if cmd[1] == "-C":
                return subprocess.CompletedProcess(cmd, 0 if ip in self.reglas else 1, "", "")
            if cmd[1] == "-I":
                self.reglas.add(ip)
                return ok
            if cmd[1] == "-D":
                self.reglas.discard(ip)
                return ok
        raise AssertionError(f"comando inesperado: {cmd}")

    def abrir(self, ruta, modo="r", *a, **k):
        ruta = str(ruta)
        if ruta == "/var/ossec/logs/active-responses.log":
            equipo = self

            class Registro(io.StringIO):
                def close(self):
                    equipo.log.append(self.getvalue())
                    super().close()

            return Registro()
        if ruta == "/var/ossec/etc/ossec.conf":
            if self.ossec is None:
                raise PermissionError(ruta)
            return io.StringIO(self.ossec)
        if ruta == "/etc/resolv.conf":
            return io.StringIO(self.resolv)
        if ruta == "/run/systemd/resolve/resolv.conf":
            raise FileNotFoundError(ruta)
        return _ABRIR(ruta, modo, *a, **k)

    def resolver(self, nombre, *_a, **_k):
        if nombre not in self.nombres:
            raise socket.gaierror("no resuelve")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in self.nombres[nombre]]


_ABRIR = builtins.open


def correr(entrada, equipo=None):
    """Corre el script con `entrada` en la entrada estándar. Devuelve (código, equipo)."""
    equipo = equipo or Equipo()
    if not isinstance(entrada, str):
        entrada = json.dumps({"version": 1, "command": "add", "parameters": {"extra_args": entrada}})
    with mock.patch("subprocess.run", equipo.run), \
         mock.patch("builtins.open", equipo.abrir), \
         mock.patch("socket.getaddrinfo", equipo.resolver), \
         mock.patch("sys.stdin", io.StringIO(entrada + "\n")):
        try:
            runpy.run_path(str(SCRIPT), run_name="__main__")
            codigo = 0
        except SystemExit as fin:
            codigo = fin.code
    return codigo, equipo


def iptables(equipo, accion):
    return [c for c in equipo.comandos if c[0] in ("iptables", "ip6tables") and c[1] == accion]


class AplicarYQuitar(unittest.TestCase):
    def test_aplicar_inserta_el_limite_de_conexiones(self):
        codigo, eq = correr(["aplicar", IP])
        self.assertEqual(codigo, 0)
        self.assertIn(IP, eq.reglas)
        self.assertEqual(
            iptables(eq, "-I"),
            [["iptables", "-I", "INPUT", "-s", IP, "-p", "tcp", "--syn", "-m", "connlimit",
              "--connlimit-above", "10", "-m", "comment", "--comment", "kronos", "-j", "DROP"]],
        )
        self.assertIn(f"aplicar {IP}: OK", eq.log[-1])

    def test_aplicar_dos_veces_no_duplica(self):
        codigo, eq = correr(["aplicar", IP], Equipo(reglas={IP}))
        self.assertEqual(codigo, 0)
        self.assertEqual(iptables(eq, "-I"), [])
        self.assertIn("sin cambios (ya estaba)", eq.log[-1])

    def test_quitar_borra_la_regla(self):
        codigo, eq = correr(["quitar", IP], Equipo(reglas={IP}))
        self.assertEqual(codigo, 0)
        self.assertNotIn(IP, eq.reglas)
        self.assertIn(f"quitar {IP}: OK", eq.log[-1])

    def test_quitar_sin_regla_dice_no_estaba(self):
        codigo, eq = correr(["quitar", IP])
        self.assertEqual(codigo, 0)
        self.assertEqual(iptables(eq, "-D"), [])
        self.assertIn("sin cambios (no estaba)", eq.log[-1])

    def test_ipv6_usa_ip6tables(self):
        codigo, eq = correr(["aplicar", "2001:db8::66"])
        self.assertEqual(codigo, 0)
        self.assertEqual(iptables(eq, "-I")[0][0], "ip6tables")

    def test_manager_por_nombre_se_resuelve(self):
        ossec = OSSEC.replace(MANAGER, "wazuh.lab")
        codigo, eq = correr(["aplicar", IP], Equipo(ossec=ossec, nombres={"wazuh.lab": [MANAGER]}))
        self.assertEqual(codigo, 0)
        self.assertIn(IP, eq.reglas)


class Rechazos(unittest.TestCase):
    def rechaza(self, args, texto, equipo=None):
        codigo, eq = correr(args, equipo)
        self.assertEqual(codigo, 1)
        self.assertEqual(iptables(eq, "-I") + iptables(eq, "-D"), [])
        self.assertIn(texto, eq.log[-1])
        return eq

    def test_el_manager(self):
        self.rechaza(["aplicar", MANAGER], "es el manager de Wazuh")

    def test_el_manager_por_nombre(self):
        ossec = OSSEC.replace(MANAGER, "wazuh.lab")
        self.rechaza(["aplicar", MANAGER], "es el manager de Wazuh",
                     Equipo(ossec=ossec, nombres={"wazuh.lab": [MANAGER]}))

    def test_sin_poder_leer_ossec_conf_no_actua(self):
        self.rechaza(["aplicar", IP], "no se pudo leer la direccion del manager",
                     Equipo(ossec=None))

    def test_ossec_conf_sin_servidor_no_actua(self):
        self.rechaza(["aplicar", IP], "no se pudo leer la direccion del manager",
                     Equipo(ossec="<ossec_config></ossec_config>"))

    def test_nombre_del_manager_que_no_resuelve_no_actua(self):
        ossec = OSSEC.replace(MANAGER, "wazuh.lab")
        self.rechaza(["aplicar", IP], "no se pudo leer la direccion del manager",
                     Equipo(ossec=ossec))

    def test_un_servidor_dns_si_se_puede_limitar(self):
        codigo, eq = correr(["aplicar", DNS])
        self.assertEqual(codigo, 0)
        self.assertIn(DNS, eq.reglas)

    def test_red_de_netbird(self):
        self.rechaza(["aplicar", "100.90.12.34"], "red de NetBird")

    def test_puerta_de_enlace(self):
        self.rechaza(["aplicar", PUERTA], "es la puerta de enlace")

    def test_sin_poder_leer_la_puerta_no_actua(self):
        self.rechaza(["aplicar", IP], "no se pudo leer la puerta de enlace",
                     Equipo(ruta4_falla=True))

    def test_ip_propia(self):
        self.rechaza(["aplicar", PROPIA], "es del propio equipo")

    def test_loopback_multicast_y_enlace_local(self):
        for ip in ("127.0.0.1", "0.0.0.0", "224.0.0.1", "169.254.1.1", "::1", "fe80::1"):
            with self.subTest(ip=ip):
                self.rechaza(["aplicar", ip], "no es un origen externo")

    def test_quitar_tambien_valida(self):
        self.rechaza(["quitar", MANAGER], "es el manager de Wazuh")

    def test_cantidad_de_argumentos(self):
        for args in ([], ["aplicar"], ["aplicar", IP, "extra"]):
            with self.subTest(args=args):
                self.rechaza(args, "se esperaban 2 argumentos")

    def test_argumento_que_no_es_texto(self):
        self.rechaza(["aplicar", 1], "se esperaban 2 argumentos")

    def test_ip_invalida(self):
        self.rechaza(["aplicar", "198.51.100.66; reboot"], "entrada invalida")

    def test_ip_no_canonica(self):
        self.rechaza(["aplicar", "2001:DB8::66"], "IP no canonica")

    def test_operacion_no_permitida(self):
        self.rechaza(["borrar", IP], "operacion invalida")

    def test_json_roto(self):
        self.rechaza("{no es json", "entrada invalida")


if __name__ == "__main__":
    unittest.main()
