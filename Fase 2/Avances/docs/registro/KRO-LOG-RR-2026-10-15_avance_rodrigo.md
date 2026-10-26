# Kronos AI · Avance de Rodrigo · jueves 15-10-2026

Hola Nicolás y Patricio. Este es el resumen de lo que hice hoy, lo que les toca a cada uno y lo que falta para tener todo en SOAR-CORE-01.

## 1. En pocas palabras

- **Ya están escritas todas las piezas del SOAR que faltaban:** EXECUTE (ejecuta las medidas en los equipos por Wazuh), NOTIFY (avisa al equipo por Telegram, con botones para aprobar o rechazar el nivel 3) y CONSOLE (panel web con contraseña y código TOTP).
- **También quedaron listos:** el respaldo diario cifrado de PostgreSQL y el despliegue con Docker.
- **Se cierran 5 preguntas abiertas que me tocaban:** #6, #28, #38, #44 y #45.
- **Todo está en 8 PR, del #17 al #24.** Pasaron sus checks (gitleaks, ruff y R1) y lo probé en mi PC contra PostgreSQL 17.11, la misma versión del servidor.
- **⚠️ Todavía no hay nada en el servidor.** Primero hay que aprobar los PR en GitHub, después mezclarlos y al final desplegar con Nicolás.

## 2. Pull requests

| PR | Qué es | Pruebas |
| :---: | :--- | :--- |
| #16 | Motivos FAMILIA_NO_COINCIDE y APROBACION_VENCIDA; una alerta crea un solo ticket | Mezclado (lo mezcló Nicolás) |
| #17 | Capa de acceso a la base para VALIDATE (registrar alertas y decisiones, contadores, cortacircuito) | 11 de integración |
| #18 | El CI corre las pruebas unitarias en cada PR | 110 unitarias en el CI |
| #19 | Respaldo diario cifrado de PostgreSQL y script que prueba la restauración | Restauración: 2822/2822 eventos, 12 inquilinos, 0 cadenas rotas |
| #20 | **SOAR-EXECUTE**: estados, órdenes validadas, actuador por la API de Wazuh y servicio | 30 unitarias + 11 de integración |
| #21 | **SOAR-NOTIFY**: avisos y aprobación del nivel 3 por Telegram | 20 unitarias + 4 de integración |
| #22 | Despliegue de EXECUTE y NOTIFY (imagen Docker y `servicios.yml`) | Probado en Docker Desktop |
| #23 | Rol `kronos_console` y funciones del esquema `consola` en la base | 8 pruebas de permisos |
| #24 | **SOAR-CONSOLE**: panel web | 24 unitarias + prueba de punta a punta con TLS |

**Orden de merge:** #17 → #20 → #21 → #22 → #23 → #24. El #18 y el #19 pueden ir en cualquier momento. Cada PR incluye los commits del anterior; mezclados en orden quedan limpios.

**⚠️ Revisión:** a la hora de este resumen, GitHub no muestra ninguna aprobación registrada. Nicolás, si ya los revisaste, aprueba cada uno en GitHub (**Files changed → Review changes → Approve → Submit review**) para que quede constancia. Después los mezclo yo.

## 3. Decisiones de diseño que tomé hoy

Les pido que las revisen. Si alguna no les parece, la conversamos.

| Pregunta abierta | Decisión |
| :---: | :--- |
| #6 | El nivel 3 espera en un **estado nuevo, `AWAITING_APPROVAL`**, y EXECUTE solo toma tickets en `PENDING`, así que un nivel 3 nunca se ejecuta sin aprobación. `FAILED` **no se reintenta solo**. La **reversión queda en la bitácora** (`REVERSION_*`) y el ticket sigue en `SUCCESS`. |
| #28 | La consola escribe con un **rol propio mínimo, `kronos_console`**. No puede tocar tablas: solo 4 funciones de la base (aprobar, rechazar con motivo, pedir reversión y cerrar el cortacircuito). Telegram usa las mismas funciones. |
| #38 | La consola es accesible **solo por NetBird**, con **TLS, contraseña y código TOTP** (Google o Microsoft Authenticator). |
| #44 | El respaldo de PostgreSQL corre a las **04:15 UTC** (el de Wazuh, a las 04:00), cifrado con **age** y con 14 copias. |
| #45 | Restaurar **no** requiere `--disable-triggers`: `pg_restore` crea los disparadores después de cargar los datos. Está probado: la cadena de hash queda intacta. |
| #51 (propuesta) | NOTIFY no envía correos. El aviso a la persona afectada sigue siendo manual (D-35); el aviso del nivel 2 lo recuerda. |
| #53 (propuesta) | Las contraseñas de los servicios van como **secretos de Docker** (archivos), nunca en variables ni en el repo. |

