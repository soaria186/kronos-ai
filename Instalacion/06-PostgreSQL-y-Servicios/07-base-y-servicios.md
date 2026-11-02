# 07 · Base SOAR-AUDIT y servicios

| Campo | Valor |
| :--- | :--- |
| Parte | 07 de 15 |
| Responsable | Rodrigo Riveros (revisa: Patricio González) |
| Versión | 1.0, 01-11-2026 |
| Estado | Vigente: seguida el 01-11-2026 (02-11, 00:03 UTC) al pasar SOAR-CORE-01 de una copia a mano a un clon de git en `v1.0.0-rc1` (caso a de la sección 1). Las secciones 2 a 6 describen la instalación desde cero, que se hizo el 15 y 16-10-2026 |
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

El servidor clona con una **llave de despliegue de sólo lectura** (GitHub → *Settings* → *Deploy keys*, desde
la cuenta dueña del repositorio). GitHub no deja usar la misma llave en dos repositorios, así que es una por
repositorio:

```
[servidor] sudo ssh-keygen -t ed25519 -N '' -C kronos-despliegue-soaria186 -f /root/.ssh/kronos_despliegue_soaria186
[servidor] sudo cat /root/.ssh/kronos_despliegue_soaria186.pub
[servidor] ssh-keyscan -t ed25519 github.com 2>/dev/null | sudo tee -a /root/.ssh/known_hosts >/dev/null
[servidor] ssh-keygen -lf <(ssh-keyscan -t ed25519 github.com 2>/dev/null)
```

**Debe mostrar:** la llave pública (una línea `ssh-ed25519 …`) y la huella de github.com,
`SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU`, igual a la publicada en docs.github.com («GitHub's SSH key
fingerprints»). Agregar la línea pública como *Deploy key* **sin** marcar *Allow write access* y comprobar:

```
[servidor] sudo ssh -i /root/.ssh/kronos_despliegue_soaria186 -T git@github.com
```

**Debe mostrar:** `Hi soaria186/kronos-ai! You've successfully authenticated, but GitHub does not provide shell
access.` Después:

El repositorio está ordenado por fases y el proyecto vive en `Fase 2/Avances`. Se clona en
`/opt/kronos/kronos-ai` y `/opt/kronos/audit` es un enlace a la carpeta del proyecto: así ninguna ruta del
servidor lleva espacios, y todos los comandos de esta guía usan `/opt/kronos/audit`.

```
[servidor] sudo GIT_SSH_COMMAND='ssh -i /root/.ssh/kronos_despliegue_soaria186' git clone git@github.com:soaria186/kronos-ai.git /opt/kronos/kronos-ai
[servidor] sudo git -C /opt/kronos/kronos-ai config core.sshCommand 'ssh -i /root/.ssh/kronos_despliegue_soaria186'
[servidor] sudo git -C /opt/kronos/kronos-ai checkout v1.0.0
[servidor] sudo ln -s "/opt/kronos/kronos-ai/Fase 2/Avances" /opt/kronos/audit
[servidor] sudo git -C /opt/kronos/kronos-ai describe --tags
[servidor] ls /opt/kronos/audit/infra/docker
```

**Debe mostrar:** `v1.0.0` y los archivos de `infra/docker` (`docker-compose.yml`, `servicios.yml`…). Si el
repositorio es público, basta con `git clone https://github.com/soaria186/kronos-ai.git`.

Lo que vive **sólo en el servidor**, fuera de git (`.gitignore`): `infra/docker/.env`, `infra/docker/secrets/`,
`infra/docker/initdb/03_roles.sql` e `infra/docker/initdb/05_clave_consola.sql`, todos dentro de
`/opt/kronos/audit`.

### Si el servidor ya tenía Kronos

Los contenedores no cambian: el proyecto de Docker se llama `kronos` en cualquier carpeta, así que la base y sus
volúmenes se mantienen. Antes, respaldo (`sudo systemctl start kronos-respaldo-postgres.service`) y aviso en el
grupo de Telegram.

**a) `/opt/kronos/audit` es una copia a mano** (como hasta el 21-10): clonar como arriba, pero **antes del
`ln -s`**, copiar lo que vive sólo en el servidor y apartar la copia vieja:

```
[servidor] N="/opt/kronos/kronos-ai/Fase 2/Avances/infra/docker"
[servidor] sudo cp -a /opt/kronos/audit/infra/docker/.env /opt/kronos/audit/infra/docker/secrets "$N/"
[servidor] sudo cp -a /opt/kronos/audit/infra/docker/initdb/03_roles.sql /opt/kronos/audit/infra/docker/initdb/05_clave_consola.sql "$N/initdb/"
[servidor] sudo mv /opt/kronos/audit /opt/kronos/audit.antes-del-clon
```

