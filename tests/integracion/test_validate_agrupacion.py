"""Prueba de integración de la agrupación de alertas: VALIDATE con la base de pruebas.

Mismas condiciones que test_repositorio.py (KRONOS_DSN como kronos_worker, base de
pruebas, inquilinos al azar). El modelo es falso: lo que se comprueba es lo que queda en
SOAR-AUDIT cuando llegan varias alertas del mismo ataque, no lo que opina la IA.
"""

import copy
import json
import random
import unittest
from dataclasses import replace

from tests.integracion._base import dsn_de_pruebas

DSN = dsn_de_pruebas()

if DSN:
    from decision.plantillas import Plantillas
    from persistencia.repositorio import Decision, Repositorio
    from validacion.catalogo import cargar_catalogo
    from validacion.ciclo import Destino, Validador
    from validacion.configuracion import DefinicionContador, cargar_configuracion

ALERTA = {
    "timestamp": "2026-10-20T22:04:14.000+0000",
    "rule": {
        "level": 10,
        "description": "Kronos F1: fuerza bruta por SSH",
        "id": "100101",
        "groups": ["syslog", "sshd", "kronos", "kronos_f1"],
    },
    "agent": {"id": "001", "name": "EP-SRV-01", "ip": "10.0.50.3"},
    "full_log": "sshd[2211]: Failed password for root from 203.0.113.50 port 51122 ssh2",
    "data": {"srcip": "203.0.113.50", "srcport": "51122", "dstuser": "root"},
    "location": "/var/log/auth.log",
}


class ModeloFalso:
    """Siempre propone F1 y PB-F1-02 (bloquear la IP externa); cuenta las llamadas."""

    def __init__(self):
        self.llamadas = 0

    def generar(self, prompt, esquema, plazo):
        self.llamadas += 1
        if "playbook_id" in json.dumps(esquema):
            return json.dumps({"playbook_id": "PB-F1-02", "confianza": 0.85})
        return json.dumps({"familia": "F1", "confianza": 0.9})


@unittest.skipUnless(DSN, "falta KRONOS_DSN")
class TestAgrupacion(unittest.TestCase):
    def setUp(self):
        self.t = random.randint(100_000, 2_000_000_000)
        self.repo = Repositorio(DSN)
        self.modelo = ModeloFalso()
        self.n = 0

    def validador(self, config=None):
        return Validador(
            self.repo,
            self.modelo,
            Plantillas.cargar(),
            cargar_catalogo(),
            config or cargar_configuracion(),
            Decision,
            plazo=30.0,
        )

    def alerta(self, **datos):
        a = copy.deepcopy(ALERTA)
        self.n += 1
        a["id"] = f"agrup-{self.t}-{self.n}"
        a["data"].update(datos)
        return a

    def sql(self, consulta, *parametros):
        with self.repo._transaccion(self.t) as cur:
            cur.execute(consulta, parametros)
            return cur.fetchall()

    def test_un_ataque_repetido_es_un_ticket_y_una_decision(self):
        v = self.validador()
        resultados = [v.procesar(self.t, self.alerta()) for _ in range(4)]

        self.assertEqual(
            [r.destino for r in resultados], [Destino.APROBADA] + [Destino.AGRUPADA] * 3
        )
        ticket = resultados[0].ticket_id
        self.assertEqual({r.ticket_id for r in resultados}, {ticket})
        self.assertEqual(self.modelo.llamadas, 2)  # sólo los dos pasos de la primera
        self.assertEqual(self.sql("SELECT count(*) FROM tickets")[0][0], 1)
        eventos = dict(
            self.sql(
                "SELECT evento, count(*) FROM auditoria WHERE ticket_id = %s GROUP BY evento",
                ticket,
            )
        )
        self.assertEqual(
            eventos, {"ALERTA_RECIBIDA": 1, "DECISION": 1, "ALERTA_AGRUPADA": 3}
        )
        estado = self.sql(
            "SELECT execution_status, playbook FROM tickets WHERE id = %s", ticket
        )
        self.assertEqual(estado, [("PENDING", "PB-F1-02")])  # una sola orden para EXECUTE
        self.assertTrue(self.sql("SELECT fn_verificar_cadena(%s) IS NULL", self.t)[0][0])

    def test_las_agrupadas_siguen_contando_para_el_cortacircuito(self):
        config = cargar_configuracion()
        config = replace(
            config, disparo_cortacircuito=DefinicionContador("alertas", 10, 5)
        )
        v = self.validador(config)
        for _ in range(4):  # 1 ticket + 3 agrupadas
            v.procesar(self.t, self.alerta())
        self.assertFalse(self.repo.cortacircuito_abierto(self.t))
        # Otro origen, otro ataque: ya van 5 alertas en la ventana y el cortacircuito abre.
        otro = v.procesar(self.t, self.alerta(srcip="203.0.113.99"))
        self.assertEqual(otro.motivo, "CORTACIRCUITO_ABIERTO")
        self.assertTrue(self.repo.cortacircuito_abierto(self.t))


if __name__ == "__main__":
    unittest.main()
