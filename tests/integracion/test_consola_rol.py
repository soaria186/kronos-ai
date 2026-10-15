"""Permisos del rol kronos_console (04_consola.sql).

Necesita KRONOS_DSN (kronos_worker, para preparar datos) y KRONOS_DSN_CONSOLA
(kronos_console). Sin ellas, se omite.
"""

import os
import random
import unittest

DSN = os.environ.get("KRONOS_DSN")
DSN_CONSOLA = os.environ.get("KRONOS_DSN_CONSOLA")

if DSN and DSN_CONSOLA:
    import psycopg

    from persistencia.repositorio import Decision, Repositorio


@unittest.skipUnless(DSN and DSN_CONSOLA, "faltan KRONOS_DSN o KRONOS_DSN_CONSOLA")
class TestRolConsola(unittest.TestCase):
    def setUp(self):
        self.t = random.randint(100_000, 2_000_000_000)
        self.worker = Repositorio(DSN)
        alerta = self.worker.registrar_alerta(self.t, "c1", "prueba", 12, {})
        self.ticket = alerta.ticket_id
        self.worker.registrar_decision(self.t, self.ticket, Decision("F3", "PB-F3-03", 0.9, 3))

    def consola(self, sql, *parametros, tenant=None):
        with psycopg.connect(DSN_CONSOLA) as conn, conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant or self.t),))
            cur.execute(sql, parametros)
            return cur.fetchall() if cur.description else None

    def assertRechazado(self, sql, *parametros, estado=None, tenant=None):
        with self.assertRaises(psycopg.Error) as caso:
            self.consola(sql, *parametros, tenant=tenant)
        if estado:
            self.assertEqual(caso.exception.sqlstate, estado)

    def test_lee_las_vistas_de_su_inquilino(self):
        filas = self.consola("SELECT id, execution_status FROM frontend.tickets")
        self.assertEqual(filas, [(self.ticket, "AWAITING_APPROVAL")])
        self.assertEqual(self.consola("SELECT tipo FROM frontend.temporizadores"), [("APROBACION",)])
        self.assertEqual(self.consola("SELECT count(*) FROM frontend.tickets", tenant=1)[0][0], 0)

    def test_no_toca_las_tablas(self):
        self.assertRechazado("SELECT * FROM public.tickets", estado="42501")
        self.assertRechazado(
            "UPDATE public.tickets SET execution_status = 'PENDING'", estado="42501"
        )
        self.assertRechazado("INSERT INTO public.auditoria (tenant_id) VALUES (1)", estado="42501")

    def test_no_llama_a_las_funciones_de_apoyo(self):
        self.assertRechazado(
            "SELECT consola._evento(%s, %s, 'X', 'yo', '{}')", self.t, self.ticket, estado="42501"
        )

    def test_aprueba_con_su_nombre(self):
        self.consola("SELECT consola.aprobar(%s, 'consola:nicolas')", self.ticket)
        estado = self.consola("SELECT execution_status FROM frontend.tickets")[0][0]
        self.assertEqual(estado, "PENDING")
        actor = self.consola(
            "SELECT actor FROM frontend.auditoria WHERE evento = 'APROBACION_CONCEDIDA'"
        )
        self.assertEqual(actor, [("consola:nicolas",)])

    def test_no_aprueba_tickets_de_otro_inquilino(self):
        otro = random.randint(100_000, 2_000_000_000)
        self.assertRechazado(
            "SELECT consola.aprobar(%s, 'consola:nicolas')", self.ticket, estado="KR001", tenant=otro
        )

    def test_rechazo_exige_motivo(self):
        self.assertRechazado(
            "SELECT consola.denegar(%s, 'consola:nicolas', '  ')", self.ticket, estado="KR002"
        )

    def test_sin_inquilino_falla_cerrado(self):
        with (
            psycopg.connect(DSN_CONSOLA) as conn,
            conn.cursor() as cur,
            self.assertRaises(psycopg.Error),
        ):
            cur.execute("SELECT consola.aprobar(%s, 'consola:nicolas')", (self.ticket,))

    def test_cortacircuito(self):
        self.assertRechazado(
            "SELECT consola.cerrar_cortacircuito('consola:nicolas', 'revisado')", estado="KR001"
        )
        self.worker.abrir_cortacircuito(self.t, "30 alertas en 10 minutos")
        self.consola("SELECT consola.cerrar_cortacircuito('consola:nicolas', 'falsa alarma')")
        self.assertFalse(self.worker.cortacircuito_abierto(self.t))
        self.assertEqual(
            self.consola("SELECT abierto FROM frontend.cortacircuito"), [(False,)]
        )


if __name__ == "__main__":
    unittest.main()
