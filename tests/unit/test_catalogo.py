import collections
import copy
import json
import tempfile
import unittest
from pathlib import Path

from validacion.catalogo import RUTA_CATALOGO, CatalogoInvalido, cargar_catalogo
from validacion.chequeos import FAMILIAS

ORIGINAL = json.loads(RUTA_CATALOGO.read_text(encoding="utf-8"))


class CatalogoVersionado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = cargar_catalogo()

    def test_25_playbooks_con_los_niveles_del_borrador(self):
        playbooks = self.catalogo.playbooks.values()
        self.assertEqual(len(self.catalogo.playbooks), 25)
        self.assertEqual(
            collections.Counter(p.nivel for p in playbooks), {0: 3, 1: 8, 2: 5, 3: 9}
        )

    def test_todas_las_familias_tienen_playbooks(self):
        self.assertEqual(
            {p.familia for p in self.catalogo.playbooks.values()}, set(FAMILIAS)
        )

    def test_ejemplos_del_borrador(self):
        p = self.catalogo.playbooks
        self.assertEqual((p["PB-F1-02"].familia, p["PB-F1-02"].nivel), ("F1", 1))
        self.assertEqual(p["PB-F3-03"].nivel, 3)
        self.assertEqual(p["PB-F6-01"].nivel, 0)

    def test_ambito_de_ip_de_los_bloqueos(self):
        ambitos = {
            p.id: p.ambito_ip for p in self.catalogo.playbooks.values() if p.ambito_ip
        }
        self.assertEqual(
            ambitos,
            {
                "PB-F1-02": "externa",
                "PB-F1-03": "interna",
                "PB-F3-01": "externa",
                "PB-F3-02": "interna",
            },
        )

    def test_es_version_de_trabajo(self):
        self.assertEqual(ORIGINAL["estado"], "version_de_trabajo")


class CatalogoDefectuoso(unittest.TestCase):
    def cargar_con(self, cambiar):
        datos = copy.deepcopy(ORIGINAL)
        cambiar(datos)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "kro-cat-01.json"
            ruta.write_text(json.dumps(datos), encoding="utf-8")
            return cargar_catalogo(ruta)

    def playbook(self, datos, identificador):
        return next(p for p in datos["playbooks"] if p["id"] == identificador)

    def test_original_carga(self):
        self.assertEqual(len(self.cargar_con(lambda d: None).playbooks), 25)

    def test_rechazos(self):
        casos = {
            "otro código": lambda d: d.update(codigo="KRO-CAT-99"),
            "id repetido": lambda d: d["playbooks"].append(d["playbooks"][0]),
            "familia distinta al id": lambda d: self.playbook(d, "PB-F1-02").update(
                familia="F2"
            ),
            "nivel 4": lambda d: self.playbook(d, "PB-F1-02").update(nivel=4),
            "acción no declarada": lambda d: self.playbook(d, "PB-F1-02").update(
                accion="formatear"
            ),
            "arquetipo desconocido": lambda d: self.playbook(d, "PB-F1-02").update(
                arquetipos=["movil"]
            ),
            "nivel 2 que se revierte solo": lambda d: self.playbook(d, "PB-F1-03")[
                "reversion"
            ].update(tipo="automatica_al_vencer"),
            "nivel 0 que no es consulta": lambda d: self.playbook(d, "PB-F1-01").update(
                accion="bloquear_ip"
            ),
            "consulta con nivel 1": lambda d: self.playbook(d, "PB-F1-01").update(
                nivel=1
            ),
            "ámbito de IP desconocido": lambda d: self.playbook(d, "PB-F1-02").update(
                ambito_ip="remota"
            ),
            "ámbito de IP en una medida que no bloquea IP": lambda d: self.playbook(
                d, "PB-F1-04"
            ).update(ambito_ip="externa"),
            "sin condición de uso": lambda d: self.playbook(d, "PB-F1-02").update(
                condicion_de_uso=" "
            ),
            "sin nombre de la medida": lambda d: self.playbook(d, "PB-F1-02").update(
                medida=""
            ),
            "sin playbooks": lambda d: d.update(playbooks=[]),
            "acción que no es texto": lambda d: self.playbook(d, "PB-F1-02").update(
                accion=["x"]
            ),
            "arquetipo que no es texto": lambda d: self.playbook(d, "PB-F1-02").update(
                arquetipos=[["x"]]
            ),
        }
        for nombre, cambiar in casos.items():
            with self.subTest(nombre), self.assertRaises(CatalogoInvalido):
                self.cargar_con(cambiar)

    def test_archivo_inexistente(self):
        with self.assertRaises(CatalogoInvalido):
            cargar_catalogo(Path("/no/existe/kro-cat-01.json"))


if __name__ == "__main__":
    unittest.main()
