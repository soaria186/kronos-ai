# KRO-LOG-RR-2026-10-21 — Bloque A de Rodrigo

Registro de trabajo del 21-10-2026 (hora de Chile). Sin secretos: el token del bot no pasó por el chat ni por el repositorio.

**Resumen:**

- Las cuatro tareas del Bloque A de Rodrigo están hechas.
- El script de Windows (#32) y la retención de alertas (#34) están mezclados; la retención está además desplegada en SOAR-CORE-01.
- NOTIFY funciona con los tres integrantes, y la revisión cruzada está escrita (`KRO-REV-RR-2026-10-21_revision_cruzada.md`).
- El recuperador de tickets huérfanos está en el **PR #35**, esperando revisión.

## 1. Script de Windows `kronos-bloquear-ip` ✅ (falta la prueba en EP-WKS-01)

- **PR #32**, mezclado en `develop` el 21-10 a las 14:37, sin revisión registrada (ver §6).
- Archivos en `infra/wazuh/active-response/windows/`:
  - `kronos-bloquear-ip.cmd`: lanzador. Usa la PowerShell de 64 bits (`Sysnative`), porque el agente es de 32 bits.
  - `kronos-bloquear-ip.ps1`: lee `parameters.extra_args` y crea o borra una regla de **entrada** `Kronos-bloqueo-<ip>` con `netsh advfirewall`.
  - `README.md`: instalación y prueba manual.
  - `.gitattributes`: `.cmd` y `.ps1` con CRLF.
- Mismo sentido que el script de Linux de Nicolás (`iptables -I INPUT`).
- Probado en el PC de Rodrigo como administrador:
  - aplicar, aplicar repetido y quitar: salida 0, con la regla creada y luego borrada;
  - 9 casos rechazados con salida 1 y su `ERROR` en el registro: loopback, puerta de enlace, IP propia, `1`, `203.0.113.50 & calc`, multicast, operación `borrar`, tres argumentos y entrada vacía;
  - al final no quedó ninguna regla `Kronos-bloqueo`.
- **Pendiente (Nicolás, en EP-WKS-01):**
  - instalarlo en el agente 002 y probarlo por EXECUTE;
  - confirmar que el agente encuentra `kronos-bloquear-ip.cmd` cuando la API envía `!kronos-bloquear-ip` sin extensión. Si no, EXECUTE debe enviar el nombre con `.cmd` a los agentes Windows.

## 2. Bot de Telegram y SOAR-NOTIFY ✅

- Bot «Kronos AI» (`@<usuario del bot>`), creado con BotFather desde la cuenta de Rodrigo.
- Grupo «Kronos — avisos»:
  - tipo `group`, id `<id del grupo>`;
  - **no convertirlo en supergrupo**, porque el id cambiaría y NOTIFY dejaría de llegar.
- Token cargado en SOAR-CORE-01 sin pasar por la terminal ni el chat:
  - se envió desde el portapapeles del PC por `ssh` a un archivo temporal, y el temporal se borró con `shred`;
  - quedó en `/opt/kronos/audit/infra/docker/secrets/telegram_token`, con 46 bytes, `root:10001` y permiso `640`.
- `.env` (respaldo en `.env.bak-2026-10-21`):
  - `KRONOS_TELEGRAM_CHAT=<id del grupo>`;
  - `KRONOS_TELEGRAM_EQUIPO=<id>:nicolas,<id>:patricio,<id>:rodrigo`.
- `docker compose … up -d --no-deps notify`. Se creó la red `kronos_salida`.
- Primer arranque (14:08): `equipo de 1 cuentas` e `inquilino 1: 4 avisos enviados`.
- 14:12: entró Patricio. 14:25: entró Nicolás. Registro: `equipo de 3 cuentas`.
- 14:29: verificación en dos pasos activada en las tres cuentas.
- ~17:00: enlace de invitación revocado y token guardado en el gestor de contraseñas (nota local borrada).
- **No volver a abrir `getUpdates` en el navegador**: le quita las respuestas a NOTIFY.
- La prueba de los botones del nivel 3 queda para la prueba integral (punto de encuentro 2).

## 3. Acceso SSH de Rodrigo ✅

- Usuario propio de Rodrigo en SOAR-CORE-01, con su llave SSH (ya autorizada), grupos `sudo` y `users`, sin `docker` (se usa `sudo docker`).
- Atajo `Host soar-core-01` en `~/.ssh/config` del PC: `ssh soar-core-01`.
- La tarea de Nicolás «llave SSH propia de Rodrigo» queda resuelta; no hubo que autorizar nada nuevo.
- El despliegue está en `/opt/kronos/audit`. **No es una copia de git**: el código se copió a mano (ver §5).

## 4. Tope y retención de las alertas guardadas ✅ (mezclado y desplegado)

- **Problema:** VALIDATE guardaba la alerta completa (con datos personales) dentro de la bitácora inmutable. No se podía borrar nunca (R-09) y no tenía tope.
- **Decisión de Rodrigo (21-10):** tabla aparte que sí se puede purgar; en la bitácora queda sólo la huella. Plazo de **90 días como propuesta** para el punto de encuentro 1.
- **PR #34**, mezclado en `develop` el 21-10 a las 14:37, sin revisión registrada (ver §6).
- Cambios:
  - `infra/docker/initdb/06_alertas_guardadas.sql` (idempotente; también es la migración):
    - tabla `alertas_guardadas` con RLS; `kronos_worker` sólo `SELECT`/`INSERT`;
    - `fn_purgar_alertas(dias)`, sólo `kronos_admin`, con un mínimo de 7 días;
    - `fn_verificar_alertas(inquilino)`.
  - `ALERTA_RECIBIDA` guarda `alerta_guardada`: SHA-256, tamaños, si se recortó, `agent.id` y `rule.id`.
  - Tope en `persistencia/alertas.py`:
    - sobre 60 000 bytes, recorta los textos a 4096 caracteres;
    - si aún no cabe, guarda sólo los campos esenciales;
    - además, la tabla tiene un CHECK de 64 KiB.
  - La purga nunca borra tickets en curso, con temporizador pendiente o con la última reversión fallida, y deja el evento `ALERTAS_PURGADAS`.
  - Timer diario a las 04:45 UTC en `infra/docker/retencion/`.
  - El contrato con EXECUTE no cambia, y `validacion/` no se tocó.
- **Pruebas** (PostgreSQL local):
  - 10 de integración nuevas y 5 unitarias nuevas;
  - suite completa: 275 unitarias y 47 de integración OK;
  - después de una purga real, 128 inquilinos con 0 cadenas rotas.
- **Límite declarado:** las alertas de los tickets anteriores a la migración (#1 a #22 aprox.) quedan dentro de la bitácora y no se pueden borrar.

## 5. Despliegue del #34 en SOAR-CORE-01 ✅ (21-10, 19:49 a 19:54 UTC)

1. **Comparación:** `develop` (`fb5387c`) se empaquetó con `git archive` en el PC de Rodrigo, se copió por `scp` y se comparó con `/opt/kronos/audit`.
   - El servidor tenía exactamente el `develop` anterior: nadie lo había modificado a mano.
   - Archivos propios del servidor, que no se tocaron: `.env`, `.env.bak-2026-10-21`, `secrets/`, `initdb/03_roles.sql` e `initdb/05_clave_consola.sql`.
2. **Respaldo previo:** `postgres-kronos-20261021T194929Z.tar.age`.
3. **Código:** se copió `develop` encima de `/opt/kronos/audit`; después, el `diff` contra `develop` quedó vacío.
4. **Migración `06`:** `MIGRACION OK`. Permisos de la tabla: `kronos_worker=ar` (sólo insertar y leer).
5. **Servicios:** `up -d --build --no-deps validate execute`. Registro: `en marcha para el inquilino 1` y `en marcha para los inquilinos [1], cada 10 s`. `db`, `notify` y `consola` no se tocaron.
6. **Purga diaria:**
   - script en `/usr/local/sbin/`, `.service` y `.timer` en `/etc/systemd/system/`;
   - primera ejecución: `plazo 90 días; nada que purgar`;
   - próxima ejecución: 22-10 a las 04:46 UTC.
7. **Comprobación:** `alertas_guardadas` vacía y `fn_verificar_alertas(1)` sin filas. A las ~20:00 UTC todavía no había llegado ninguna alerta nueva (VALIDATE sin lotes desde las 19:53). **Pendiente:** repetir las dos consultas después de la próxima prueba de Nicolás:

   ```bash
   sudo docker exec kronos-db-1 psql -U kronos_admin -d kronos -c "SELECT ticket_id, bytes_original, recortada, guardada_en FROM alertas_guardadas ORDER BY ticket_id DESC LIMIT 3"
   sudo docker exec kronos-db-1 psql -U kronos_admin -d kronos -c "SELECT * FROM fn_verificar_alertas(1)"
   ```

- Se confirmó lo observado en la revisión del #29: la imagen `kronos-servicios:local` se construye dos veces (una por `validate` y otra por `execute`).
- `notify` y `consola` siguen con la imagen anterior; no les afecta el cambio y toman la nueva la próxima vez que se recreen.
- Nicolás quedó avisado por WhatsApp del despliegue y de los PR mezclados sin revisión.

## 6. Revisión cruzada ✅

- Documento `KRO-REV-RR-2026-10-21_revision_cruzada.md`, con los comentarios listos para pegar desde la cuenta personal de GitHub de Rodrigo.
- **Los PR #31, #32, #33 y #34 se mezclaron el 21-10 a las 14:37** desde la cuenta compartida `soarai2026`, sin revisión registrada. Se anota como excepción (R-04).
- Las observaciones al #31 (rechazar la puerta de enlace y exigir dos argumentos) pasan a un **PR nuevo de Nicolás**.
- La contradicción del #33 queda resuelta: la reversión de 60 minutos se confirmó en la segunda prueba de Nicolás (21-10, 16:35 UTC).
- Del #28 quedan dos hallazgos:
  - **tickets huérfanos** → resuelto en el PR #35 (§8);
  - **cortacircuito que cuenta tickets procesados y no alertas llegadas** (Patricio).

## 7. Hallazgos que dejaron los primeros avisos

1. **La reversión del ticket #20 falló** (`REVERSION_FALLIDA`: «agent is not active»), porque EP-SRV-01 estaba apagada al vencer el plazo.
   - Al reiniciarse la VM, la regla de `iptables` ya no existía.
   - Pendiente de diseño: EXECUTE no reintenta una reversión fallida (hallazgo 1 de Nicolás).
2. **Ruido por la VM apagada.**
   - Cada vez que se apaga una VM, la regla 100115 lleva al PB-F6-01 (nivel 0), que no tiene comando y termina en `FAILED` con aviso (tickets #21, #22…).
   - Para el punto de encuentro 1: decidir cómo tratar el nivel 0 sin comando, para no llenar el grupo de avisos en la farmacia.

## 8. Recuperador de tickets huérfanos ✅ (PR #35, falta revisión y despliegue)

- **Problema** (hallazgo del #28): si VALIDATE falla después de crear el ticket y antes de registrar la decisión, el ticket queda en `PENDING` sin playbook para siempre:
  - al releer la alerta sale como `REPETIDA`;
  - EXECUTE no lo toma;
  - NOTIFY no avisa.
- **Decisión de Rodrigo (21-10):** revisión manual con aviso, a los **10 minutos**; nunca se reclasifica.
- Rama `feat/e3-tickets-huerfanos`, **PR #35**, con los 4 checks del CI en verde. Revisor: Patricio.
- Cambios:
  - `Repositorio.recuperar_huerfanos`:
    - un `PENDING` sin playbook ni motivo, de más de 10 minutos, pasa a `MANUAL_TRIAGE` con `DECISION_NO_REGISTRADA`;
    - deja el evento `TICKET_SIN_DECISION`;
    - si VALIDATE decide al mismo tiempo, sólo uno de los dos cambia el ticket (mismo `WHERE` que `registrar_decision`, con `FOR UPDATE SKIP LOCKED`).
  - EXECUTE lo llama al comienzo de cada ciclo.
  - NOTIFY avisa «[SIN DECISIÓN]», sin botones.
  - Motivo nuevo en `02_esquema.sql` y migración idempotente `infra/docker/migraciones/2026-10-21_motivo_decision_no_registrada.sql`.
  - No toca `validacion/`.
- **Pruebas:** 6 de integración nuevas y unitarias de EXECUTE y NOTIFY; 53 de integración OK en total, más ruff y R1. La migración se aplicó dos veces sin error.
- **Para desplegar después del merge:**
  1. migración;
  2. recrear `execute` y `notify` (coordinar con Nicolás);
  3. antes, revisar si el inquilino 1 tiene `PENDING` sin playbook, porque el primer ciclo los pasará a revisión manual con aviso.

## 9. Siguiente

- Patricio revisa el **PR #35**; después, desplegarlo en SOAR-CORE-01.
- [servidor] Comprobar `alertas_guardadas` con la próxima alerta real.
- [PC] Reintento de reversiones fallidas por agente inactivo, después del punto de encuentro 1.
- **Punto de encuentro 1:** los cinco temas del plan, más:
  - plazo de retención de 90 días;
  - ruido de avisos del nivel 0;
  - límite de las alertas anteriores a la migración;
  - cortacircuito que cuenta tickets y no alertas;
  - reintento de reversiones fallidas.
