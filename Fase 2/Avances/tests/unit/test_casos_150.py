import json
import re
import unittest
from collections import Counter

from decision.mediciones.casos_150.generar import ENTRADA, SALIDA, generar_casos
from validacion.contrato import FAMILIAS


class Casos150(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.alertas = json.loads(ENTRADA.read_text(encoding="utf-8"))
        cls.casos = json.loads(SALIDA.read_text(encoding="utf-8"))

    def test_son_150_con_identificadores_unicos(self):
        self.assertEqual(len(self.casos), 150)
        self.assertEqual(len({c["id"] for c in self.casos}), 150)

    def test_los_casos_estan_al_dia_con_las_alertas(self):
        self.assertEqual(
            generar_casos(self.alertas),
            self.casos,
            "regenerar con: python -m decision.mediciones.casos_150.generar",
        )

    def test_etiquetas_y_playbook_pendiente(self):
        for c in self.casos:
            self.assertIn(c["familia_esperada"], FAMILIAS)
            self.assertEqual(c["playbook_esperado"], "")
            self.assertNotIn("kronos", c["texto"].lower())

    def test_cubren_las_15_reglas_de_sobre(self):
        self.assertEqual(
            {c["regla"] for c in self.casos}, {str(n) for n in range(100101, 100116)}
        )

    def test_solo_ip_de_documentacion(self):
        for c in self.casos:
            for ip in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", c["texto"]):
                self.assertTrue(
                    ip == "127.0.0.1" or ip.startswith("192.0.2."), f"{c['id']}: {ip}"
                )

    def test_hay_al_menos_tres_casos_por_familia(self):
        cuenta = Counter(c["familia_esperada"] for c in self.casos)
        for familia in FAMILIAS:
            self.assertGreaterEqual(cuenta[familia], 3, familia)


if __name__ == "__main__":
    unittest.main()
