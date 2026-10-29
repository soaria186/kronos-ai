import unittest

from ejecucion.actuador import ErrorActuador
from ejecucion.ejecutor import Ejecutor
from ejecucion.medidas import Medida, cargar_actuadores, cargar_medidas
from validacion.catalogo import CatalogoInvalido


class RepoFalso:
    """Imita las operaciones de persistencia.repositorio que usa el ejecutor."""

    def __init__(self, tickets=(), reversiones=(), huerfanos=()):
        self.huerfanos = list(huerfanos)
        self.tickets = list(tickets)
        self.reversiones = list(reversiones)
        self.ejecuciones = []
        self.revertidas = []

    def recuperar_huerfanos(self, tenant_id):
        huerfanos, self.huerfanos = self.huerfanos, []
        return huerfanos

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
# Igual que actuadores_v1 del catálogo 1.0.
ACTUADORES = {
    "linux": frozenset({"bloquear_ip"}),
    "windows": frozenset({"bloquear_ip", "deshabilitar_cuenta", "aislar_equipo"}),
}
AGENTES_SO = {"001": "linux", "002": "windows"}
MEDIDAS = {
    "PB-F1-02": Medida("PB-F1-02", "bloquear_ip", 1, "automatica_al_vencer", 60),
    "PB-F1-03": Medida("PB-F1-03", "bloquear_ip", 2, "manual", None),
    "PB-SIN-PLAZO": Medida("PB-SIN-PLAZO", "bloquear_ip", 1, "automatica_al_vencer", None),
    "PB-F2-02": Medida("PB-F2-02", "cuarentena", 1, "manual", None),
    "PB-F1-05": Medida("PB-F1-05", "deshabilitar_cuenta", 2, "manual", None),
    "PB-F3-03": Medida("PB-F3-03", "aislar_equipo", 3, "manual", None),
}


def ejecutor(repo, actuador, agentes_so=AGENTES_SO):
    return Ejecutor(repo, actuador, MEDIDAS, ACTUADORES, agentes_so)


class CicloEjecucion(unittest.TestCase):
    def ciclo(self, ticket, actuador=None):
        repo = RepoFalso([ticket])
        actuador = actuador or ActuadorFalso()
        resumen = ejecutor(repo, actuador).ciclo(1)
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


class SistemaOperativo(unittest.TestCase):
    def ciclo(self, ticket, agentes_so=AGENTES_SO):
        repo = RepoFalso([ticket])
        actuador = ActuadorFalso()
        resumen = ejecutor(repo, actuador, agentes_so).ciclo(1)
        return repo, actuador, resumen

    def test_bloquear_ip_en_windows_lleva_el_sistema(self):
        repo, actuador, resumen = self.ciclo(Ticket(30, "PB-F1-03", ALERTA))
        self.assertEqual(resumen.exitosas, [30])
        self.assertEqual(actuador.ordenes[0].sistema, "windows")
        self.assertEqual(repo.ejecuciones[0][2]["orden"]["sistema"], "windows")

    def test_bloquear_ip_en_linux(self):
        alerta = {"agent": {"id": "001"}, "data": {"srcip": "203.0.113.7"}}
        _, actuador, _ = self.ciclo(Ticket(31, "PB-F1-02", alerta))
        self.assertEqual(actuador.ordenes[0].sistema, "linux")

    def test_aislar_un_equipo_linux_falla_sin_llamar_al_actuador(self):
        alerta = {"agent": {"id": "001"}, "data": {"srcip": "203.0.113.7"}}
        repo, actuador, resumen = self.ciclo(Ticket(32, "PB-F3-03", alerta))
        self.assertEqual(resumen.fallidas, [32])
        self.assertEqual(actuador.ordenes, [])
        _, exito, detalle, _ = repo.ejecuciones[0]
        self.assertFalse(exito)
        self.assertEqual(detalle["motivo"], "ACCION_NO_IMPLEMENTADA")
        self.assertIn("sin script en linux", detalle["error"])

    def test_deshabilitar_cuenta_en_linux_falla(self):
        alerta = {"agent": {"id": "001"}, "data": {"dstuser": "usuario.demo"}}
        repo, actuador, _ = self.ciclo(Ticket(33, "PB-F1-05", alerta))
        self.assertEqual(actuador.ordenes, [])
        self.assertEqual(repo.ejecuciones[0][2]["motivo"], "ACCION_NO_IMPLEMENTADA")

    def test_sistema_desconocido_falla_sin_llamar_al_actuador(self):
        alerta = {"agent": {"id": "005"}, "data": {"srcip": "203.0.113.7"}}
        repo, actuador, resumen = self.ciclo(Ticket(34, "PB-F1-03", alerta))
        self.assertEqual(resumen.fallidas, [34])
        self.assertEqual(actuador.ordenes, [])
        detalle = repo.ejecuciones[0][2]
        self.assertEqual(detalle["motivo"], "ACCION_NO_IMPLEMENTADA")
        self.assertIn("no se pudo determinar el sistema operativo del agente 005", detalle["error"])

    def test_el_manager_sigue_siendo_orden_invalida(self):
        alerta = {"agent": {"id": "000"}, "location": "journald", "data": {"srcip": "203.0.113.7"}}
        repo, actuador, _ = self.ciclo(Ticket(37, "PB-F1-03", alerta))
        self.assertEqual(actuador.ordenes, [])
        self.assertEqual(repo.ejecuciones[0][2]["motivo"], "ORDEN_INVALIDA")

    def test_sin_mapa_se_deduce_de_la_alerta(self):
        alerta = {
            "agent": {"id": "002"},
            "location": "EventChannel",
            "data": {"win": {"eventdata": {"targetUserName": "usuario.demo"}}},
        }
        _, actuador, resumen = self.ciclo(Ticket(35, "PB-F1-05", alerta), agentes_so={})
        self.assertEqual(resumen.exitosas, [35])
        self.assertEqual(actuador.ordenes[0].sistema, "windows")
        self.assertEqual(actuador.ordenes[0].argumentos, ("aplicar", "usuario.demo"))

    def test_mapa_y_alerta_en_contradiccion_no_se_actua(self):
        alerta = {"agent": {"id": "001"}, "location": "EventChannel", "data": {"srcip": "203.0.113.7"}}
        repo, actuador, _ = self.ciclo(Ticket(36, "PB-F1-03", alerta))
        self.assertEqual(actuador.ordenes, [])
        self.assertEqual(repo.ejecuciones[0][2]["motivo"], "ACCION_NO_IMPLEMENTADA")


