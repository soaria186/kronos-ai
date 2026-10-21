"""Pruebas de integración del contrato VALIDATE -> EXECUTE: ALERTA_RECIBIDA.

Mismas condiciones que test_repositorio.py: KRONOS_DSN como kronos_worker e inquilinos al
azar. Comprueban, contra la base real, que la alerta completa que guarda
validacion.servicio.registrar vuelve íntegra a SOAR-EXECUTE tras pasar por jsonb y por la
cadena de hash, y que una alerta con caracteres que jsonb no admite igual se registra.
"""

import random
import unittest

from tests.integracion._base import dsn_de_pruebas

DSN = dsn_de_pruebas()

if DSN:
    from ejecucion.ordenes import construir
    from persistencia.repositorio import Decision, Repositorio
    from validacion.servicio import registrar


def _alerta(ref: str) -> dict:
    return {
        "timestamp": "2026-10-15T03:14:22.000+0000",
        "rule": {
            "level": 10,
            "description": "Kronos F1: fuerza bruta por SSH desde 192.0.2.77",
            "id": "100101",
            "firedtimes": 3,
            "groups": ["syslog", "sshd", "kronos", "kronos_f1"],
        },
        "agent": {"id": "003", "name": "srv-web-01", "ip": "192.0.2.10"},
        "id": ref,
        "full_log": "sshd[2211]: Failed password for root from 192.0.2.77 port 51122 ssh2",
        "data": {"srcip": "192.0.2.77", "srcport": "51122", "dstuser": "operador02"},
        "location": "/var/log/auth.log",
    }


@unittest.skipUnless(DSN, "falta KRONOS_DSN")
class TestValidateAlerta(unittest.TestCase):
    def setUp(self):
        self.t = random.randint(100_000, 2_000_000_000)
        self.validate = Repositorio(DSN)
        self.execute = Repositorio(DSN, actor="soar-execute")

    def sql(self, consulta, *parametros):
        with self.validate._transaccion(self.t) as cur:
            cur.execute(consulta, parametros)
            return cur.fetchall()

    def cadena_integra(self):
        return self.sql("SELECT fn_verificar_cadena(%s) IS NULL", self.t)[0][0]

    def test_la_alerta_completa_llega_a_execute(self):
        alerta = _alerta("1760411662.1")
        registrada = registrar(self.validate, self.t, alerta)
        self.assertTrue(registrada.nuevo)
        self.validate.registrar_decision(
            self.t,
            registrada.ticket_id,
            Decision("F1", "PB-F1-02", 0.9, 1, equipo="srv-web-01"),
        )

        ticket = self.execute.tomar_para_ejecutar(self.t)

        self.assertEqual(ticket.ticket_id, registrada.ticket_id)
        self.assertEqual(ticket.alerta["alerta"], alerta)
        orden = construir("bloquear_ip", ticket.alerta.get("alerta", {}))
        self.assertEqual(orden.agente, "003")
        self.assertEqual(orden.argumentos, ("aplicar", "192.0.2.77"))
        self.assertTrue(self.cadena_integra())

    def test_alerta_releida_no_duplica_el_ticket_ni_el_evento(self):
        alerta = _alerta("1760411662.2")
        primera = registrar(self.validate, self.t, alerta)
        segunda = registrar(self.validate, self.t, alerta)
        self.assertTrue(primera.nuevo)
        self.assertFalse(segunda.nuevo)
        self.assertEqual(primera.ticket_id, segunda.ticket_id)
        eventos = self.sql(
            "SELECT count(*) FROM auditoria WHERE evento = 'ALERTA_RECIBIDA'"
        )
        self.assertEqual(eventos[0][0], 1)

    def test_alerta_con_caracteres_que_jsonb_no_admite_se_registra(self):
        alerta = _alerta("1760411662.3")
        alerta["full_log"] = "usuario\x00root \ud800 ñandú 🙂"
        alerta["data"]["dstuser"] = "a\x00b"
        registrada = registrar(self.validate, self.t, alerta)
        guardado = self.sql(
            "SELECT alerta FROM alertas_guardadas WHERE ticket_id = %s",
            registrada.ticket_id,
        )[0][0]
        self.assertEqual(guardado["full_log"], "usuario�root � ñandú 🙂")
        self.assertEqual(guardado["data"]["dstuser"], "a�b")
        self.assertTrue(self.cadena_integra())


if __name__ == "__main__":
    unittest.main()
