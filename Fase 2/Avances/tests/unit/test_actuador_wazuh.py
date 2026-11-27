import http.client
import json
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ejecucion.actuador import ErrorActuador
from ejecucion.actuador_wazuh import ActuadorWazuh
from ejecucion.ordenes import Orden

ORDEN = Orden("002", "kronos-bloquear-ip", ("aplicar", "203.0.113.7"), "linux")
ORDEN_WINDOWS = Orden("002", "kronos-bloquear-ip", ("aplicar", "203.0.113.7"), "windows")


class ApiFalsa(BaseHTTPRequestHandler):
    """Imita las dos rutas de la API de Wazuh que usa el actuador."""

    def log_message(self, *args):
        pass

    def do_POST(self):
        estado = self.server.estado
        estado["autenticaciones"] += 1
        estado["basic"] = self.headers.get("Authorization", "")
        if estado["auth_falla"]:
            return self.responder(401, {"title": "Unauthorized"})
        self.responder(200, {"data": {"token": f"tok-{estado['autenticaciones']}"}})

    def do_PUT(self):
        estado = self.server.estado
        largo = int(self.headers.get("Content-Length", 0))
        estado["peticiones"].append(
            {
                "ruta": self.path,
                "auth": self.headers.get("Authorization"),
                "cuerpo": json.loads(self.rfile.read(largo)),
            }
        )
        if estado["put_401"]:
            estado["put_401"] -= 1
            return self.responder(401, {"title": "Unauthorized"})
        if estado["agente_desconectado"]:
            return self.responder(
                200,
                {
                    "data": {
                        "affected_items": [],
                        "failed_items": [
                            {
                                "error": {
                                    "code": 1707,
                                    "message": "Cannot send request, agent is not active",
                                }
                            }
                        ],
                    }
                },
            )
        self.responder(
            200, {"data": {"affected_items": ["002"], "failed_items": []}, "error": 0}
        )

    def responder(self, codigo, datos):
        crudo = json.dumps(datos).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(crudo)))
        self.end_headers()
        self.wfile.write(crudo)


class Base(unittest.TestCase):
    def setUp(self):
        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), ApiFalsa)
        self.servidor.estado = {
            "autenticaciones": 0,
            "peticiones": [],
            "auth_falla": False,
            "put_401": 0,
            "agente_desconectado": False,
        }
        self.hilo = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.hilo.start()
        self.ahora = 0.0

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()

    def actuador(self):
        puerto = self.servidor.server_address[1]
        return ActuadorWazuh(
            "https://wazuh.prueba:55000",
            "kronos-execute",
            "s3creta",
            conectar=lambda: http.client.HTTPConnection("127.0.0.1", puerto, timeout=5),
            reloj=lambda: self.ahora,
        )

    @property
    def estado(self):
        return self.servidor.estado


class Envio(Base):
    def test_envia_la_orden(self):
        referencia = self.actuador().enviar(ORDEN)
        self.assertEqual(referencia, "wazuh-ar:002:kronos-bloquear-ip")
        peticion = self.estado["peticiones"][0]
        self.assertEqual(peticion["ruta"], "/active-response?agents_list=002")
        self.assertEqual(peticion["auth"], "Bearer tok-1")
        self.assertEqual(
            peticion["cuerpo"],
            {"command": "!kronos-bloquear-ip", "arguments": ["aplicar", "203.0.113.7"]},
        )

    def test_en_windows_envia_el_cmd(self):
        referencia = self.actuador().enviar(ORDEN_WINDOWS)
        self.assertEqual(referencia, "wazuh-ar:002:kronos-bloquear-ip.cmd")
        self.assertEqual(
            self.estado["peticiones"][0]["cuerpo"],
            {"command": "!kronos-bloquear-ip.cmd", "arguments": ["aplicar", "203.0.113.7"]},
        )

    def test_reutiliza_el_token(self):
        actuador = self.actuador()
        actuador.enviar(ORDEN)
        actuador.enviar(ORDEN)
        self.assertEqual(self.estado["autenticaciones"], 1)

    def test_renueva_el_token_viejo(self):
        actuador = self.actuador()
        actuador.enviar(ORDEN)
        self.ahora = 601.0
        actuador.enviar(ORDEN)
        self.assertEqual(self.estado["autenticaciones"], 2)

    def test_401_reautentica_una_sola_vez(self):
        self.estado["put_401"] = 1
        self.actuador().enviar(ORDEN)
        self.assertEqual(self.estado["autenticaciones"], 2)
        self.assertEqual(len(self.estado["peticiones"]), 2)

    def test_401_persistente_falla(self):
        self.estado["put_401"] = 5
        with self.assertRaises(ErrorActuador):
            self.actuador().enviar(ORDEN)
        self.assertEqual(len(self.estado["peticiones"]), 2)

    def test_agente_desconectado(self):
        self.estado["agente_desconectado"] = True
        with self.assertRaisesRegex(ErrorActuador, "agent is not active"):
            self.actuador().enviar(ORDEN)

    def test_credenciales_rechazadas_sin_mostrar_la_clave(self):
        self.estado["auth_falla"] = True
        with self.assertRaises(ErrorActuador) as caso:
            self.actuador().enviar(ORDEN)
        self.assertNotIn("s3creta", str(caso.exception))
        self.assertEqual(self.estado["peticiones"], [])

    def test_api_apagada(self):
        actuador = self.actuador()
        self.tearDown()
        self.setUp()  # otro puerto: el actuador apunta a uno cerrado
        with self.assertRaises(ErrorActuador):
            actuador.enviar(ORDEN)


