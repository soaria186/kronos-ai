"""Pruebas de integración de alertas_guardadas: tope, huella en la bitácora y retención.

Mismas condiciones que test_repositorio.py: KRONOS_DSN como kronos_worker e inquilinos al
azar. Las pruebas de la purga necesitan además KRONOS_DSN_ADMIN (kronos_admin), porque
fn_purgar_alertas sólo la ejecuta el administrador; sin esa variable se omiten.

Para simular el paso del tiempo, las pruebas de la purga retroceden guardada_en como
kronos_admin (la tabla no es inmutable; los servicios no pueden modificarla).
"""

import random
import unittest

from tests.integracion._base import dsn_de_pruebas

DSN = dsn_de_pruebas()
DSN_ADMIN = dsn_de_pruebas("KRONOS_DSN_ADMIN")

if DSN:
    import psycopg

    from persistencia.alertas import TOPE_BYTES
    from persistencia.repositorio import Decision, Repositorio


def _alerta(ref: str, **extra) -> dict:
    alerta = {
        "timestamp": "2026-10-21T17:00:00.000+0000",
        "rule": {"level": 10, "id": "100101", "description": "Kronos F1: fuerza bruta",
                 "groups": ["sshd", "kronos_f1"]},
        "agent": {"id": "001", "name": "EP-SRV-01", "ip": "192.0.2.10"},
        "id": ref,
        "full_log": "sshd: Failed password for invalid user admin from 203.0.113.50",
        "data": {"srcip": "203.0.113.50", "dstuser": "admin"},
    }
    alerta.update(extra)
    return alerta


