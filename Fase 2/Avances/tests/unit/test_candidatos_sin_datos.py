"""El paso 2 no acepta medidas cuyo dato no viene en la alerta (hallazgo de E4, 04-11).

Con la alerta real de E4 (registro de auditoría borrado en un puesto, sin archivo ni
tarea), el modelo eligió las 5 veces la cuarentena (PB-F5-03), que EXECUTE termina en
ARGUMENTO_FALTANTE. VALIDATE ahora quita esas medidas del esquema de la respuesta del paso 2
(el texto del prompt no cambia).
"""

import json
import unittest
from collections import namedtuple
from dataclasses import dataclass

from decision.inferencia import clasificar
from decision.plantillas import Plantillas
from ejecucion.ordenes import falta_argumento, no_aplicable
from validacion.catalogo import cargar_catalogo
from validacion.ciclo import Destino, Validador
from validacion.configuracion import cargar_configuracion

PLANTILLAS = Plantillas.cargar()
CATALOGO = cargar_catalogo()
CONFIG = cargar_configuracion()

Ticket = namedtuple("Ticket", "ticket_id nuevo")


def alerta(regla, nivel, grupos, agente, datos, ubicacion):
    return {
        "timestamp": "2026-11-04T20:00:00.000+0000",
        "rule": {"level": nivel, "description": "prueba", "id": regla, "firedtimes": 1,
                 "groups": grupos},
        "agent": agente,
        "id": f"prueba-{regla}",
        "location": ubicacion,
        "data": datos,
    }


PUESTO = {"id": "002", "name": "EP-WKS-01", "ip": "192.0.2.20"}


def e4():
    """Registro de auditoría borrado en EP-WKS-01: no trae archivo ni tarea."""
    return alerta(
        "100113", 12, ["windows", "kronos", "kronos_f5"], PUESTO,
        {"win": {"system": {"eventID": "1102", "channel": "Security"},
                 "eventdata": {"subjectUserName": "usuario.ejemplo"}}},
        "EventChannel",
    )


def con_archivo():
    """Un ejecutable sospechoso en un puesto, con su ruta (Sysmon)."""
    return alerta(
        "100112", 10, ["windows", "kronos", "kronos_f5"], PUESTO,
        {"win": {"system": {"eventID": "11"},
                 "eventdata": {"image": "C:\\Users\\usuario01\\Downloads\\factura.exe",
                               "targetFilename": "C:\\Users\\usuario01\\Downloads\\factura.exe"}}},
        "EventChannel",
    )


class FaltaArgumento(unittest.TestCase):
    def test_cuarentena_sin_ruta(self):
        self.assertTrue(falta_argumento("cuarentena", e4()))

    def test_cuarentena_con_ruta(self):
        self.assertFalse(falta_argumento("cuarentena", con_archivo()))

    def test_revertir_tarea_sin_nombre(self):
        self.assertTrue(falta_argumento("revertir_tarea", e4()))

    def test_aislar_no_necesita_datos(self):
        self.assertFalse(falta_argumento("aislar_equipo", e4()))

    def test_un_valor_invalido_no_es_un_dato_faltante(self):
        # Una ruta del sistema la rechaza EXECUTE (ORDEN_INVALIDA), como siempre: aquí no.
        a = con_archivo()
        a["data"]["win"]["eventdata"]["targetFilename"] = "C:\\Windows\\System32\\cmd.exe"
        a["data"]["win"]["eventdata"]["image"] = "C:\\Windows\\System32\\cmd.exe"
        self.assertFalse(falta_argumento("cuarentena", a))

    def test_sin_sistema_operativo_conocido_no_excluye(self):
        a = e4()
        del a["data"]["win"]
        a["location"] = "desconocida"
        self.assertFalse(falta_argumento("cuarentena", a))

    def test_la_consulta_y_las_acciones_sin_comando_no_se_excluyen(self):
        self.assertFalse(falta_argumento("consulta", e4()))
        self.assertFalse(falta_argumento("no_existe", e4()))