class CicloReversion(unittest.TestCase):
    def test_reversion_ok(self):
        repo = RepoFalso(reversiones=[Ticket(20, "PB-F1-02", ALERTA)])
        actuador = ActuadorFalso()
        resumen = ejecutor(repo, actuador).ciclo(1)
        self.assertEqual(resumen.revertidas, [20])
        self.assertEqual(actuador.ordenes[0].argumentos, ("quitar", "203.0.113.7"))

    def test_reversion_de_windows_sale_con_el_sistema(self):
        repo = RepoFalso(reversiones=[Ticket(22, "PB-F3-03", ALERTA)])
        actuador = ActuadorFalso()
        resumen = ejecutor(repo, actuador).ciclo(1)
        self.assertEqual(resumen.revertidas, [22])
        self.assertEqual(actuador.ordenes[0].sistema, "windows")
        self.assertEqual(actuador.ordenes[0].argumentos, ("quitar",))
        self.assertEqual(repo.revertidas[0][2]["orden"]["sistema"], "windows")

    def test_reversion_con_sistema_desconocido_no_se_envia(self):
        alerta = {"agent": {"id": "005"}, "data": {"srcip": "203.0.113.7"}}
        repo = RepoFalso(reversiones=[Ticket(23, "PB-F1-02", alerta)])
        actuador = ActuadorFalso()
        resumen = ejecutor(repo, actuador).ciclo(1)
        self.assertEqual(resumen.reversiones_fallidas, [23])
        self.assertEqual(actuador.ordenes, [])
        self.assertEqual(repo.revertidas[0][2]["motivo"], "AccionNoImplementada")

    def test_reversion_fallida_se_registra(self):
        repo = RepoFalso(reversiones=[Ticket(21, "PB-F1-02", ALERTA)])
        resumen = ejecutor(repo, ActuadorFalso(falla=True)).ciclo(1)
        self.assertEqual(resumen.reversiones_fallidas, [21])
        self.assertEqual(repo.revertidas[0][2]["motivo"], "ErrorActuador")


class CicloHuerfanos(unittest.TestCase):
    def test_los_huerfanos_se_informan_y_no_se_ejecutan(self):
        repo = RepoFalso(huerfanos=[7, 9])
        actuador = ActuadorFalso()
        resumen = ejecutor(repo, actuador).ciclo(1)
        self.assertEqual(resumen.huerfanos, [7, 9])
        self.assertEqual(repo.ejecuciones, [])
        self.assertEqual(actuador.ordenes, [])


class CatalogoReal(unittest.TestCase):
    def test_carga_las_25_medidas(self):
        medidas = cargar_medidas()
        self.assertEqual(len(medidas), 25)
        self.assertEqual(medidas["PB-F1-02"].accion, "bloquear_ip")
        self.assertEqual(medidas["PB-F1-02"].reversion, "automatica_al_vencer")

    def test_actuadores_v1_del_catalogo(self):
        self.assertEqual(cargar_actuadores(), ACTUADORES)


class ActuadoresInvalidos(unittest.TestCase):
    def cargar(self, actuadores):
        import json
        import tempfile
        from pathlib import Path

        from validacion.catalogo import RUTA_CATALOGO

        datos = json.loads(RUTA_CATALOGO.read_text(encoding="utf-8"))
        if actuadores is None:
            del datos["actuadores_v1"]
        else:
            datos["actuadores_v1"] = actuadores
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "kro-cat-01.json"
            ruta.write_text(json.dumps(datos), encoding="utf-8")
            return cargar_actuadores(ruta)

    def test_rechazos(self):
        casos = {
            "sin sección": None,
            "sistema desconocido": {"linux": [], "windows": [], "macos": []},
            "falta un sistema": {"linux": ["bloquear_ip"]},
            "acción sin comando": {"linux": ["consulta"], "windows": []},
            "acción no declarada": {"linux": ["borrar_todo"], "windows": []},
            "no es lista": {"linux": "bloquear_ip", "windows": []},
        }
        for nombre, actuadores in casos.items():
            with self.subTest(nombre), self.assertRaises(CatalogoInvalido):
                self.cargar(actuadores)


if __name__ == "__main__":
    unittest.main()
