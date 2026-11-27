"""Pruebas del script de Active Response para Linux (infra/wazuh/active-response/linux).

El script se ejecuta completo en el mismo proceso (runpy), con `ip`, `hostname` e
`iptables` simulados y el registro capturado: no toca el firewall ni necesita root.
"""

from __future__ import annotations

import builtins
import io
import json
import runpy
import subprocess
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "infra" / "wazuh" / "active-response" / "linux" / "kronos-bloquear-ip"
)

PROPIA = "192.0.2.10"
PUERTA = "192.0.2.1"
IP = "203.0.113.50"


class Equipo:
    """Simula los comandos que usa el script y guarda lo que pasa."""

    def __init__(self, reglas=(), ruta4=None, ruta4_falla=False, ruta6_falla=False):
        self.reglas = set(reglas)
        self.ruta4 = [{"dst": "default", "gateway": PUERTA}] if ruta4 is None else ruta4
        self.ruta4_falla = ruta4_falla
        self.ruta6_falla = ruta6_falla
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
                return subprocess.CompletedProcess(cmd, 0, json.dumps(self.ruta4), "")
            if self.ruta6_falla:
                return subprocess.CompletedProcess(cmd, 2, "", "Address family not supported")
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        if cmd[0] in ("iptables", "ip6tables"):
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
        if str(ruta) == "/var/ossec/logs/active-responses.log":
            equipo = self

            class Registro(io.StringIO):
                def close(self):
                    equipo.log.append(self.getvalue())
                    super().close()

            return Registro()
        return _ABRIR(ruta, modo, *a, **k)


_ABRIR = builtins.open


def correr(entrada, equipo=None):
    """Corre el script con `entrada` en la entrada estándar. Devuelve (código, equipo)."""
    equipo = equipo or Equipo()
    if not isinstance(entrada, str):
        entrada = json.dumps({"version": 1, "command": "add", "parameters": {"extra_args": entrada}})
    with mock.patch("subprocess.run", equipo.run), \
         mock.patch("builtins.open", equipo.abrir), \
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
    def test_aplicar_inserta_la_regla(self):
        codigo, eq = correr(["aplicar", IP])
        self.assertEqual(codigo, 0)
        self.assertIn(IP, eq.reglas)
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
        codigo, eq = correr(["aplicar", "2001:db8::50"])
        self.assertEqual(codigo, 0)
        self.assertEqual(iptables(eq, "-I")[0][0], "ip6tables")

    def test_equipo_sin_ipv6_igual_actua(self):
        codigo, eq = correr(["aplicar", IP], Equipo(ruta6_falla=True))
        self.assertEqual(codigo, 0)
        self.assertIn(IP, eq.reglas)


class Rechazos(unittest.TestCase):
    def assertRechazada(self, entrada, texto, equipo=None):
        codigo, eq = correr(entrada, equipo)
        self.assertEqual(codigo, 1)
        self.assertEqual(iptables(eq, "-I") + iptables(eq, "-D"), [])
        self.assertIn(texto, eq.log[-1])

    def test_puerta_de_enlace(self):
        self.assertRechazada(["aplicar", PUERTA], "es la puerta de enlace")

    def test_puerta_de_enlace_ipv6(self):
        eq = Equipo()
        original = eq.run

        def run(cmd, **k):
            if cmd[:3] == ["ip", "-j", "-6"]:
                return subprocess.CompletedProcess(cmd, 0, json.dumps([{"gateway": "fe80::1%eth0"}]), "")
            return original(cmd, **k)

        eq.run = run
        self.assertRechazada(["aplicar", "fe80::1"], "es la puerta de enlace", eq)

    def test_sin_poder_leer_la_puerta_no_actua(self):
        self.assertRechazada(["aplicar", IP], "no se pudo leer la puerta de enlace", Equipo(ruta4_falla=True))

    def test_ip_propia(self):
        self.assertRechazada(["aplicar", PROPIA], "es del propio equipo")

    def test_loopback(self):
        self.assertRechazada(["aplicar", "127.0.0.1"], "es del propio equipo")

    def test_no_especificada(self):
        self.assertRechazada(["aplicar", "0.0.0.0"], "es del propio equipo")

    def test_tres_argumentos(self):
        self.assertRechazada(["aplicar", IP, "extra"], "se esperaban 2 argumentos y llegaron 3")

    def test_un_argumento(self):
        self.assertRechazada(["aplicar"], "se esperaban 2 argumentos y llegaron 1")

    def test_argumento_que_no_es_texto(self):
        self.assertRechazada(["aplicar", 7], "se esperaban 2 argumentos")

    def test_ip_invalida(self):
        self.assertRechazada(["aplicar", "203.0.113.50 & calc"], "entrada invalida")

    def test_ip_no_canonica(self):
        self.assertRechazada(["aplicar", "1"], "entrada invalida")

    def test_operacion_no_permitida(self):
        self.assertRechazada(["borrar", IP], "operacion invalida")

    def test_json_roto(self):
        self.assertRechazada("{roto", "entrada invalida")


if __name__ == "__main__":
    unittest.main()
