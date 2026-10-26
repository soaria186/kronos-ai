import unittest

from ejecucion.ordenes import (
    AccionNoImplementada,
    OrdenInvalida,
    construir,
    construir_reversion,
)


def alerta(**data):
    return {"agent": {"id": "002", "ip": "10.0.2.15"}, "data": data}


def windows(**eventdata):
    return {"agent": {"id": "003"}, "data": {"win": {"eventdata": eventdata}}}


class Construir(unittest.TestCase):
    def test_bloquear_ip(self):
        orden = construir("bloquear_ip", alerta(srcip="203.0.113.7"))
        self.assertEqual(orden.agente, "002")
        self.assertEqual(orden.comando, "kronos-bloquear-ip")
        self.assertEqual(orden.argumentos, ("aplicar", "203.0.113.7"))

    def test_reversion_usa_el_mismo_objetivo(self):
        orden = construir_reversion("bloquear_ip", alerta(srcip="203.0.113.7"))
        self.assertEqual(orden.argumentos, ("quitar", "203.0.113.7"))

    def test_ip_de_windows(self):
        orden = construir("bloquear_ip", windows(ipAddress="198.51.100.4"))
        self.assertEqual(orden.argumentos, ("aplicar", "198.51.100.4"))

    def test_ip_normalizada(self):
        orden = construir("bloquear_ip", alerta(srcip="2001:DB8::1"))
        self.assertEqual(orden.argumentos[1], "2001:db8::1")

    def test_cuenta(self):
        orden = construir("deshabilitar_cuenta", windows(targetUserName="caja01"))
        self.assertEqual(orden.argumentos, ("aplicar", "caja01"))
        reversion = construir_reversion("deshabilitar_cuenta", windows(targetUserName="caja01"))
        self.assertEqual(reversion.argumentos, ("habilitar", "caja01"))

    def test_aislar_sin_argumentos(self):
        self.assertEqual(construir("aislar_equipo", alerta()).argumentos, ("aplicar",))

    def test_terminar_proceso(self):
        orden = construir("terminar_proceso", windows(processId="4312"))
        self.assertEqual(orden.argumentos, ("aplicar", "4312"))

    def test_servicio(self):
        orden = construir("detener_servicio", windows(serviceName="Spooler"))
        self.assertEqual(orden.argumentos, ("aplicar", "Spooler"))


class Rechazos(unittest.TestCase):
    def assertInvalida(self, accion, datos):
        with self.assertRaises(OrdenInvalida):
            construir(accion, datos)

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
                construir(accion, alerta(srcip="203.0.113.7"))

    def test_sin_reversion_desde_kronos(self):
        for accion in ("cerrar_sesion", "terminar_proceso"):
            with self.subTest(accion=accion), self.assertRaises(AccionNoImplementada):
                construir_reversion(accion, windows(targetUserName="caja01", processId="99"))


if __name__ == "__main__":
    unittest.main()
