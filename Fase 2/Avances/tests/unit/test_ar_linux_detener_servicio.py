"""Pruebas de kronos-detener-servicio, el script de Active Response para Linux.

El script se ejecuta completo en el mismo proceso (runpy), con `systemctl` simulado, `grp`
reemplazado (no existe en Windows), el archivo de marcas en memoria y el registro capturado:
no toca ningún servicio ni necesita root.
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
    / "infra" / "wazuh" / "active-response" / "linux" / "kronos-detener-servicio"
)

LOG = "/var/ossec/logs/active-responses.log"
MARCAS = "/var/ossec/active-response/kronos-servicios.json"
UNIDAD = "apache2.service"
GID_WAZUH = 115

_ABRIR = builtins.open


class Equipo:
    """Simula systemd, el archivo de marcas y el registro, y guarda lo que pasa."""

    def __init__(self, servicios=None, marcas=None, falla=None, no_cambia=False, falla_replace=False):
        # unidad -> True (en marcha) o False (detenida); las que no están, no existen.
        self.servicios = {UNIDAD: True, "wazuh-agent.service": True, "ssh.service": True}
        self.servicios.update(servicios or {})
        self.archivos = {} if marcas is None else {MARCAS: marcas if isinstance(marcas, str) else json.dumps(marcas)}
        self.falla = falla  # "stop" o "start": systemctl devuelve error
        self.no_cambia = no_cambia  # systemctl responde 0 pero el estado no cambia
        self.falla_replace = falla_replace
        self.comandos = []
        self.log = []
        self.reemplazos = []

    def run(self, cmd, **opciones):
        assert isinstance(cmd, list), f"el comando debe ser una lista: {cmd!r}"
        assert not opciones.get("shell"), "nunca shell=True"
        assert cmd[0] == "systemctl", f"comando inesperado: {cmd}"
        self.comandos.append(cmd)
        unidad = cmd[-1]
        if cmd[1] == "show":
            estado = "loaded" if unidad in self.servicios else "not-found"
            return subprocess.CompletedProcess(cmd, 0, estado + "\n", "")
        if cmd[1] == "is-active":
            activo = self.servicios.get(unidad, False)
            return subprocess.CompletedProcess(cmd, 0 if activo else 3, ("active" if activo else "inactive") + "\n", "")
        if cmd[1] in ("stop", "start"):
            if self.falla == cmd[1]:
                return subprocess.CompletedProcess(cmd, 1, "", f"Failed to {cmd[1]} {unidad}: fallo simulado")
            if not self.no_cambia:
                self.servicios[unidad] = cmd[1] == "start"
            return subprocess.CompletedProcess(cmd, 0, "", "")
        raise AssertionError(f"comando inesperado: {cmd}")

    def getgrnam(self, nombre):
        if nombre != "wazuh":
            raise KeyError(nombre)
        return types.SimpleNamespace(gr_name=nombre, gr_gid=GID_WAZUH, gr_mem=[])

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

    def unlink(self, ruta):
        self.archivos.pop(ruta, None)

    def cambios(self):
        return [c for c in self.comandos if c[1] in ("stop", "start")]

    def marcas(self):
        return json.loads(self.archivos[MARCAS]) if MARCAS in self.archivos else None


def correr(entrada, equipo=None):
    """Corre el script con `entrada` en la entrada estándar. Devuelve (código, equipo)."""
    equipo = equipo or Equipo()
    if not isinstance(entrada, str):
        entrada = json.dumps({"version": 1, "command": "add", "parameters": {"extra_args": entrada}})
    grp = types.ModuleType("grp")
    grp.getgrnam = equipo.getgrnam
    with mock.patch("subprocess.run", equipo.run), \
         mock.patch("builtins.open", equipo.abrir), \
         mock.patch.dict(sys.modules, {"grp": grp}), \
         mock.patch("os.replace", equipo.replace), \
         mock.patch("os.chmod", lambda *a: None), \
         mock.patch("os.chown", lambda *a: None, create=True), \
         mock.patch("os.unlink", equipo.unlink), \
         mock.patch("sys.stdin", io.StringIO(entrada + "\n")):
        try:
            runpy.run_path(str(SCRIPT), run_name="__main__")
            codigo = 0
        except SystemExit as fin:
            codigo = fin.code
    return codigo, equipo


MARCA = {UNIDAD: {"desde": "2026-11-04T10:00:00Z"}}


class Aplicar(unittest.TestCase):
    def test_aplicar_detiene_y_marca(self):
        codigo, eq = correr(["aplicar", "apache2"])
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [["systemctl", "stop", UNIDAD]])
        self.assertFalse(eq.servicios[UNIDAD])
        self.assertRegex(eq.marcas()[UNIDAD]["desde"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertIn(f"kronos-detener-servicio: aplicar {UNIDAD} OK\n", eq.log[-1])

    def test_acepta_el_nombre_con_sufijo_service(self):
        codigo, eq = correr(["aplicar", UNIDAD])
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [["systemctl", "stop", UNIDAD]])

    def test_la_marca_se_guarda_antes_de_detener(self):
        eq = Equipo()
        orden = []
        original_run, original_replace = eq.run, eq.replace
        eq.run = lambda cmd, **o: (orden.append(cmd[1]), original_run(cmd, **o))[1]
        eq.replace = lambda a, b: (orden.append("marca"), original_replace(a, b))[1]
        correr(["aplicar", "apache2"], eq)
        self.assertLess(orden.index("marca"), orden.index("stop"))

    def test_ya_detenido_sin_marca_no_cambia_ni_marca(self):
        codigo, eq = correr(["aplicar", "apache2"], Equipo(servicios={UNIDAD: False}))
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [])
        self.assertIsNone(eq.marcas())
        self.assertIn("sin cambios: ya estaba detenido; no lo detuvo Kronos", eq.log[-1])

    def test_ya_detenido_por_kronos(self):
        codigo, eq = correr(["aplicar", "apache2"], Equipo(servicios={UNIDAD: False}, marcas=MARCA))
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [])
        self.assertIn("ya lo habia detenido Kronos", eq.log[-1])

    def test_falla_stop_quita_la_marca(self):
        codigo, eq = correr(["aplicar", "apache2"], Equipo(falla="stop"))
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.marcas(), {})
        self.assertIn("ERROR systemctl stop", eq.log[-1])

    def test_sigue_en_marcha_despues_de_stop_es_error(self):
        codigo, eq = correr(["aplicar", "apache2"], Equipo(no_cambia=True))
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.marcas(), {})
        self.assertIn("sigue en marcha", eq.log[-1])

    def test_si_no_se_puede_guardar_la_marca_no_detiene(self):
        codigo, eq = correr(["aplicar", "apache2"], Equipo(falla_replace=True))
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.cambios(), [])
        self.assertTrue(eq.servicios[UNIDAD])
        self.assertIn("ERROR no se pudo guardar", eq.log[-1])

    def test_conserva_las_marcas_de_otros_servicios(self):
        otra = {"nginx.service": {"desde": "2026-11-04T09:00:00Z"}}
        codigo, eq = correr(["aplicar", "apache2"], Equipo(marcas=otra))
        self.assertEqual(codigo, 0)
        self.assertEqual(set(eq.marcas()), {"nginx.service", UNIDAD})

    def test_registro_con_hora_utc(self):
        _, eq = correr(["aplicar", "apache2"])
        self.assertRegex(eq.log[-1], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z kronos-detener-servicio: ")


class Iniciar(unittest.TestCase):
    def test_iniciar_con_marca_arranca_y_borra_la_marca(self):
        codigo, eq = correr(["iniciar", "apache2"], Equipo(servicios={UNIDAD: False}, marcas=MARCA))
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [["systemctl", "start", UNIDAD]])
        self.assertTrue(eq.servicios[UNIDAD])
        self.assertEqual(eq.marcas(), {})
        self.assertIn(f"iniciar {UNIDAD} OK\n", eq.log[-1])

    def test_iniciar_sin_marca_no_toca_el_servicio(self):
        codigo, eq = correr(["iniciar", "apache2"], Equipo(servicios={UNIDAD: False}))
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [])
        self.assertFalse(eq.servicios[UNIDAD])
        self.assertIn("sin cambios: no lo detuvo Kronos", eq.log[-1])

    def test_iniciar_con_marca_y_ya_en_marcha_solo_borra_la_marca(self):
        codigo, eq = correr(["iniciar", "apache2"], Equipo(marcas=MARCA))
        self.assertEqual(codigo, 0)
        self.assertEqual(eq.cambios(), [])
        self.assertEqual(eq.marcas(), {})
        self.assertIn("ya estaba en marcha", eq.log[-1])

    def test_falla_start_conserva_la_marca(self):
        codigo, eq = correr(["iniciar", "apache2"], Equipo(servicios={UNIDAD: False}, marcas=MARCA, falla="start"))
        self.assertEqual(codigo, 1)
        self.assertIn(UNIDAD, eq.marcas())
        self.assertIn("ERROR systemctl start", eq.log[-1])

    def test_vuelta_completa(self):
        eq = Equipo()
        self.assertEqual(correr(["aplicar", "apache2"], eq)[0], 0)
        self.assertFalse(eq.servicios[UNIDAD])
        self.assertEqual(correr(["iniciar", "apache2"], eq)[0], 0)
        self.assertTrue(eq.servicios[UNIDAD])
        self.assertEqual(eq.marcas(), {})


class Protegidos(unittest.TestCase):
    def test_servicios_protegidos(self):
        for nombre in ("wazuh-agent", "ssh", "sshd.service", "netbird", "systemd-journald",
                       "postgresql@17-main", "docker", "ollama", "NetworkManager", "getty@tty1"):
            with self.subTest(nombre=nombre):
                codigo, eq = correr(["aplicar", nombre], Equipo(servicios={nombre if nombre.endswith(".service") else nombre + ".service": True}))
                self.assertEqual(codigo, 1)
                self.assertEqual(eq.cambios(), [])
                self.assertIn("servicio protegido", eq.log[-1])

    def test_iniciar_tampoco_toca_un_protegido(self):
        codigo, eq = correr(["iniciar", "wazuh-agent"])
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.cambios(), [])


class Entrada(unittest.TestCase):
    def test_servicio_inexistente(self):
        codigo, eq = correr(["aplicar", "no-existe"])
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.cambios(), [])
        self.assertIn("ERROR no existe el servicio: no-existe.service", eq.log[-1])

    def test_cantidad_de_argumentos(self):
        for args in (["aplicar"], ["aplicar", "apache2", "extra"]):
            with self.subTest(args=args):
                codigo, eq = correr(args)
                self.assertEqual(codigo, 1)
                self.assertEqual(eq.comandos, [])

    def test_operacion_desconocida(self):
        codigo, eq = correr(["quitar", "apache2"])
        self.assertEqual(codigo, 1)
        self.assertIn("operacion desconocida", eq.log[-1])

    def test_nombres_no_permitidos(self):
        for nombre in ("apache2;id", "apache 2", "-apache2", "../x", "apache2\n", "a" * 129, "*"):
            with self.subTest(nombre=nombre):
                codigo, eq = correr(["aplicar", nombre])
                self.assertEqual(codigo, 1)
                self.assertEqual(eq.comandos, [])

    def test_argumento_que_no_es_texto(self):
        codigo, eq = correr(["aplicar", 5])
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.comandos, [])

    def test_json_roto(self):
        codigo, eq = correr("{no es json")
        self.assertEqual(codigo, 1)
        self.assertIn("entrada invalida", eq.log[-1])

    def test_marca_corrupta_no_toca_el_servicio(self):
        codigo, eq = correr(["aplicar", "apache2"], Equipo(marcas="{roto"))
        self.assertEqual(codigo, 1)
        self.assertEqual(eq.cambios(), [])
        self.assertIn("no es JSON valido", eq.log[-1])


if __name__ == "__main__":
    unittest.main()
