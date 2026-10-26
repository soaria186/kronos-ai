# Kronos AI — Estado al 20-10-2026 (19:45, hora de Chile) y plan en paralelo

Documento de traspaso para los chats de trabajo de cada integrante. Reemplaza como punto de partida a `KRO-ESTADO-2026-10-16_avance_y_pendientes.md`.

## 1. Lo que se logró el 20-10 (Nicolás y Patricio)

**Primera alerta real ejecutada por Kronos de punta a punta, sin intervención humana.**

| Hora (UTC) | Evento del ticket #20 | Quién |
| :--- | :--- | :--- |
| 22:04:14 | `ALERTA_RECIBIDA` (fuerza bruta SSH desde 203.0.113.50, regla 100101) | soar-validate |
| 22:04:25 | `DECISION`: F1, PB-F1-02, nivel 1, confianza 0,8, aprobada (11 s con la IA) | soar-validate |
| 22:36:12 | `EJECUCION_INICIADA` | soar-execute |
| 22:36:13 | `EJECUCION_OK`: EP-SRV-01 bloquea 203.0.113.50 con iptables | soar-execute |

La espera entre la decisión y la ejecución fue sólo porque EXECUTE estaba apagado. Con todo encendido, el total desde la alerta hasta el bloqueo es de unos 12 s. Reversión automática programada a los 60 min (23:36 UTC): **por confirmar**.

**Meta del Sprint 2 cumplida** (con un día de atraso) y **hito del 07-11 adelantado**: la contingencia ya no hace falta.

### Detalle de lo probado
- **Prueba con IP interna (10.0.50.1, puerta de enlace NAT de VirtualBox):**
  - la IA propuso PB-F1-02 y VALIDATE la rechazó con `PLAYBOOK_FUERA_DE_CATALOGO` («PB-F1-02 es para una IP externa»);
  - era correcto rechazarla: bloquear la puerta de enlace deja al equipo sin red;
  - un ticket terminó en `TIEMPO_EXCEDIDO` porque el modelo estaba frío.
- **Prueba con IP externa simulada** (`logger` con 203.0.113.50 en EP-SRV-01): 2 decisiones aprobadas.
  - Ticket #19: PB-F1-01, nivel 0 → `FAILED` al ejecutar (`ACCION_NO_IMPLEMENTADA`, esperado).
  - Ticket #20: PB-F1-02, nivel 1 → `SUCCESS`.
- **Usuario de API de Wazuh `kronos-execute`:**
  - usuario 100, rol 100, política de fábrica 6 `agents_commands_agents` (sólo `active-response:command` sobre `agent:id:*`);
  - la clave de `wazuh-wui` del gestor **no era la vigente**: se usó la del dashboard (`wazuh.yml`).
