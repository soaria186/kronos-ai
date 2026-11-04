"""Pruebas del script de Active Response kronos-terminar-proceso para Linux.

El script se carga con runpy y termina procesos hijos de la propia prueba (un sleep), con
/proc real y el registro en una carpeta temporal: no necesita root ni toca otros procesos.
"""

from __future__ import annotations

import io
import json
import os
import runpy
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "infra" / "wazuh" / "active-response" / "linux" / "kronos-terminar-proceso"
)


@unittest.skipUnless(sys.platform.startswith("linux"), "el script es de Linux: usa /proc")
class TerminarProceso(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "active-responses.log"
        self.main = runpy.run_path(str(SCRIPT), run_name="kronos_terminar_proceso")["main"]
        self.hijos = []

    def tearDown(self):
        for hijo in self.hijos:
            if hijo.poll() is None:
                hijo.kill()
            hijo.wait()
        self.tmp.cleanup()

    def hijo(self, codigo="import time; time.sleep(60)"):
        proceso = subprocess.Popen([sys.executable, "-c", codigo])
        self.hijos.append(proceso)
        time.sleep(0.2)
        return proceso, os.readlink(f"/proc/{proceso.pid}/exe")

    def correr(self, entrada, **cambios):
        if not isinstance(entrada, str):
            entrada = json.dumps({"version": 1, "command": "add", "parameters": {"extra_args": entrada}})
        cambios = {"LOG": str(self.log), "ESPERA_TERM": 0.5, **cambios}
        with mock.patch.dict(self.main.__globals__, cambios), \
             mock.patch("sys.stdin", io.StringIO(entrada + "\n")):
            return self.main()

    def ultima_linea(self):
        return self.log.read_text().splitlines()[-1]

    def esperar_fin(self, proceso):
        try:
            proceso.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        return proceso.poll() is not None

    def test_termina_el_proceso(self):
        proceso, ruta = self.hijo()
        self.assertEqual(self.correr(["aplicar", str(proceso.pid), ruta]), 0)
        self.assertTrue(self.esperar_fin(proceso))
        self.assertIn(f"kronos-terminar-proceso: aplicar {proceso.pid} {ruta}: OK (SIGTERM)", self.ultima_linea())

    def test_si_ignora_sigterm_usa_sigkill(self):
        proceso, ruta = self.hijo(
            "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"
        )
        self.assertEqual(self.correr(["aplicar", str(proceso.pid), ruta]), 0)
        self.assertTrue(self.esperar_fin(proceso))
        self.assertIn("OK (SIGKILL)", self.ultima_linea())

    def test_otro_ejecutable_no_se_toca(self):
        proceso, _ = self.hijo()
        self.assertEqual(self.correr(["aplicar", str(proceso.pid), "/usr/bin/otro-programa"]), 1)
        self.assertIsNone(proceso.poll())
        self.assertIn("no se toca", self.ultima_linea())

    def test_proceso_que_ya_no_existe(self):
        proceso, ruta = self.hijo()
        proceso.kill()
        proceso.wait()
        self.assertEqual(self.correr(["aplicar", str(proceso.pid), ruta]), 0)
        self.assertIn("sin cambios", self.ultima_linea())

    def test_proceso_protegido(self):
        proceso, ruta = self.hijo()
        protegidos = {os.path.basename(ruta)}
        self.assertEqual(self.correr(["aplicar", str(proceso.pid), ruta], PROTEGIDOS=protegidos), 1)
        self.assertIsNone(proceso.poll())
        self.assertIn("proceso protegido", self.ultima_linea())

    def test_carpeta_del_agente_protegida(self):
        proceso, ruta = self.hijo()
        carpeta = os.path.dirname(ruta) + "/"
        self.assertEqual(self.correr(["aplicar", str(proceso.pid), ruta], CARPETAS_PROTEGIDAS=(carpeta,)), 1)
        self.assertIsNone(proceso.poll())

    def test_nunca_a_si_mismo(self):
        propio = os.readlink(f"/proc/{os.getpid()}/exe")
        self.assertEqual(self.correr(["aplicar", str(os.getpid()), propio]), 1)
        self.assertIn("de este script", self.ultima_linea())

    def test_argumentos_invalidos(self):
        proceso, ruta = self.hijo()
        for entrada in (
            ["aplicar", "1", "/sbin/init"],
            ["aplicar", "4", ruta],
            ["aplicar", "-1", ruta],
            ["aplicar", "12a", ruta],
            ["aplicar", str(proceso.pid), "sleep"],
            ["aplicar", str(proceso.pid), "/tmp/../usr/bin/sleep"],
            ["aplicar", str(proceso.pid), "/tmp/$(id)"],
            ["quitar", str(proceso.pid), ruta],
            ["aplicar", str(proceso.pid)],
            ["aplicar", str(proceso.pid), ruta, "extra"],
            ["aplicar", proceso.pid, ruta],
            "",
            "no es json",
        ):
            with self.subTest(entrada=entrada):
                self.assertEqual(self.correr(entrada), 1)
        self.assertIsNone(proceso.poll())


if __name__ == "__main__":
    unittest.main()
