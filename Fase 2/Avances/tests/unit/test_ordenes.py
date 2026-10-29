import unittest

from ejecucion.ordenes import (
    AccionNoImplementada,
    Orden,
    OrdenInvalida,
    construir,
    construir_reversion,
    leer_mapa_agentes,
    sistema_operativo,
)


def alerta(**data):
    return {"agent": {"id": "002", "ip": "10.0.2.15"}, "data": data}


def windows(**eventdata):
    return {"agent": {"id": "003"}, "data": {"win": {"eventdata": eventdata}}}


class Construir(unittest.TestCase):
    def test_bloquear_ip(self):
        orden = construir("bloquear_ip", alerta(srcip="203.0.113.7"), sistema="linux")
        self.assertEqual(orden.agente, "002")
        self.assertEqual(orden.comando, "kronos-bloquear-ip")
        self.assertEqual(orden.argumentos, ("aplicar", "203.0.113.7"))

    def test_reversion_usa_el_mismo_objetivo(self):
        orden = construir_reversion("bloquear_ip", alerta(srcip="203.0.113.7"), sistema="linux")
        self.assertEqual(orden.argumentos, ("quitar", "203.0.113.7"))

    def test_ip_de_windows(self):
        orden = construir("bloquear_ip", windows(ipAddress="198.51.100.4"), sistema="windows")
        self.assertEqual(orden.argumentos, ("aplicar", "198.51.100.4"))

    def test_ip_normalizada(self):
        orden = construir("bloquear_ip", alerta(srcip="2001:DB8::1"), sistema="linux")
        self.assertEqual(orden.argumentos[1], "2001:db8::1")

    def test_cuenta(self):
        orden = construir("deshabilitar_cuenta", windows(targetUserName="caja01"), sistema="windows")
        self.assertEqual(orden.argumentos, ("aplicar", "caja01"))
        reversion = construir_reversion("deshabilitar_cuenta", windows(targetUserName="caja01"), sistema="windows")
        self.assertEqual(reversion.argumentos, ("habilitar", "caja01"))

    def test_aislar_sin_argumentos(self):
        self.assertEqual(construir("aislar_equipo", alerta(), sistema="windows").argumentos, ("aplicar",))

    def test_terminar_proceso(self):
        orden = construir("terminar_proceso", windows(processId="4312"), sistema="windows")
        self.assertEqual(orden.argumentos, ("aplicar", "4312"))

    def test_servicio(self):
        orden = construir("detener_servicio", windows(serviceName="Spooler"), sistema="windows")
        self.assertEqual(orden.argumentos, ("aplicar", "Spooler"))


class Rechazos(unittest.TestCase):
    def assertInvalida(self, accion, datos):
        with self.assertRaises(OrdenInvalida):
            construir(accion, datos, sistema="windows")

    def test_inyeccion_en_la_ip(self):
        for valor in ("1.2.3.4; rm -rf /", "1.2.3.4 && whoami", "$(id)", "1.2.3.4\n5.6.7.8"):
            with self.subTest(valor=valor):
                self.assertInvalida("bloquear_ip", alerta(srcip=valor))

    def test_ips_que_nunca_se_bloquean(self):
        for valor in ("127.0.0.1", "0.0.0.0", "::1", "224.0.0.1", "169.254.1.1"):
            with self.subTest(valor=valor):
                self.assertInvalida("bloquear_ip", alerta(srcip=valor))

    def test_ip_del_propio_equipo(self):
        self.assertInvalida("bloquear_ip", alerta(srcip="10.0.2.15"))

    def test_inyeccion_en_la_cuenta(self):
        for valor in ("caja01;whoami", "caja 01", "../etc", "a" * 65, "caja01`id`"):
            with self.subTest(valor=valor):
                self.assertInvalida("deshabilitar_cuenta", windows(targetUserName=valor))

    def test_cuentas_protegidas(self):
        for valor in ("root", "Administrator", "SYSTEM", "EQUIPO01$"):
            with self.subTest(valor=valor):
                self.assertInvalida("deshabilitar_cuenta", windows(targetUserName=valor))

    def test_pid_del_sistema_o_no_numerico(self):
        for valor in ("4", "0", "12a", "-1", "1 2"):
            with self.subTest(valor=valor):
                self.assertInvalida("terminar_proceso", windows(processId=valor))

    def test_nunca_el_manager(self):
        self.assertInvalida("aislar_equipo", {"agent": {"id": "000"}})

    def test_agente_invalido(self):
        for agente in (None, "", "2", "abc", "002;id", True):
            with self.subTest(agente=agente):
                self.assertInvalida("aislar_equipo", {"agent": {"id": agente}})

    def test_sin_objetivo(self):
        self.assertInvalida("bloquear_ip", alerta())
        self.assertInvalida("deshabilitar_cuenta", alerta())

    def test_valor_que_no_es_texto(self):
        self.assertInvalida("bloquear_ip", alerta(srcip={"a": 1}))
        self.assertInvalida("bloquear_ip", alerta(srcip=["1.2.3.4"]))

    def test_acciones_pendientes(self):
        for accion in ("consulta", "cuarentena", "bloquear_destino", "revertir_tarea", "otra"):
            with self.subTest(accion=accion), self.assertRaises(AccionNoImplementada):
                construir(accion, alerta(srcip="203.0.113.7"), sistema="windows")

    def test_sin_reversion_desde_kronos(self):
        for accion in ("cerrar_sesion", "terminar_proceso"):
            with self.subTest(accion=accion), self.assertRaises(AccionNoImplementada):
                construir_reversion(accion, windows(targetUserName="caja01", processId="99"), sistema="windows")


