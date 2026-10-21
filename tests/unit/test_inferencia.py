import unittest

from decision.inferencia import (
    Clasificacion,
    FallaSegura,
    MotivoFalla,
    MotorNoDisponible,
    TiempoExcedido,
    clasificar,
)
from decision.plantillas import Plantillas

PLANTILLAS = Plantillas.cargar()


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class ModeloFalso:
    """Devuelve respuestas en orden; cada una puede ser texto o una excepción.

    demora: segundos que avanza el reloj en cada llamada.
    """

    def __init__(self, respuestas, reloj, demora=1.0):
        self.respuestas = list(respuestas)
        self.reloj = reloj
        self.demora = demora
        self.llamadas = []

    def generar(self, prompt, esquema, plazo):
        self.llamadas.append((prompt, esquema, plazo))
        self.reloj.t += self.demora
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


PASO1 = '{"familia": "F1", "confianza": 0.9}'
PASO2 = '{"playbook_id": "PB-F1-02", "confianza": 0.7}'


class Clasificar(unittest.TestCase):
    def setUp(self):
        self.reloj = Reloj()

    def ejecutar(self, respuestas, plazo=30.0, demora=1.0):
        self.modelo = ModeloFalso(respuestas, self.reloj, demora)
        return clasificar("alerta X", self.modelo, PLANTILLAS, plazo, self.reloj)

    def test_camino_feliz(self):
        r = self.ejecutar([PASO1, PASO2])
        self.assertEqual(r, Clasificacion("F1", 0.9, "PB-F1-02", 0.7))

    def test_el_ambito_de_la_ip_llega_sólo_al_paso_2(self):
        self.modelo = ModeloFalso([PASO1, PASO2], self.reloj)
        clasificar(
            "alerta X",
            self.modelo,
            PLANTILLAS,
            30.0,
            self.reloj,
            ambito_ip="interna",
        )
        (paso1, _, _), (paso2, _, _) = self.modelo.llamadas
        self.assertNotIn("ORIGEN DE LA ALERTA", paso1)
        self.assertIn("ORIGEN DE LA ALERTA", paso2)
        self.assertIn("es INTERNA", paso2)

    def test_sin_ambito_el_paso_2_no_cambia(self):
        self.ejecutar([PASO1, PASO2])
        self.assertNotIn("ORIGEN DE LA ALERTA", self.modelo.llamadas[1][0])

    def test_paso_2_recibe_los_candidatos_de_la_familia_y_el_plazo_restante(self):
        self.ejecutar([PASO1, PASO2], plazo=30.0, demora=4.0)
        (_, esquema1, plazo1), (prompt2, esquema2, plazo2) = self.modelo.llamadas
        self.assertEqual(esquema1["properties"]["familia"]["enum"][0], "F1")
        self.assertEqual(
            esquema2["properties"]["playbook_id"]["enum"],
            ["PB-F1-01", "PB-F1-02", "PB-F1-03", "PB-F1-04", "PB-F1-05"],
        )
        self.assertIn("F1 - Abuso de credenciales", prompt2)
        self.assertEqual((plazo1, plazo2), (30.0, 26.0))

    def test_la_confianza_a_validar_es_la_menor_de_los_dos_pasos(self):
        r = self.ejecutar(['{"familia": "F1", "confianza": 0.95}', PASO2])
        self.assertEqual(r.confianza, 0.7)
        r = self.ejecutar(['{"familia": "F1", "confianza": 0.6}', PASO2])
        self.assertEqual(r.confianza, 0.6)

    def test_motor_caido_en_el_paso_1(self):
        r = self.ejecutar([MotorNoDisponible("conexión rechazada")])
        self.assertEqual(
            (r.motivo, r.paso), (MotivoFalla.MOTOR_INFERENCIA_NO_DISPONIBLE, 1)
        )
        self.assertEqual(len(self.modelo.llamadas), 1)

    def test_motor_caido_en_el_paso_2(self):
        r = self.ejecutar([PASO1, MotorNoDisponible("500")])
        self.assertEqual(
            (r.motivo, r.paso), (MotivoFalla.MOTOR_INFERENCIA_NO_DISPONIBLE, 2)
        )

    def test_timeout_del_cliente(self):
        r = self.ejecutar([TiempoExcedido("sin respuesta")])
        self.assertEqual((r.motivo, r.paso), (MotivoFalla.TIEMPO_EXCEDIDO, 1))

    def test_respuesta_valida_pero_tardia(self):
        r = self.ejecutar([PASO1], plazo=10.0, demora=11.0)
        self.assertEqual((r.motivo, r.paso), (MotivoFalla.TIEMPO_EXCEDIDO, 1))

    def test_sin_tiempo_para_el_paso_2(self):
        r = self.ejecutar([PASO1, PASO2], plazo=10.0, demora=10.0)
        self.assertIsInstance(r, FallaSegura)
        self.assertEqual((r.motivo, r.paso), (MotivoFalla.TIEMPO_EXCEDIDO, 2))
        self.assertEqual(len(self.modelo.llamadas), 1)

    def test_esquema_invalido_en_el_paso_1_no_llama_al_paso_2(self):
        r = self.ejecutar(['{"familia": "F9", "confianza": 0.9}', PASO2])
        self.assertEqual((r.motivo, r.paso), (MotivoFalla.ESQUEMA_INVALIDO, 1))
        self.assertEqual(len(self.modelo.llamadas), 1)

    def test_playbook_de_otra_familia_es_esquema_invalido(self):
        r = self.ejecutar([PASO1, '{"playbook_id": "PB-F3-01", "confianza": 0.9}'])
        self.assertEqual((r.motivo, r.paso), (MotivoFalla.ESQUEMA_INVALIDO, 2))

    def test_los_motivos_coinciden_con_el_esquema_de_tickets(self):
        self.assertEqual(
            {m.value for m in MotivoFalla},
            {"MOTOR_INFERENCIA_NO_DISPONIBLE", "TIEMPO_EXCEDIDO", "ESQUEMA_INVALIDO"},
        )

    def test_plazo_no_positivo(self):
        with self.assertRaises(ValueError):
            self.ejecutar([PASO1], plazo=0)


if __name__ == "__main__":
    unittest.main()
