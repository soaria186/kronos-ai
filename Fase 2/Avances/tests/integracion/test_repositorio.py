"""Pruebas de integración de persistencia.repositorio contra un PostgreSQL real.

Necesitan la variable KRONOS_DSN con una conexión como kronos_worker a una base
creada con infra/docker/initdb. Sin ella, se omiten.

Cada ejecución usa inquilinos al azar: auditoria es de sólo inserción y las filas
de pruebas anteriores no se pueden borrar.
"""

import random
import unittest

from tests.integracion._base import dsn_de_pruebas

DSN = dsn_de_pruebas()

if DSN:
    from persistencia.repositorio import (
        Decision,
        DefinicionUso,
        EstadoInvalido,
        Repositorio,
        TicketYaDecidido,
    )

CONTADORES = [
    DefinicionUso("acciones_por_inquilino", 60),
    DefinicionUso("acciones_por_equipo", 60),
    DefinicionUso("acciones_por_playbook", 60),
    DefinicionUso("acciones_nivel_2", 1440),
]


def _inquilino() -> int:
    return random.randint(100_000, 2_000_000_000)


@unittest.skipUnless(DSN, "falta KRONOS_DSN")
class TestRepositorio(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repositorio(DSN)
        self.t = _inquilino()

    def _consulta(self, sql: str, *parametros):
        with self.repo._transaccion(self.t) as cur:
            cur.execute(sql, parametros)
            return cur.fetchall()

    def _cadena_integra(self) -> bool:
        return self._consulta("SELECT fn_verificar_cadena(%s) IS NULL", self.t)[0][0]

    def test_alerta_releida_no_duplica(self) -> None:
        primero = self.repo.registrar_alerta(self.t, "1729000000.123", "Fuerza bruta SSH", 10)
        segundo = self.repo.registrar_alerta(self.t, "1729000000.123", "Fuerza bruta SSH", 10)
        self.assertTrue(primero.nuevo)
        self.assertFalse(segundo.nuevo)
        self.assertEqual(primero.ticket_id, segundo.ticket_id)
        eventos = self._consulta(
            "SELECT count(*) FROM auditoria WHERE evento = 'ALERTA_RECIBIDA'"
        )[0][0]
        self.assertEqual(eventos, 1)
        self.assertTrue(self._cadena_integra())

    def test_decision_aprobada(self) -> None:
        ticket = self.repo.registrar_alerta(self.t, "a-1", "Fuerza bruta SSH", 10)
        seq = self.repo.registrar_decision(
            self.t,
            ticket.ticket_id,
            Decision("F1", "PB-F1-02", 0.85, 1, equipo="EP-SRV-01"),
        )
        estado, playbook, nivel, motivo = self._consulta(
            "SELECT execution_status, playbook, autonomia_aplicada, rechazo_motivo"
            " FROM tickets WHERE id = %s",
            ticket.ticket_id,
        )[0]
        self.assertEqual((estado, playbook, nivel, motivo), ("PENDING", "PB-F1-02", 1, None))
        self.assertEqual(seq, 2)  # 1: alerta recibida, 2: decisión
        self.assertTrue(self._cadena_integra())

    def test_decision_rechazada_con_motivo_nuevo(self) -> None:
        ticket = self.repo.registrar_alerta(self.t, "a-2", "PowerShell codificado", 12)
        self.repo.registrar_decision(
            self.t,
            ticket.ticket_id,
            Decision("F5", "PB-F5-01", 0.85, None, motivo="FAMILIA_NO_COINCIDE",
                     detalle="el modelo dijo F5; la regla de sobre, F2"),
        )
        estado, motivo, nivel = self._consulta(
            "SELECT execution_status, rechazo_motivo, autonomia_aplicada"
            " FROM tickets WHERE id = %s",
            ticket.ticket_id,
        )[0]
        self.assertEqual((estado, motivo, nivel), ("MANUAL_TRIAGE", "FAMILIA_NO_COINCIDE", None))

    def test_motivo_aprobacion_vencida_aceptado(self) -> None:
        ticket = self.repo.registrar_alerta(self.t, "a-3", "Ejecución remota", 12)
        self.repo.registrar_decision(
            self.t, ticket.ticket_id,
            Decision("F3", "PB-F3-03", 0.9, None, motivo="APROBACION_VENCIDA"),
        )
        motivo = self._consulta(
            "SELECT rechazo_motivo FROM tickets WHERE id = %s", ticket.ticket_id
        )[0][0]
        self.assertEqual(motivo, "APROBACION_VENCIDA")

    def test_segunda_decision_se_rechaza_sin_dejar_evento(self) -> None:
        ticket = self.repo.registrar_alerta(self.t, "a-4", "Fuerza bruta SSH", 10)
        self.repo.registrar_decision(
            self.t, ticket.ticket_id, Decision("F1", "PB-F1-02", 0.85, 1)
        )
        with self.assertRaises(TicketYaDecidido):
            self.repo.registrar_decision(
                self.t, ticket.ticket_id, Decision("F1", "PB-F1-05", 0.85, 2)
            )
        decisiones = self._consulta(
            "SELECT count(*) FROM auditoria WHERE evento = 'DECISION'"
        )[0][0]
        self.assertEqual(decisiones, 1)
        self.assertTrue(self._cadena_integra())

    def test_otro_inquilino_no_puede_decidir(self) -> None:
        ticket = self.repo.registrar_alerta(self.t, "a-5", "Fuerza bruta SSH", 10)
        with self.assertRaises(TicketYaDecidido):
            self.repo.registrar_decision(
                _inquilino(), ticket.ticket_id, Decision("F1", "PB-F1-02", 0.85, 1)
            )

    def test_contadores(self) -> None:
        for i, (playbook, nivel, equipo) in enumerate([
            ("PB-F1-02", 1, "EP-SRV-01"),
            ("PB-F1-02", 1, "EP-SRV-01"),
            ("PB-F1-05", 2, "EP-WKS-01"),
            ("PB-F1-01", 0, "EP-SRV-01"),  # nivel 0: no cuenta como acción
        ]):
            ticket = self.repo.registrar_alerta(self.t, f"c-{i}", "Fuerza bruta SSH", 10)
            self.repo.registrar_decision(
                self.t, ticket.ticket_id, Decision("F1", playbook, 0.85, nivel, equipo=equipo)
            )
        usos = self.repo.usos(self.t, CONTADORES, equipo="EP-SRV-01", playbook_id="PB-F1-02")
        self.assertEqual(
            usos,
            {
                "acciones_por_inquilino": 3,
                "acciones_por_equipo": 2,
                "acciones_por_playbook": 2,
                "acciones_nivel_2": 1,
            },
        )

    def test_contador_sin_dato_no_aparece(self) -> None:
        usos = self.repo.usos(
            self.t, CONTADORES + [DefinicionUso("desconocido", 10)]
        )
        self.assertNotIn("acciones_por_equipo", usos)  # sin equipo
        self.assertNotIn("acciones_por_playbook", usos)  # sin playbook
        self.assertNotIn("desconocido", usos)
        self.assertEqual(usos["acciones_por_inquilino"], 0)

    def test_cortacircuito(self) -> None:
        self.assertFalse(self.repo.cortacircuito_abierto(self.t))
        self.assertTrue(self.repo.abrir_cortacircuito(self.t, "30 alertas en 10 minutos"))
        self.assertTrue(self.repo.cortacircuito_abierto(self.t))
        self.assertFalse(self.repo.abrir_cortacircuito(self.t, "otra vez"))
        filas = self._consulta("SELECT count(*) FROM cortacircuito")[0][0]
        self.assertEqual(filas, 1)
        self.assertTrue(self._cadena_integra())

    def test_alertas_en_ventana(self) -> None:
        for i in range(3):
            self.repo.registrar_alerta(self.t, f"v-{i}", "Disco lleno", 7)
        self.assertEqual(self.repo.alertas_en_ventana(self.t, 10), 3)

    def test_alerta_agrupada_es_un_evento_del_ticket_y_no_un_ticket(self) -> None:
        ticket = self.repo.registrar_alerta(self.t, "g-0", "Fuerza bruta SSH", 10).ticket_id
        self.repo.agrupar_alerta(self.t, ticket, {"alerta_ref": "g-1", "regla": "100101"})
        self.repo.agrupar_alerta(self.t, ticket, {"alerta_ref": "g-2", "regla": "100101"})
        tickets = self._consulta("SELECT count(*) FROM tickets")[0][0]
        eventos = self._consulta(
            "SELECT ticket_id, detalle->>'alerta_ref' FROM auditoria "
            "WHERE evento = 'ALERTA_AGRUPADA' ORDER BY seq"
        )
        self.assertEqual(tickets, 1)
        self.assertEqual(eventos, [(ticket, "g-1"), (ticket, "g-2")])
        self.assertTrue(self._cadena_integra())

    def test_las_alertas_agrupadas_cuentan_para_el_cortacircuito(self) -> None:
        ticket = self.repo.registrar_alerta(self.t, "w-0", "Fuerza bruta SSH", 10).ticket_id
        for i in range(4):
            self.repo.agrupar_alerta(self.t, ticket, {"alerta_ref": f"w-{i + 1}"})
        self.assertEqual(self.repo.alertas_en_ventana(self.t, 10), 5)

    def test_agrupar_en_un_ticket_de_otro_inquilino_falla(self) -> None:
        ticket = self.repo.registrar_alerta(self.t, "x-0", "Fuerza bruta SSH", 10).ticket_id
        with self.assertRaises(EstadoInvalido):
            self.repo.agrupar_alerta(_inquilino(), ticket, {"alerta_ref": "x-1"})
        with self.assertRaises(EstadoInvalido):
            self.repo.agrupar_alerta(self.t, ticket + 10_000_000, {"alerta_ref": "x-2"})

    def test_inquilino_invalido(self) -> None:
        for malo in (0, -1, True, "1"):
            with self.assertRaises(ValueError):
                self.repo.cortacircuito_abierto(malo)


if __name__ == "__main__":
    unittest.main()
