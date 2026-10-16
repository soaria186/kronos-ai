"""Prueba de integración del ciclo de VALIDATE: base real y modelo real.

Necesita KRONOS_DSN (kronos_worker, como las demás pruebas de integración) y además
KRONOS_OLLAMA_URL, el servidor de Ollama con qwen2.5:7b cargado. Usa un inquilino al azar,
así que deja filas permanentes sólo en su propia cadena de la bitácora.

Lo que el modelo decida puede variar; lo que se comprueba es lo que no debe variar:
cada alerta termina con una decisión registrada, el estado del ticket es coherente con
ella, la cadena de hash sigue íntegra, el agente 000 nunca llega a EXECUTE, una IP
interna nunca recibe un bloqueo de IP externa y el cortacircuito abre con el disparo.
"""

import copy
import json
import os
import random
import unittest
from dataclasses import replace
from pathlib import Path

DSN = os.environ.get("KRONOS_DSN")
OLLAMA = os.environ.get("KRONOS_OLLAMA_URL")

if DSN and OLLAMA:
    from decision.ollama import ClienteOllama
    from decision.plantillas import Plantillas
    from persistencia.repositorio import Decision, Repositorio
    from validacion.catalogo import cargar_catalogo
    from validacion.ciclo import Destino, Validador
    from validacion.configuracion import DefinicionContador, cargar_configuracion

ALERTAS_150 = (
    Path(__file__).resolve().parents[2]
    / "decision"
    / "mediciones"
    / "casos_150"
    / "alertas.json"
)


def _casos() -> list[dict]:
    return json.loads(ALERTAS_150.read_text(encoding="utf-8"))


@unittest.skipUnless(DSN and OLLAMA, "faltan KRONOS_DSN y KRONOS_OLLAMA_URL")
class TestCicloDeValidate(unittest.TestCase):
    def setUp(self):
        self.t = random.randint(100_000, 2_000_000_000)
        self.repo = Repositorio(DSN)
        self.config = cargar_configuracion()
        self.modelo = ClienteOllama(
            os.environ.get("KRONOS_MODELO", "qwen2.5:7b"), OLLAMA
        )
        self.n = 0

    def validador(self, config=None):
        return Validador(
            self.repo,
            self.modelo,
            Plantillas.cargar(),
            cargar_catalogo(),
            config or self.config,
            Decision,
            plazo=90.0,
        )

    def alerta(self, regla, **cambios):
        """Primera alerta de 150 casos con esa regla, con id propio y campos cambiados."""
        base = next(c["alerta"] for c in _casos() if c["regla"] == regla)
        alerta = copy.deepcopy(base)
        self.n += 1
        alerta["id"] = f"ciclo-{self.t}-{self.n}"
        for ruta, valor in cambios.items():
            destino = alerta
            *camino, hoja = ruta.split(".")
            for clave in camino:
                destino = destino[clave]
            destino[hoja] = valor
        return alerta

    # ------------------------------------------------------------- utilidades

    def sql(self, consulta, *parametros):
        with self.repo._transaccion(self.t) as cur:
            cur.execute(consulta, parametros)
            return cur.fetchall() if cur.description else None

    def ticket(self, ticket_id):
        return self.sql(
            "SELECT execution_status, rechazo_motivo, playbook, autonomia_aplicada"
            " FROM tickets WHERE id = %s",
            ticket_id,
        )[0]

    def eventos(self, ticket_id):
        return [
            f[0]
            for f in self.sql(
                "SELECT evento FROM auditoria WHERE ticket_id = %s ORDER BY seq",
                ticket_id,
            )
        ]

    def cadena_integra(self):
        return self.sql("SELECT fn_verificar_cadena(%s) IS NULL", self.t)[0][0]

    def comprobar_coherencia(self, resultado):
        """El ticket quedó decidido y su estado cuadra con la decisión."""
        estado, motivo, playbook, nivel = self.ticket(resultado.ticket_id)
        self.assertEqual(
            self.eventos(resultado.ticket_id), ["ALERTA_RECIBIDA", "DECISION"]
        )
        if resultado.destino == Destino.APROBADA:
            self.assertIsNone(motivo)
            self.assertIsNotNone(playbook)
            self.assertIn(estado, ("PENDING", "AWAITING_APPROVAL"))
            self.assertEqual(estado == "AWAITING_APPROVAL", nivel == 3)
        else:
            self.assertEqual((estado, motivo), ("MANUAL_TRIAGE", resultado.motivo))
        return estado, motivo, playbook

    # ----------------------------------------------------------------- pruebas

    def test_el_manager_se_rechaza_sin_llamar_al_modelo(self):
        r = self.validador().procesar(
            self.t, self.alerta("100101", **{"agent.id": "000"})
        )
        self.assertEqual((r.destino, r.motivo), (Destino.RECHAZADA, "ACTIVO_EXCLUIDO"))
        self.assertEqual(
            self.comprobar_coherencia(r)[:2], ("MANUAL_TRIAGE", "ACTIVO_EXCLUIDO")
        )
        self.assertTrue(self.cadena_integra())

    def test_alerta_repetida_no_se_procesa_dos_veces(self):
        alerta = self.alerta("100101", **{"agent.id": "000"})
        validador = self.validador()
        self.assertEqual(validador.procesar(self.t, alerta).destino, Destino.RECHAZADA)
        self.assertEqual(validador.procesar(self.t, alerta).destino, Destino.REPETIDA)

    def test_alerta_real_con_el_modelo_real(self):
        alerta = self.alerta("100101", **{"data.srcip": "203.0.113.9"})
        r = self.validador().procesar(self.t, alerta)
        _estado, motivo, playbook = self.comprobar_coherencia(r)
        print(
            f"\n  F1 con IP externa: {r.destino.value} {motivo or ''} {playbook or ''}"
        )
        self.assertTrue(self.cadena_integra())

    def test_una_ip_interna_nunca_recibe_un_bloqueo_de_ip_externa(self):
        alerta = self.alerta("100108", **{"data.win.eventdata.ipAddress": "10.0.0.7"})
        alerta.get("data", {}).pop("srcip", None)
        r = self.validador().procesar(self.t, alerta)
        _estado, motivo, playbook = self.comprobar_coherencia(r)
        print(
            f"\n  F3 con IP interna: {r.destino.value} {motivo or ''} {playbook or ''}"
        )
        self.assertNotEqual((r.destino, playbook), (Destino.APROBADA, "PB-F3-01"))
        self.assertNotEqual((r.destino, playbook), (Destino.APROBADA, "PB-F1-02"))
        self.assertTrue(self.cadena_integra())

    def test_el_cortacircuito_se_abre_con_el_disparo_y_frena_al_modelo(self):
        disparo = DefinicionContador("alertas_por_ventana", 10, 3)
        config = replace(self.config, disparo_cortacircuito=disparo)
        validador = self.validador(config)
        resultados = [
            validador.procesar(self.t, self.alerta("100101", **{"agent.id": "000"}))
            for _ in range(3)
        ]
        # Las tres son del manager; la tercera ya llega con 3 alertas en la ventana.
        self.assertEqual(resultados[2].motivo, "CORTACIRCUITO_ABIERTO")
        self.assertTrue(self.repo.cortacircuito_abierto(self.t))
        # Con el cortacircuito abierto no se llama al modelo: una alerta normal se rechaza.
        cuarta = validador.procesar(self.t, self.alerta("100101"))
        self.assertEqual(cuarta.motivo, "CORTACIRCUITO_ABIERTO")
        self.assertTrue(self.cadena_integra())


if __name__ == "__main__":
    unittest.main()