class CandidatosDelPaso2(unittest.TestCase):
    def test_sin_exclusiones_quedan_todos(self):
        self.assertEqual(PLANTILLAS.candidatos("F5"), PLANTILLAS.familias["F5"].candidatos)

    def test_se_quitan_de_los_candidatos(self):
        quedan = PLANTILLAS.candidatos("F5", frozenset({"PB-F5-03"}))
        self.assertNotIn("PB-F5-03", quedan)
        self.assertIn("PB-F5-04", quedan)

    def test_si_se_excluyen_todos_se_ofrecen_todos(self):
        todos = frozenset(PLANTILLAS.familias["F5"].candidatos)
        self.assertEqual(PLANTILLAS.candidatos("F5", todos), PLANTILLAS.familias["F5"].candidatos)

    def test_las_exclusiones_de_otra_familia_no_cambian_nada(self):
        self.assertEqual(
            PLANTILLAS.candidatos("F5", frozenset({"PB-F1-02"})),
            PLANTILLAS.familias["F5"].candidatos,
        )


class ModeloQueGuarda:
    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.prompts = []
        self.esquemas = []

    def generar(self, prompt, esquema, plazo):
        self.prompts.append(prompt)
        self.esquemas.append(esquema)
        return self.respuestas.pop(0)


def modelo(familia, playbook):
    return ModeloQueGuarda(
        json.dumps({"familia": familia, "confianza": 0.9}),
        json.dumps({"playbook_id": playbook, "confianza": 0.85}),
    )


class ClasificarConExclusiones(unittest.TestCase):
    def test_el_modelo_no_puede_elegir_un_excluido(self):
        m = modelo("F5", "PB-F5-03")
        resultado = clasificar("ALERTA", m, PLANTILLAS, 60, excluir=frozenset({"PB-F5-03"}))
        self.assertNotIn("PB-F5-03", json.dumps(m.esquemas[1]))
        self.assertFalse(hasattr(resultado, "playbook_id"))  # falla segura: fuera del esquema

    def test_el_prompt_es_el_mismo_que_sin_exclusiones(self):
        # Sólo cambia el esquema: si el modelo iba a elegir una medida posible, elige la misma.
        con, sin = modelo("F5", "PB-F5-04"), modelo("F5", "PB-F5-04")
        clasificar("ALERTA", con, PLANTILLAS, 60, excluir=frozenset({"PB-F5-03"}))
        clasificar("ALERTA", sin, PLANTILLAS, 60)
        self.assertEqual(con.prompts, sin.prompts)


@dataclass(frozen=True)
class DecisionFalsa:
    familia: str | None
    playbook_id: str | None
    confianza: float | None
    nivel: int | None
    motivo: str | None = None
    detalle: str = ""
    equipo: str | None = None


class AlmacenFalso:
    def __init__(self):
        self.registradas = []
        self.decisiones = []

    def registrar_alerta(self, tenant_id, alerta_ref, titulo, severidad, detalle=None):
        self.registradas.append(alerta_ref)
        return Ticket(len(self.registradas), True)

    def agrupar_alerta(self, tenant_id, ticket_id, detalle):
        pass

    def registrar_decision(self, tenant_id, ticket_id, decision):
        self.decisiones.append(decision)
        return len(self.decisiones)

    def usos(self, tenant_id, definiciones, equipo=None, playbook_id=None):
        return {c.nombre: 0 for c in CONFIG.contadores}

    def alertas_en_ventana(self, tenant_id, ventana_minutos):
        return 1

    def cortacircuito_abierto(self, tenant_id):
        return False

    def abrir_cortacircuito(self, tenant_id, motivo):
        return True


class ValidadorConLaAlertaDeE4(unittest.TestCase):
    def procesar(self, alerta_wazuh, familia, playbook):
        m = modelo(familia, playbook)
        almacen = AlmacenFalso()
        v = Validador(almacen, m, PLANTILLAS, CATALOGO, CONFIG, DecisionFalsa)
        return v.procesar(1, alerta_wazuh), m, almacen

    def test_e4_no_acepta_cuarentena_ni_revertir_tarea(self):
        resultado, m, almacen = self.procesar(e4(), "F5", "PB-F5-04")
        esquema = json.dumps(m.esquemas[1])
        for excluido in ("PB-F5-01", "PB-F5-02", "PB-F5-03"):
            self.assertNotIn(excluido, esquema)
        self.assertIn("PB-F5-04", esquema)
        self.assertIn("- PB-F5-03 (", m.prompts[1])  # el texto del prompt no cambia
        self.assertEqual(resultado.destino, Destino.APROBADA)
        self.assertEqual(almacen.decisiones[0].playbook_id, "PB-F5-04")

    def test_con_archivo_la_cuarentena_sigue_disponible(self):
        # Severidad 12: la cuarentena de un archivo de sistema (PB-F5-03) es nivel 3.
        con_sev_12 = con_archivo()
        con_sev_12["rule"]["level"] = 12
        _, m, _ = self.procesar(con_sev_12, "F5", "PB-F5-03")
        self.assertIn("PB-F5-03", json.dumps(m.esquemas[1]))


