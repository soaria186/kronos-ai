import json
import unittest

from decision.mediciones.generar_casos_wazuh import ENTRADA, SALIDA, generar_casos


class CasosFormatoWazuh(unittest.TestCase):
    def test_los_casos_estan_al_dia_con_las_alertas(self):
        alertas = json.loads(ENTRADA.read_text(encoding="utf-8"))
        guardados = json.loads(SALIDA.read_text(encoding="utf-8"))
        self.assertEqual(
            generar_casos(alertas),
            guardados,
            "regenerar con: python -m decision.mediciones.generar_casos_wazuh",
        )

    def test_cubren_las_15_reglas_de_sobre_sin_mostrar_la_familia(self):
        casos = json.loads(SALIDA.read_text(encoding="utf-8"))
        self.assertEqual(
            {c["regla"] for c in casos}, {str(n) for n in range(100101, 100116)}
        )
        for caso in casos:
            self.assertNotIn("kronos", caso["texto"].lower())


if __name__ == "__main__":
    unittest.main()
