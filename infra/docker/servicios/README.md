# Despliegue de SOAR-VALIDATE, SOAR-EXECUTE, SOAR-NOTIFY y SOAR-CONSOLE

Una sola imagen (`Dockerfile`) con cuatro servicios en `../servicios.yml`, que se suma al
`docker-compose.yml` de la base:

```bash
cd infra/docker
docker compose -f docker-compose.yml -f servicios.yml up -d --build
```

La imagen la construye sólo el servicio `execute`; `validate`, `notify` y `consola` la usan.
Para reconstruirla sin levantar todo: `docker compose -f docker-compose.yml -f servicios.yml build execute`.

| Servicio | Redes | Sale a |
| :--- | :--- | :--- |
| `validate` | `interna` (base) y `inferencia` (Ollama) | Sólo a Ollama (`ollama:11434`), sin internet. Lee `alerts.json` en sólo lectura |
| `execute` | `interna` (base) y la red del compose de Wazuh | API de Wazuh (`wazuh.manager:55000`), sin internet ni NetBird |
| `notify` | `interna` y `salida` | `api.telegram.org` |
| `consola` | `interna` y `consola` | Nada: recibe en el 443 de la IP de NetBird (`KRONOS_CONSOLA_IP`) |

Los cuatro corren con usuario sin privilegios (uid 10001), sistema de archivos de sólo
lectura, sin capacidades y con `no-new-privileges`. Sólo la consola publica un puerto, y
sólo en la IP de NetBird.

## Secretos (`infra/docker/secrets/`, fuera del repositorio)

| Archivo | Qué es | Cómo se crea |
| :--- | :--- | :--- |
| `kronos_worker_password` | Contraseña de `kronos_worker` | `generar_secretos.sh` (la toma de `03_roles.sql` si ya existe) |
| `wazuh_api_password` | Contraseña del usuario de API `kronos-execute` | A mano, desde el gestor |
| `wazuh_api_ca.pem` | Certificado de la API de Wazuh | Copiado del manager (abajo) |
| `telegram_token` | Token del bot | A mano, desde el gestor |
| `kronos_console_password` | Contraseña de `kronos_console` | `generar_secretos.sh` (con `initdb/05_clave_consola.sql`) |
| `consola_certificado.pem` / `consola_llave.pem` | TLS de la consola | `bash generar_certificado_consola.sh <IP de NetBird>` |
| `consola_usuarios.json` | Cuentas de la consola | Cada integrante, con el comando de abajo |

Los que se escriben a mano se cargan sin que la contraseña quede en pantalla ni en el
historial:

```bash
read -rs CLAVE && printf '%s' "$CLAVE" > secrets/wazuh_api_password && unset CLAVE
```

**En el servidor (Linux)** los archivos deben poder leerse desde el contenedor, que no
corre como root:

```bash
cd infra/docker/secrets
sudo chown root:10001 kronos_worker_password wazuh_api_password wazuh_api_ca.pem telegram_token \
    kronos_console_password consola_usuarios.json consola_certificado.pem consola_llave.pem
sudo chmod 640 kronos_worker_password wazuh_api_password wazuh_api_ca.pem telegram_token \
    kronos_console_password consola_usuarios.json consola_certificado.pem consola_llave.pem
```

## Cuentas de la consola

Cada integrante crea la suya; el comando pide la contraseña sin mostrarla (mínimo 12
caracteres) y muestra **una sola vez** el secreto TOTP para la app de autenticación
(Google Authenticator, Microsoft Authenticator, Aegis…):

```bash
docker run --rm -it --user root -v "$PWD/secrets:/s" kronos-servicios:local \
    python -m consola.usuarios agregar nicolas --archivo /s/consola_usuarios.json
```

En una base que ya existía, la contraseña del rol se aplica una vez:
`docker exec -i kronos-db-1 psql -U kronos_admin -d kronos < initdb/05_clave_consola.sql`
(antes, `initdb/04_consola.sql` de la misma forma).

## SOAR-VALIDATE (Patricio y Nicolás)

Lee `alerts.json` de Wazuh, clasifica cada alerta con el modelo y registra la decisión
(`python -m validacion`; variables en `validacion/__main__.py`). Antes de levantarlo:

1. **Grupo `wazuh`.** `alerts.json` es del usuario `wazuh` con permiso 640. El contenedor
   entra por el grupo: `id wazuh` da el GID (999 en SOAR-CORE-01, el valor por omisión de
   `KRONOS_GID_WAZUH`). El GID 999 también lo usa otro grupo del servidor: por eso el
   servicio monta **sólo** el secreto `kronos_worker_password` y no la carpeta `secrets/`.
