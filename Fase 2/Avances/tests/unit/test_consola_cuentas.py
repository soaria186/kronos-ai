import base64
import json
import tempfile
import unittest
from pathlib import Path

from consola.sesiones import MAX_FALLOS, CodigosUsados, Intentos, Sesiones
from consola.usuarios import (
    agregar,
    cargar,
    codigo_totp,
    hash_clave,
    uri_totp,
    verificar_clave,
    verificar_totp,
)

RFC = base64.b32encode(b"12345678901234567890").decode()


class Totp(unittest.TestCase):
    def test_vectores_rfc_6238(self):
        # RFC 6238, apéndice B (SHA-1), últimos 6 dígitos.
        for t, esperado in (
            (59, "287082"),
            (1111111109, "081804"),
            (2000000000, "279037"),
        ):
            with self.subTest(t=t):
                self.assertEqual(codigo_totp(RFC, t // 30), esperado)

    def test_ventana_de_un_paso(self):
        ahora = 1_000_000_000
        anterior = codigo_totp(RFC, ahora // 30 - 1)
        viejo = codigo_totp(RFC, ahora // 30 - 3)
        self.assertIsNotNone(verificar_totp(RFC, anterior, ahora))
        self.assertIsNone(verificar_totp(RFC, viejo, ahora))

    def test_formato(self):
        for malo in ("", "12345", "1234567", "abcdef", None):
            with self.subTest(malo=malo):
                self.assertIsNone(verificar_totp(RFC, malo, 59))

    def test_uri(self):
        self.assertTrue(
            uri_totp("nicolas", RFC).startswith("otpauth://totp/Kronos%20AI%3Anicolas?")
        )


class Claves(unittest.TestCase):
    def test_hash_y_verificacion(self):
        h = hash_clave("una-clave-larga")
        self.assertTrue(verificar_clave("una-clave-larga", h))
        self.assertFalse(verificar_clave("otra-clave-larga", h))
        self.assertNotEqual(h, hash_clave("una-clave-larga"))  # sal distinta

    def test_hash_corrupto(self):
        self.assertFalse(verificar_clave("x", "basura"))
        self.assertFalse(verificar_clave("x", "md5$1$2$3$a$b"))

    def test_archivo_de_cuentas(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "cuentas.json"
            secreto = agregar(ruta, "nicolas", "una-clave-larga")
            cuentas = cargar(ruta)
            self.assertEqual(cuentas["nicolas"].totp, secreto)
            self.assertNotIn("una-clave-larga", ruta.read_text())
            with self.assertRaises(ValueError):
                agregar(ruta, "Nicolas Z", "una-clave-larga")
            with self.assertRaises(ValueError):
                agregar(ruta, "patricio", "corta")
            ruta.write_text(json.dumps({"usuarios": {}}))
            with self.assertRaises(ValueError):
                cargar(ruta)


class SesionesYBloqueos(unittest.TestCase):
    def setUp(self):
        self.ahora = 1000.0

    def reloj(self):
        return self.ahora

    def test_sesion_vence(self):
        s = Sesiones(duracion=60, reloj=self.reloj)
        token = s.crear("nicolas")
        self.assertEqual(s.obtener(token).usuario, "nicolas")
        self.ahora += 61
        self.assertIsNone(s.obtener(token))
        self.assertIsNone(s.obtener(None))

    def test_cerrar(self):
        s = Sesiones(reloj=self.reloj)
        token = s.crear("nicolas")
        s.cerrar(token)
        self.assertIsNone(s.obtener(token))

    def test_bloqueo_y_desbloqueo(self):
        i = Intentos(reloj=self.reloj)
        for _ in range(MAX_FALLOS):
            i.fallo("u:nicolas")
        self.assertTrue(i.bloqueado("u:nicolas"))
        self.ahora += 15 * 60 + 1
        self.assertFalse(i.bloqueado("u:nicolas"))

    def test_codigo_no_se_reutiliza(self):
        c = CodigosUsados()
        self.assertTrue(c.aceptar("nicolas", 10))
        self.assertFalse(c.aceptar("nicolas", 10))
        self.assertFalse(c.aceptar("nicolas", 9))
        self.assertTrue(c.aceptar("patricio", 10))


if __name__ == "__main__":
    unittest.main()
