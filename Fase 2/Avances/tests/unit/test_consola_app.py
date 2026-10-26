"""Pruebas de la aplicación web de SOAR-CONSOLE (necesitan consola/requirements.txt y httpx)."""

import importlib.util
import re
import unittest
from datetime import UTC, datetime, timedelta

HAY_FASTAPI = all(
    importlib.util.find_spec(m) for m in ("fastapi", "httpx", "multipart")
)

if HAY_FASTAPI:
    from fastapi.testclient import TestClient

    from consola.app import COOKIE, crear_app
    from consola.datos import AccionRechazada
    from consola.usuarios import Cuenta, codigo_totp, hash_clave

SECRETO = "JBSWY3DPEHPK3PXP"
AHORA = datetime(2026, 10, 15, 12, 0, tzinfo=UTC).timestamp()


class DatosFalsos:
    def __init__(self):
        self.acciones = []

    def panel(self, tenant_id):
        hora = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
        return {
            "pendientes": [
                {
                    "id": 7,
                    "titulo": "<script>alert(1)</script>",
                    "playbook": "PB-F3-03",
                    "severidad": 12,
                    "creado_en": hora,
                    "vence_en": hora + timedelta(days=2),
                }
            ],
            "activas": [
                {
                    "id": 8,
                    "titulo": "Fuerza bruta",
                    "playbook": "PB-F1-03",
                    "ejecutada_en": hora,
                    "revisar_antes_de": hora - timedelta(days=1),
                    "reversion_pedida": False,
                }
            ],
            "fallidas": [],
            "triage": [],
            "cortacircuito": [
                {
                    "ambito": "inquilino",
                    "abierto": True,
                    "motivo": "30 alertas",
                    "creado_en": hora,
                }
            ],
        }

    def aprobar(self, tenant_id, ticket_id, persona):
        self.acciones.append(("aprobar", tenant_id, ticket_id, persona))

    def denegar(self, tenant_id, ticket_id, persona, motivo):
        if not motivo.strip():
            raise AccionRechazada("falta el motivo del rechazo")
        self.acciones.append(("denegar", tenant_id, ticket_id, persona, motivo))

    def revertir(self, tenant_id, ticket_id, persona):
        self.acciones.append(("revertir", tenant_id, ticket_id, persona))

    def cerrar_cortacircuito(self, tenant_id, persona, motivo):
        self.acciones.append(("cerrar", tenant_id, persona, motivo))


@unittest.skipUnless(HAY_FASTAPI, "faltan fastapi, httpx o python-multipart")
class Consola(unittest.TestCase):
    def setUp(self):
        self.ahora = AHORA
        self.datos = DatosFalsos()
        cuentas = {"nicolas": Cuenta("nicolas", hash_clave("una-clave-larga"), SECRETO)}
        app = crear_app(
            self.datos, cuentas, [1, 2], reloj=lambda: self.ahora, cookie_segura=False
        )
        self.cliente = TestClient(app, follow_redirects=False)

    def codigo(self, desfase=0):
        return codigo_totp(SECRETO, int(self.ahora // 30) + desfase)

    def entrar(self, clave="una-clave-larga", codigo=None):
        return self.cliente.post(
            "/login",
            data={
                "usuario": "nicolas",
                "clave": clave,
                "codigo": codigo or self.codigo(),
            },
        )

    def csrf(self):
        html = self.cliente.get("/").text
        return re.search(r'name="csrf" value="([^"]+)"', html).group(1)

    # ----------------------------------------------------------- acceso

    def test_sin_sesion_va_al_login(self):
        r = self.cliente.get("/")
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/login"))

    def test_entra_con_clave_y_codigo(self):
        r = self.entrar()
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/"))
        cookie = r.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)
        self.assertEqual(self.cliente.get("/").status_code, 200)

    def test_clave_o_codigo_incorrectos(self):
        self.assertEqual(
            self.entrar(clave="otra").headers["location"], "/login?error=1"
        )
        self.assertEqual(
            self.entrar(codigo="000000").headers["location"], "/login?error=1"
        )
        r = self.cliente.post(
            "/login", data={"usuario": "nadie", "clave": "x", "codigo": self.codigo()}
        )
        self.assertEqual(r.headers["location"], "/login?error=1")
        self.assertNotIn(COOKIE, self.cliente.cookies)

    def test_codigo_no_se_reutiliza(self):
        codigo = self.codigo()
        self.entrar(codigo=codigo)
        self.cliente.cookies.clear()
        self.assertEqual(
            self.entrar(codigo=codigo).headers["location"], "/login?error=1"
        )

    def test_bloqueo_tras_cinco_fallos(self):
        for _ in range(5):
            self.entrar(clave="otra")
        self.assertEqual(self.entrar().headers["location"], "/login?error=b")
        self.ahora += 15 * 60 + 31
        self.assertEqual(self.entrar().headers["location"], "/")

    def test_salir(self):
        self.entrar()
        self.cliente.post("/salir", data={"csrf": self.csrf()})
        self.assertEqual(self.cliente.get("/").status_code, 303)

    def test_cabeceras_de_seguridad(self):
        r = self.cliente.get("/login")
        self.assertIn("script-src 'none'", r.headers["content-security-policy"])
        self.assertEqual(r.headers["x-frame-options"], "DENY")
        self.assertEqual(r.headers["cache-control"], "no-store")

    # ----------------------------------------------------------- panel

    def test_panel_escapa_el_titulo(self):
        self.entrar()
        html = self.cliente.get("/").text
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Cortacircuito abierto", html)
        self.assertIn('class="vencida"', html)

    def test_aprobar_con_su_nombre(self):
        self.entrar()
        r = self.cliente.post(
            "/tickets/7/aprobar", data={"inquilino": 1, "csrf": self.csrf()}
        )
        self.assertEqual(r.headers["location"], "/?inquilino=1&aviso=aprobado")
        self.assertEqual(self.datos.acciones, [("aprobar", 1, 7, "consola:nicolas")])

    def test_sin_csrf_no_actua(self):
        self.entrar()
        r = self.cliente.post(
            "/tickets/7/aprobar", data={"inquilino": 1, "csrf": "falso"}
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.datos.acciones, [])

    def test_inquilino_no_configurado(self):
        self.entrar()
        r = self.cliente.post(
            "/tickets/7/aprobar", data={"inquilino": 99, "csrf": self.csrf()}
        )
        self.assertEqual(r.status_code, 403)

    def test_rechazo_sin_motivo(self):
        self.entrar()
        r = self.cliente.post(
            "/tickets/7/rechazar",
            data={"inquilino": 1, "csrf": self.csrf(), "motivo": " "},
        )
        self.assertIn("error=falta", r.headers["location"])
        self.assertEqual(self.datos.acciones, [])

    def test_revertir_y_cerrar_cortacircuito(self):
        self.entrar()
        csrf = self.csrf()
        self.cliente.post("/tickets/8/revertir", data={"inquilino": 2, "csrf": csrf})
        self.cliente.post(
            "/cortacircuito/cerrar",
            data={"inquilino": 2, "csrf": csrf, "motivo": "revisado"},
        )
        self.assertEqual(
            self.datos.acciones,
            [
                ("revertir", 2, 8, "consola:nicolas"),
                ("cerrar", 2, "consola:nicolas", "revisado"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