@unittest.skipUnless(DSN, "falta KRONOS_DSN")
class TestAlertasGuardadas(unittest.TestCase):
    def setUp(self):
        self.t = random.randint(100_000, 2_000_000_000)
        self.validate = Repositorio(DSN)
        self.execute = Repositorio(DSN, actor="soar-execute")

    def sql(self, consulta, *parametros):
        with self.validate._transaccion(self.t) as cur:
            cur.execute(consulta, parametros)
            return cur.fetchall()

    def registrar(self, alerta):
        return self.validate.registrar_alerta(
            self.t, alerta["id"], "Fuerza bruta SSH", 10, {"alerta": alerta}
        ).ticket_id

    def evento(self, ticket_id):
        return self.sql(
            "SELECT detalle FROM auditoria WHERE ticket_id = %s AND evento = 'ALERTA_RECIBIDA'",
            ticket_id,
        )[0][0]

    def test_la_bitacora_guarda_la_huella_y_no_la_alerta(self):
        ticket = self.registrar(_alerta("r-1"))
        detalle = self.evento(ticket)
        self.assertNotIn("alerta", detalle)
        huella = detalle["alerta_guardada"]
        self.assertEqual(len(huella["sha256"]), 64)
        self.assertEqual((huella["agente"], huella["regla"]), ("001", "100101"))
        self.assertFalse(huella["recortada"])
        self.assertNotIn("203.0.113.50", str(detalle))
        self.assertEqual(self.sql("SELECT * FROM fn_verificar_alertas(%s)", self.t), [])
        self.assertTrue(self.sql("SELECT fn_verificar_cadena(%s) IS NULL", self.t)[0][0])

    def test_execute_recibe_la_alerta_completa(self):
        alerta = _alerta("r-2")
        ticket = self.registrar(alerta)
        self.validate.registrar_decision(
            self.t, ticket, Decision("F1", "PB-F1-02", 0.9, 1, equipo="EP-SRV-01")
        )
        tomado = self.execute.tomar_para_ejecutar(self.t)
        self.assertEqual(tomado.alerta, {"alerta": alerta})

    def test_alerta_enorme_se_recorta_y_cabe(self):
        alerta = _alerta("r-3", full_log="x" * 300_000)
        ticket = self.registrar(alerta)
        guardada, bytes_original, recortada = self.sql(
            "SELECT alerta, bytes_original, recortada FROM alertas_guardadas"
            " WHERE ticket_id = %s",
            ticket,
        )[0]
        self.assertTrue(recortada)
        self.assertGreater(bytes_original, 300_000)
        self.assertLess(len(guardada["full_log"]), 5_000)
        self.assertEqual(guardada["data"]["srcip"], "203.0.113.50")
        self.assertTrue(self.evento(ticket)["alerta_guardada"]["recortada"])
        self.assertLessEqual(self.evento(ticket)["alerta_guardada"]["bytes"], TOPE_BYTES)

    def test_alerta_con_muchas_claves_guarda_lo_esencial(self):
        basura = {f"k{i}": "v" * 50 for i in range(5_000)}
        ticket = self.registrar(_alerta("r-4", data={"srcip": "203.0.113.50", **basura}))
        guardada = self.sql(
            "SELECT alerta FROM alertas_guardadas WHERE ticket_id = %s", ticket
        )[0][0]
        self.assertEqual(guardada["data"], {"srcip": "203.0.113.50"})
        self.assertEqual(guardada["agent"]["id"], "001")
        self.assertIn("kronos_recorte", guardada)

    def test_el_servicio_no_puede_borrar_ni_modificar(self):
        ticket = self.registrar(_alerta("r-5"))
        for consulta in (
            "DELETE FROM alertas_guardadas WHERE ticket_id = %s",
            "UPDATE alertas_guardadas SET recortada = true WHERE ticket_id = %s",
        ):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                self.sql(consulta, ticket)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.sql("SELECT * FROM fn_purgar_alertas(90)")

    def test_ticket_antiguo_con_la_alerta_en_la_bitacora_sigue_funcionando(self):
        # Antes de alertas_guardadas, VALIDATE escribía la alerta dentro del evento.
        alerta = _alerta("r-6")
        with self.validate._transaccion(self.t) as cur:
            cur.execute(
                "INSERT INTO tickets (tenant_id, alerta_ref, titulo, severidad)"
                " VALUES (%s, 'r-6', 'Fuerza bruta SSH', 10) RETURNING id",
                (self.t,),
            )
            ticket = cur.fetchone()[0]
            self.validate._evento(cur, self.t, ticket, "ALERTA_RECIBIDA", {"alerta": alerta})
        self.validate.registrar_decision(
            self.t, ticket, Decision("F1", "PB-F1-02", 0.9, 1, equipo="EP-SRV-01")
        )
        self.assertEqual(self.execute.tomar_para_ejecutar(self.t).alerta, {"alerta": alerta})

    def test_ticket_sin_alerta_entrega_vacio(self):
        # Sin alerta guardada (purgada) ni en la bitácora: EXECUTE recibe {} y falla seguro.
        ticket = self.validate.registrar_alerta(self.t, "r-7", "Fuerza bruta SSH", 10)
        self.validate.registrar_decision(
            self.t, ticket.ticket_id, Decision("F1", "PB-F1-02", 0.9, 1, equipo="x")
        )
        self.assertEqual(self.execute.tomar_para_ejecutar(self.t).alerta, {})


