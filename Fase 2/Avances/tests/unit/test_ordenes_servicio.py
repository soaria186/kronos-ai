"""Servicio a detener (F6) cuando la alerta no trae serviceName (cobertura de los 25 playbooks)."""

import unittest

from ejecucion.ordenes import (
    ArgumentoFaltante,
    OrdenInvalida,
    construir,
    falta_argumento,
)

# «Spooler» en UTF-16LE, en hexadecimal, terminado en cero: así lo trae el evento 7031.
SPOOLER = "530070006F006F006C00650072000000"


def win_7031(**eventdata):
    datos = {"param1": "Cola de impresión", "param2": "1", **eventdata}
    return {
        "agent": {"id": "002", "ip": "10.0.2.15"},
        "location": "EventChannel",
        "data": {"win": {"system": {"eventID": "7031"}, "eventdata": datos}},
    }


def web(ubicacion):
    return {
        "agent": {"id": "001", "ip": "10.0.2.16"},
        "location": ubicacion,
        "data": {"srcip": "198.51.100.20", "url": "/../../etc/passwd"},
    }


class Windows7031(unittest.TestCase):
    def test_nombre_real_desde_binary(self):
        orden = construir("detener_servicio", win_7031(binary=SPOOLER), sistema="windows")
        self.assertEqual(orden.argumentos, ("aplicar", "Spooler"))

    def test_service_name_manda(self):
        alerta = win_7031(binary=SPOOLER, serviceName="Otro")
        self.assertEqual(construir("detener_servicio", alerta, sistema="windows").argumentos[1], "Otro")

    def test_binary_invalido_se_rechaza(self):
        for binario in ("zz", "410", "41004200200043000000"):  # no hex, largo impar, con espacio
            with self.subTest(binario=binario), self.assertRaises(OrdenInvalida):
                construir("detener_servicio", win_7031(binary=binario), sistema="windows")

    def test_sin_binary_falta_el_dato(self):
        with self.assertRaises(ArgumentoFaltante):
            construir("detener_servicio", win_7031(), sistema="windows")
        self.assertTrue(falta_argumento("detener_servicio", win_7031()))
        self.assertFalse(falta_argumento("detener_servicio", win_7031(binary=SPOOLER)))


class LinuxWeb(unittest.TestCase):
    def test_servicio_desde_el_registro_web(self):
        for carpeta in ("nginx", "apache2", "httpd", "lighttpd"):
            alerta = web(f"/var/log/{carpeta}/access.log")
            with self.subTest(carpeta=carpeta):
                self.assertEqual(
                    construir("detener_servicio", alerta, sistema="linux").argumentos,
                    ("aplicar", carpeta),
                )

    def test_otros_registros_no_dicen_servicio(self):
        for ubicacion in ("/var/log/auth.log", "/var/log/mysql/error.log", "/var/log/nginx/x/a.log", "journald"):
            with self.subTest(ubicacion=ubicacion), self.assertRaises(ArgumentoFaltante):
                construir("detener_servicio", web(ubicacion), sistema="linux")


if __name__ == "__main__":
    unittest.main()
