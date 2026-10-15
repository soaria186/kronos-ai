import json
import os
import tempfile
import unittest
from pathlib import Path

from conectores.alertas_wazuh import LectorAlertas, Posicion


def linea(n):
    return json.dumps({"id": f"1760000000.{n}", "rule": {"level": 10}}) + "\n"


class Lector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self.tmp.name) / "alerts.json"
        self.ruta.write_text(linea(1) + linea(2), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def agregar(self, texto, ruta=None):
        with open(ruta or self.ruta, "a", encoding="utf-8") as f:
            f.write(texto)

    def ids(self, alertas):
        return [a["id"].split(".")[1] for a in alertas]

    def test_primer_arranque_empieza_por_el_final(self):
        lector = LectorAlertas(self.ruta)
        self.assertEqual(lector.leer(), [])
        self.agregar(linea(3))
        self.assertEqual(self.ids(lector.leer()), ["3"])
        lector.cerrar()

    def test_linea_a_medio_escribir_espera_a_estar_completa(self):
        lector = LectorAlertas(self.ruta)
        texto = linea(3)
        self.agregar(texto[:10])
        self.assertEqual(lector.leer(), [])
        posicion = lector.posicion
        self.agregar(texto[10:])
        self.assertEqual(self.ids(lector.leer()), ["3"])
        self.assertGreater(lector.posicion.desplazamiento, posicion.desplazamiento)
        lector.cerrar()

    def test_retoma_desde_la_posicion_guardada(self):
        lector = LectorAlertas(self.ruta)
        self.agregar(linea(3))
        lector.leer()
        guardada = lector.posicion
        lector.cerrar()
        self.agregar(linea(4) + linea(5))
        otro = LectorAlertas(self.ruta, guardada)
        self.assertEqual(self.ids(otro.leer()), ["4", "5"])
        otro.cerrar()

    def test_rotacion_sin_perder_las_ultimas_alertas(self):
        lector = LectorAlertas(self.ruta)
        self.agregar(linea(3))
        self.assertEqual(self.ids(lector.leer()), ["3"])
        self.agregar(linea(4))  # escrita justo antes de rotar
        os.rename(self.ruta, self.ruta.with_name("ossec-alerts-14.json"))
        self.ruta.write_text(linea(5), encoding="utf-8")
        self.assertEqual(self.ids(lector.leer()), ["4", "5"])
        self.agregar(linea(6))
        self.assertEqual(self.ids(lector.leer()), ["6"])
        lector.cerrar()

    def test_archivo_nuevo_todavia_no_creado(self):
        lector = LectorAlertas(self.ruta)
        self.agregar(linea(3))
        os.rename(self.ruta, self.ruta.with_name("ossec-alerts-14.json"))
        self.assertEqual(self.ids(lector.leer()), ["3"])
        self.ruta.write_text(linea(4), encoding="utf-8")
        self.assertEqual(self.ids(lector.leer()), ["4"])
        lector.cerrar()

    def test_posicion_de_un_archivo_que_ya_roto(self):
        guardada = Posicion(inodo=1, desplazamiento=99)
        lector = LectorAlertas(self.ruta, guardada)
        self.assertEqual(self.ids(lector.leer()), ["1", "2"])
        self.assertEqual(lector.perdidas_por_rotacion, 1)
        lector.cerrar()

    def test_truncado_vuelve_al_principio(self):
        lector = LectorAlertas(self.ruta)
        self.ruta.write_text(linea(9), encoding="utf-8")  # mismo inodo, más corto
        self.assertEqual(self.ids(lector.leer()), ["9"])
        lector.cerrar()

    def test_lineas_que_no_son_un_objeto_json(self):
        lector = LectorAlertas(self.ruta)
        self.agregar("no es json\n" + "[1, 2]\n" + "\n" + linea(3))
        self.assertEqual(self.ids(lector.leer()), ["3"])
        self.assertEqual(lector.descartadas, 2)
        lector.cerrar()

    def test_archivo_inexistente_al_arrancar(self):
        self.ruta.unlink()
        lector = LectorAlertas(self.ruta)
        self.assertEqual(lector.leer(), [])
        self.ruta.write_text(linea(1), encoding="utf-8")
        self.assertEqual(self.ids(lector.leer()), ["1"])
        lector.cerrar()


if __name__ == "__main__":
    unittest.main()
