import copy
import json
import unittest
from collections import namedtuple
from pathlib import Path

from ejecucion.ordenes import AccionNoImplementada, OrdenInvalida, construir
from validacion.alerta import AlertaInvalida, preparar
from validacion.chequeos import ListaExclusion
from validacion.servicio import registrar

ALERTAS_150 = (
    Path(__file__).resolve().parents[2]
    / "decision"
    / "mediciones"
    / "casos_150"
    / "alertas.json"
)

Ticket = namedtuple("Ticket", "ticket_id nuevo")


class RepoFalso:
    """Guarda lo que recibe registrar_alerta, como lo haría Repositorio."""

    def __init__(self, nuevo=True):
        self.nuevo = nuevo
        self.llamadas = []

    def registrar_alerta(self, tenant_id, alerta_ref, titulo, severidad, detalle=None):
        self.llamadas.append(
            {
                "tenant_id": tenant_id,
                "alerta_ref": alerta_ref,
                "titulo": titulo,
                "severidad": severidad,
                "detalle": detalle,
            }
        )
        return Ticket(7, self.nuevo)


def ssh():
    # Alerta ficticia con la forma de alerts.json tras la regla de sobre 100101.
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
        "manager": {"name": "soar-core"},
        "id": "1760411662.12345",
        "full_log": "sshd[2211]: Failed password for root from 192.0.2.77 port 51122 ssh2",
        "decoder": {"name": "sshd"},
        "data": {"srcip": "192.0.2.77", "srcport": "51122", "dstuser": "operador02"},
        "location": "/var/log/auth.log",
    }


class AlertaCompleta(unittest.TestCase):
    def setUp(self):
        self.repo = RepoFalso()
        self.alerta = ssh()

    def registrar(self, alerta=None, tenant=1):
        return registrar(self.repo, tenant, self.alerta if alerta is None else alerta)

    def detalle(self):
        return self.repo.llamadas[0]["detalle"]

    def test_guarda_la_alerta_completa_en_detalle_alerta(self):
        self.registrar()
        self.assertEqual(set(self.detalle()), {"alerta"})
        self.assertEqual(self.detalle()["alerta"], ssh())

    def test_es_una_copia(self):
        self.registrar()
        guardado = self.detalle()["alerta"]
        self.assertIsNot(guardado, self.alerta)
        self.alerta["agent"]["id"] = "999"
        self.assertEqual(guardado["agent"]["id"], "003")
        guardado["data"]["srcip"] = "192.0.2.1"
        self.assertEqual(self.alerta["data"]["srcip"], "192.0.2.77")

    def test_lo_guardado_es_json_y_conserva_la_etiqueta_de_familia(self):
        # La etiqueta no se la ven al modelo, pero la bitácora guarda lo que llegó.
        registrada = self.registrar()
        guardado = self.detalle()["alerta"]
        self.assertEqual(json.loads(json.dumps(guardado)), guardado)
        self.assertIn("kronos_f1", guardado["rule"]["groups"])
        self.assertNotIn("kronos_f1", registrada.alerta.texto)

    def test_referencia_titulo_severidad_e_inquilino(self):
        registrada = self.registrar(tenant=42)
        llamada = self.repo.llamadas[0]
        self.assertEqual(llamada["tenant_id"], 42)
        self.assertEqual(llamada["alerta_ref"], "1760411662.12345")
        self.assertEqual(llamada["titulo"], "fuerza bruta por SSH desde 192.0.2.77")
        self.assertEqual(llamada["severidad"], 10)
        self.assertEqual((registrada.ticket_id, registrada.nuevo), (7, True))
        self.assertEqual(registrada.alerta.familia_candidata, "F1")

    def test_titulo_largo_o_vacio(self):
        self.alerta["rule"]["description"] = "Kronos F1: " + "x" * 5000
        self.registrar()
        self.assertLess(len(self.repo.llamadas[0]["titulo"]), 300)
        self.alerta["rule"]["description"] = "Kronos F1:"
        self.alerta["id"] = "1760411662.99999"
        self.registrar()
        self.assertEqual(self.repo.llamadas[1]["titulo"], "Regla 100101")

    def test_alerta_releida_no_es_nueva(self):
        self.repo = RepoFalso(nuevo=False)
        self.assertFalse(self.registrar().nuevo)

    def test_sin_regla_de_sobre_no_se_registra(self):
        self.alerta["rule"]["groups"] = ["syslog", "sshd"]
        self.assertIsNone(self.registrar())
        self.assertEqual(self.repo.llamadas, [])

    def test_alerta_invalida_no_llega_a_la_base(self):
        del self.alerta["id"]
        with self.assertRaises(AlertaInvalida):
            self.registrar()
        self.assertEqual(self.repo.llamadas, [])


