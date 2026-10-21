"""Pruebas de integración de los avisos de SOAR-NOTIFY contra la bitácora real."""

import random
import unittest

from tests.integracion._base import dsn_de_pruebas

DSN = dsn_de_pruebas()

if DSN:
    from persistencia.repositorio import Decision, EstadoInvalido, Repositorio


@unittest.skipUnless(DSN, "falta KRONOS_DSN")
class TestAvisos(unittest.TestCase):
    def setUp(self):
        self.t = random.randint(100_000, 2_000_000_000)
        self.repo = Repositorio(DSN)

    def ticket(self, ref, playbook, nivel):
        t = self.repo.registrar_alerta(self.t, ref, "prueba", 12, {"alerta": {}})
        self.repo.registrar_decision(
            self.t, t.ticket_id, Decision("F1", playbook, 0.9, nivel)
        )
        return t.ticket_id

    def ejecutar(self, exito):
        ticket = self.repo.tomar_para_ejecutar(self.t)
        self.repo.registrar_ejecucion(self.t, ticket.ticket_id, exito, {"motivo": "X"})
        return ticket.ticket_id

    def pendientes(self):
        return [(e.evento, e.ticket_id) for e in self.repo.eventos_para_avisar(self.t)]

    def test_solo_lo_que_hay_que_avisar(self):
        n1 = self.ticket("n1", "PB-F1-02", 1)
        self.ejecutar(True)  # nivel 1 bien: no se avisa
        n2 = self.ticket("n2", "PB-F1-03", 2)
        self.ejecutar(True)  # nivel 2 bien: se avisa
        n3 = self.ticket("n3", "PB-F3-03", 3)  # nivel 3: se pide aprobación
        f = self.ticket("f", "PB-F1-03", 2)
        self.ejecutar(False)  # falla: se avisa
        self.repo.abrir_cortacircuito(self.t, "30 alertas en 10 minutos")
        self.assertEqual(
            self.pendientes(),
            [
                ("EJECUCION_OK", n2),
                ("DECISION", n3),
                ("EJECUCION_FALLIDA", f),
                ("CORTACIRCUITO_ABIERTO", None),
            ],
        )
        self.assertNotIn(n1, [t for _, t in self.pendientes()])

    def test_lo_avisado_no_se_repite(self):
        self.ticket("a", "PB-F3-03", 3)
        self.ticket("b", "PB-F3-03", 3)
        primero, segundo = self.repo.eventos_para_avisar(self.t)
        self.repo.registrar_aviso(self.t, primero.seq, "telegram:1:101")
        self.assertEqual(
            [e.seq for e in self.repo.eventos_para_avisar(self.t)], [segundo.seq]
        )
        self.repo.registrar_aviso(self.t, segundo.seq, "telegram:1:102")
        self.assertEqual(self.repo.eventos_para_avisar(self.t), [])

    def test_aviso_de_evento_inexistente(self):
        with self.assertRaises(ValueError):
            self.repo.registrar_aviso(self.t, 999_999, "x")

    def test_rechazo_desde_telegram_queda_con_actor_y_motivo(self):
        tid = self.ticket("r", "PB-F3-03", 3)
        self.repo.denegar(self.t, tid, "telegram:patricio", "falso positivo")
        with self.repo._transaccion(self.t) as cur:
            cur.execute(
                "SELECT actor, detalle->>'motivo' FROM auditoria"
                " WHERE ticket_id = %s AND evento = 'APROBACION_DENEGADA'",
                (tid,),
            )
            self.assertEqual(cur.fetchall(), [("telegram:patricio", "falso positivo")])
        with self.assertRaises(EstadoInvalido):
            self.repo.aprobar(self.t, tid, "telegram:nicolas")


if __name__ == "__main__":
    unittest.main()
