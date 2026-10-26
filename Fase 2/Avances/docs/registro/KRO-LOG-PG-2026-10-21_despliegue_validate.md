# KRO-LOG-PG-2026-10-21 · Despliegue de VALIDATE (PR #36) en SOAR-CORE-01

## Estado
- PR #35 (Rodrigo), #36 (Patricio) y #38 (documento 02) **mezclados** en `develop` (66d955e).
- **VALIDATE desplegado el 21-10 (22:09 hora de Chile)** con el código del #36: plazo de 120 s, precalentamiento del modelo, exclusión de 10.0.50.1 y agrupación de alertas. Log al arrancar: «cargando el modelo en memoria» y «en marcha para el inquilino 1». `ollama ps`: qwen2.5:7b «Forever».
- **Pendiente: prueba de la ráfaga con Nicolás** (varias alertas iguales en menos de 10 minutos = un solo ticket y «agrupada» en el log). Se hará otro día.
- EXECUTE, NOTIFY, consola y base no se tocaron.

## Cómo se desplegó
- `/opt/kronos/audit` en el servidor **no es un clon de git** (D-55 lo cambia Rodrigo): el código se copió con `scp` desde el PC a `~/relevo` y de ahí a `/opt/kronos/audit` (sólo `validacion`, `decision`, `persistencia` y `infra/docker/servicios.yml`). Respaldo previo en `/opt/kronos/audit.bak-2026-10-21`.
- El usuario de Patricio en el servidor está en el grupo `sudo`, no en `docker`: los comandos de Docker van con `sudo`.
- La tabla `alertas_guardadas` (PR #34) ya existía en la base del servidor.
- `ejecucion` y `notificacion` (PR #35) **no se copiaron**: son del despliegue de Rodrigo, que aún necesita aplicar `2026-10-21_motivo_decision_no_registrada.sql`.

## Hallazgo: permisos al copiar desde Windows
- Tras el primer despliegue VALIDATE entró en bucle de reinicios (`Permission denied` al leer `validate.json`, unos 3 minutos sin clasificar; las alertas se retoman por la posición guardada).
- Causa: `scp` desde Windows dejó `validacion/configuracion` con permiso `drwx------`; el `COPY` del Dockerfile lo llevó a la imagen y el contenedor (usuario 10001) no podía entrar.
- Un `chmod -R a+rX` en el disco no bastó: Docker reutilizó la capa `COPY` en caché. Se resolvió cambiando el contenido de `validacion/README.md` (una línea en blanco) para forzar la reconstrucción de esas capas.
- **Para el próximo despliegue** (también el de Rodrigo): tras copiar, `sudo chmod -R a+rX` en las carpetas copiadas y, si Docker dice «CACHED» en los `COPY`, verificar con `docker run --rm --entrypoint ls <imagen> -ld /app/<carpeta>` antes de dar por bueno el despliegue.

## Pendientes de Patricio
- Prueba de la ráfaga con Nicolás (y avisar en Telegram).
- Revisar en la consola que no quedaran alertas sin ticket entre las 22:05 y las 22:09 del 21-10.
- Tareas 4 (modo observación), 5 (inquilino por grupo), 6 (cortacircuito por alertas recibidas), 7, 8, 9 y 10 de `KRO-TAREAS-2026-10-21_patricio.md`.
- Avisar a Rodrigo de que VALIDATE ya está desplegado y del problema de permisos.
