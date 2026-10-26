import json
import unittest

from decision.catalogo.generar_prompt import CATALOGO, PROMPT, prompt_generado
from decision.plantillas import Plantillas
from validacion.catalogo import cargar_catalogo


class PromptYCatalogo(unittest.TestCase):
    def test_el_prompt_esta_generado_desde_el_catalogo(self):
        catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
        actual = PROMPT.read_text(encoding="utf-8")
        self.assertEqual(
            actual,
            prompt_generado(catalogo, actual),
            "paso2_plantilla.txt no coincide con kro-cat-01.json: "
            "corre python decision/catalogo/generar_prompt.py",
        )

    def test_los_candidatos_son_los_25_playbooks_del_catalogo(self):
        plantillas = Plantillas.cargar()
        candidatos = {i for f in plantillas.familias.values() for i in f.candidatos}
        self.assertEqual(candidatos, set(cargar_catalogo().playbooks))

    def test_cada_candidato_es_de_su_familia_y_van_de_menor_a_mayor_nivel(self):
        plantillas, catalogo = Plantillas.cargar(), cargar_catalogo()
        for familia, datos in plantillas.familias.items():
            niveles = [catalogo.playbooks[i].nivel for i in datos.candidatos]
            self.assertEqual(niveles, sorted(niveles), familia)
            for i in datos.candidatos:
                self.assertEqual(catalogo.playbooks[i].familia, familia)


if __name__ == "__main__":
    unittest.main()