- **Verificado en Wazuh 4.14.8 (pregunta abierta #20 cerrada):**
  - la API acepta `"command": "!kronos-..."` **sin** `<command>` en el manager, así que no se tocó su configuración;
  - `arguments` llega al script en `parameters.extra_args` (JSON por stdin).
  - Formato exacto de `ejecucion/actuador_wazuh.py`: no requiere cambios.
- **Script `kronos-bloquear-ip` (Python, Linux):**
  - instalado en EP-SRV-01 (`/var/ossec/active-response/bin/`, `root:wazuh 750`, huella `089a23e5533dd17f`);
  - aplicar y quitar probados a mano y por EXECUTE.
- **EXECUTE encendido en SOAR-CORE-01:**
  - secretos `wazuh_api_password` y `wazuh_api_ca.pem` cargados (`root:10001 640`);
  - `KRONOS_WAZUH_NOMBRE_SERVIDOR=localhost`: el certificado de la API es autofirmado, con CN `wazuh.com`, SAN `localhost` y vence el 08-10-2027.
- **Tickets #1, #2 y #5 en `PENDING`:** son datos de las pruebas de integración de Patricio (16-10, inquilinos al azar, agente 003 inexistente). EXECUTE no los toma porque sólo atiende el inquilino 1. No se pueden borrar: quedan como evidencia.

### Hallazgos que pasan a pendientes
1. La puerta de enlace de cada cliente debe ir en la **lista de exclusión**. Con redirección de puertos, un ataque externo puede verse como si viniera del router.
2. El paso 2 debería saber si la IP es interna o externa (VALIDATE ya lo calcula).
3. Un mismo ataque generó varios tickets con decisiones distintas: hay que **agrupar** por origen y regla en una ventana de tiempo.
4. Plazo de la IA: subir de 60 a 120 s, o revisar por qué el modelo estaba frío.
5. Las pruebas de integración escriben en la base real: usar una base o un inquilino de prueba aparte.
6. **Gestor de contraseñas:**
   - actualizar `wazuh-wui`;
   - guardar `kronos-execute`;
   - descartar la clave que quedó escrita en el chat y regenerar la del agente 001.

## 2. Plan en paralelo hacia la farmacia

### Bloque A — desde ya, sin esperar a nadie
| Nicolás | Patricio | Rodrigo |
| :--- | :--- | :--- |
| [notebook] Confirmar la reversión del #20 (20:36 hora de Chile) | [PC] VALIDATE: IP interna o externa en el paso 2, plazo de 120 s, agrupar alertas, `10.0.50.1` excluida | [PC] Script de Windows `kronos-bloquear-ip` (`.cmd` + PowerShell, `netsh advfirewall`) |
| [notebook] EP-WKS-01: renombrar, `base-limpia` e instalar el agente 4.14.8 | [PC] Pruebas de integración contra una base aparte | [PC + servidor] Bot de Telegram y encender NOTIFY |
| [PC escritorio] PR con `kronos-bloquear-ip` (Linux) y la guía del usuario de API | [PC] Documento 02 §8.1 y `preguntas-abiertas.md` | [PC] Tope y retención de las alertas guardadas |
| [servidor] Regenerar la llave del agente 001; llave SSH propia de Rodrigo | | [PC] Revisar los PR #25 al #30 después del hecho |

Revisión cruzada de PR: Rodrigo revisa los de Nicolás, Nicolás los de Patricio y Patricio los de Rodrigo.

**Punto de encuentro 1 (los tres, unos 20 min):**
- decidir si los playbooks son de un solo paso;
- confirmar los 60 min de reversión del nivel 1;
- definir qué medidas se habilitan en la farmacia;
- asignar el inquilino por grupo de agentes de Wazuh;
- decidir si se parte en modo observación.

### Bloque B — después del punto de encuentro 1
| Nicolás | Patricio | Rodrigo |
| :--- | :--- | :--- |
| [notebook] Probar en EP-WKS-01 cada script de Windows (aplicar y quitar) | [PC] Catálogo y prompt del paso 2 sólo con las medidas habilitadas | [PC] Scripts de Windows del resto de medidas habilitadas |
| [servidor] Grupo `farmacia` y su inquilino en Wazuh | [PC] Asignación de inquilino por grupo en VALIDATE | [PC] Medidas no habilitadas desactivadas en EXECUTE |
| [PC escritorio] Copia del respaldo fuera del servidor | [PC] Playbook de los 150 casos y medición del paso 2 | [PC] CI para las pruebas de la consola |

Cadena: Rodrigo entrega los scripts de a uno y Nicolás los prueba mientras él escribe el siguiente.

**Punto de encuentro 2 — prueba integral en el laboratorio (los tres, unas 2 h):**
- casos de nivel 1, 2 y 3, la reversión, el vencimiento del nivel 3 y la aprobación por Telegram;
- en las dos VM.

### Bloque C — preparar la farmacia
- **Los tres, con la farmacia:**
  - inventario de equipos;
  - lista de exclusión (incluida la puerta de enlace);
  - redes internas;
  - salida al 1514;
  - fecha, contacto y plan de desinstalación;
  - acuerdo de datos con el proveedor (BR-05).
- **Nicolás:** registrar los agentes desde el servidor.
- **Patricio:** `validate.json` de la farmacia.
- **Rodrigo:** texto del correo a la persona afectada (D-35) y gestor y Telegram 2FA al día.

**Punto de encuentro 3:** instalación en la farmacia, en modo observación los primeros días.

**Ruta crítica:** EP-WKS-01 con agente → scripts de Windows → prueba integral → farmacia.

## 3. Reglas que siguen vigentes
- Nunca secretos en el chat ni en el repositorio. Las claves se cargan con `read -rs` y van al gestor.
- No tocar la configuración de Wazuh del servidor sin avisar a Nicolás.
- Cada PR lo aprueba otro integrante **antes** de mezclar.
- No pegar scripts largos en la terminal de la VM: se corta. Copiar el archivo con `scp -P 2222`.
- En Bash, desactivar la expansión del historial (`set +H`) antes de comandos con `!`.
- En pruebas manuales, nunca bloquear `10.0.50.1`: es por donde se entra a la VM.
