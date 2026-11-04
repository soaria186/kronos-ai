"""Pruebas de kronos-deshabilitar-cuenta, el script de Active Response para Linux.

El script se ejecuta completo en el mismo proceso (runpy), con `passwd`, `getent`, `usermod`
y `chage` simulados, `pwd` y `grp` reemplazados (no existen en Windows), el archivo de
marcas en memoria y el registro capturado: no toca ninguna cuenta ni necesita root.
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

LOG = "/var/ossec/logs/active-responses.log"
MARCAS = "/var/ossec/active-response/kronos-cuentas.json"
CUENTA = "usuario.demo"
GID_WAZUH = 115


def cuenta(uid, gid=None, bloqueada=False, vencida=False):
    return {"uid": uid, "gid": uid if gid is None else gid, "bloqueada": bloqueada, "vencida": vencida}


class Equipo:
    """Simula las cuentas, los grupos, los comandos y el archivo de marcas, y guarda lo que pasa."""

    def __init__(self, cuentas=None, grupos=None, marcas=None, falla=None, falla_replace=False):
        self.cuentas = {
            CUENTA: cuenta(1001),
            "labadmin": cuenta(1000),
            "root": cuenta(0),
            "systemd-network": cuenta(998),
        }
        self.cuentas.update(cuentas or {})
        # nombre -> (gid, miembros)
        self.grupos = {"wazuh": (GID_WAZUH, []), "sudo": (27, ["labadmin"])} if grupos is None else grupos
        self.archivos = {} if marcas is None else {MARCAS: marcas if isinstance(marcas, str) else json.dumps(marcas)}
        self.falla = falla  # (comando, opción) que devuelve error, por ejemplo ("usermod", "-L")
        self.falla_replace = falla_replace
        self.comandos = []
        self.log = []
        self.reemplazos = []
        self.permisos = []

    # Comandos
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

    # pwd y grp
    def getpwnam(self, nombre):
        if nombre not in self.cuentas:
            raise KeyError(f"getpwnam(): name not found: '{nombre}'")
        c = self.cuentas[nombre]
        return types.SimpleNamespace(pw_name=nombre, pw_uid=c["uid"], pw_gid=c["gid"])

    def getgrnam(self, nombre):
        if nombre not in self.grupos:
            raise KeyError(f"getgrnam(): name not found: '{nombre}'")
        gid, miembros = self.grupos[nombre]
        return types.SimpleNamespace(gr_name=nombre, gr_gid=gid, gr_mem=list(miembros))

    # Archivos
    def abrir(self, ruta, modo="r", *a, **k):
        ruta = str(ruta)
        if ruta == LOG or (ruta.startswith(MARCAS) and ruta != MARCAS):
            assert ruta == LOG or modo == "x", f"el temporal se crea con modo x, no {modo}"
            equipo = self

            class Archivo(io.StringIO):
                def close(self):
                    if ruta == LOG:
                        equipo.log.append(self.getvalue())
                    else:
                        equipo.archivos[ruta] = self.getvalue()
                    super().close()

            return Archivo()
        if ruta == MARCAS:
            assert modo == "r", "el archivo de marcas nunca se escribe directo: va por un temporal"
            if MARCAS not in self.archivos:
                raise FileNotFoundError(MARCAS)
            return io.StringIO(self.archivos[MARCAS])
        return _ABRIR(ruta, modo, *a, **k)

    def replace(self, origen, destino):
        if self.falla_replace:
            raise OSError(28, "No space left on device")
        self.reemplazos.append((origen, destino))
        self.archivos[destino] = self.archivos.pop(origen)

    def chmod(self, ruta, modo):
        self.permisos.append(("chmod", ruta, modo))

    def chown(self, ruta, uid, gid):
        self.permisos.append(("chown", ruta, uid, gid))

    def unlink(self, ruta):
        self.archivos.pop(ruta, None)

    # Consultas para las pruebas
    def cambios(self):
        """Los comandos que cambian una cuenta (usermod y chage)."""
        return [c for c in self.comandos if c[0] in ("usermod", "chage")]

    def marcas(self):
        return json.loads(self.archivos[MARCAS]) if MARCAS in self.archivos else None


_ABRIR = builtins.open


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
         mock.patch("os.replace", equipo.replace), \
         mock.patch("os.chmod", equipo.chmod), \
         mock.patch("os.chown", equipo.chown, create=True), \
         mock.patch("os.unlink", equipo.unlink), \
         mock.patch("sys.stdin", io.StringIO(entrada + "\n")):
        try:
            runpy.run_path(str(SCRIPT), run_name="__main__")
            codigo = 0
        except SystemExit as fin:
            codigo = fin.code
    return codigo, equipo


def marca_de(bloqueo, vencio):
    return {CUENTA: {"bloqueo": bloqueo, "vencio": vencio, "desde": "2026-11-04T10:00:00Z"}}


class Aplicar(unittest.TestCase):
    def test_aplicar_bloquea_vence_y_marca_los_dos_pasos(self):
        codigo, eq = correr(["aplicar", CUENTA])
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [["usermod", "-L", CUENTA], ["chage", "-E", "0", CUENTA]])
        self.assertTrue(eq.cuentas[CUENTA]["bloqueada"] and eq.cuentas[CUENTA]["vencida"])
        marca = eq.marcas()[CUENTA]
        self.assertEqual((marca["bloqueo"], marca["vencio"]), (True, True))
        self.assertRegex(marca["desde"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertIn(f"kronos-deshabilitar-cuenta: aplicar {CUENTA} OK\n", eq.log[-1])

    def test_aplicar_sin_cambios_si_ya_estaba_deshabilitada_y_no_marca(self):
        eq = Equipo(cuentas={CUENTA: cuenta(1001, bloqueada=True, vencida=True)})
        codigo, eq = correr(["aplicar", CUENTA], eq)
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [])
        self.assertIsNone(eq.marcas())
        self.assertIn(f"aplicar {CUENTA} OK (sin cambios: ya estaba deshabilitada)", eq.log[-1])

    def test_aplicar_sobre_contrasena_ya_bloqueada_solo_vence_y_marca_vencio(self):
        eq = Equipo(cuentas={CUENTA: cuenta(1001, bloqueada=True)})
        codigo, eq = correr(["aplicar", CUENTA], eq)
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [["chage", "-E", "0", CUENTA]])
        marca = eq.marcas()[CUENTA]
        self.assertEqual((marca["bloqueo"], marca["vencio"]), (False, True))

    def test_registro_con_hora_utc(self):
        _, eq = correr(["aplicar", CUENTA])
        self.assertRegex(eq.log[-1], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z kronos-deshabilitar-cuenta: ")


class Habilitar(unittest.TestCase):
    def test_habilitar_deshace_los_dos_pasos_y_borra_la_marca(self):
        eq = Equipo(cuentas={CUENTA: cuenta(1001, bloqueada=True, vencida=True)}, marcas=marca_de(True, True))
        codigo, eq = correr(["habilitar", CUENTA], eq)
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [["usermod", "-U", CUENTA], ["chage", "-E", "-1", CUENTA]])
        self.assertFalse(eq.cuentas[CUENTA]["bloqueada"] or eq.cuentas[CUENTA]["vencida"])
        self.assertEqual(eq.marcas(), {})
        self.assertIn(f"habilitar {CUENTA} OK\n", eq.log[-1])

    def test_habilitar_sin_marca_no_toca_la_cuenta(self):
        eq = Equipo(cuentas={CUENTA: cuenta(1001, bloqueada=True, vencida=True)})
        codigo, eq = correr(["habilitar", CUENTA], eq)
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [])
        self.assertTrue(eq.cuentas[CUENTA]["bloqueada"] and eq.cuentas[CUENTA]["vencida"])
        self.assertIn(f"habilitar {CUENTA} OK (sin cambios: no la deshabilito Kronos)", eq.log[-1])

    def test_habilitar_con_marca_de_una_cuenta_ya_habilitada(self):
        codigo, eq = correr(["habilitar", CUENTA], Equipo(marcas=marca_de(True, True)))
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [])
        self.assertEqual(eq.marcas(), {})
        self.assertIn(f"habilitar {CUENTA} OK (sin cambios: ya estaba habilitada)", eq.log[-1])

    def test_habilitar_tras_vencer_una_contrasena_ya_bloqueada_solo_quita_el_vencimiento(self):
        eq = Equipo(cuentas={CUENTA: cuenta(1001, bloqueada=True)})
        _, eq = correr(["aplicar", CUENTA], eq)
        eq.comandos.clear()
        codigo, eq = correr(["habilitar", CUENTA], eq)
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [["chage", "-E", "-1", CUENTA]])
        self.assertNotIn(["usermod", "-U", CUENTA], eq.comandos)
        self.assertTrue(eq.cuentas[CUENTA]["bloqueada"], "la contraseña la bloqueó otra persona: sigue bloqueada")
        self.assertEqual(eq.marcas(), {})

    def test_aplicar_y_habilitar_dejan_la_cuenta_como_estaba(self):
        _, eq = correr(["aplicar", CUENTA])
        codigo, eq = correr(["habilitar", CUENTA], eq)
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cuentas[CUENTA], cuenta(1001))
        self.assertEqual(eq.marcas(), {})

    def test_la_marca_de_otra_cuenta_se_conserva(self):
        otra = {"otra.cuenta": {"bloqueo": True, "vencio": True, "desde": "2026-11-04T09:00:00Z"}}
        eq = Equipo(cuentas={CUENTA: cuenta(1001, bloqueada=True, vencida=True)}, marcas={**otra, **marca_de(True, True)})
        _, eq = correr(["habilitar", CUENTA], eq)
        self.assertEqual(eq.marcas(), otra)


class Marcas(unittest.TestCase):
    def test_escritura_atomica_con_temporal_y_os_replace(self):
        _, eq = correr(["aplicar", CUENTA])
        self.assertTrue(eq.reemplazos)
        for origen, destino in eq.reemplazos:
            self.assertEqual(destino, MARCAS)
            self.assertTrue(origen.startswith(MARCAS + ".") and origen.endswith(".tmp"), origen)
            self.assertIn(("chmod", origen, 0o640), eq.permisos)
            self.assertIn(("chown", origen, 0, GID_WAZUH), eq.permisos)

    def test_la_marca_se_guarda_antes_de_cambiar_la_cuenta(self):
        eq = Equipo()
        original = eq.run

        def run(cmd, **k):
            if cmd[:2] == ["usermod", "-L"]:
                self.assertTrue(eq.marcas()[CUENTA]["bloqueo"], "la marca debe estar antes de bloquear")
            return original(cmd, **k)

        eq.run = run
        codigo, _ = correr(["aplicar", CUENTA], eq)
        self.assertEqual(codigo, 0)

    def test_marca_corrupta_no_toca_la_cuenta(self):
        for op, cuenta_inicial in (("aplicar", cuenta(1001)), ("habilitar", cuenta(1001, bloqueada=True, vencida=True))):
            with self.subTest(op=op):
                eq = Equipo(cuentas={CUENTA: cuenta_inicial}, marcas="{roto")
                codigo, eq = correr([op, CUENTA], eq)
                self.assertEqual(codigo, 1)
                self.assertEqual(eq.cambios(), [])
                self.assertEqual(eq.archivos[MARCAS], "{roto")
                self.assertIn("no es JSON valido; no se toca la cuenta", eq.log[-1])

    def test_marca_que_no_es_un_objeto_tampoco(self):
        codigo, eq = correr(["aplicar", CUENTA], Equipo(marcas=json.dumps([1, 2])))
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.cambios(), [])

    def test_si_no_se_puede_guardar_la_marca_no_toca_la_cuenta(self):
        codigo, eq = correr(["aplicar", CUENTA], Equipo(falla_replace=True))
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.cambios(), [])
        self.assertIn("ERROR no se pudo guardar", eq.log[-1])
        self.assertEqual([r for r in eq.archivos if r != MARCAS], [], "el temporal se borra")


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
        eq = Equipo(cuentas={"nobody": cuenta(65534)})
        self.assertRechazada(["aplicar", "nobody"], "cuenta protegida: nobody", eq)

    def test_uid_menor_que_1000(self):
        self.assertRechazada(["aplicar", "systemd-network"], "cuenta protegida: systemd-network")

    def test_habilitar_una_cuenta_protegida_tampoco(self):
        self.assertRechazada(["habilitar", "root"], "cuenta protegida: root")

    def test_json_roto(self):
        self.assertRechazada("{roto", "entrada invalida")


class Administradores(unittest.TestCase):
    def assertProtegida(self, op, equipo):
        codigo, eq = correr([op, "ana.admin"], equipo)
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.cambios(), [])
        self.assertIn("cuenta protegida: ana.admin (administrador)", eq.log[-1])

    def test_miembro_de_sudo(self):
        for op in ("aplicar", "habilitar"):
            with self.subTest(op=op):
                eq = Equipo(cuentas={"ana.admin": cuenta(1002, bloqueada=op == "habilitar")},
                            grupos={"wazuh": (GID_WAZUH, []), "sudo": (27, ["ana.admin"])},
                            marcas={"ana.admin": {"bloqueo": True, "vencio": False, "desde": "x"}})
                self.assertProtegida(op, eq)

    def test_wheel_como_grupo_primario(self):
        for op in ("aplicar", "habilitar"):
            with self.subTest(op=op):
                eq = Equipo(cuentas={"ana.admin": cuenta(1002, gid=10)},
                            grupos={"wazuh": (GID_WAZUH, []), "wheel": (10, [])})
                self.assertProtegida(op, eq)

    def test_miembro_de_admin(self):
        eq = Equipo(cuentas={"ana.admin": cuenta(1002)}, grupos={"wazuh": (GID_WAZUH, []), "admin": (4, ["ana.admin"])})
        self.assertProtegida("aplicar", eq)

    def test_sin_grupos_de_administracion_en_el_equipo_igual_actua(self):
        codigo, eq = correr(["aplicar", CUENTA], Equipo(grupos={"wazuh": (GID_WAZUH, [])}))
        self.assertEqual(codigo, 0)
        self.assertEqual(len(eq.cambios()), 2)


class Fallos(unittest.TestCase):
    def test_fallo_de_usermod(self):
        codigo, eq = correr(["aplicar", CUENTA], Equipo(falla=("usermod", "-L")))
        self.assertEqual(codigo, 1)
        self.assertIn(f"ERROR usermod -L {CUENTA} (codigo 1): usermod: fallo simulado", eq.log[-1])
        self.assertNotIn(["chage", "-E", "0", CUENTA], eq.comandos)
        self.assertEqual(eq.marcas(), {}, "un paso que falló no queda marcado")

    def test_fallo_de_chage_deja_marcado_solo_el_bloqueo(self):
        codigo, eq = correr(["aplicar", CUENTA], Equipo(falla=("chage", "-E")))
        self.assertEqual(codigo, 1)
        marca = eq.marcas()[CUENTA]
        self.assertEqual((marca["bloqueo"], marca["vencio"]), (True, False))

    def test_fallo_al_leer_el_estado(self):
        codigo, eq = correr(["aplicar", CUENTA], Equipo(falla=("passwd", "-S")))
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.cambios(), [])
        self.assertIn("ERROR passwd -S", eq.log[-1])

    def test_fallo_al_habilitar_conserva_la_marca(self):
        eq = Equipo(cuentas={CUENTA: cuenta(1001, bloqueada=True, vencida=True)},
                    marcas=marca_de(True, True), falla=("usermod", "-U"))
        codigo, eq = correr(["habilitar", CUENTA], eq)
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.marcas(), marca_de(True, True))


if __name__ == "__main__":
    unittest.main()