class AlertaHostil(unittest.TestCase):
    """Quien controla un campo de la alerta no debe poder impedir que se registre."""

    def setUp(self):
        self.repo = RepoFalso()
        self.alerta = ssh()

    def guardado(self):
        registrar(self.repo, 1, self.alerta)
        return self.repo.llamadas[0]["detalle"]["alerta"]

    def test_nul_y_sustitutos_sueltos_se_reemplazan(self):
        self.alerta["full_log"] = "usuario\x00root \ud800 fin"
        self.alerta["data"]["dstuser"] = "a\x00b"
        guardado = self.guardado()
        self.assertEqual(guardado["full_log"], "usuario�root � fin")
        self.assertEqual(guardado["data"]["dstuser"], "a�b")
        crudo = json.dumps(self.repo.llamadas[0]["detalle"])
        self.assertNotIn("\\u0000", crudo)
        self.assertNotIn("\\ud800", crudo)

    def test_nul_en_una_clave(self):
        self.alerta["data"]["campo\x00raro"] = "valor"
        self.assertIn("campo�raro", self.guardado()["data"])

    def test_el_original_no_se_modifica(self):
        self.alerta["full_log"] = "a\x00b"
        self.guardado()
        self.assertEqual(self.alerta["full_log"], "a\x00b")

    def test_texto_normal_con_acentos_y_emoji_queda_igual(self):
        self.alerta["full_log"] = "contraseña incorrecta para «ñandú» 🙂"
        self.assertEqual(
            self.guardado()["full_log"], "contraseña incorrecta para «ñandú» 🙂"
        )

    def test_rechazos_sin_tocar_la_base(self):
        casos = {
            "NaN": float("nan"),
            "infinito": float("inf"),
            "no es JSON": {1, 2},
        }
        for nombre, valor in casos.items():
            self.alerta["data"]["extra"] = valor
            with self.subTest(nombre), self.assertRaises(AlertaInvalida):
                registrar(self.repo, 1, self.alerta)
        self.assertEqual(self.repo.llamadas, [])

    def test_claves_que_chocan_al_quitar_caracteres(self):
        self.alerta["data"]["a\x00"] = 1
        self.alerta["data"]["a�"] = 2
        with self.assertRaises(AlertaInvalida):
            registrar(self.repo, 1, self.alerta)

    def test_clave_que_no_es_texto(self):
        self.alerta["data"][7] = "x"
        with self.assertRaises(AlertaInvalida):
            registrar(self.repo, 1, self.alerta)


