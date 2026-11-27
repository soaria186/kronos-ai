"""Pruebas de kronos-cerrar-sesion, el script de Active Response para Linux.

El script se ejecuta completo en el mismo proceso (runpy), con `loginctl` simulado, `pwd` y
`grp` reemplazados (no existen en Windows) y el registro capturado: no cierra ninguna sesión
ni necesita root.
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
    / "infra" / "wazuh" / "active-response" / "linux" / "kronos-cerrar-sesion"
)

LOG = "/var/ossec/logs/active-responses.log"
CUENTA = "usuario.demo"
UID = 1001

_ABRIR = builtins.open


class Equipo:
    """Simula las cuentas, los grupos y `loginctl`, y guarda lo que pasa."""

    def __init__(self, sesiones=2, cuentas=None, grupos=None, falla=None):
        # nombre -> (uid, gid)
        self.cuentas = {CUENTA: (UID, UID), "labadmin": (1000, 1000), "root": (0, 0), "daemon": (1, 1)}
        self.cuentas.update(cuentas or {})
        self.grupos = {"sudo": (27, ["labadmin"])} if grupos is None else grupos
        self.sesiones = {UID: sesiones}
        self.falla = falla  # "show-user" o "terminate-user": loginctl devuelve un error inesperado
        self.comandos = []
        self.log = []

    def run(self, cmd, **opciones):
        assert isinstance(cmd, list), f"el comando debe ser una lista: {cmd!r}"
        assert not opciones.get("shell"), "nunca shell=True"
        assert cmd[0] == "loginctl", f"comando inesperado: {cmd}"
        self.comandos.append(cmd)
        uid = int(cmd[2])
        if self.falla == cmd[1]:
            return subprocess.CompletedProcess(cmd, 1, "", "Failed: Access denied")
        if cmd[1] == "show-user":
            n = self.sesiones.get(uid, 0)
            if n == 0:
                return subprocess.CompletedProcess(
                    cmd, 1, "", f"Failed to get user: User ID {uid} is not logged in or lingering")
            return subprocess.CompletedProcess(cmd, 0, " ".join(str(10 + i) for i in range(n)) + "\n", "")
        if cmd[1] == "terminate-user":
            self.sesiones[uid] = 0
            return subprocess.CompletedProcess(cmd, 0, "", "")
        raise AssertionError(f"comando inesperado: {cmd}")

    def getpwnam(self, nombre):
        if nombre not in self.cuentas:
            raise KeyError(nombre)
        uid, gid = self.cuentas[nombre]
        return types.SimpleNamespace(pw_name=nombre, pw_uid=uid, pw_gid=gid)

    def getgrnam(self, nombre):
        if nombre not in self.grupos:
            raise KeyError(nombre)
        gid, miembros = self.grupos[nombre]
        return types.SimpleNamespace(gr_name=nombre, gr_gid=gid, gr_mem=list(miembros))

    def abrir(self, ruta, modo="r", *a, **k):
        if str(ruta) == LOG:
            equipo = self

            class Archivo(io.StringIO):
                def close(self):
                    equipo.log.append(self.getvalue())
                    super().close()

            return Archivo()
        return _ABRIR(ruta, modo, *a, **k)

    def cierres(self):
        return [c for c in self.comandos if c[1] == "terminate-user"]


def correr(entrada, equipo=None):
    """Corre el script con `entrada` en la entrada estándar. Devuelve (código, equipo)."""
    equipo = equipo or Equipo()
    if not isinstance(entrada, str):
        entrada = json.dumps({"version": 1, "command": "add", "parameters": {"extra_args": entrada}})
    pwd = types.ModuleType("pwd")
    pwd.getpwnam = equipo.getpwnam
    grp = types.ModuleType("grp")
    grp.getgrnam = equipo.getgrnam
    with mock.patch("subprocess.run", equipo.run), \
         mock.patch("builtins.open", equipo.abrir), \
         mock.patch.dict(sys.modules, {"pwd": pwd, "grp": grp}), \
         mock.patch("sys.stdin", io.StringIO(entrada + "\n")):
        try:
            runpy.run_path(str(SCRIPT), run_name="__main__")
            codigo = 0
        except SystemExit as fin:
            codigo = fin.code
    return codigo, equipo


class Aplicar(unittest.TestCase):
    def test_cierra_las_sesiones(self):
        codigo, eq = correr(["aplicar", CUENTA])
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cierres(), [["loginctl", "terminate-user", str(UID)]])
        self.assertEqual(eq.sesiones[UID], 0)
        self.assertIn(f"kronos-cerrar-sesion: aplicar {CUENTA} OK (2 sesion(es) cerrada(s))", eq.log[-1])

    def test_sin_sesiones_no_hace_nada(self):
        codigo, eq = correr(["aplicar", CUENTA], Equipo(sesiones=0))
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cierres(), [])
        self.assertIn("sin cambios: no tenia sesiones abiertas", eq.log[-1])

    def test_dos_veces_es_idempotente(self):
        eq = Equipo()
        self.assertEqual(correr(["aplicar", CUENTA], eq)[0], 0)
        self.assertEqual(correr(["aplicar", CUENTA], eq)[0], 0)
        self.assertEqual(len(eq.cierres()), 1)

    def test_falla_terminate_user(self):
        codigo, eq = correr(["aplicar", CUENTA], Equipo(falla="terminate-user"))
        self.assertEqual(codigo, 1)
        self.assertIn("ERROR loginctl terminate-user", eq.log[-1])

    def test_error_inesperado_al_leer_sesiones_no_actua(self):
        codigo, eq = correr(["aplicar", CUENTA], Equipo(falla="show-user"))
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.cierres(), [])
        self.assertIn("ERROR loginctl show-user", eq.log[-1])

    def test_registro_con_hora_utc(self):
        _, eq = correr(["aplicar", CUENTA])
        self.assertRegex(eq.log[-1], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z kronos-cerrar-sesion: ")


class Protegidas(unittest.TestCase):
    def test_por_nombre(self):
        for nombre in ("root", "labadmin", "nobody"):
            with self.subTest(nombre=nombre):
                codigo, eq = correr(["aplicar", nombre], Equipo(cuentas={"nobody": (65534, 65534)}))
                self.assertEqual(codigo, 1)
                self.assertEqual(eq.comandos, [])
                self.assertIn("cuenta protegida", eq.log[-1])

    def test_uid_menor_que_1000(self):
        codigo, eq = correr(["aplicar", "daemon"])
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.comandos, [])

    def test_administrador_por_sudo_y_por_wheel(self):
        for grupos in ({"sudo": (27, ["ana"])}, {"wheel": (10, ["ana"])}, {"admin": (1500, [])}):
            with self.subTest(grupos=grupos):
                gid = 1500 if "admin" in grupos else 1600
                eq = Equipo(cuentas={"ana": (1600, gid)}, grupos=grupos)
                codigo, eq = correr(["aplicar", "ana"], eq)
                self.assertEqual(codigo, 1)
                self.assertEqual(eq.comandos, [])
                self.assertIn("cuenta protegida: ana (administrador)", eq.log[-1])

    def test_grupo_inexistente_se_ignora(self):
        codigo, eq = correr(["aplicar", CUENTA], Equipo(grupos={}))
        self.assertEqual(codigo, 0)
        self.assertEqual(len(eq.cierres()), 1)


class Entrada(unittest.TestCase):
    def test_cuenta_inexistente(self):
        codigo, eq = correr(["aplicar", "nadie"])
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.comandos, [])
        self.assertIn("ERROR no existe la cuenta local: nadie", eq.log[-1])

    def test_no_hay_operacion_inversa(self):
        for op in ("habilitar", "quitar", "revertir"):
            with self.subTest(op=op):
                codigo, eq = correr([op, CUENTA])
                self.assertEqual(codigo, 1)
                self.assertIn("esta medida no se revierte", eq.log[-1])

    def test_cantidad_de_argumentos(self):
        for args in (["aplicar"], ["aplicar", CUENTA, "extra"]):
            with self.subTest(args=args):
                codigo, eq = correr(args)
                self.assertEqual(codigo, 1)
                self.assertEqual(eq.comandos, [])

    def test_nombres_no_permitidos(self):
        for nombre in ("usuario;id", "usuario demo", "usuario.demo\n", "a" * 33, "*"):
            with self.subTest(nombre=nombre):
                codigo, eq = correr(["aplicar", nombre])
                self.assertEqual(codigo, 1)
                self.assertEqual(eq.comandos, [])

    def test_argumento_que_no_es_texto(self):
        codigo, eq = correr(["aplicar", 1001])
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.comandos, [])

    def test_json_roto(self):
        codigo, eq = correr("{no es json")
        self.assertEqual(codigo, 1)
        self.assertIn("entrada invalida", eq.log[-1])


if __name__ == "__main__":
    unittest.main()