def f3_rdp(nivel, ip="10.0.50.4"):
    """Inicio de sesión remoto en EP-WKS-01 (regla 100107), como el ticket 190 del 11-11."""
    return alerta(
        "100107", nivel, ["windows", "kronos", "kronos_f3"], PUESTO,
        {"win": {"system": {"eventID": "4624", "channel": "Security"},
                 "eventdata": {"ipAddress": ip, "logonType": "3",
                               "targetUserName": "labadmin"}}},
        "EventChannel",
    )


class SeveridadEnElEsquema(unittest.TestCase):
    """El paso 2 no ofrece medidas de un nivel mayor al que permite la severidad (11-11-2026).

    Ticket 190: un RDP desde una IP interna (100107, severidad 10) terminó en aislar el puesto
    (PB-F3-03, nivel 3) y VALIDATE lo frenó, en vez de bloquear la IP del otro equipo (PB-F3-02).
    """

    def procesar(self, alerta_wazuh, familia, playbook):
        m = modelo(familia, playbook)
        almacen = AlmacenFalso()
        v = Validador(almacen, m, PLANTILLAS, CATALOGO, CONFIG, DecisionFalsa)
        return v.procesar(1, alerta_wazuh), m, almacen

    def test_ticket_190_solo_se_ofrece_bloquear_la_ip_del_otro_equipo(self):
        resultado, m, almacen = self.procesar(f3_rdp(10), "F3", "PB-F3-02")
        enum = m.esquemas[1]["properties"]["playbook_id"]["enum"]
        self.assertEqual(enum, ["PB-F3-02"])
        self.assertEqual(resultado.destino, Destino.APROBADA)
        self.assertEqual(almacen.decisiones[0].playbook_id, "PB-F3-02")

    def test_aislar_el_puesto_ya_no_se_ofrece_con_severidad_10(self):
        resultado, m, _ = self.procesar(f3_rdp(10), "F3", "PB-F3-03")
        self.assertNotIn("PB-F3-03", json.dumps(m.esquemas[1]))
        self.assertEqual(resultado.motivo, "ESQUEMA_INVALIDO")

    def test_archivo_de_sistema_con_severidad_10_queda_la_cuarentena_de_nivel_1(self):
        _, m, _ = self.procesar(con_archivo(), "F5", "PB-F5-01")
        esquema = json.dumps(m.esquemas[1])
        self.assertNotIn("PB-F5-03", esquema)
        self.assertIn("PB-F5-01", esquema)

    def test_ssh_interno_en_un_servidor_solo_ofrece_bloquear_la_ip(self):
        # Regla 100125 (severidad 10): el SSH trae la IP del otro equipo.
        servidor = {"id": "001", "name": "EP-SRV-01", "ip": "192.0.2.30"}
        ssh = alerta("100125", 10, ["sshd", "kronos", "kronos_f3"], servidor,
                     {"srcip": "10.0.50.5", "dstuser": "labadmin"}, "journald")
        _, m, _ = self.procesar(ssh, "F3", "PB-F3-02")
        self.assertEqual(m.esquemas[1]["properties"]["playbook_id"]["enum"], ["PB-F3-02"])

    def test_sudo_despues_del_ssh_interno_solo_ofrece_aislar_el_servidor(self):
        # Regla 100127 (severidad 12): la alerta de sudo no trae IP.
        servidor = {"id": "001", "name": "EP-SRV-01", "ip": "192.0.2.30"}
        sudo = alerta("100127", 12, ["sudo", "kronos", "kronos_f3"], servidor,
                      {"srcuser": "labadmin", "dstuser": "root"}, "journald")
        resultado, m, _ = self.procesar(sudo, "F3", "PB-F3-04")
        self.assertEqual(m.esquemas[1]["properties"]["playbook_id"]["enum"], ["PB-F3-04"])
        self.assertEqual(resultado.destino, Destino.APROBADA)

    def test_si_ninguna_medida_esta_permitida_el_chequeo_de_severidad_frena(self):
        # Severidad 7 (nivel máximo 1) con una IP interna: en F3 no queda ninguna medida
        # permitida, se ofrecen todas y el chequeo de severidad sigue siendo la barrera.
        resultado, m, _ = self.procesar(f3_rdp(7), "F3", "PB-F3-02")
        self.assertIn("PB-F3-02", json.dumps(m.esquemas[1]))
        self.assertEqual(resultado.motivo, "NIVEL_NO_PERMITIDO_POR_SEVERIDAD")


