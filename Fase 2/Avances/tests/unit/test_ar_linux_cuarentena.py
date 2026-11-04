"""Pruebas del script de Active Response kronos-cuarentena para Linux.

El script se carga con runpy y su main() corre sobre una carpeta temporal: la cuarentena y
el registro apuntan ahí, así que no necesita root ni toca /var/lib. En Windows se omiten
(el CI corre en Linux y no admite pruebas omitidas).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import runpy
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "infra" / "wazuh" / "active-response" / "linux" / "kronos-cuarentena"
)


@unittest.skipIf(os.name == "nt", "el script es de Linux: necesita permisos y enlaces POSIX")
class Cuarentena(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(os.path.realpath(self.tmp.name))
        self.casa = base / "home" / "usuario"
        self.casa.mkdir(parents=True)
        self.cuarentena = base / "cuarentena"
        self.log = base / "active-responses.log"
        self.main = runpy.run_path(str(SCRIPT), run_name="kronos_cuarentena")["main"]
        self.archivo = self.casa / "factura.sh"
        self.archivo.write_bytes(b"#!/bin/sh\necho minero\n")
        self.archivo.chmod(0o755)

    def tearDown(self):
        for raiz, carpetas, archivos in os.walk(self.tmp.name):
            for nombre in carpetas + archivos:
                ruta = os.path.join(raiz, nombre)
                if not os.path.islink(ruta):
                    os.chmod(ruta, 0o700)
        self.tmp.cleanup()

    def correr(self, entrada):
        if not isinstance(entrada, str):
            entrada = json.dumps({"version": 1, "command": "add", "parameters": {"extra_args": entrada}})
        cambios = {"CUARENTENA": str(self.cuarentena), "LOG": str(self.log)}
        with mock.patch.dict(self.main.__globals__, cambios), \
             mock.patch("sys.stdin", io.StringIO(entrada + "\n")):
            return self.main()

    def ultima_linea(self):
        return self.log.read_text().splitlines()[-1]

    def guardados(self):
        return sorted(p.name for p in self.cuarentena.iterdir()) if self.cuarentena.exists() else []

    def test_aplicar_mueve_el_archivo_y_deja_el_registro(self):
        sha = hashlib.sha256(self.archivo.read_bytes()).hexdigest()
        self.assertEqual(self.correr(["aplicar", str(self.archivo)]), 0)
        self.assertFalse(self.archivo.exists())
        bins = [p for p in self.cuarentena.iterdir() if p.suffix == ".bin"]
        self.assertEqual(len(bins), 1)
        self.assertEqual(stat.S_IMODE(bins[0].stat().st_mode), 0)
        self.assertEqual(stat.S_IMODE(self.cuarentena.stat().st_mode), 0o700)
        registro = json.loads(bins[0].with_suffix(".json").read_text())
        self.assertEqual(registro["ruta"], str(self.archivo))
        self.assertEqual(registro["sha256"], sha)
        self.assertIn(f"kronos-cuarentena: aplicar {self.archivo}: OK (sha256 {sha})", self.ultima_linea())

    def test_aplicar_dos_veces_es_sin_cambios(self):
        self.correr(["aplicar", str(self.archivo)])
        self.assertEqual(self.correr(["aplicar", str(self.archivo)]), 0)
        self.assertIn("sin cambios (ya estaba en cuarentena)", self.ultima_linea())

    def test_restaurar_devuelve_contenido_y_permisos(self):
        contenido = self.archivo.read_bytes()
        self.correr(["aplicar", str(self.archivo)])
        self.assertEqual(self.correr(["restaurar", str(self.archivo)]), 0)
        self.assertEqual(self.archivo.read_bytes(), contenido)
        self.assertEqual(stat.S_IMODE(self.archivo.stat().st_mode), 0o755)
        self.assertEqual(self.guardados(), [])
        self.assertIn(f"restaurar {self.archivo}: OK", self.ultima_linea())

    def test_restaurar_sin_cuarentena_es_sin_cambios(self):
        self.assertEqual(self.correr(["restaurar", str(self.archivo)]), 0)
        self.assertTrue(self.archivo.exists())
        self.assertIn("sin cambios (no estaba en cuarentena)", self.ultima_linea())

    def test_restaurar_no_sobrescribe(self):
        self.correr(["aplicar", str(self.archivo)])
        self.archivo.write_bytes(b"otro")
        self.assertEqual(self.correr(["restaurar", str(self.archivo)]), 1)
        self.assertEqual(self.archivo.read_bytes(), b"otro")
        self.assertIn("ya esta ocupada", self.ultima_linea())
        self.assertEqual(len(self.guardados()), 2)  # sigue en cuarentena

    def test_restaurar_con_huella_cambiada_no_restaura(self):
        self.correr(["aplicar", str(self.archivo)])
        guardado = next(p for p in self.cuarentena.iterdir() if p.suffix == ".bin")
        guardado.chmod(0o600)
        guardado.write_bytes(b"alterado")
        self.assertEqual(self.correr(["restaurar", str(self.archivo)]), 1)
        self.assertFalse(self.archivo.exists())
        self.assertIn("huella", self.ultima_linea())

    def test_archivo_que_no_existe(self):
        self.assertEqual(self.correr(["aplicar", str(self.casa / "nada.sh")]), 1)
        self.assertIn("no existe", self.ultima_linea())
        self.assertEqual(self.guardados(), [])

    def test_no_mueve_carpetas_ni_enlaces(self):
        carpeta = self.casa / "carpeta"
        carpeta.mkdir()
        enlace = self.casa / "enlace"
        enlace.symlink_to(self.archivo)
        for ruta in (carpeta, enlace):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.correr(["aplicar", str(ruta)]), 1)
                self.assertIn("no es un archivo regular", self.ultima_linea())
        self.assertTrue(self.archivo.exists())

    def test_enlace_hacia_una_carpeta_protegida(self):
        enlace = self.casa / "sistema"
        enlace.symlink_to("/etc")
        self.assertEqual(self.correr(["aplicar", str(enlace / "hostname")]), 1)
        self.assertIn("ruta protegida (enlace", self.ultima_linea())

    def test_rutas_rechazadas(self):
        for ruta in (
            "/etc/passwd",
            "/usr/bin/ls",
            "/var/ossec/bin/wazuh-agentd",
            "/var/lib/kronos/cuarentena/x.bin",
            "/tmp/../etc/passwd",
            "/tmp/./x",
            "/tmp//x",
            "/tmp/x/",
            "/tmp/$(id)",
            "/tmp/a;b",
            "relativa/x",
            "C:\\Users\\x.exe",
            "/" + "a" * 1100,
        ):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.correr(["aplicar", ruta]), 1)
                self.assertIn("rechazada", self.ultima_linea())
        self.assertEqual(self.guardados(), [])

    def test_argumentos_invalidos(self):
        for entrada in (
            ["borrar", str(self.archivo)],
            ["aplicar"],
            ["aplicar", str(self.archivo), "extra"],
            ["aplicar", 5],
            "",
            "no es json",
            json.dumps({"parameters": {}}),
        ):
            with self.subTest(entrada=entrada):
                self.assertEqual(self.correr(entrada), 1)
        self.assertTrue(self.archivo.exists())
        self.assertEqual(self.guardados(), [])

    def test_si_la_copia_falla_el_original_queda(self):
        with mock.patch.dict(self.main.__globals__, {"huella": _huella_que_cambia()}):
            self.assertEqual(self.correr(["aplicar", str(self.archivo)]), 1)
        self.assertTrue(self.archivo.exists())
        self.assertEqual(self.guardados(), [])


def _huella_que_cambia():
    llamadas = iter(range(1000))
    return lambda ruta: f"h{next(llamadas)}"


if __name__ == "__main__":
    unittest.main()