2. **Volumen de logs de Wazuh.** `docker volume ls | grep wazuh_logs` da el nombre
   (`single-node_wazuh_logs`, en `KRONOS_WAZUH_LOGS`). Se monta con `:ro`.
3. **Ollama.** VALIDATE llega por la red `kronos_inferencia`, con el nombre `ollama`. Mientras
   Ollama siga siendo el contenedor creado a mano (red `bridge`), se le agrega esa red sin
   recrearlo ni tocar sus modelos; la red es interna, así VALIDATE no tiene salida a internet:

   ```bash
   sudo docker network create --internal kronos_inferencia
   sudo docker network connect --alias ollama kronos_inferencia ollama
   ```

   Al pasar Ollama a `infra/ollama/docker-compose.yml`, ese archivo crea la red con el mismo
   nombre y el mismo alias, y aquí no cambia nada. Antes hay que borrar la red manual
   (`docker network disconnect kronos_inferencia ollama` y `docker network rm kronos_inferencia`),
   porque Compose no adopta una red que no creó.
4. **Permiso del secreto de la base.** `kronos_worker_password` nace `root:root` con permiso
   600, y el contenedor (uid y gid 10001) no puede leerlo: el servicio se reinicia en bucle con
   `Permission denied: '/run/secrets/kronos_worker_password'`. Antes de levantarlo:

   ```bash
   sudo chown root:10001 secrets/kronos_worker_password
   sudo chmod 640 secrets/kronos_worker_password
   ```

5. **Inquilino.** `KRONOS_INQUILINO` (uno solo por ahora, hasta decidir cómo se asigna cada
   alerta). Se usa el mismo inquilino que `KRONOS_INQUILINOS` de EXECUTE.

La posición de lectura queda en el volumen `validate_estado` (`/estado/posicion.json`) y
sobrevive a reinicios; si se borra, el servicio empieza por el final de `alerts.json`. En el
primer arranque, entonces, no procesa las alertas anteriores.

El prompt del paso 2 sale de KRO-CAT-01; si no coinciden, el servicio no arranca y el registro
lo dice (`el prompt del paso 2 no describe el catálogo KRO-CAT-01`).

## Configuración (`infra/docker/.env`, fuera del repositorio)

Copiar `servicios/.env.example` a `infra/docker/.env` y completar. `KRONOS_WAZUH_RED`
es el nombre de la red del compose de Wazuh (`docker network ls`).

## Preparación en SOAR-CORE-01 (Nicolás)

1. Nombre de la red de Wazuh: `sudo docker network ls | grep single-node`.
2. Certificado de la API:
   `sudo docker exec <contenedor-del-manager> cat /var/ossec/api/configuration/ssl/server.crt > secrets/wazuh_api_ca.pem`,
   y su nombre: `openssl x509 -in secrets/wazuh_api_ca.pem -noout -subject -ext subjectAltName`.
   Si no es `wazuh.manager`, ponerlo en `KRONOS_WAZUH_NOMBRE_SERVIDOR`.
3. Usuario de API, comandos y scripts de Active Response: ver `ejecucion/README.md`.

## Bot de Telegram (una persona del equipo)

1. En Telegram, hablar con **@BotFather**: `/newbot`, nombre y usuario del bot. El token
   va al gestor y a `secrets/telegram_token`; nunca al chat ni al repositorio.
2. Crear un grupo con los tres integrantes y agregar el bot.
3. Identificadores: escribir algo en el grupo y abrir
   `https://api.telegram.org/bot<token>/getUpdates` en el navegador. `chat.id` (negativo)
   va a `KRONOS_TELEGRAM_CHAT`; el `from.id` de cada integrante, a `KRONOS_TELEGRAM_EQUIPO`.
   **Sólo antes de levantar NOTIFY:** con el servicio en marcha, abrir `getUpdates` le quita
   las respuestas a los botones. Tampoco convertir el grupo en supergrupo: cambia su id.
4. Activar la verificación en dos pasos en todas las cuentas del grupo.

## Comprobación

```bash
docker compose -f docker-compose.yml -f servicios.yml ps
docker compose -f docker-compose.yml -f servicios.yml logs --tail 20 validate execute notify consola
```

`validate` debe mostrar `en marcha para el inquilino 1`, `consola` debe mostrar `en marcha: N cuentas`, y por NetBird se abre
`https://<IP de NetBird>/`. `execute` debe mostrar `en marcha para los inquilinos [...]`, y `notify`, `en marcha ...;
equipo de 3 cuentas`. Si falta algo, el servicio no arranca y el registro dice qué
(`no arranca: falta la variable ...`).
