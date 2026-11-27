"""Pruebas de la consulta de nivel 0 por syscollector (D-72) y del GET de la API."""

from __future__ import annotations

import io
import json
import unittest

from ejecucion.actuador import ErrorActuador
from ejecucion.actuador_wazuh import ActuadorWazuh
from ejecucion.consulta import ErrorConsulta
from ejecucion.consulta_wazuh import MAX_PROCESOS, ConsultaWazuh


def respuesta(items, total=None):
    return {
        "data": {
            "affected_items": items,
            "total_affected_items": len(items) if total is None else total,
        },
        "error": 0,
    }


INVENTARIO = {
    "os": respuesta([{"os": {"name": "Ubuntu", "version": "24.04.5 LTS"}}]),
    "processes": respuesta(
        [{"name": "sshd"}, {"name": "wazuh-agentd"}, {"name": "sshd"}, {"name": "bash"}], total=118
    ),
    "ports": respuesta(
        [
            {"protocol": "tcp", "local": {"port": 22}, "state": "listening", "process": "sshd"},
            {"protocol": "tcp", "local": {"port": 22}, "state": "listening", "process": "sshd"},
            {"protocol": "tcp", "local": {"port": 40000}, "state": "established"},
            {"protocol": "udp", "local": {"port": 68}, "process": "dhclient"},
        ]
    ),
    "netaddr": respuesta(
        [{"iface": "enp0s3", "address": "10.0.2.15"}, {"iface": "enp0s3", "address": ""}]
    ),
}


class LectorFalso:
    def __init__(self, inventario=None, fallan=()):
        self.inventario = INVENTARIO if inventario is None else inventario
        self.fallan = set(fallan)
        self.rutas = []

    def leer(self, ruta):
        self.rutas.append(ruta)
        recurso = ruta.split("/")[3].split("?")[0]
        if recurso in self.fallan:
            raise ErrorActuador("la API respondió 403: Permission denied")
        return self.inventario[recurso]


class Consulta(unittest.TestCase):
    def test_resumen_completo(self):
        lector = LectorFalso()
        resumen = ConsultaWazuh(lector).consultar("001")
        self.assertEqual(resumen["sistema"], "Ubuntu 24.04.5 LTS")
        self.assertEqual(resumen["procesos"], {"total": 118, "muestra": ["bash", "sshd", "wazuh-agentd"]})
        self.assertEqual(resumen["puertos"], ["tcp/22 (sshd)", "udp/68 (dhclient)"])
        self.assertEqual(resumen["red"], ["enp0s3 10.0.2.15"])
        self.assertEqual(resumen["fuente"], "syscollector")
        self.assertTrue(all(r.startswith("/syscollector/001/") for r in lector.rutas))

    def test_solo_lee_syscollector_del_agente_pedido(self):
        lector = LectorFalso()
        ConsultaWazuh(lector).consultar("002")
        recursos = sorted(r.split("/")[3].split("?")[0] for r in lector.rutas)
        self.assertEqual(recursos, ["netaddr", "os", "ports", "processes"])
        self.assertTrue(all("/002/" in r for r in lector.rutas))

    def test_muestra_de_procesos_acotada(self):
        muchos = respuesta([{"name": f"p{i:03d}"} for i in range(50)])
        inventario = dict(INVENTARIO, processes=muchos)
        resumen = ConsultaWazuh(LectorFalso(inventario)).consultar("001")
        self.assertEqual(len(resumen["procesos"]["muestra"]), MAX_PROCESOS)
        self.assertEqual(resumen["procesos"]["total"], 50)

    def test_una_parte_falla_y_las_demas_siguen(self):
        resumen = ConsultaWazuh(LectorFalso(fallan={"ports"})).consultar("001")
        self.assertEqual(resumen["puertos"], "no disponible")
        self.assertEqual(resumen["sistema"], "Ubuntu 24.04.5 LTS")

    def test_si_fallan_todas_es_error_de_consulta(self):
        lector = LectorFalso(fallan={"os", "processes", "ports", "netaddr"})
        with self.assertRaises(ErrorConsulta) as ctx:
            ConsultaWazuh(lector).consultar("001")
        self.assertIn("syscollector no respondió", str(ctx.exception))

    def test_agente_sin_datos(self):
        vacio = {k: respuesta([]) for k in INVENTARIO}
        resumen = ConsultaWazuh(LectorFalso(vacio)).consultar("001")
        self.assertEqual(resumen["sistema"], "sin datos")
        self.assertEqual(resumen["procesos"], {"total": 0, "muestra": []})
        self.assertEqual(resumen["puertos"], [])

    def test_respuesta_rara_no_rompe(self):
        raro = {k: {"data": {"affected_items": "no es lista"}} for k in INVENTARIO}
        resumen = ConsultaWazuh(LectorFalso(raro)).consultar("001")
        self.assertEqual(resumen["red"], [])

    def test_agentes_no_validos(self):
        for agente in ("000", "1", "abc", "001/../x", "", None):
            with self.subTest(agente=agente):
                lector = LectorFalso()
                with self.assertRaises(ErrorConsulta):
                    ConsultaWazuh(lector).consultar(agente)
                self.assertEqual(lector.rutas, [])


