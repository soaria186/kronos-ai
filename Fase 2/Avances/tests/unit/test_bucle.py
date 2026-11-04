import logging
import unittest
from dataclasses import dataclass
from enum import Enum

from validacion.bucle import Bucle


class LectorGuion:
    """Entrega, lectura tras lectura, los lotes del guion; después, nada."""

    def __init__(self, *lotes):
        self.lotes = [list(lote) for lote in lotes]
        self.lecturas = 0
        self.entregadas = 0

    def leer(self):
        self.lecturas += 1
        lote = self.lotes.pop(0) if self.lotes else []
        self.entregadas += len(lote)
        return lote

    @property
    def posicion(self):
        return self.entregadas


class DestinoFalso(Enum):
    APROBADA = "aprobada"


@dataclass(frozen=True)
class ResultadoFalso:
    destino: DestinoFalso = DestinoFalso.APROBADA
    motivo: str | None = None


class ValidadorFalso:
    def __init__(self, falla_con=None):
        self.eventos = []
        self.falla_con = falla_con

    def anotar_llegadas(self, tenant_id, alertas):
        self.eventos.append(("llegadas", tenant_id, [a["id"] for a in alertas]))
        return len(alertas)

    def procesar(self, tenant_id, alerta):
        self.eventos.append(("procesar", tenant_id, alerta["id"]))
        if alerta["id"] == self.falla_con:
            raise RuntimeError("falla de prueba")
        return ResultadoFalso()


def alertas(*ids):
    return [{"id": i} for i in ids]


def correr(bucle, vueltas=10):
    """Como el servicio, pero sin la pausa entre lecturas cuando la cola queda vacía."""
    for _ in range(vueltas):
        bucle.vuelta()


class BucleDeLectura(unittest.TestCase):
    def test_lee_de_nuevo_antes_de_cada_alerta(self):
        lector = LectorGuion(alertas("a", "b"), alertas("c"))
        validador = ValidadorFalso()
        correr(Bucle(lector, validador, 7))

        self.assertEqual(
            validador.eventos,
            [
                ("llegadas", 7, ["a", "b"]),
                ("procesar", 7, "a"),
                ("llegadas", 7, ["c"]),  # llegó mientras se procesaba «a»
                ("procesar", 7, "b"),
                ("procesar", 7, "c"),
            ],
        )
        self.assertEqual(lector.lecturas, 10)  # una por vuelta

    def test_lo_que_llega_se_cuenta_antes_de_procesarlo(self):
        lector = LectorGuion(alertas("a"), alertas("b", "c"))
        validador = ValidadorFalso()
        correr(Bucle(lector, validador, 1))

        orden = [(e[0], e[2]) for e in validador.eventos]
        self.assertLess(orden.index(("llegadas", ["b", "c"])), orden.index(("procesar", "b")))

    def test_vuelta_avisa_si_quedan_en_la_cola(self):
        bucle = Bucle(LectorGuion(alertas("a", "b")), ValidadorFalso(), 1)

        self.assertTrue(bucle.vuelta())
        self.assertEqual(bucle.pendientes, 1)
        self.assertFalse(bucle.vuelta())
        self.assertFalse(bucle.vuelta())  # sin nada nuevo

    def test_la_posicion_se_guarda_solo_con_la_cola_vacia(self):
        lector = LectorGuion(alertas("a", "b"), alertas("c"))
        guardadas = []
        bucle = Bucle(lector, ValidadorFalso(), 1, guardadas.append)

        bucle.vuelta()
        bucle.vuelta()
        self.assertEqual(guardadas, [])  # todavía queda «c»
        bucle.vuelta()
        self.assertEqual(guardadas, [3])  # la posición incluye las tres

    def test_sin_alertas_no_guarda_ni_registra(self):
        guardadas = []
        bucle = Bucle(LectorGuion(), ValidadorFalso(), 1, guardadas.append)

        with self.assertNoLogs("soar-validate", level="INFO"):
            self.assertFalse(bucle.vuelta())
        self.assertEqual(guardadas, [])

    def test_registra_el_resumen_al_vaciar_la_cola(self):
        bucle = Bucle(LectorGuion(alertas("a", "b")), ValidadorFalso(), 1)

        with self.assertLogs("soar-validate", level="INFO") as registros:
            correr(bucle)
        self.assertEqual(
            registros.output, ["INFO:soar-validate:lote de 2 alertas: {'aprobada': 2}"]
        )

    def test_una_alerta_con_error_no_detiene_a_las_demas(self):
        validador = ValidadorFalso(falla_con="a")
        bucle = Bucle(LectorGuion(alertas("a", "b")), validador, 1)

        with self.assertLogs("soar-validate", level="INFO") as registros:
            correr(bucle)
        self.assertIn(("procesar", 1, "b"), validador.eventos)
        self.assertIn("lote de 2 alertas: {'error': 1, 'aprobada': 1}", registros.output[-1])

    def test_si_no_se_puede_guardar_la_posicion_sigue(self):
        def falla(_):
            raise OSError("disco lleno")

        bucle = Bucle(LectorGuion(alertas("a")), ValidadorFalso(), 1, falla)

        with self.assertLogs("soar-validate", level=logging.ERROR):
            self.assertFalse(bucle.vuelta())


if __name__ == "__main__":
    unittest.main()
