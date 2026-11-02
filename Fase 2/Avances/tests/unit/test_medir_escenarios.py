"""El script de medición de escenarios E1 a E4 (tools/medir_escenarios.py), con un modelo falso."""

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

RUTA = Path(__file__).resolve().parents[2] / "tools" / "medir_escenarios.py"
_spec = importlib.util.spec_from_file_location("medir_escenarios", RUTA)
medir_escenarios = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = medir_escenarios  # los dataclasses lo necesitan
_spec.loader.exec_module(medir_escenarios)


class ModeloPorEscenario:
    """Responde según la alerta (lo que va después del último «ALERTA») y cuenta llamadas."""

    def __init__(self):
        self.llamadas = 0

    def generar(self, prompt, esquema, plazo):
        self.llamadas += 1
        alerta = prompt.rsplit("ALERTA\n", 1)[1]
        if "playbook_id" in json.dumps(esquema):
            if "auditoría borrado" in alerta:
                playbook = "PB-F5-04"
            elif "Windows" in alerta:
                playbook = "PB-F1-05"
            elif "192.168.50.20" in alerta:
                playbook = "PB-F1-03"
            else:
                playbook = "PB-F1-02"
            return json.dumps({"playbook_id": playbook, "confianza": 0.85})
        familia = "F5" if "auditoría borrado" in alerta else "F1"
        return json.dumps({"familia": familia, "confianza": 0.9})


class MedirEscenarios(unittest.TestCase):
    def setUp(self):
        self.casos = medir_escenarios.escenarios_por_omision()
        self.modelo = ModeloPorEscenario()
        self.filas = medir_escenarios.medir(self.modelo, self.casos, 2, 60.0)

    def fila(self, escenario, repeticion=1):
        return next(
            f
            for f in self.filas
            if f["escenario"] == escenario and f["repeticion"] == repeticion
        )

    def test_hay_una_fila_por_escenario_y_repeticion(self):
        self.assertEqual(len(self.filas), 8)
        self.assertEqual(self.modelo.llamadas, 16)  # dos pasos por repetición

    def test_e1_bloquea_la_ip_externa_y_se_aprueba(self):
        f = self.fila("E1")
        self.assertEqual((f["familia"], f["playbook"]), ("F1", "PB-F1-02"))
        self.assertEqual((f["resultado"], f["nivel"]), ("aprobada", 1))
        self.assertEqual(f["confianza_paso1"], 0.9)
        self.assertEqual(f["confianza_paso2"], 0.85)
        self.assertTrue(f["tiene_script"])  # bloquear_ip en Linux

    def test_e2_la_ip_interna_elige_el_playbook_interno(self):
        f = self.fila("E2")
        self.assertEqual(f["playbook"], "PB-F1-03")
        self.assertEqual(f["resultado"], "aprobada")

    def test_e3_deshabilitar_cuenta_tiene_script_en_windows(self):
        f = self.fila("E3")
        self.assertEqual(f["playbook"], "PB-F1-05")
        self.assertEqual(f["accion"], "deshabilitar_cuenta")
        self.assertTrue(f["tiene_script"])
        self.assertEqual(f["nivel"], 2)

    def test_e4_aislar_el_equipo_es_nivel_3(self):
        f = self.fila("E4")
        self.assertEqual((f["playbook"], f["nivel"]), ("PB-F5-04", 3))
        self.assertEqual(f["accion"], "aislar_equipo")
        self.assertTrue(f["tiene_script"])

    def test_el_resumen_nombra_cada_escenario(self):
        texto = medir_escenarios.resumen(self.filas, self.casos)
        for escenario in ("E1", "E2", "E3", "E4"):
            self.assertIn(f"{escenario}: esperada", texto)
        self.assertIn("coincide con la esperada 2/2", texto)

    def test_los_datos_de_ejemplo_usan_sólo_ip_de_documentación_o_privadas(self):
        texto = json.dumps(self.casos)
        ips = set(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", texto))
        self.assertTrue(ips)
        permitidas = ("192.0.2.", "198.51.100.", "203.0.113.", "192.168.")
        self.assertEqual({ip for ip in ips if not ip.startswith(permitidas)}, set())


if __name__ == "__main__":
    unittest.main()
