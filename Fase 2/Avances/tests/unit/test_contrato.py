import json
import unittest

from validacion.contrato import (
    LARGO_MAXIMO_RESPUESTA,
    EsquemaInvalido,
    esquema_familia,
    esquema_playbook,
    leer_familia,
    leer_playbook,
)

CANDIDATOS = ("PB-F1-01", "PB-F1-02", "PB-F1-03")


class LeerFamilia(unittest.TestCase):
    def test_respuesta_valida(self):
        r = leer_familia('{"familia": "F3", "confianza": 0.82}')
        self.assertEqual((r.familia, r.confianza), ("F3", 0.82))

    def test_confianza_entera_en_los_extremos(self):
        self.assertEqual(
            leer_familia('{"familia": "F1", "confianza": 0}').confianza, 0.0
        )
        self.assertEqual(
            leer_familia('{"familia": "F1", "confianza": 1}').confianza, 1.0
        )

    def test_espacios_alrededor_permitidos(self):
        self.assertEqual(
            leer_familia(' \n{"familia":"F6","confianza":0.5}\n').familia, "F6"
        )

    def test_rechazos(self):
        casos = {
            "texto libre": "F3",
            "texto antes del JSON": 'Respuesta: {"familia": "F3", "confianza": 0.8}',
            "no es objeto": '["F3", 0.8]',
            "falta confianza": '{"familia": "F3"}',
            "clave de más": '{"familia": "F3", "confianza": 0.8, "motivo": "x"}',
            "clave repetida": '{"familia": "F1", "familia": "F3", "confianza": 0.8}',
            "familia inexistente": '{"familia": "F9", "confianza": 0.8}',
            "familia en minúscula": '{"familia": "f3", "confianza": 0.8}',
            "familia no texto": '{"familia": 3, "confianza": 0.8}',
            "confianza texto": '{"familia": "F3", "confianza": "0.8"}',
            "confianza booleana": '{"familia": "F3", "confianza": true}',
            "confianza nula": '{"familia": "F3", "confianza": null}',
            "confianza mayor que 1": '{"familia": "F3", "confianza": 1.5}',
            "confianza negativa": '{"familia": "F3", "confianza": -0.1}',
            "NaN": '{"familia": "F3", "confianza": NaN}',
            "infinito": '{"familia": "F3", "confianza": Infinity}',
            "vacío": "",
            "demasiado largo": '{"familia": "F3", "confianza": 0.8'
            + " " * LARGO_MAXIMO_RESPUESTA
            + "}",
        }
        for nombre, texto in casos.items():
            with self.subTest(nombre), self.assertRaises(EsquemaInvalido):
                leer_familia(texto)

    def test_no_texto(self):
        with self.assertRaises(EsquemaInvalido):
            leer_familia(None)


class LeerPlaybook(unittest.TestCase):
    def test_respuesta_valida(self):
        r = leer_playbook('{"playbook_id": "PB-F1-02", "confianza": 0.7}', CANDIDATOS)
        self.assertEqual((r.playbook_id, r.confianza), ("PB-F1-02", 0.7))

    def test_playbook_de_otra_familia(self):
        with self.assertRaises(EsquemaInvalido):
            leer_playbook('{"playbook_id": "PB-F3-01", "confianza": 0.7}', CANDIDATOS)

    def test_playbook_inventado(self):
        with self.assertRaises(EsquemaInvalido):
            leer_playbook('{"playbook_id": "PB-F1-99", "confianza": 0.7}', CANDIDATOS)

    def test_clave_del_paso_1(self):
        with self.assertRaises(EsquemaInvalido):
            leer_playbook('{"familia": "F1", "confianza": 0.7}', CANDIDATOS)


class Esquemas(unittest.TestCase):
    def test_esquema_familia(self):
        e = esquema_familia()
        self.assertEqual(
            e["properties"]["familia"]["enum"], ["F1", "F2", "F3", "F4", "F5", "F6"]
        )
        self.assertEqual(e["required"], ["familia", "confianza"])
        self.assertIs(e["additionalProperties"], False)
        json.dumps(e)

    def test_esquema_playbook_limita_a_candidatos(self):
        e = esquema_playbook(CANDIDATOS)
        self.assertEqual(e["properties"]["playbook_id"]["enum"], list(CANDIDATOS))

    def test_esquema_playbook_sin_candidatos(self):
        with self.assertRaises(ValueError):
            esquema_playbook(())


if __name__ == "__main__":
    unittest.main()
