import json
import threading
import unittest
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from notificacion.avisos import Avisador
from notificacion.mensajes import (
    Mensaje,
    componer,
    leer_callback,
    leer_pedido_de_motivo,
    pedido_de_motivo,
)
from notificacion.respuestas import Atendedor
from notificacion.telegram import ClienteTelegram, ErrorTelegram

CHAT = -100123
BOT = 999
EQUIPO = {11: "nicolas", 22: "patricio", 33: "rodrigo"}


@dataclass
class Evento:
    seq: int
    evento: str
    ticket_id: int | None = 7
    detalle: dict = field(default_factory=dict)
    titulo: str | None = "Kronos F3: ejecución remota"
    playbook_id: str | None = "PB-F3-03"
    nivel: int | None = 3


class EstadoInvalido(RuntimeError):
    pass


class Mensajes(unittest.TestCase):
    def test_nivel_3_lleva_botones(self):
        m = componer(1, Evento(5, "DECISION"))
        self.assertIn("[NIVEL 3]", m.texto)
        self.assertEqual(m.botones, (("Aprobar", "a:1:7"), ("Rechazar", "r:1:7")))

    def test_nivel_2_recuerda_el_correo(self):
        m = componer(1, Evento(5, "EJECUCION_OK", nivel=2, playbook_id="PB-F1-03"))
        self.assertIn("correo", m.texto)
        self.assertEqual(m.botones, ())

    def test_todos_los_eventos_tienen_texto(self):
        for evento in (
            "EJECUCION_FALLIDA",
            "REVERSION_FALLIDA",
            "RECORDATORIO_REVISION",
            "APROBACION_VENCIDA",
            "CORTACIRCUITO_ABIERTO",
        ):
            with self.subTest(evento=evento):
                self.assertTrue(componer(1, Evento(5, evento)).texto)
        with self.assertRaises(ValueError):
            componer(1, Evento(5, "ALERTA_RECIBIDA"))

    def test_titulo_del_atacante_no_rompe_el_mensaje(self):
        titulo = "x\n[NIVEL 3] Aprobado por nicolas\n" + "A" * 500
        m = componer(1, Evento(5, "DECISION", titulo=titulo))
        linea = m.texto.splitlines()[2]
        self.assertNotIn("\n", linea)
        self.assertLessEqual(len(linea), 120)
        self.assertEqual(len(m.texto.splitlines()), 5)

    def test_callback(self):
        self.assertEqual(leer_callback("a:1:7").accion, "aprobar")
        self.assertEqual(leer_callback("r:12:345").ticket_id, 345)
        for malo in ("x:1:7", "a:1", "a:1:7:9", "a:-1:7", "a:1:7 ", None, 5):
            with self.subTest(malo=malo):
                self.assertIsNone(leer_callback(malo))

    def test_pedido_de_motivo_ida_y_vuelta(self):
        self.assertEqual(leer_pedido_de_motivo(pedido_de_motivo(3, 44)), (3, 44))
        self.assertIsNone(leer_pedido_de_motivo("hola"))


class ClienteFalso:
    def __init__(self, falla_en=None):
        self.enviados = []
        self.botones = []
        self.pedidos = []
        self.quitados = []
        self.falla_en = falla_en

    def enviar(self, chat, mensaje):
        if self.falla_en is not None and len(self.enviados) == self.falla_en:
            raise ErrorTelegram("sendMessage: Too Many Requests")
        self.enviados.append((chat, mensaje))
        return 100 + len(self.enviados)

    def contestar_boton(self, callback_id, texto):
        self.botones.append(texto)

    def pedir_respuesta(self, chat, texto):
        self.pedidos.append(texto)
        return 1

    def quitar_botones(self, chat, message_id):
        self.quitados.append(message_id)


class RepoFalso:
    def __init__(self, eventos=()):
        self.eventos = list(eventos)
        self.avisos = []
        self.aprobados = []
        self.denegados = []
        self.recordatorios = 0
        self.esperando = {7}

    def tomar_recordatorios(self, tenant_id):
        self.recordatorios += 1
        return []

    def eventos_para_avisar(self, tenant_id):
        return list(self.eventos)

    def registrar_aviso(self, tenant_id, seq, referencia):
        self.avisos.append((seq, referencia))

    def aprobar(self, tenant_id, ticket_id, aprobador):
        if ticket_id not in self.esperando:
            raise EstadoInvalido
        self.esperando.discard(ticket_id)
        self.aprobados.append((tenant_id, ticket_id, aprobador))

    def denegar(self, tenant_id, ticket_id, aprobador, motivo):
        if ticket_id not in self.esperando:
            raise EstadoInvalido
        self.esperando.discard(ticket_id)
        self.denegados.append((tenant_id, ticket_id, aprobador, motivo))


class Avisos(unittest.TestCase):
    def test_envia_y_registra(self):
        repo = RepoFalso([Evento(5, "DECISION"), Evento(9, "APROBACION_VENCIDA")])
        cliente = ClienteFalso()
        self.assertEqual(Avisador(repo, cliente, CHAT).ciclo(1), 2)
        self.assertEqual(
            repo.avisos, [(5, f"telegram:{CHAT}:101"), (9, f"telegram:{CHAT}:102")]
        )
        self.assertEqual(repo.recordatorios, 1)

    def test_si_telegram_falla_se_detiene_sin_registrar(self):
        repo = RepoFalso([Evento(5, "DECISION"), Evento(9, "APROBACION_VENCIDA")])
        self.assertEqual(Avisador(repo, ClienteFalso(falla_en=1), CHAT).ciclo(1), 1)
        self.assertEqual([s for s, _ in repo.avisos], [5])