@unittest.skipUnless(DSN and DSN_ADMIN, "faltan KRONOS_DSN o KRONOS_DSN_ADMIN")
class TestRetencion(unittest.TestCase):
    def setUp(self):
        self.t = random.randint(100_000, 2_000_000_000)
        self.repo = Repositorio(DSN)
        self.execute = Repositorio(DSN, actor="soar-execute")

    def admin(self, consulta, *parametros):
        with psycopg.connect(DSN_ADMIN, autocommit=True) as conexion:
            cursor = conexion.execute(consulta, parametros)
            return cursor.fetchall() if cursor.description else []

    def nueva(self, ref, decision=None):
        ticket = self.repo.registrar_alerta(
            self.t, ref, "Fuerza bruta SSH", 10, {"alerta": _alerta(ref)}
        ).ticket_id
        if decision is not None:
            self.repo.registrar_decision(self.t, ticket, decision)
        return ticket

    def envejecer(self, dias):
        self.admin(
            "UPDATE alertas_guardadas SET guardada_en = now() - make_interval(days => %s)"
            " WHERE tenant_id = %s",
            dias,
            self.t,
        )

    def quedan(self):
        filas = self.admin(
            "SELECT ticket_id FROM alertas_guardadas WHERE tenant_id = %s ORDER BY 1", self.t
        )
        return [f[0] for f in filas]

    def purgar(self, dias=90):
        return dict(self.admin("SELECT * FROM fn_purgar_alertas(%s)", dias)).get(self.t, 0)

    def test_purga_las_vencidas_y_deja_evento(self):
        rechazado = self.nueva("p-1", Decision("F1", None, 0.4, None, motivo="CONFIANZA_BAJA"))
        reciente = self.nueva("p-2", Decision("F1", None, 0.4, None, motivo="CONFIANZA_BAJA"))
        self.admin(
            "UPDATE alertas_guardadas SET guardada_en = now() - interval '100 days'"
            " WHERE tenant_id = %s AND ticket_id = %s",
            self.t,
            rechazado,
        )
        self.assertEqual(self.purgar(90), 1)
        self.assertEqual(self.quedan(), [reciente])
        evento = self.admin(
            "SELECT actor, detalle FROM auditoria WHERE tenant_id = %s"
            " AND evento = 'ALERTAS_PURGADAS'",
            self.t,
        )
        self.assertEqual(len(evento), 1)
        self.assertEqual(evento[0][0], "soar-retencion")
        self.assertEqual(evento[0][1]["alertas"], 1)
        self.assertTrue(
            self.admin("SELECT fn_verificar_cadena(%s) IS NULL", self.t)[0][0]
        )
        # El ticket purgado conserva su huella en la bitácora.
        huella = self.admin(
            "SELECT detalle FROM auditoria WHERE tenant_id = %s AND ticket_id = %s"
            " AND evento = 'ALERTA_RECIBIDA'",
            self.t,
            rechazado,
        )[0][0]
        self.assertIn("sha256", huella["alerta_guardada"])

    def test_no_purga_tickets_en_curso_ni_medidas_por_revertir(self):
        pendiente = self.nueva("p-3", Decision("F1", "PB-F1-02", 0.9, 1, equipo="x"))
        nivel3 = self.nueva("p-4", Decision("F3", "PB-F3-03", 0.9, 3, equipo="x"))
        self.envejecer(200)
        self.assertEqual(self.purgar(90), 0)
        self.assertEqual(self.quedan(), sorted([pendiente, nivel3]))

        # Nivel 1 ejecutado, con su reversión programada: tampoco.
        tomado = self.execute.tomar_para_ejecutar(self.t)
        self.execute.registrar_ejecucion(
            self.t, tomado.ticket_id, True, {}, reversion_en_minutos=60
        )
        self.assertEqual(self.purgar(90), 0)

        # Reversión fallida: sigue haciendo falta para pedirla otra vez.
        self.admin(
            "UPDATE temporizadores SET vence_en = now() WHERE tenant_id = %s", self.t
        )
        self.execute.tomar_reversion(self.t)
        self.execute.registrar_reversion(self.t, tomado.ticket_id, False, {"error": "x"})
        self.assertEqual(self.purgar(90), 0)
        self.assertIn(tomado.ticket_id, self.quedan())

        # Revertida con éxito: ya se puede purgar.
        self.execute.registrar_reversion(self.t, tomado.ticket_id, True, {})
        self.assertEqual(self.purgar(90), 1)
        self.assertNotIn(tomado.ticket_id, self.quedan())

    def test_plazo_minimo(self):
        with self.assertRaises(psycopg.errors.RaiseException):
            self.admin("SELECT * FROM fn_purgar_alertas(0)")


if __name__ == "__main__":
    unittest.main()