def f2_codificado(nivel):
    """PowerShell codificado en un puesto (Sysmon), con PID e imagen."""
    return alerta(
        "100104", nivel, ["windows", "kronos", "kronos_f2"], PUESTO,
        {"win": {"system": {"eventID": "1"},
                 "eventdata": {"processId": "5480",
                               "image": "C:\\Users\\Public\\upd.exe"}}},
        "EventChannel",
    )


class SinConsultaDesdeSeveridad10(unittest.TestCase):
    """Desde severidad 10, reunir contexto no se ofrece si hay otra medida aplicable."""

    def esquema(self, alerta_wazuh, familia, playbook):
        m = modelo(familia, playbook)
        Validador(AlmacenFalso(), m, PLANTILLAS, CATALOGO, CONFIG, DecisionFalsa).procesar(
            1, alerta_wazuh
        )
        return json.dumps(m.esquemas[1])

    def test_severidad_alta_quita_la_consulta(self):
        esquema = self.esquema(f2_codificado(12), "F2", "PB-F2-03")
        self.assertNotIn("PB-F2-01", esquema)
        self.assertIn("PB-F2-03", esquema)

    def test_severidad_baja_mantiene_la_consulta(self):
        self.assertIn("PB-F2-01", self.esquema(f2_codificado(7), "F2", "PB-F2-01"))

    def test_sin_otra_medida_posible_la_consulta_queda(self):
        # Sin PID, imagen ni ruta, F2 sólo tiene la consulta: no se deja a la familia vacía.
        a = f2_codificado(12)
        a["data"]["win"]["eventdata"] = {}
        self.assertIn("PB-F2-01", self.esquema(a, "F2", "PB-F2-01"))


class MedidasImposiblesNoSeOfrecen(unittest.TestCase):
    """Prueba integral 2 (10-11): objetivos inválidos y medidas de otro ámbito de IP."""

    def esquema(self, alerta_wazuh, familia, playbook):
        m = modelo(familia, playbook)
        Validador(AlmacenFalso(), m, PLANTILLAS, CATALOGO, CONFIG, DecisionFalsa).procesar(
            1, alerta_wazuh
        )
        return json.dumps(m.esquemas[1])

    def test_ip_local_no_se_ofrece_bloquear(self):
        a = alerta(
            "100103", 10, ["windows", "kronos", "kronos_f1"], PUESTO,
            {"win": {"system": {"eventID": "4625"},
                     "eventdata": {"ipAddress": "::1", "targetUserName": "usuario.demo"}}},
            "EventChannel",
        )
        esquema = self.esquema(a, "F1", "PB-F1-05")
        self.assertNotIn("PB-F1-02", esquema)
        self.assertNotIn("PB-F1-03", esquema)
        self.assertIn("PB-F1-05", esquema)

    def test_ip_interna_no_ofrece_la_medida_externa(self):
        a = alerta(
            "100101", 10, ["sshd", "kronos", "kronos_f1"],
            {"id": "001", "name": "EP-SRV-01", "ip": "192.0.2.30"},
            {"srcip": "192.168.50.21", "srcuser": "prueba"}, "/var/log/auth.log",
        )
        esquema = self.esquema(a, "F1", "PB-F1-03")
        self.assertNotIn("PB-F1-02", esquema)
        self.assertIn("PB-F1-03", esquema)