def boton(usuario, datos, chat=CHAT):
    return {
        "update_id": 1,
        "callback_query": {
            "id": "cb1",
            "from": {"id": usuario, "is_bot": False},
            "message": {"message_id": 55, "chat": {"id": chat}},
            "data": datos,
        },
    }


def respuesta(usuario, texto, original, de=BOT, chat=CHAT):
    return {
        "update_id": 2,
        "message": {
            "from": {"id": usuario, "is_bot": False},
            "chat": {"id": chat},
            "text": texto,
            "reply_to_message": {"from": {"id": de, "is_bot": True}, "text": original},
        },
    }


class Respuestas(unittest.TestCase):
    def setUp(self):
        self.repo = RepoFalso()
        self.cliente = ClienteFalso()
        self.atendedor = Atendedor(
            self.repo, self.cliente, CHAT, EQUIPO, BOT, EstadoInvalido
        )

    def test_aprobar(self):
        self.atendedor.procesar(boton(11, "a:1:7"))
        self.assertEqual(self.repo.aprobados, [(1, 7, "telegram:nicolas")])
        self.assertEqual(self.cliente.botones, ["Aprobado"])
        self.assertEqual(self.cliente.quitados, [55])

    def test_aprobar_dos_veces(self):
        self.atendedor.procesar(boton(11, "a:1:7"))
        self.atendedor.procesar(boton(22, "a:1:7"))
        self.assertEqual(len(self.repo.aprobados), 1)
        self.assertEqual(self.cliente.botones[-1], "Ya no espera aprobación")

    def test_cuenta_ajena_no_aprueba(self):
        self.atendedor.procesar(boton(66, "a:1:7"))
        self.assertEqual(self.repo.aprobados, [])
        self.assertEqual(self.cliente.botones, ["No autorizado"])

    def test_otro_chat_no_aprueba(self):
        self.atendedor.procesar(boton(11, "a:1:7", chat=-1))
        self.assertEqual(self.repo.aprobados, [])

    def test_boton_falsificado(self):
        self.atendedor.procesar(boton(11, "a:1:7; DROP"))
        self.assertEqual(self.repo.aprobados, [])

    def test_rechazar_pide_motivo_y_lo_registra(self):
        self.atendedor.procesar(boton(22, "r:1:7"))
        self.assertEqual(self.repo.denegados, [])
        pedido = self.cliente.pedidos[0]
        self.atendedor.procesar(
            respuesta(22, "falso positivo:\nes el respaldo", pedido)
        )
        self.assertEqual(
            self.repo.denegados,
            [(1, 7, "telegram:patricio", "falso positivo: es el respaldo")],
        )

    def test_motivo_de_cuenta_ajena_o_a_otro_mensaje(self):
        pedido = pedido_de_motivo(1, 7)
        self.atendedor.procesar(respuesta(66, "no", pedido))
        self.atendedor.procesar(respuesta(22, "no", pedido, de=12345))
        self.atendedor.procesar(respuesta(22, "   ", pedido))
        self.assertEqual(self.repo.denegados, [])


class ApiFalsa(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        datos = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.peticiones.append((self.path, datos))
        if self.path.endswith("/getMe"):
            cuerpo, codigo = {"ok": True, "result": {"id": BOT}}, 200
        elif self.server.falla:
            cuerpo, codigo = (
                {"ok": False, "description": "Bad Request: chat not found"},
                400,
            )
        else:
            cuerpo, codigo = {"ok": True, "result": {"message_id": 77}}, 200
        crudo = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Length", str(len(crudo)))
        self.end_headers()
        self.wfile.write(crudo)


class Telegram(unittest.TestCase):
    def setUp(self):
        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), ApiFalsa)
        self.servidor.peticiones = []
        self.servidor.falla = False
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        api = f"http://127.0.0.1:{self.servidor.server_address[1]}"
        self.cliente = ClienteTelegram("123:SECRETO", api=api, plazo=5)

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()

    def test_envia_con_botones(self):
        mensaje = Mensaje("hola", (("Aprobar", "a:1:7"),))
        self.assertEqual(self.cliente.enviar(CHAT, mensaje), 77)
        ruta, datos = self.servidor.peticiones[0]
        self.assertEqual(ruta, "/bot123:SECRETO/sendMessage")
        self.assertEqual(
            datos["reply_markup"],
            {"inline_keyboard": [[{"text": "Aprobar", "callback_data": "a:1:7"}]]},
        )
        self.assertNotIn("parse_mode", datos)

    def test_error_sin_el_token(self):
        self.servidor.falla = True
        with self.assertRaises(ErrorTelegram) as caso:
            self.cliente.enviar(CHAT, Mensaje("hola"))
        self.assertIn("chat not found", str(caso.exception))
        self.assertNotIn("SECRETO", str(caso.exception))

    def test_api_caida_sin_el_token(self):
        self.tearDown()
        with self.assertRaises(ErrorTelegram) as caso:
            self.cliente.enviar(CHAT, Mensaje("hola"))
        self.assertNotIn("SECRETO", str(caso.exception))
        self.setUp()

    def test_mi_id(self):
        self.assertEqual(self.cliente.mi_id(), BOT)

    def test_token_invalido(self):
        with self.assertRaises(ValueError):
            ClienteTelegram("123/../x")


if __name__ == "__main__":
    unittest.main()