**b) `/opt/kronos/audit` ya es un clon con la estructura anterior al 26-10:** traer la versión nueva, mover
el clon a su ruta nueva y llevar lo que vive sólo en el servidor a la carpeta del proyecto:

```
[servidor] sudo git -C /opt/kronos/audit pull
[servidor] sudo mv /opt/kronos/audit /opt/kronos/kronos-ai
[servidor] cd /opt/kronos/kronos-ai
[servidor] sudo mv infra/docker/.env infra/docker/secrets "Fase 2/Avances/infra/docker/"
[servidor] sudo mv infra/docker/initdb/03_roles.sql infra/docker/initdb/05_clave_consola.sql "Fase 2/Avances/infra/docker/initdb/"
[servidor] sudo git status --short --ignored
```

**Debe mostrar:** ninguna línea fuera de `Fase 2/Avances` (las carpetas viejas que quedaron vacías se borran con
`sudo find infra -type d -empty -delete`).

En los dos casos, después: el `ln -s` de arriba, `cd /opt/kronos/audit/infra/docker` y recrear los servicios
(sección 7).

**Así se hizo en SOAR-CORE-01 (caso a), el 01-11-2026:** respaldo previo; clon en `v1.0.0-rc1`; los cuatro
archivos que viven sólo en el servidor copiados al clon; la copia vieja apartada en
`/opt/kronos/audit.antes-del-clon` y el enlace creado. `git status --short --ignored` mostró sólo esos cuatro
archivos. Después se agregó `KRONOS_AGENTES_SO`, se aplicaron las tres migraciones sin errores y los cinco
servicios quedaron en marcha. Todo eso, junto, lo hace `infra/docker/desplegar.sh` (sección 8). La copia vieja
se borra cuando la versión nueva lleve unos días funcionando; el respaldo `/root/audit-antes-del-clon-*.tar.gz`
se conserva hasta el cierre.

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
| `KRONOS_AGENTES_SO` | El sistema operativo de cada agente, `001:linux,002:windows` en la PyME simulada (parte 13) |
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
- `execute`: `en marcha para los inquilinos [1]` y `sistema operativo por agente: {'001': 'linux', '002': 'windows'}`;
- `notify`: `equipo de N cuentas`;
- `consola`: `en marcha: N cuentas`.

Desde un PC con NetBird, `https://<IP de NetBird del servidor>/` abre el inicio de sesión. La primera vez, el
navegador avisa que el certificado no es de una autoridad conocida: comparar su huella SHA-256 con la que imprimió
`generar_certificado_consola.sh`.

Si falta algo, el servicio no arranca y su registro dice qué (`no arranca: falta la variable …`).

## 8. Desplegar una versión nueva

1. Avisar en el grupo de Telegram y confirmar que no hay una prueba en curso. Un despliegue a la vez.
2. Correr el script de despliegue con la etiqueta. Hace el respaldo previo, el `fetch` y el `checkout` de la
   etiqueta, agrega `KRONOS_AGENTES_SO` si falta, aplica las migraciones (todas son idempotentes), reconstruye
   los servicios y muestra la comprobación de la sección 7. Se detiene en el primer error:

   ```
   [servidor] bash /opt/kronos/audit/infra/docker/desplegar.sh vX.Y.Z
   ```

   **Debe mostrar:** `versión desplegada: vX.Y.Z`, sólo los cuatro archivos que viven en el servidor fuera de git,
   las migraciones sin `ERROR`, los cinco servicios `running` y las líneas de arranque de la sección 7. El
   registro queda en `~/kronos-despliegue-<fecha UTC>.log`.

   A mano, los pasos son los mismos: `sudo systemctl start kronos-respaldo-postgres.service`,
   `sudo git -C /opt/kronos/kronos-ai fetch --tags`, `sudo git -C /opt/kronos/kronos-ai checkout vX.Y.Z`, las
   migraciones de la sección 2 y `sudo docker compose -f docker-compose.yml -f servicios.yml up -d --build`.
3. Anotar en el registro del día qué se desplegó y a qué hora (UTC).

## 9. Lista de comprobación

- [ ] `/opt/kronos/kronos-ai` es un clon de git en una etiqueta (`git describe --tags`) y `/opt/kronos/audit` apunta a su carpeta `Fase 2/Avances`.
- [ ] Base `healthy` y pruebas SQL a–d en orden.
- [ ] Secretos con grupo 10001 y permiso 640; ninguno en el repositorio.
- [ ] Los cuatro servicios en marcha; la consola sólo en la IP de NetBird.
- [ ] Una cuenta de consola por persona, con TOTP.