## 4. Cómo funciona ahora cada nivel

- **Nivel 0 y 1:** se ejecutan solos. El nivel 1 se revierte solo cuando vence su plazo.
- **Nivel 2:** se ejecuta, se avisa por Telegram y se abre un plazo de 2 días. Al vencer, llega un recordatorio diario y la medida **nunca se revierte sola** (D-33). Se revierte desde la consola.
- **Nivel 3:** queda esperando. Llega un aviso por Telegram con los botones **Aprobar** y **Rechazar** (el rechazo pide el motivo) y la decisión también se puede tomar en la consola. Si en 2 días nadie responde, pasa a revisión manual con `APROBACION_VENCIDA` sin ejecutarse (D-34).
- **Todo queda en la bitácora con quién lo hizo:** `telegram:nicolas`, `consola:patricio`, etc.
- **Seguridad de EXECUTE:**
  - el comando sale de una tabla fija, nunca de la alerta;
  - las IP, cuentas, PID y servicios se validan con reglas estrictas;
  - nunca se actúa sobre el agente 000 (el manager), sobre la IP del propio equipo ni sobre cuentas como `root` o `Administrator`.

## 5. Pendientes por persona

### Nicolás

1. **Aprobar en GitHub los PR #17 a #24**, o repartirlos con Patricio.
2. **Sesión de despliegue en SOAR-CORE-01 conmigo**, después del merge. Les mando los comandos exactos antes:
   - las migraciones de la base: `2026-10-15_estado_espera_aprobacion.sql`, `04_consola.sql` y la clave de la consola;
   - el respaldo de PostgreSQL (`infra/docker/respaldo/`), con la misma llave pública de age del respaldo de Wazuh;
   - la consola: certificado para `<IP de NetBird del servidor>`, una cuenta por persona y el 443 publicado solo en NetBird.
3. **Wazuh para EXECUTE** (detalle en `ejecucion/README.md`):
   - usuario de API `kronos-execute` con permiso **solo** de `active-response:command`;
   - un `<command>` por cada comando `kronos-*` en el manager, **sin** bloques `<active-response>` (el Active Response automático debe seguir apagado);
   - los scripts `kronos-*` en los agentes del laboratorio;
   - el certificado de la API (puerto 55000) y el nombre de la red Docker de Wazuh (`docker network ls`).
4. **Verificar en el laboratorio** que la API de Wazuh 4.14.8 acepte el comando con prefijo `!` y entregue `arguments` al script. No encontré documentación clara para esa versión.

### Patricio

1. **Revisar y aprobar los PR**, si Nicolás no alcanza con todos.
2. **VALIDATE debe guardar la alerta completa de Wazuh en `detalle["alerta"]`** del evento `ALERTA_RECIBIDA`, porque EXECUTE saca de ahí el agente y el objetivo (IP, cuenta, etc.).
3. **Agregar `@unittest.skipIf(sys.platform == "win32", ...)` a 3 pruebas** que fallan solo en Windows, no por el código: las 2 de rotación en `test_alertas_wazuh.py` y `test_servidor_apagado` en `test_ollama.py`.
4. **Actualizar la sección 8.1 del documento 02** con los estados nuevos y quitar de `preguntas-abiertas.md` las filas #6, #28, #38, #44 y #45.

### Los tres

1. **Crear el bot de Telegram** con @BotFather y un grupo con los tres y el bot. Los pasos están en `infra/docker/servicios/README.md`. El token va al gestor, nunca al chat.
2. **Activar la verificación en dos pasos en Telegram** (pregunta #39).
3. **Definir los plazos de reversión del nivel 1** en el catálogo. Mientras no estén, los playbooks de nivel 1 terminan en `FAILED` con `PLAZO_DE_REVERSION_SIN_DEFINIR`: es a propósito, para no aplicar algo que no se sabe cuándo deshacer.
4. **Anotar como excepción** el PR #16, que se mezcló sin revisión registrada.

### Yo (Rodrigo), más adelante

- Un job de CI con FastAPI para correr las 13 pruebas de la consola que hoy se omiten (después del #18).
- La vista de solo lectura para el encargado del cliente.
- La red `kronos_inferencia` (con Nicolás).
- La parte 07 de la guía de instalación.
- Pasar mis secretos al gestor y bajar mi rol de NetBird a User.

## 6. Para el hito del lunes 19-10

Si se aprueban y mezclan los PR, y hacemos la sesión de despliegue, el lunes puede estar **la consola en la nube por NetBird, la base migrada y el respaldo diario funcionando**.

EXECUTE y NOTIFY se encienden cuando estén los agentes del laboratorio y el bot.

---
*Rodrigo · 15-10-2026*
