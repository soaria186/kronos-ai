import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from decision.inferencia import MotorNoDisponible, TiempoExcedido
from decision.ollama import ClienteOllama

ESQUEMA = {"type": "object"}


class Servidor:
    """Servidor HTTP local que responde según self.modo."""

    def __init__(self):
        servidor = self

        class Manejador(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                largo = int(self.headers["Content-Length"])
                servidor.cuerpo = json.loads(self.rfile.read(largo))
                modo = servidor.modo
                if modo == "lento":
                    time.sleep(1.0)
                if modo == "error":
                    self.responder(500, b'{"error": "fallo interno"}')
                elif modo == "basura":
                    self.responder(200, b"<html>no es json</html>")
                elif modo == "sin_response":
                    self.responder(200, b'{"done": true}')
                else:
                    datos = {
                        "response": '{"familia": "F2", "confianza": 0.6}',
                        "done": True,
                    }
                    self.responder(200, json.dumps(datos).encode())

            def responder(self, codigo, crudo):
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(crudo)))
                self.end_headers()
                try:
                    self.wfile.write(crudo)
                except BrokenPipeError:
                    pass  # el cliente ya se rindió por timeout

        self.modo = "ok"
        self.cuerpo = None
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def cerrar(self):
        self.http.shutdown()
        self.http.server_close()


class ClienteOllamaPruebas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servidor = Servidor()
        cls.cliente = ClienteOllama("modelo:prueba", cls.servidor.url)

    @classmethod
    def tearDownClass(cls):
        cls.servidor.cerrar()

    def generar(self, modo, plazo=5.0):
        self.servidor.modo = modo
        return self.cliente.generar("prompt", ESQUEMA, plazo)

    def test_respuesta_y_cuerpo_de_la_peticion(self):
        self.assertEqual(self.generar("ok"), '{"familia": "F2", "confianza": 0.6}')
        cuerpo = self.servidor.cuerpo
        self.assertEqual(cuerpo["model"], "modelo:prueba")
        self.assertIs(cuerpo["stream"], False)
        self.assertEqual(cuerpo["format"], ESQUEMA)
        self.assertEqual(cuerpo["options"], {"temperature": 0, "num_ctx": 4096})
        self.assertEqual(cuerpo["keep_alive"], -1)

    def test_demora(self):
        with self.assertRaises(TiempoExcedido):
            self.generar("lento", plazo=0.2)

    def test_error_http(self):
        with self.assertRaises(MotorNoDisponible):
            self.generar("error")

    def test_respuesta_que_no_es_json(self):
        with self.assertRaises(MotorNoDisponible):
            self.generar("basura")

    def test_respuesta_sin_campo_response(self):
        with self.assertRaises(MotorNoDisponible):
            self.generar("sin_response")

    def test_servidor_apagado(self):
        servidor = Servidor()
        url = servidor.url
        servidor.cerrar()
        with self.assertRaises(MotorNoDisponible):
            ClienteOllama("m", url).generar("prompt", ESQUEMA, 2.0)


if __name__ == "__main__":
    unittest.main()