class RutaDelArchivoCreado(unittest.TestCase):
    def test_sysmon_11_usa_target_filename(self):
        from ejecucion.ordenes import construir

        a = alerta(
            "100106", 10, ["windows", "kronos", "kronos_f2"], PUESTO,
            {"win": {"system": {"eventID": "11"},
                     "eventdata": {"image": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                                   "targetFilename": "C:\\Users\\Public\\svc-update2.exe"}}},
            "EventChannel",
        )
        orden = construir("cuarentena", a, sistema="windows")
        self.assertEqual(orden.argumentos[1], "C:\\Users\\Public\\svc-update2.exe")


class InundacionYRegistroVaciado(unittest.TestCase):
    """Prueba integral 2 (10-11): F6-02/F6-03 según el origen y la 592 sin sistema operativo."""

    def esquema(self, alerta_wazuh, familia, playbook):
        m = modelo(familia, playbook)
        Validador(AlmacenFalso(), m, PLANTILLAS, CATALOGO, CONFIG, DecisionFalsa).procesar(
            1, alerta_wazuh
        )
        return json.dumps(m.esquemas[1])

    def inundacion(self, ip):
        return alerta(
            "100118", 12, ["web", "kronos", "kronos_f6"],
            {"id": "001", "name": "EP-SRV-01", "ip": "192.0.2.30"},
            {"srcip": ip, "url": "/admin1", "id": "404"}, "/var/log/nginx/access.log",
        )

    def test_equipo_interno_se_limita(self):
        esquema = self.esquema(self.inundacion("192.168.50.30"), "F6", "PB-F6-03")
        self.assertNotIn("PB-F6-02", esquema)
        self.assertIn("PB-F6-03", esquema)

    def test_origen_externo_se_bloquea(self):
        esquema = self.esquema(self.inundacion("198.51.100.29"), "F6", "PB-F6-02")
        self.assertIn("PB-F6-02", esquema)
        self.assertNotIn("PB-F6-03", esquema)

    def test_registro_vaciado_sin_sistema_no_ofrece_cuarentena(self):
        a = alerta(
            "100113", 12, ["ossec", "kronos", "kronos_f5"],
            {"id": "001", "name": "EP-SRV-01", "ip": "192.0.2.30"},
            {}, "ossec-logcollector",
        )
        self.assertTrue(no_aplicable("cuarentena", a))
        self.assertTrue(no_aplicable("revertir_tarea", a))
        self.assertFalse(no_aplicable("aislar_equipo", a))


if __name__ == "__main__":
    unittest.main()


class MedidasDelOtroTipoDeEquipo(unittest.TestCase):
    """Prueba integral 2 (10-11, ticket 168): salida de datos desde un servidor, aislar puesto."""

    def esquema(self, alerta_wazuh, familia, playbook):
        m = modelo(familia, playbook)
        Validador(AlmacenFalso(), m, PLANTILLAS, CATALOGO, CONFIG, DecisionFalsa).procesar(
            1, alerta_wazuh
        )
        return json.dumps(m.esquemas[1])

    def salida(self, agente):
        return alerta(
            "100124", 12, ["audit", "kronos", "kronos_f4"], agente,
            {"audit": {"key": "kronos_salida", "exe": "/usr/bin/curl"}},
            "/var/log/audit/audit.log",
        )

    def test_servidor_no_ofrece_aislar_puesto(self):
        agente = {"id": "001", "name": "ep-srv-01", "ip": "192.0.2.30"}
        esquema = self.esquema(self.salida(agente), "F4", "PB-F4-03")
        self.assertNotIn("PB-F4-02", esquema)
        self.assertIn("PB-F4-03", esquema)

    def test_puesto_no_ofrece_aislar_servidor(self):
        esquema = self.esquema(self.salida(PUESTO), "F4", "PB-F4-02")
        self.assertIn("PB-F4-02", esquema)
        self.assertNotIn("PB-F4-03", esquema)

    def test_equipo_sin_tipo_recibe_todas(self):
        agente = {"id": "009", "name": "otro-equipo", "ip": "192.0.2.40"}
        esquema = self.esquema(self.salida(agente), "F4", "PB-F4-03")
        self.assertIn("PB-F4-02", esquema)
        self.assertIn("PB-F4-03", esquema)
