# 07 · Base SOAR-AUDIT y servicios

| Campo | Valor |
| :--- | :--- |
| Parte | 07 de 15 |
| Responsable | Rodrigo Riveros (revisa: Patricio González) |
| Versión | 0.9, 26-10-2026 |
| Estado | Borrador para revisión: reúne `infra/docker/docker-compose.yml`, `infra/docker/servicios/README.md` y el despliegue desde un clon de git (D-55). Rodrigo lo sigue al pasar el servidor al clon y lo corrige |
| Requisitos | Partes 01 a 04 y 06 |

Esta parte levanta SOAR-AUDIT (PostgreSQL 17.11) y los cuatro servicios de Kronos: SOAR-VALIDATE, SOAR-EXECUTE,
SOAR-NOTIFY y SOAR-CONSOLE. Todos salen de una sola imagen y corren con un usuario sin privilegios (uid 10001),
con el sistema de archivos de sólo lectura y sin capacidades.

| Servicio | Redes | Sale a |
| :--- | :--- | :--- |
| `db` (PostgreSQL) | `interna` | Nada; no publica puertos |
| `validate` | `interna` e `inferencia` | Sólo a Ollama. Lee `alerts.json` en sólo lectura |
| `execute` | `interna` y la red de Wazuh | Sólo a la API de Wazuh (`wazuh.manager:55000`) |
| `notify` | `interna` y `salida` | `api.telegram.org` |
| `consola` | `interna` y `consola` | Nada: recibe en el 443 de la IP de NetBird |

---

## 1. El servidor corre un clon de git (D-55)

Se despliega sólo lo que está en el repositorio, en una **etiqueta de versión**. No se copian archivos desde
Windows: el 21-10-2026 eso rompió los permisos de una carpeta dentro de la imagen.

Mientras el repositorio sea privado, el servidor clona con una **llave de despliegue de sólo lectura** (GitHub →
*Settings* → *Deploy keys*, desde la cuenta dueña):

```
[servidor] sudo ssh-keygen -t ed25519 -N '' -C kronos-despliegue -f /root/.ssh/kronos_despliegue
[servidor] sudo cat /root/.ssh/kronos_despliegue.pub
```

Agregar esa llave pública como *Deploy key* **sin** permiso de escritura. Después:

```
[servidor] sudo GIT_SSH_COMMAND='ssh -i /root/.ssh/kronos_despliegue' git clone git@github.com:soarai2026/kronos-ai.git /opt/kronos/audit
[servidor] sudo git -C /opt/kronos/audit config core.sshCommand 'ssh -i /root/.ssh/kronos_despliegue'
[servidor] sudo git -C /opt/kronos/audit checkout v1.0.0
[servidor] sudo git -C /opt/kronos/audit describe --tags
```

**Debe mostrar:** `v1.0.0`. Si el repositorio es público, basta con `git clone https://github.com/soarai2026/kronos-ai.git`.

Lo que vive **sólo en el servidor**, fuera de git (`.gitignore`): `infra/docker/.env`, `infra/docker/secrets/`,
`infra/docker/initdb/03_roles.sql` e `infra/docker/initdb/05_clave_consola.sql`.

## 2. La base

```
[servidor] cd /opt/kronos/audit/infra/docker
[servidor] sudo bash generar_secretos.sh
[servidor] sudo docker compose -f docker-compose.yml up -d db
[servidor] sudo docker compose -f docker-compose.yml ps db
```

**Debe mostrar:** los secretos creados (sin mostrar su contenido) y `db` en estado `healthy`. Los scripts de
`initdb/` corren sólo la primera vez, con el volumen vacío: crean el esquema, los roles y las funciones de la
consola y de la retención.

Pruebas del esquema (a: dos inquilinos, b: concurrencia, c: inmutabilidad, d: manipulación detectada):

```
[servidor] sudo bash /opt/kronos/audit/tests/sql/ejecutar.sh
```

### Base que ya existía: migraciones

Una base creada con una versión anterior se pone al día con las migraciones, en orden de fecha. Todas son
idempotentes; antes, un respaldo (parte 12):

```
[servidor] sudo systemctl start kronos-respaldo-postgres.service
[servidor] for m in /opt/kronos/audit/infra/docker/migraciones/*.sql; do echo "== $m"; sudo docker exec -i kronos-db-1 psql -U kronos_admin -d kronos -v ON_ERROR_STOP=1 < "$m"; done
```

## 3. Secretos de los servicios

| Archivo en `infra/docker/secrets/` | Qué es | Cómo se crea |
| :--- | :--- | :--- |
| `kronos_worker_password` | Contraseña de `kronos_worker` | `generar_secretos.sh` |
| `kronos_console_password` | Contraseña de `kronos_console` | `generar_secretos.sh` |
| `wazuh_api_password` | Contraseña de `kronos-execute` | A mano, desde el gestor (parte 08) |
| `wazuh_api_ca.pem` | Certificado de la API de Wazuh | Parte 04, sección 8 |
| `telegram_token` | Token del bot | Parte 11 |
| `consola_certificado.pem` y `consola_llave.pem` | TLS de la consola | `sudo bash generar_certificado_consola.sh <IP de NetBird del servidor>` |
| `consola_usuarios.json` | Cuentas de la consola | Sección 6 |

Los que se escriben a mano se cargan sin que la contraseña quede en pantalla ni en el historial:

