"""Pruebas de kronos-deshabilitar-cuenta, el script de Active Response para Linux.

El script se ejecuta completo en el mismo proceso (runpy), con `passwd`, `getent`, `usermod`
y `chage` simulados, `pwd` reemplazado (no existe en Windows) y el registro capturado: no
toca ninguna cuenta ni necesita root.
"""

from __future__ import annotations

import builtins
import io
import json
import runpy
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "infra" / "wazuh" / "active-response" / "linux" / "kronos-deshabilitar-cuenta"
)

CUENTA = "usuario.demo"


class Equipo:
    """Simula las cuentas y los comandos que usa el script, y guarda lo que pasa."""

    def __init__(self, cuentas=None, falla=None):
        # nombre -> {"uid", "bloqueada", "vencida"}
        self.cuentas = cuentas if cuentas is not None else {
            CUENTA: {"uid": 1001, "bloqueada": False, "vencida": False},
            "labadmin": {"uid": 1000, "bloqueada": False, "vencida": False},
            "root": {"uid": 0, "bloqueada": False, "vencida": False},
            "systemd-network": {"uid": 998, "bloqueada": False, "vencida": False},
        }
        self.falla = falla  # (comando, opción) que devuelve error, por ejemplo ("usermod", "-L")
        self.comandos = []
        self.log = []

    def run(self, cmd, **opciones):
        assert isinstance(cmd, list), f"el comando debe ser una lista: {cmd!r}"
        assert not opciones.get("shell"), "nunca shell=True"
        self.comandos.append(cmd)
        if self.falla and tuple(cmd[:2]) == self.falla:
            return subprocess.CompletedProcess(cmd, 1, "", f"{cmd[0]}: fallo simulado")
        nombre = cmd[-1]
        c = self.cuentas[nombre]
        if cmd[:2] == ["passwd", "-S"]:
            marca = "L" if c["bloqueada"] else "P"
            return subprocess.CompletedProcess(cmd, 0, f"{nombre} {marca} 2026-11-03 0 99999 7 -1\n", "")
        if cmd[:2] == ["getent", "shadow"]:
            clave = ("!" if c["bloqueada"] else "") + "$6$sal$resumen"
            vence = "0" if c["vencida"] else ""
            return subprocess.CompletedProcess(cmd, 0, f"{nombre}:{clave}:20395:0:99999:7::{vence}:\n", "")
        if cmd[:2] == ["usermod", "-L"]:
            c["bloqueada"] = True
        elif cmd[:2] == ["usermod", "-U"]:
            c["bloqueada"] = False
        elif cmd[:3] == ["chage", "-E", "0"]:
            c["vencida"] = True
        elif cmd[:3] == ["chage", "-E", "-1"]:
            c["vencida"] = False
        else:
            raise AssertionError(f"comando inesperado: {cmd}")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def getpwnam(self, nombre):
        if nombre not in self.cuentas:
            raise KeyError(f"getpwnam(): name not found: '{nombre}'")
        return types.SimpleNamespace(pw_name=nombre, pw_uid=self.cuentas[nombre]["uid"])

    def abrir(self, ruta, modo="r", *a, **k):
        if str(ruta) == "/var/ossec/logs/active-responses.log":
            equipo = self

            class Registro(io.StringIO):
                def close(self):
                    equipo.log.append(self.getvalue())
                    super().close()

            return Registro()
        return _ABRIR(ruta, modo, *a, **k)

    def cambios(self):
        """Los comandos que cambian una cuenta (usermod y chage)."""
        return [c for c in self.comandos if c[0] in ("usermod", "chage")]


_ABRIR = builtins.open


def correr(entrada, equipo=None):
    """Corre el script con `entrada` en la entrada estándar. Devuelve (código, equipo)."""
    equipo = equipo or Equipo()
    if not isinstance(entrada, str):
        entrada = json.dumps({"version": 1, "command": "add", "parameters": {"extra_args": entrada}})
    pwd = types.ModuleType("pwd")
    pwd.getpwnam = equipo.getpwnam
    with mock.patch("subprocess.run", equipo.run), \
         mock.patch("builtins.open", equipo.abrir), \
         mock.patch.dict(sys.modules, {"pwd": pwd}), \
         mock.patch("sys.stdin", io.StringIO(entrada + "\n")):
        try:
            runpy.run_path(str(SCRIPT), run_name="__main__")
            codigo = 0
        except SystemExit as fin:
            codigo = fin.code
    return codigo, equipo


def equipo_con(bloqueada, vencida):
    eq = Equipo()
    eq.cuentas[CUENTA].update(bloqueada=bloqueada, vencida=vencida)
    return eq


