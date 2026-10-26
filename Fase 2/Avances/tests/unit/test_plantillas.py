import tempfile
import unittest
from pathlib import Path

from decision.plantillas import DIR_PROMPTS, PlantillaInvalida, Plantillas


class PlantillasReales(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = Plantillas.cargar()

    def test_seis_familias_con_candidatos_de_su_familia(self):
        self.assertEqual(sorted(self.p.familias), ["F1", "F2", "F3", "F4", "F5", "F6"])
        for familia, datos in self.p.familias.items():
            self.assertGreaterEqual(len(datos.candidatos), 3)
            for identificador in datos.candidatos:
                self.assertTrue(identificador.startswith(f"PB-{familia}-"))

    def test_prompt_familia_termina_en_la_alerta(self):
        prompt = self.p.prompt_familia("ALERTA-DE-PRUEBA")
        self.assertTrue(prompt.rstrip().endswith("ALERTA-DE-PRUEBA"))
        self.assertNotIn("{{", prompt)

    def test_prompt_playbook_sin_catalogo_ni_marcadores(self):
        prompt = self.p.prompt_playbook("F4", "ALERTA-DE-PRUEBA")
        self.assertTrue(prompt.rstrip().endswith("ALERTA-DE-PRUEBA"))
        self.assertIn("F4 - Exfiltración o salida anómala", prompt)
        self.assertIn("PB-F4-02", prompt)
        self.assertNotIn("PB-F1-01", prompt)
        self.assertNotIn("=== CATALOGO ===", prompt)
        self.assertNotIn("{{", prompt)

    def test_sin_ambito_el_prompt_es_el_de_siempre(self):
        base = self.p.prompt_playbook("F1", "ALERTA")
        self.assertEqual(self.p.prompt_playbook("F1", "ALERTA", None), base)
        self.assertEqual(self.p.prompt_playbook("F1", "ALERTA", "desconocido"), base)
        self.assertNotIn("ORIGEN DE LA ALERTA", base)

    def test_el_ambito_de_la_ip_va_antes_de_la_alerta(self):
        for ambito, dice, no_dice in (
            ("interna", "es INTERNA", "es EXTERNA"),
            ("externa", "es EXTERNA", "es INTERNA"),
        ):
            prompt = self.p.prompt_playbook("F1", "ALERTA", ambito)
            self.assertIn("ORIGEN DE LA ALERTA", prompt)
            self.assertIn(dice, prompt)
            self.assertNotIn(no_dice, prompt)
            self.assertTrue(prompt.rstrip().endswith("ALERTA"))
            self.assertLess(
                prompt.index("PB-F1-05"), prompt.index("ORIGEN DE LA ALERTA")
            )
            self.assertLess(prompt.index("ORIGEN DE LA ALERTA"), prompt.rindex("ALERTA"))
            self.assertNotIn("{{", prompt)

    def test_marcadores_dentro_de_la_alerta_no_se_reinterpretan(self):
        prompt = self.p.prompt_playbook("F1", "texto {{condiciones}} {{familia}}")
        self.assertTrue(prompt.rstrip().endswith("texto {{condiciones}} {{familia}}"))


class PlantillasDefectuosas(unittest.TestCase):
    def cargar_con(self, paso1=None, paso2=None):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "paso1_familia.txt").write_text(
                paso1
                or (DIR_PROMPTS / "paso1_familia.txt").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (d / "paso2_plantilla.txt").write_text(
                paso2
                or (DIR_PROMPTS / "paso2_plantilla.txt").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            return Plantillas.cargar(d)

    def test_alerta_que_no_va_al_final(self):
        with self.assertRaises(PlantillaInvalida):
            self.cargar_con(paso1="ALERTA\n{{alerta}}\nFORMATO: JSON\n")

    def test_marcador_desconocido(self):
        with self.assertRaises(PlantillaInvalida):
            self.cargar_con(paso1="{{otro}}\n{{alerta}}\n")

    def test_familia_sin_playbooks(self):
        original = (DIR_PROMPTS / "paso2_plantilla.txt").read_text(encoding="utf-8")
        sin_f6 = "\n".join(
            linea for linea in original.splitlines() if not linea.startswith("PB-F6")
        )
        with self.assertRaises(PlantillaInvalida):
            self.cargar_con(paso2=sin_f6)

    def test_playbook_fuera_de_su_familia(self):
        original = (DIR_PROMPTS / "paso2_plantilla.txt").read_text(encoding="utf-8")
        with self.assertRaises(PlantillaInvalida):
            self.cargar_con(paso2=original.replace("PB-F2-01 |", "PB-F3-09 |", 1))

    def test_sin_separadores(self):
        with self.assertRaises(PlantillaInvalida):
            self.cargar_con(paso2="{{familia}} {{condiciones}} {{alerta}}")


if __name__ == "__main__":
    unittest.main()
