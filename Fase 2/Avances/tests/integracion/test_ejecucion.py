"""Pruebas de integración de SOAR-EXECUTE (estados, temporizadores y bitácora).

Mismas condiciones que test_repositorio.py: KRONOS_DSN como kronos_worker e
inquilinos al azar. El actuador es falso; el resto es la base real.
"""

import random
import unittest

from tests.integracion._base import dsn_de_pruebas

DSN = dsn_de_pruebas()

if DSN:
    from ejecucion.actuador import ErrorActuador
    from ejecucion.ejecutor import Ejecutor
    from ejecucion.medidas import Medida, cargar_actuadores
    from persistencia.repositorio import (
        Decision,
        EstadoInvalido,
        Repositorio,
    )

ALERTA = {"alerta": {"agent": {"id": "002"}, "data": {"srcip": "203.0.113.7"}}}


class ActuadorFalso:
    def __init__(self):
        self.falla = False
        self.ordenes = []

    def enviar(self, orden):
        if self.falla:
            raise ErrorActuador("agente desconectado")
        self.ordenes.append(orden)
        return f"ar-{len(self.ordenes)}"


@unittest.skipUnless(DSN, "falta KRONOS_DSN")
class TestEjecucion(unittest.TestCase):
    def setUp(self):
        self.t = random.randint(100_000, 2_000_000_000)
        self.validate = Repositorio(DSN)
        self.repo = Repositorio(DSN, actor="soar-execute")
        self.actuador = ActuadorFalso()
        medidas = {
            "PB-F1-02": Medida("PB-F1-02", "bloquear_ip", 1, "automatica_al_vencer", 60),
            "PB-F1-03": Medida("PB-F1-03", "bloquear_ip", 2, "manual", None),
            "PB-F3-03": Medida("PB-F3-03", "aislar_equipo", 3, "manual", None),
        }
        # La alerta de prueba es del agente 002 (Windows en la PyME simulada).
        self.ejecutor = Ejecutor(
            self.repo, self.actuador, medidas, cargar_actuadores(), {"002": "windows"}
        )

    # ------------------------------------------------------------ utilidades

    def sql(self, consulta, *parametros):
        with self.repo._transaccion(self.t) as cur:
            cur.execute(consulta, parametros)
            return cur.fetchall() if cur.description else None

    def ticket(self, ref, playbook, nivel, alerta=ALERTA):
        t = self.validate.registrar_alerta(self.t, ref, "prueba", 12, alerta)
        self.validate.registrar_decision(
            self.t, t.ticket_id, Decision("F1", playbook, 0.9, nivel, equipo="EP-SRV-01")
        )
        return t.ticket_id

    def estado(self, ticket_id):
        return self.sql(
            "SELECT execution_status, rechazo_motivo FROM tickets WHERE id = %s", ticket_id
        )[0]

    def eventos(self, ticket_id):
        return [
            f[0]
            for f in self.sql(
                "SELECT evento FROM auditoria WHERE ticket_id = %s ORDER BY seq", ticket_id
            )
        ]

    def temporizadores(self, ticket_id):
        return self.sql(
            "SELECT tipo, disparado_en IS NOT NULL FROM temporizadores"
            " WHERE ticket_id = %s ORDER BY id",
            ticket_id,
        )

    def vencer(self, ticket_id, tipo):
        self.sql(
            "UPDATE temporizadores SET vence_en = now() - interval '1 minute'"
            " WHERE ticket_id = %s AND tipo = %s AND disparado_en IS NULL",
            ticket_id,
            tipo,
        )

    def cadena_integra(self):
        return self.sql("SELECT fn_verificar_cadena(%s) IS NULL", self.t)[0][0]

    # ---------------------------------------------------------------- nivel 1

    def test_nivel_1_ejecuta_y_revierte_al_vencer(self):
        tid = self.ticket("n1", "PB-F1-02", 1)
        resumen = self.ejecutor.ciclo(self.t)
        self.assertEqual(resumen.exitosas, [tid])
        self.assertEqual(self.estado(tid), ("SUCCESS", None))
        self.assertEqual(self.temporizadores(tid), [("REVERSION", False)])

        self.assertEqual(self.ejecutor.ciclo(self.t).revertidas, [])  # aún no vence
        self.vencer(tid, "REVERSION")
        self.assertEqual(self.ejecutor.ciclo(self.t).revertidas, [tid])
        self.assertEqual(self.actuador.ordenes[1].argumentos, ("quitar", "203.0.113.7"))
        self.assertEqual(self.estado(tid), ("SUCCESS", None))
        self.assertEqual(
            self.eventos(tid),
            [
                "ALERTA_RECIBIDA",
                "DECISION",
                "EJECUCION_INICIADA",
                "EJECUCION_OK",
                "REVERSION_INICIADA",
                "REVERSION_OK",
            ],
        )
        self.assertTrue(self.cadena_integra())

    def test_falla_del_actuador_deja_failed_sin_reintento(self):
        tid = self.ticket("f1", "PB-F1-03", 2)
        self.actuador.falla = True
        self.assertEqual(self.ejecutor.ciclo(self.t).fallidas, [tid])
        self.assertEqual(self.estado(tid), ("FAILED", None))
        self.assertEqual(self.temporizadores(tid), [])
        self.actuador.falla = False
        self.assertEqual(self.ejecutor.ciclo(self.t).exitosas, [])  # no se retoma

    def test_un_ticket_lo_toma_un_solo_ejecutor(self):
        tid = self.ticket("u1", "PB-F1-03", 2)
        primero = self.repo.tomar_para_ejecutar(self.t)
        self.assertEqual(primero.ticket_id, tid)
        self.assertEqual(primero.alerta, ALERTA)
        self.assertIsNone(self.repo.tomar_para_ejecutar(self.t))

    # ---------------------------------------------------------------- nivel 2

    def test_nivel_2_revision_recordatorio_y_reversion_manual(self):
        tid = self.ticket("n2", "PB-F1-03", 2)
        self.ejecutor.ciclo(self.t)
        self.assertEqual(self.temporizadores(tid), [("REVISION", False)])

        self.vencer(tid, "REVISION")
        self.assertEqual(self.repo.tomar_recordatorios(self.t), [tid])
        self.assertEqual(self.repo.tomar_recordatorios(self.t), [])  # el siguiente, mañana
        self.assertEqual(self.temporizadores(tid), [("REVISION", True), ("REVISION", False)])

        self.repo.solicitar_reversion(self.t, tid, "rodrigo")
        self.assertEqual(self.ejecutor.ciclo(self.t).revertidas, [tid])
        # Tras revertir, se terminan los recordatorios.
        self.assertTrue(all(disparado for _, disparado in self.temporizadores(tid)))
        actores = self.sql(
            "SELECT actor FROM auditoria WHERE ticket_id = %s AND evento = %s",
            tid,
            "REVERSION_SOLICITADA",
        )
        self.assertEqual(actores, [("rodrigo",)])
        with self.assertRaises(EstadoInvalido):
            self.repo.solicitar_reversion(self.t, tid, "rodrigo")
        self.assertTrue(self.cadena_integra())

    def test_no_se_revierte_lo_que_no_se_ejecuto(self):
        tid = self.ticket("n2b", "PB-F1-03", 2)
        with self.assertRaises(EstadoInvalido):
            self.repo.solicitar_reversion(self.t, tid, "rodrigo")

    # ---------------------------------------------------------------- nivel 3

    def test_nivel_3_espera_y_no_se_ejecuta_solo(self):
        tid = self.ticket("n3", "PB-F3-03", 3)
        self.assertEqual(self.estado(tid), ("AWAITING_APPROVAL", None))
        self.assertEqual(self.temporizadores(tid), [("APROBACION", False)])
        self.assertEqual(self.ejecutor.ciclo(self.t).exitosas, [])
        self.assertEqual(self.actuador.ordenes, [])

    def test_nivel_3_aprobado_se_ejecuta(self):
        tid = self.ticket("n3a", "PB-F3-03", 3)
        self.repo.aprobar(self.t, tid, "nicolas")
        self.assertEqual(self.estado(tid), ("PENDING", None))
        self.assertEqual(self.ejecutor.ciclo(self.t).exitosas, [tid])
        self.assertEqual(self.actuador.ordenes[0].comando, "kronos-aislar-equipo")
        with self.assertRaises(EstadoInvalido):
            self.repo.aprobar(self.t, tid, "nicolas")

    def test_nivel_3_denegado(self):
        tid = self.ticket("n3d", "PB-F3-03", 3)
        self.repo.denegar(self.t, tid, "patricio", "falso positivo")
        self.assertEqual(self.estado(tid), ("REJECTED", None))
        self.assertEqual(self.temporizadores(tid), [("APROBACION", True)])
        self.assertEqual(self.ejecutor.ciclo(self.t).exitosas, [])

    def test_nivel_3_vencido(self):
        tid = self.ticket("n3v", "PB-F3-03", 3)
        self.vencer(tid, "APROBACION")
        self.assertEqual(self.ejecutor.ciclo(self.t).vencidas, [tid])
        self.assertEqual(self.estado(tid), ("MANUAL_TRIAGE", "APROBACION_VENCIDA"))
        self.assertIn("APROBACION_VENCIDA", self.eventos(tid))
        with self.assertRaises(EstadoInvalido):
            self.repo.aprobar(self.t, tid, "nicolas")  # tarde

    def test_aprobador_obligatorio(self):
        tid = self.ticket("n3x", "PB-F3-03", 3)
        with self.assertRaises(ValueError):
            self.repo.aprobar(self.t, tid, "  ")

    def test_otro_inquilino_no_ve_ni_toma(self):
        self.ticket("aj", "PB-F1-03", 2)
        otro = random.randint(100_000, 2_000_000_000)
        self.assertIsNone(self.repo.tomar_para_ejecutar(otro))


if __name__ == "__main__":
    unittest.main()
