"""Pruebas del tope de tamaño de la alerta guardada (persistencia/alertas.py)."""

import copy
import unittest

from persistencia.alertas import (
    CLAVE_RECORTE,
    LARGO_TEXTO,
    MARCA_RECORTE,
    TOPE_BYTES,
    preparar,
    tamano,
)


def _alerta(**extra) -> dict:
    alerta = {
        "id": "1760411662.1",
        "timestamp": "2026-10-21T17:00:00.000+0000",
        "rule": {"id": "100101", "level": 10, "description": "Kronos F1: fuerza bruta",
                 "groups": ["sshd", "kronos_f1"]},
        "agent": {"id": "001", "name": "EP-SRV-01", "ip": "192.0.2.10"},
        "data": {"srcip": "203.0.113.50", "dstuser": "admin"},
        "full_log": "sshd: Failed password",
    }
    alerta.update(extra)
    return alerta


class TestTope(unittest.TestCase):
    def test_alerta_normal_queda_igual(self):
        alerta = _alerta()
        resultado = preparar(alerta)
        self.assertIs(resultado.alerta, alerta)
        self.assertFalse(resultado.recortada)
        self.assertEqual(resultado.bytes_original, tamano(alerta))

    def test_texto_enorme_se_recorta(self):
        alerta = _alerta(full_log="ñ" * 200_000)
        original = copy.deepcopy(alerta)
        resultado = preparar(alerta)
        self.assertTrue(resultado.recortada)
        self.assertLessEqual(tamano(resultado.alerta), TOPE_BYTES)
        self.assertEqual(
            resultado.alerta["full_log"], "ñ" * LARGO_TEXTO + MARCA_RECORTE
        )
        self.assertEqual(resultado.alerta["data"], alerta["data"])
        self.assertIn(CLAVE_RECORTE, resultado.alerta)
        self.assertEqual(alerta, original)  # la original no cambia

    def test_muchas_claves_dejan_solo_lo_esencial(self):
        basura = {f"campo{i}": "v" * 100 for i in range(2_000)}
        alerta = _alerta(data={"srcip": "203.0.113.50", "win": {"eventdata": {
            "targetUserName": "operador02", "processId": "4242", **basura}}})
        resultado = preparar(alerta)
        self.assertTrue(resultado.recortada)
        self.assertLessEqual(tamano(resultado.alerta), TOPE_BYTES)
        self.assertEqual(resultado.alerta["agent"], alerta["agent"])
        self.assertEqual(resultado.alerta["data"]["srcip"], "203.0.113.50")
        self.assertEqual(
            resultado.alerta["data"]["win"]["eventdata"],
            {"targetUserName": "operador02", "processId": "4242"},
        )
        self.assertNotIn("full_log", resultado.alerta)

    def test_lista_enorme_en_campo_esencial(self):
        alerta = _alerta(rule={"id": "1", "level": 3, "groups": ["g" * 500] * 10_000},
                         otro=["x" * 1000] * 100)
        resultado = preparar(alerta)
        self.assertLessEqual(tamano(resultado.alerta), TOPE_BYTES)
        self.assertLessEqual(len(resultado.alerta["rule"]["groups"]), 20)

    def test_tamano_usa_el_formato_de_jsonb(self):
        self.assertEqual(tamano({"a": 1, "b": [1, 2]}), len('{"a": 1, "b": [1, 2]}'))
        self.assertEqual(tamano({"a": "ñ"}), len('{"a": "ñ"}'.encode()))


if __name__ == "__main__":
    unittest.main()
