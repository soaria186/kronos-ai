import unittest

from ejecucion.actuador import ErrorActuador
from ejecucion.ejecutor import Ejecutor
from ejecucion.medidas import Medida, cargar_medidas


class RepoFalso:
    """Imita las operaciones de persistencia.repositorio que usa el ejecutor."""

    def __init__(self, tickets=(), reversiones=()):
        self.tickets = list(tickets)
        self.reversiones = list(reversiones)
        self.ejecuciones = []
        self.revertidas = []

    def vencer_aprobaciones(self, tenant_id):
        return []

    def tomar_para_ejecutar(self, tenant_id):
        return self.tickets.pop(0) if self.tickets else None

    def tomar_reversion(self, tenant_id):
        return self.reversiones.pop(0) if self.reversiones else None

    def registrar_ejecucion(self, tenant_id, ticket_id, exito, detalle, reversion_en_minutos=None):
        self.ejecuciones.append((ticket_id, exito, detalle, reversion_en_minutos))

    def registrar_reversion(self, tenant_id, ticket_id, exito, detalle):
        self.revertidas.append((ticket_id, exito, detalle))


class ActuadorFalso:
    def __init__(self, falla=False):
        self.falla = falla
        self.ordenes = []

    def enviar(self, orden):
        if self.falla:
            raise ErrorActuador("agente desconectado")
        self.ordenes.append(orden)
        return f"ar-{len(self.ordenes)}"


class Ticket:
    def __init__(self, ticket_id, playbook_id, alerta):
        self.ticket_id = ticket_id
        self.playbook_id = playbook_id
        self.nivel = 1
        self.alerta = {"alerta": alerta}


ALERTA = {"agent": {"id": "002"}, "data": {"srcip": "203.0.113.7"}}
MEDIDAS = {
    "PB-F1-02": Medida("PB-F1-02", "bloquear_ip", 1, "automatica_al_vencer", 60),
    "PB-F1-03": Medida("PB-F1-03", "bloquear_ip", 2, "manual", None),
    "PB-SIN-PLAZO": Medida("PB-SIN-PLAZO", "bloquear_ip", 1, "automatica_al_vencer", None),
    "PB-F2-02": Medida("PB-F2-02", "cuarentena", 1, "manual", None),
}


class CicloEjecucion(unittest.TestCase):
    def ciclo(self, ticket, actuador=None):
        repo = RepoFalso([ticket])
        actuador = actuador or ActuadorFalso()
        resumen = Ejecutor(repo, actuador, MEDIDAS).ciclo(1)
        return repo, actuador, resumen

    def test_nivel_1_programa_la_reversion(self):
        repo, actuador, resumen = self.ciclo(Ticket(10, "PB-F1-02", ALERTA))
        self.assertEqual(resumen.exitosas, [10])
        self.assertEqual(len(actuador.ordenes), 1)
        _, exito, detalle, plazo = repo.ejecuciones[0]
        self.assertTrue(exito)
        self.assertEqual(plazo, 60)
        self.assertEqual(detalle["referencia"], "ar-1")

    def test_nivel_2_sin_reversion_automatica(self):
        repo, _, _ = self.ciclo(Ticket(11, "PB-F1-03", ALERTA))
        self.assertIsNone(repo.ejecuciones[0][3])

    def test_sin_plazo_no_se_ejecuta(self):
        repo, actuador, resumen = self.ciclo(Ticket(12, "PB-SIN-PLAZO", ALERTA))
        self.assertEqual(resumen.fallidas, [12])
        self.assertEqual(actuador.ordenes, [])
        self.assertEqual(repo.ejecuciones[0][2]["motivo"], "PLAZO_DE_REVERSION_SIN_DEFINIR")

    def test_accion_no_implementada(self):
        repo, actuador, _ = self.ciclo(Ticket(13, "PB-F2-02", ALERTA))
        self.assertEqual(actuador.ordenes, [])
        self.assertEqual(repo.ejecuciones[0][2]["motivo"], "ACCION_NO_IMPLEMENTADA")

    def test_playbook_desconocido(self):
        repo, _, _ = self.ciclo(Ticket(14, "PB-F9-99", ALERTA))
        self.assertEqual(repo.ejecuciones[0][2]["motivo"], "PLAYBOOK_SIN_MEDIDA")

    def test_orden_invalida_no_llega_al_actuador(self):
        alerta = {"agent": {"id": "002"}, "data": {"srcip": "1.2.3.4; reboot"}}
        repo, actuador, _ = self.ciclo(Ticket(15, "PB-F1-03", alerta))
        self.assertEqual(actuador.ordenes, [])
        self.assertEqual(repo.ejecuciones[0][2]["motivo"], "ORDEN_INVALIDA")

    def test_actuador_caido_queda_en_failed(self):
        repo, _, resumen = self.ciclo(Ticket(16, "PB-F1-03", ALERTA), ActuadorFalso(falla=True))
        self.assertEqual(resumen.fallidas, [16])
        _, exito, detalle, _ = repo.ejecuciones[0]
        self.assertFalse(exito)
        self.assertEqual(detalle["motivo"], "ACTUADOR_FALLO")
        self.assertEqual(detalle["orden"]["comando"], "kronos-bloquear-ip")


class CicloReversion(unittest.TestCase):
    def test_reversion_ok(self):
        repo = RepoFalso(reversiones=[Ticket(20, "PB-F1-02", ALERTA)])
        actuador = ActuadorFalso()
        resumen = Ejecutor(repo, actuador, MEDIDAS).ciclo(1)
        self.assertEqual(resumen.revertidas, [20])
        self.assertEqual(actuador.ordenes[0].argumentos, ("quitar", "203.0.113.7"))

    def test_reversion_fallida_se_registra(self):
        repo = RepoFalso(reversiones=[Ticket(21, "PB-F1-02", ALERTA)])
        resumen = Ejecutor(repo, ActuadorFalso(falla=True), MEDIDAS).ciclo(1)
        self.assertEqual(resumen.reversiones_fallidas, [21])
        self.assertEqual(repo.revertidas[0][2]["motivo"], "ErrorActuador")


class CatalogoReal(unittest.TestCase):
    def test_carga_las_25_medidas(self):
        medidas = cargar_medidas()
        self.assertEqual(len(medidas), 25)
        self.assertEqual(medidas["PB-F1-02"].accion, "bloquear_ip")
        self.assertEqual(medidas["PB-F1-02"].reversion, "automatica_al_vencer")


if __name__ == "__main__":
    unittest.main()