class ContratoConExecute(unittest.TestCase):
    """EXECUTE lee detalle.get("alerta", {}) (ejecucion/ejecutor.py)."""

    def test_execute_saca_el_agente_y_la_ip_de_lo_guardado(self):
        repo = RepoFalso()
        registrar(repo, 1, ssh())
        detalle = repo.llamadas[0]["detalle"]
        orden = construir("bloquear_ip", detalle.get("alerta", {}))
        self.assertEqual(orden.agente, "003")
        self.assertEqual(orden.comando, "kronos-bloquear-ip")
        self.assertEqual(orden.argumentos, ("aplicar", "192.0.2.77"))

    def test_execute_saca_la_cuenta_de_lo_guardado(self):
        repo = RepoFalso()
        registrar(repo, 1, ssh())
        orden = construir("deshabilitar_cuenta", repo.llamadas[0]["detalle"]["alerta"])
        self.assertEqual(orden.argumentos, ("aplicar", "operador02"))

    def test_execute_saca_el_pid_de_una_alerta_de_sysmon_guardada(self):
        # Las 150 alertas de prueba no traen processId; el evento 1 de Sysmon sí.
        alerta = {
            "rule": {
                "level": 12,
                "id": "100104",
                "description": "Kronos F2: PowerShell con comando codificado en Base64",
                "groups": ["sysmon", "kronos", "kronos_f2"],
            },
            "agent": {"id": "007", "name": "pc-adm-07", "ip": "192.0.2.31"},
            "id": "1760498062.777",
            "data": {
                "win": {
                    "system": {"eventID": "1"},
                    "eventdata": {
                        "image": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                        "processId": "4312",
                        "user": "EJEMPLO\\usuario01",
                    },
                }
            },
        }
        repo = RepoFalso()
        registrar(repo, 1, alerta)
        orden = construir("terminar_proceso", repo.llamadas[0]["detalle"]["alerta"])
        self.assertEqual((orden.agente, orden.argumentos), ("007", ("aplicar", "4312")))


class EjecutarSoloLoQueSeRevisó(unittest.TestCase):
    """Todo valor sobre el que EXECUTE actuaría lo habría detectado la lista de exclusión.

    Se prueba con las 150 alertas: si el valor estuviera en la lista, VALIDATE rechazaría.
    """

    @classmethod
    def setUpClass(cls):
        cls.alertas = [
            c["alerta"] for c in json.loads(ALERTAS_150.read_text(encoding="utf-8"))
        ]

    def ordenes(self, accion, alertas=None):
        for alerta in alertas or self.alertas:
            try:
                yield alerta, construir(accion, alerta)
            except (OrdenInvalida, AccionNoImplementada):
                continue

    def assertRevisado(self, categoria, valor, alerta):
        exclusion = ListaExclusion.desde([(categoria, valor)])
        self.assertIsNotNone(
            exclusion.coincidencia(preparar(alerta).objetivo),
            f"{alerta['id']}: EXECUTE actuaría sobre {categoria}={valor} sin que la "
            "lista de exclusión lo revisara",
        )

    def test_ip(self):
        total = 0
        for alerta, orden in self.ordenes("bloquear_ip"):
            self.assertRevisado("ip", orden.argumentos[1], alerta)
            total += 1
        self.assertGreaterEqual(total, 10)

    def test_cuenta(self):
        total = 0
        for alerta, orden in self.ordenes("deshabilitar_cuenta"):
            self.assertRevisado("cuenta", orden.argumentos[1], alerta)
            total += 1
        self.assertGreaterEqual(total, 10)

    def test_servicio(self):
        total = 0
        for alerta, orden in self.ordenes("detener_servicio"):
            self.assertRevisado("servicio", orden.argumentos[1], alerta)
            total += 1
        self.assertGreaterEqual(total, 3)

    def test_equipo(self):
        # Toda medida actúa sobre el agente de la alerta: el equipo se revisa siempre.
        for alerta in self.alertas:
            self.assertRevisado("equipo", alerta["agent"]["name"], alerta)

    def test_ip_en_otra_forma_sigue_revisada(self):
        # EXECUTE acepta ::ffff:a.b.c.d y bloquea esa dirección.
        total = 0
        for alerta in self.alertas:
            ip = alerta.get("data", {}).get("srcip")
            if not ip:
                continue
            disfrazada = copy.deepcopy(alerta)
            disfrazada["data"]["srcip"] = f"::ffff:{ip}"
            try:
                construir("bloquear_ip", disfrazada)
            except OrdenInvalida:
                self.fail(
                    f"{alerta['id']}: EXECUTE debería aceptar {disfrazada['data']['srcip']}"
                )
            exclusion = ListaExclusion.desde([("ip", ip)])
            self.assertIsNotNone(exclusion.coincidencia(preparar(disfrazada).objetivo))
            total += 1
        self.assertGreaterEqual(total, 10)


if __name__ == "__main__":
    unittest.main()