class RespuestaFalsa:
    """Lo único que usa ActuadorWazuh de la respuesta: el estado y read()."""

    def __init__(self, estado, cuerpo):
        self.status = estado
        self._cuerpo = io.BytesIO(cuerpo)

    def read(self, n=-1):
        return self._cuerpo.read(n)


class ConexionFalsa:
    """Imita http.client.HTTPConnection para probar ActuadorWazuh.leer sin red."""

    def __init__(self, registro, respuestas):
        self.registro = registro
        self.respuestas = respuestas

    def request(self, metodo, ruta, body=None, headers=None):
        self.registro.append((metodo, ruta, (headers or {}).get("Authorization", "")))

    def getresponse(self):
        estado, datos = self.respuestas.pop(0)
        return RespuestaFalsa(estado, json.dumps(datos).encode())

    def close(self):
        pass


class Leer(unittest.TestCase):
    def actuador(self, respuestas):
        registro = []
        a = ActuadorWazuh(
            "https://wazuh:55000", "kronos-execute", "clave",
            conectar=lambda: ConexionFalsa(registro, respuestas),
        )
        return a, registro

    def test_get_con_token(self):
        a, registro = self.actuador([(200, {"data": {"token": "tok"}}), (200, respuesta([]))])
        datos = a.leer("/syscollector/001/os")
        self.assertEqual(datos["error"], 0)
        self.assertEqual(registro[0][0:2], ("POST", "/security/user/authenticate"))
        self.assertEqual(registro[1], ("GET", "/syscollector/001/os", "Bearer tok"))

    def test_403_es_error(self):
        a, _ = self.actuador([(200, {"data": {"token": "tok"}}), (403, {"title": "Permission denied"})])
        with self.assertRaises(ErrorActuador):
            a.leer("/syscollector/001/os")

    def test_401_renueva_el_token_una_vez(self):
        a, registro = self.actuador([
            (200, {"data": {"token": "t1"}}),
            (401, {"title": "Unauthorized"}),
            (200, {"data": {"token": "t2"}}),
            (200, respuesta([])),
        ])
        a.leer("/syscollector/001/os")
        self.assertEqual(registro[-1][2], "Bearer t2")

    def test_ruta_no_valida(self):
        a, registro = self.actuador([])
        for ruta in ("syscollector/001/os", "/x y", "/x\r\nHost: otro"):
            with self.subTest(ruta=ruta), self.assertRaises(ErrorActuador):
                a.leer(ruta)
        self.assertEqual(registro, [])


if __name__ == "__main__":
    unittest.main()