class OrdenConSistema(unittest.TestCase):
    def test_la_orden_lleva_el_sistema(self):
        orden = construir("bloquear_ip", alerta(srcip="203.0.113.7"), sistema="linux")
        self.assertEqual(orden.sistema, "linux")
        self.assertEqual(orden.como_detalle()["sistema"], "linux")
        reversion = construir_reversion(
            "bloquear_ip", alerta(srcip="203.0.113.7"), sistema="windows"
        )
        self.assertEqual(reversion.sistema, "windows")

    def test_sistema_desconocido(self):
        with self.assertRaises(ValueError):
            Orden("002", "kronos-bloquear-ip", ("aplicar", "203.0.113.7"), "macos")

    def test_el_sistema_es_obligatorio(self):
        with self.assertRaises(TypeError):
            construir("bloquear_ip", alerta(srcip="203.0.113.7"))  # type: ignore[call-arg]


def con(**campos):
    return {"agent": {"id": "002"}, **campos}


MAPA = {"001": "linux", "002": "windows"}


class SistemaOperativo(unittest.TestCase):
    def test_por_mapa(self):
        self.assertEqual(sistema_operativo({"agent": {"id": "001"}}, MAPA), "linux")
        self.assertEqual(sistema_operativo({"agent": {"id": "002"}}, MAPA), "windows")

    def test_por_alerta_de_windows(self):
        casos = (
            con(data={"win": {"system": {"eventID": "4625"}}}),
            con(location="EventChannel"),
            con(decoder={"name": "windows_eventchannel"}),
            con(syscheck={"path": "C:\\Windows\\System32\\drivers\\etc\\hosts"}),
        )
        for alerta_ in casos:
            with self.subTest(alerta=alerta_):
                self.assertEqual(sistema_operativo(alerta_, {}), "windows")

    def test_por_alerta_de_linux(self):
        casos = (
            con(location="/var/log/auth.log"),
            con(location="journald"),
            con(syscheck={"path": "/etc/passwd"}),
        )
        for alerta_ in casos:
            with self.subTest(alerta=alerta_):
                self.assertEqual(sistema_operativo(alerta_, {}), "linux")

    def test_sin_datos(self):
        self.assertIsNone(sistema_operativo(con(data={"srcip": "203.0.113.7"}), {}))
        self.assertIsNone(sistema_operativo({}, {}))
        self.assertIsNone(sistema_operativo(con(location="C:/raro"), {}))

    def test_mapa_y_alerta_se_contradicen(self):
        alerta_ = {"agent": {"id": "001"}, "data": {"win": {}}}
        self.assertIsNone(sistema_operativo(alerta_, MAPA))

    def test_alerta_con_senales_de_los_dos(self):
        self.assertIsNone(
            sistema_operativo(con(location="EventChannel", syscheck={"path": "/etc"}), {})
        )

    def test_mapa_y_alerta_coinciden(self):
        alerta_ = {"agent": {"id": "002"}, "location": "EventChannel"}
        self.assertEqual(sistema_operativo(alerta_, MAPA), "windows")

    def test_agente_fuera_del_mapa_se_deduce(self):
        alerta_ = {"agent": {"id": "009"}, "location": "journald"}
        self.assertEqual(sistema_operativo(alerta_, MAPA), "linux")


class MapaDeAgentes(unittest.TestCase):
    def test_lee_el_mapa(self):
        self.assertEqual(
            leer_mapa_agentes("001:linux, 002:windows"),
            {"001": "linux", "002": "windows"},
        )

    def test_vacio_es_valido(self):
        self.assertEqual(leer_mapa_agentes(""), {})
        self.assertEqual(leer_mapa_agentes(" , "), {})

    def test_formatos_invalidos(self):
        for texto in (
            "001",
            "001:",
            "1:linux",
            "001:Linux",
            "001:macos",
            "abc:linux",
            "000:linux",
            "001:linux,001:windows",
            "001=linux",
        ):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                leer_mapa_agentes(texto)


if __name__ == "__main__":
    unittest.main()