class AplicarYHabilitar(unittest.TestCase):
    def test_aplicar_bloquea_y_vence(self):
        codigo, eq = correr(["aplicar", CUENTA])
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [["usermod", "-L", CUENTA], ["chage", "-E", "0", CUENTA]])
        self.assertTrue(eq.cuentas[CUENTA]["bloqueada"] and eq.cuentas[CUENTA]["vencida"])
        self.assertIn(f"kronos-deshabilitar-cuenta: aplicar {CUENTA} OK\n", eq.log[-1])

    def test_aplicar_sin_cambios_si_ya_estaba_deshabilitada(self):
        codigo, eq = correr(["aplicar", CUENTA], equipo_con(bloqueada=True, vencida=True))
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [])
        self.assertIn(f"aplicar {CUENTA} OK (sin cambios: ya estaba deshabilitada)", eq.log[-1])

    def test_aplicar_sobre_cuenta_bloqueada_solo_la_vence(self):
        codigo, eq = correr(["aplicar", CUENTA], equipo_con(bloqueada=True, vencida=False))
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [["chage", "-E", "0", CUENTA]])

    def test_habilitar_desbloquea_y_quita_el_vencimiento(self):
        codigo, eq = correr(["habilitar", CUENTA], equipo_con(bloqueada=True, vencida=True))
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [["usermod", "-U", CUENTA], ["chage", "-E", "-1", CUENTA]])
        self.assertFalse(eq.cuentas[CUENTA]["bloqueada"] or eq.cuentas[CUENTA]["vencida"])
        self.assertIn(f"habilitar {CUENTA} OK\n", eq.log[-1])

    def test_habilitar_sin_cambios_si_ya_estaba_habilitada(self):
        codigo, eq = correr(["habilitar", CUENTA])
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [])
        self.assertIn(f"habilitar {CUENTA} OK (sin cambios: ya estaba habilitada)", eq.log[-1])

    def test_aplicar_y_habilitar_dejan_la_cuenta_como_estaba(self):
        _, eq = correr(["aplicar", CUENTA])
        codigo, eq = correr(["habilitar", CUENTA], eq)
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cuentas[CUENTA], {"uid": 1001, "bloqueada": False, "vencida": False})

    def test_registro_con_hora_utc(self):
        _, eq = correr(["aplicar", CUENTA])
        self.assertRegex(eq.log[-1], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z kronos-deshabilitar-cuenta: ")


class Rechazos(unittest.TestCase):
    def assertRechazada(self, entrada, texto, equipo=None):
        codigo, eq = correr(entrada, equipo)
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.cambios(), [])
        self.assertIn(texto, eq.log[-1])

    def test_un_argumento(self):
        self.assertRechazada(["aplicar"], "entrada invalida: se esperaban 2 argumentos y llegaron 1")

    def test_tres_argumentos(self):
        self.assertRechazada(["aplicar", CUENTA, "extra"], "entrada invalida: se esperaban 2 argumentos y llegaron 3")

    def test_argumento_que_no_es_texto(self):
        self.assertRechazada(["aplicar", 1001], "entrada invalida: se esperaban 2 argumentos")

    def test_operacion_desconocida(self):
        self.assertRechazada(["borrar", CUENTA], "entrada invalida: operacion desconocida: borrar")

    def test_cuenta_con_caracteres_invalidos(self):
        self.assertRechazada(["aplicar", "usuario.demo; id"], "entrada invalida: nombre de cuenta no permitido")

    def test_cuenta_con_salto_de_linea_al_final(self):
        self.assertRechazada(["aplicar", CUENTA + "\n"], "entrada invalida: nombre de cuenta no permitido")

    def test_cuenta_de_mas_de_32_caracteres(self):
        self.assertRechazada(["aplicar", "a" * 33], "entrada invalida: nombre de cuenta no permitido")

    def test_cuenta_inexistente(self):
        self.assertRechazada(["aplicar", "noexiste01"], "ERROR no existe la cuenta local: noexiste01")

    def test_root(self):
        self.assertRechazada(["aplicar", "root"], "cuenta protegida: root")

    def test_labadmin(self):
        self.assertRechazada(["aplicar", "labadmin"], "cuenta protegida: labadmin")

    def test_nobody_aunque_su_uid_sea_alto(self):
        eq = Equipo()
        eq.cuentas["nobody"] = {"uid": 65534, "bloqueada": False, "vencida": False}
        self.assertRechazada(["aplicar", "nobody"], "cuenta protegida: nobody", eq)

    def test_uid_menor_que_1000(self):
        self.assertRechazada(["aplicar", "systemd-network"], "cuenta protegida: systemd-network")

    def test_habilitar_una_cuenta_protegida_tampoco(self):
        self.assertRechazada(["habilitar", "root"], "cuenta protegida: root")

    def test_json_roto(self):
        self.assertRechazada("{roto", "entrada invalida")


class Fallos(unittest.TestCase):
    def test_fallo_de_usermod(self):
        codigo, eq = correr(["aplicar", CUENTA], Equipo(falla=("usermod", "-L")))
        self.assertEqual(codigo, 1)
        self.assertIn(f"ERROR usermod -L {CUENTA} (codigo 1): usermod: fallo simulado", eq.log[-1])
        self.assertNotIn(["chage", "-E", "0", CUENTA], eq.comandos)

    def test_fallo_al_leer_el_estado(self):
        codigo, eq = correr(["aplicar", CUENTA], Equipo(falla=("passwd", "-S")))
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.cambios(), [])
        self.assertIn("ERROR passwd -S", eq.log[-1])


if __name__ == "__main__":
    unittest.main()
