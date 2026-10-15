# Consola (SOAR-CONSOLE)

Panel web del equipo (RF-14, RF-18, RF-19, CU-02, CU-04). FastAPI con HTML simple:
sin JavaScript, la política de contenido prohíbe todo script.

| Pantalla | Qué permite |
| :--- | :--- |
| Inicio de sesión | Usuario, contraseña y código TOTP de 6 dígitos |
| Panel, por inquilino | Aprobar o rechazar (con motivo) los niveles 3; ver las medidas de nivel 2 vigentes con su plazo de revisión y revertirlas; ver fallas y revisión manual de 7 días; cerrar el cortacircuito con motivo |

| Módulo | Qué hace |
| :--- | :--- |
| `usuarios.py` | Cuentas: contraseña con scrypt y TOTP (RFC 6238). Alta: `python -m consola.usuarios agregar <nombre> --archivo <ruta>` |
| `sesiones.py` | Sesiones de 8 horas en memoria, bloqueo tras 5 fallos en 15 minutos, códigos TOTP de un solo uso |
| `datos.py` | Lee las vistas `frontend` y escribe sólo con las funciones `consola` de la base, como `kronos_console` |
| `app.py` | Rutas, cookies y cabeceras de seguridad |
| `__main__.py` | Servicio con TLS: `python -m consola` |

## Decisiones (preguntas abiertas #28 y #38)

- **Acceso:** sólo por NetBird (el puerto se publica en su IP), con TLS, contraseña y TOTP.
- **Escritura:** rol `kronos_console`, que no toca tablas: sólo las cuatro funciones del
  esquema `consola` (`infra/docker/initdb/04_consola.sql`). Telegram usa las mismas.
- Quien actúa queda en la bitácora como `consola:<usuario>`.

## Seguridad

- Cookie `HttpOnly`, `Secure`, `SameSite=Strict`; token CSRF en cada formulario.
- El error de inicio de sesión no dice qué dato falló, y una cuenta inexistente tarda
  lo mismo que una contraseña equivocada.
- CSP sin scripts, `X-Frame-Options: DENY`, `no-store`, HSTS y sin cabecera `server`.
- Plantillas con escape automático: el título de una alerta no puede inyectar HTML.
- Pendiente: la vista del encargado del cliente (sólo lectura de su inquilino).

## Pruebas

`tests/unit/test_consola_cuentas.py` (sin dependencias) y `tests/unit/test_consola_app.py`
(necesita `consola/requirements.txt` y `httpx`; sin ellos se omite).
`tests/integracion/test_consola_rol.py` prueba los permisos del rol en la base.