class Configuracion(unittest.TestCase):
    def test_desde_entorno_con_opcionales_vacios(self):
        import os
        from unittest import mock

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("s3creta\n")
        entorno = {
            "KRONOS_WAZUH_URL": "https://wazuh.manager:55000",
            "KRONOS_WAZUH_USUARIO": "kronos-execute",
            "KRONOS_WAZUH_CLAVE_ARCHIVO": f.name,
            "KRONOS_WAZUH_CA": "",
            "KRONOS_WAZUH_NOMBRE_SERVIDOR": "",
        }
        try:
            with mock.patch.dict(os.environ, entorno):
                actuador = ActuadorWazuh.desde_entorno()
            self.assertIsInstance(actuador._conectar(), http.client.HTTPSConnection)
            self.assertEqual(actuador._clave, "s3creta")
        finally:
            os.unlink(f.name)

    def test_solo_https(self):
        with self.assertRaises(ValueError):
            ActuadorWazuh("http://wazuh:55000", "u", "c")

    def test_credenciales_obligatorias(self):
        with self.assertRaises(ValueError):
            ActuadorWazuh("https://wazuh:55000", "u", "")


@unittest.skipUnless(shutil.which("openssl"), "falta openssl")
class Tls(unittest.TestCase):
    """HTTPS real con un certificado de prueba emitido para «wazuh.manager»."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        d = Path(cls.dir.name)
        cls.cert, llave = d / "cert.pem", d / "llave.pem"
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-keyout",
                str(llave),
                "-out",
                str(cls.cert),
                "-subj",
                "/CN=wazuh.manager",
                "-addext",
                "subjectAltName=DNS:wazuh.manager",
            ],
            check=True,
            capture_output=True,
        )
        cls.servidor = ThreadingHTTPServer(("127.0.0.1", 0), ApiFalsa)
        cls.servidor.estado = {
            "autenticaciones": 0,
            "peticiones": [],
            "auth_falla": False,
            "put_401": 0,
            "agente_desconectado": False,
        }
        contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contexto.load_cert_chain(cls.cert, llave)
        cls.servidor.socket = contexto.wrap_socket(
            cls.servidor.socket, server_side=True
        )
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()
        cls.url = f"https://127.0.0.1:{cls.servidor.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        cls.dir.cleanup()

    def test_verifica_contra_el_nombre_del_certificado(self):
        actuador = ActuadorWazuh(
            self.url, "u", "c", ca=str(self.cert), nombre_servidor="wazuh.manager"
        )
        self.assertEqual(actuador.enviar(ORDEN), "wazuh-ar:002:kronos-bloquear-ip")

    def test_nombre_que_no_coincide(self):
        actuador = ActuadorWazuh(
            self.url, "u", "c", ca=str(self.cert)
        )  # verifica 127.0.0.1
        with self.assertRaisesRegex(ErrorActuador, "certificado"):
            actuador.enviar(ORDEN)

    def test_sin_la_ca_no_confia(self):
        actuador = ActuadorWazuh(self.url, "u", "c", nombre_servidor="wazuh.manager")
        with self.assertRaisesRegex(ErrorActuador, "certificado"):
            actuador.enviar(ORDEN)


if __name__ == "__main__":
    unittest.main()