```
[servidor] read -rs CLAVE; printf '%s' "$CLAVE" | sudo tee secrets/wazuh_api_password >/dev/null; unset CLAVE
```

Los contenedores no corren como `root`: los secretos van con grupo 10001 y permiso 640.

```
[servidor] cd /opt/kronos/audit/infra/docker/secrets
[servidor] sudo chown root:10001 kronos_worker_password kronos_console_password wazuh_api_password wazuh_api_ca.pem telegram_token consola_usuarios.json consola_certificado.pem consola_llave.pem
[servidor] sudo chmod 640 kronos_worker_password kronos_console_password wazuh_api_password wazuh_api_ca.pem telegram_token consola_usuarios.json consola_certificado.pem consola_llave.pem
```

## 4. Configuración (`infra/docker/.env`)

```
[servidor] cd /opt/kronos/audit/infra/docker
[servidor] sudo install -m 600 servicios/.env.example .env
[servidor] sudo nano .env
```

Lo que cambia respecto del ejemplo:

| Variable | Valor |
| :--- | :--- |
| `KRONOS_INQUILINO` y `KRONOS_INQUILINOS` | El número de la PyME (parte 13) |
| `KRONOS_WAZUH_NOMBRE_SERVIDOR` | `localhost`, con el certificado de fábrica de la API |
| `KRONOS_TELEGRAM_CHAT`, `KRONOS_TELEGRAM_EQUIPO` y `KRONOS_NOMBRES_INQUILINOS` | Parte 11 |
| `KRONOS_CONSOLA_IP` | La IP de NetBird del servidor; nunca `0.0.0.0` |

## 5. Antes de levantar SOAR-VALIDATE

1. **Grupo `wazuh`.** `alerts.json` es del usuario `wazuh` con permiso 640, y el contenedor entra por su grupo:
   `sudo docker exec single-node-wazuh.manager-1 id wazuh` da el GID (999 en SOAR-CORE-01; si es otro, va a
   `KRONOS_GID_WAZUH`).
2. **Volumen de logs de Wazuh:** `sudo docker volume ls | grep wazuh_logs` debe mostrar `single-node_wazuh_logs`.
3. **Red hacia Ollama:** `sudo docker network ls | grep kronos_inferencia` (la crea el compose de Ollama, parte 06).
4. **Catálogo y prompt:** si el prompt del paso 2 no describe KRO-CAT-01, VALIDATE no arranca y su registro lo dice.

## 6. Levantar los servicios y crear las cuentas de la consola

```
[servidor] cd /opt/kronos/audit/infra/docker
[servidor] sudo docker compose -f docker-compose.yml -f servicios.yml up -d --build
```

La imagen `kronos-servicios:local` la construye el servicio `execute`; los otros tres la usan.

Cada persona que usa la consola crea su cuenta. El comando pide la contraseña sin mostrarla (mínimo 12
caracteres) y muestra **una sola vez** el secreto TOTP, para la app de autenticación:

```
[servidor] sudo docker run --rm -it --user root -v "$PWD/secrets:/s" kronos-servicios:local python -m consola.usuarios agregar XXXX --archivo /s/consola_usuarios.json
[servidor] sudo docker compose -f docker-compose.yml -f servicios.yml up -d --force-recreate consola
```

Para quitar una cuenta se borra su entrada de `consola_usuarios.json` y se recrea `consola`.

## 7. Comprobar

```
[servidor] sudo docker compose -f docker-compose.yml -f servicios.yml ps
[servidor] sudo docker compose -f docker-compose.yml -f servicios.yml logs --tail 20 validate execute notify consola
```

**Debe mostrar:**

- `validate`: `en marcha para el inquilino 1`;
- `execute`: `en marcha para los inquilinos [1]`;
- `notify`: `equipo de N cuentas`;
- `consola`: `en marcha: N cuentas`.

Desde un PC con NetBird, `https://<IP de NetBird del servidor>/` abre el inicio de sesión. La primera vez, el
navegador avisa que el certificado no es de una autoridad conocida: comparar su huella SHA-256 con la que imprimió
`generar_certificado_consola.sh`.

Si falta algo, el servicio no arranca y su registro dice qué (`no arranca: falta la variable …`).

## 8. Desplegar una versión nueva

1. Avisar en el grupo de Telegram y confirmar que no hay una prueba en curso. Un despliegue a la vez.
2. Respaldo: `sudo systemctl start kronos-respaldo-postgres.service`.
3. Traer la etiqueta y cambiarse a ella:

   ```
   [servidor] sudo git -C /opt/kronos/audit fetch --tags
   [servidor] sudo git -C /opt/kronos/audit checkout vX.Y.Z
   ```

4. Migraciones nuevas, si las hay (sección 2).
5. `sudo docker compose -f docker-compose.yml -f servicios.yml up -d --build` y la comprobación de la sección 7.
6. Anotar en el registro del día qué se desplegó y a qué hora (UTC).

## 9. Lista de comprobación

- [ ] `/opt/kronos/audit` es un clon de git en una etiqueta (`git describe --tags`).
- [ ] Base `healthy` y pruebas SQL a–d en orden.
- [ ] Secretos con grupo 10001 y permiso 640; ninguno en el repositorio.
- [ ] Los cuatro servicios en marcha; la consola sólo en la IP de NetBird.
- [ ] Una cuenta de consola por persona, con TOTP.
