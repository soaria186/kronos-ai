"""Pruebas de integración del recuperador de tickets huérfanos (Repositorio.recuperar_huerfanos).

Mismas condiciones que test_repositorio.py: KRONOS_DSN como kronos_worker e inquilinos al
azar. Para simular el paso del tiempo se retrocede tickets.creado_en como kronos_admin
(KRONOS_DSN_ADMIN); sin esa variable se omiten.
"""

import random
import unittest

from tests.integracion._base import dsn_de_pruebas

DSN = dsn_de_pruebas()
DSN_ADMIN = dsn_de_pruebas("KRONOS_DSN_ADMIN")

if DSN:
    import psycopg

    from notificacion.mensajes import componer
    from persistencia.repositorio import (
        EVENTOS_AVISABLES,
        Decision,
        Repositorio,
        TicketYaDecidido,
    )


@unittest.skipUnless(DSN and DSN_ADMIN, "faltan KRONOS_DSN o KRONOS_DSN_ADMIN")
class TestTicketsHuerfanos(unittest.TestCase):
    def setUp(self):
        self.t = random.randint(100_000, 2_000_000_000)
        self.validate = Repositorio(DSN)
        self.execute = Repositorio(DSN, actor="soar-execute")

    def nuevo(self, ref):
        return self.validate.registrar_alerta(self.t, ref, "Fuerza bruta SSH", 10).ticket_id

    def envejecer(self, ticket_id, minutos):
        with psycopg.connect(DSN_ADMIN, autocommit=True) as conexion:
            conexion.execute(
                "UPDATE tickets SET creado_en = now() - make_interval(mins => %s)"
                " WHERE tenant_id = %s AND id = %s",
                (minutos, self.t, ticket_id),
            )

    def estado(self, ticket_id):
        with self.validate._transaccion(self.t) as cur:
            cur.execute(
                "SELECT execution_status, rechazo_motivo FROM tickets WHERE id = %s",
                (ticket_id,),
            )
            return cur.fetchone()

    def eventos(self, ticket_id):
        with self.validate._transaccion(self.t) as cur:
            cur.execute(
                "SELECT evento, actor, detalle FROM auditoria WHERE ticket_id = %s ORDER BY seq",
                (ticket_id,),
            )
            return cur.fetchall()

    def test_huerfano_pasa_a_revision_manual_con_aviso(self):
        ticket = self.nuevo("h-1")
        self.envejecer(ticket, 11)
        self.assertEqual(self.execute.recuperar_huerfanos(self.t), [ticket])
        self.assertEqual(self.estado(ticket), ("MANUAL_TRIAGE", "DECISION_NO_REGISTRADA"))
        evento, actor, detalle = self.eventos(ticket)[-1]
        self.assertEqual((evento, actor), ("TICKET_SIN_DECISION", "soar-execute"))
        self.assertEqual(detalle["plazo_minutos"], 10)
        self.assertTrue(detalle["creado_en"].endswith("Z"))
        # NOTIFY lo ofrece como aviso.
        avisos = self.execute.eventos_para_avisar(self.t)
        self.assertIn(("TICKET_SIN_DECISION", ticket), [(a.evento, a.ticket_id) for a in avisos])
        # Una segunda pasada no lo vuelve a tocar.
        self.assertEqual(self.execute.recuperar_huerfanos(self.t), [])
        with self.validate._transaccion(self.t) as cur:
            cur.execute("SELECT fn_verificar_cadena(%s) IS NULL", (self.t,))
            self.assertTrue(cur.fetchone()[0])

    def test_no_toca_tickets_recientes_ni_decididos(self):
        reciente = self.nuevo("h-2")
        self.envejecer(reciente, 5)
        aprobado = self.nuevo("h-3")
        self.validate.registrar_decision(
            self.t, aprobado, Decision("F1", "PB-F1-02", 0.9, 1, equipo="x")
        )
        rechazado = self.nuevo("h-4")
        self.validate.registrar_decision(
            self.t, rechazado, Decision("F1", None, 0.4, None, motivo="CONFIANZA_BAJA")
        )
        for ticket in (aprobado, rechazado):
            self.envejecer(ticket, 60)
        self.assertEqual(self.execute.recuperar_huerfanos(self.t), [])
        self.assertEqual(self.estado(reciente), ("PENDING", None))
        self.assertEqual(self.estado(aprobado), ("PENDING", None))
        self.assertEqual(self.estado(rechazado), ("MANUAL_TRIAGE", "CONFIANZA_BAJA"))

    def test_validate_no_decide_un_ticket_ya_recuperado(self):
        ticket = self.nuevo("h-5")
        self.envejecer(ticket, 15)
        self.execute.recuperar_huerfanos(self.t)
        with self.assertRaises(TicketYaDecidido):
            self.validate.registrar_decision(
                self.t, ticket, Decision("F1", "PB-F1-02", 0.9, 1, equipo="x")
            )
        self.assertEqual(self.estado(ticket), ("MANUAL_TRIAGE", "DECISION_NO_REGISTRADA"))

    def test_otro_inquilino_no_se_toca(self):
        ticket = self.nuevo("h-6")
        self.envejecer(ticket, 30)
        self.assertEqual(self.execute.recuperar_huerfanos(self.t + 1), [])
        self.assertEqual(self.estado(ticket), ("PENDING", None))

    def test_plazo_invalido(self):
        with self.assertRaises(ValueError):
            self.execute.recuperar_huerfanos(self.t, minutos=0)

    def test_todos_los_eventos_avisables_tienen_mensaje(self):
        class Ev:
            seq, ticket_id, detalle, titulo, playbook_id, nivel = 1, 7, {}, "x", None, None

        for evento in EVENTOS_AVISABLES:
            with self.subTest(evento=evento):
                ev = Ev()
                ev.evento = evento
                self.assertTrue(componer(1, ev).texto)


if __name__ == "__main__":
    unittest.main()
