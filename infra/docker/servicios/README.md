# Despliegue de SOAR-EXECUTE y SOAR-NOTIFY

Una sola imagen (`Dockerfile`) con dos servicios en `../servicios.yml`, que se suma al
`docker-compose.yml` de la base:

```bash
cd infra/docker
docker compose -f docker-compose.yml -f servicios.yml up -d --build
```

| Servicio | Redes | Sale a |
| :--- | :--- | :--- |
| `execute` | `interna` (base) y la red del compose de Wazuh | API de Wazuh (`wazuh.manager:55000`), sin internet ni NetBird |
| `notify` | `interna` y `salida` | `api.telegram.org` |

Los dos corren con usuario sin privilegios (uid 10001), sistema de archivos de sólo
lectura, sin capacidades y con `no-new-privileges`. Ninguno publica puertos.

## Secretos (`infra/docker/secrets/`, fuera del repositorio)

| Archivo | Qué es | Cómo se crea |
| :--- | :--- | :--- |
| `kronos_worker_password` | Contraseña de `kronos_worker` | `generar_secretos.sh` (la toma de `03_roles.sql` si ya existe) |
| `wazuh_api_password` | Contraseña del usuario de API `kronos-execute` | A mano, desde el gestor |
| `wazuh_api_ca.pem` | Certificado de la API de Wazuh | Copiado del manager (abajo) |
| `telegram_token` | Token del bot | A mano, desde el gestor |

Los que se escriben a mano se cargan sin que la contraseña quede en pantalla ni en el
historial:

```bash
read -rs CLAVE && printf '%s' "$CLAVE" > secrets/wazuh_api_password && unset CLAVE
```

**En el servidor (Linux)** los archivos deben poder leerse desde el contenedor, que no
corre como root:

```bash
sudo chown root:10001 secrets/kronos_worker_password secrets/wazuh_api_password secrets/wazuh_api_ca.pem secrets/telegram_token
sudo chmod 640 secrets/kronos_worker_password secrets/wazuh_api_password secrets/wazuh_api_ca.pem secrets/telegram_token
```

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
4. Activar la verificación en dos pasos en las tres cuentas (pregunta abierta #39).

## Comprobación

```bash
docker compose -f docker-compose.yml -f servicios.yml ps
docker compose -f docker-compose.yml -f servicios.yml logs --tail 20 execute notify
```

`execute` debe mostrar `en marcha para los inquilinos [...]`, y `notify`, `en marcha ...;
equipo de 3 cuentas`. Si falta algo, el servicio no arranca y el registro dice qué
(`no arranca: falta la variable ...`).
