# Ejecución (SOAR-EXECUTE)

Ejecuta las decisiones aprobadas de SOAR-VALIDATE como Active Response de Wazuh y
programa sus reversiones. Es el único actuador de Kronos.

| Módulo | Qué hace |
| :--- | :--- |
| `medidas.py` | Carga el catálogo KRO-CAT-01 (validado con `validacion.catalogo`) y entrega, por playbook, la acción, el nivel y cómo se revierte |
| `ordenes.py` | Traduce una acción a una orden cerrada: comando de una tabla fija, argumentos tomados de campos fijos de la alerta y validados (IP con `ipaddress`; cuentas, servicios, rutas y tareas con lista blanca de caracteres). Nunca el agente 000, la IP del propio equipo, las IP de `KRONOS_IP_PROTEGIDAS`, cuentas como `root` o `Administrator`, ni archivos de las carpetas del sistema, del agente o de Kronos |
| `consulta.py` | Interfaz de la consulta de nivel 0 (D-72): inventario del agente por la API de Wazuh, sin Active Response |
| `consulta_wazuh.py` | Consulta real de nivel 0: lee syscollector (sistema, procesos, puertos en escucha y red) con `ActuadorWazuh.leer` y arma un resumen corto para la bitácora |
| `actuador.py` | Interfaz del actuador |
| `actuador_wazuh.py` | Actuador real: `PUT /active-response` por la API de Wazuh. HTTPS con verificación obligatoria, token renovado, un solo envío por orden |
| `ejecutor.py` | Un ciclo por inquilino: pasa a revisión manual los tickets huérfanos (sin decisión de VALIDATE a los 10 minutos), vence aprobaciones de nivel 3, ejecuta los tickets `PENDING` y las reversiones vencidas |
| `__main__.py` | Servicio: `python -m ejecucion`, un ciclo por inquilino cada N segundos |

## Falla segura

El ticket queda en `FAILED`, con el motivo en la bitácora, y nada se reintenta solo, si:

| Motivo | Cuándo |
| :--- | :--- |
| `PLAYBOOK_SIN_MEDIDA` | El playbook no está en el catálogo cargado |
| `PLAZO_DE_REVERSION_SIN_DEFINIR` | Reversión automática sin `plazo_minutos` en el catálogo. Desde KRO-CAT-01 0.2, las cinco medidas de nivel 1 con reversión automática tienen 60 minutos (D-45) |
| `ACCION_NO_IMPLEMENTADA` | Acción sin comando (`consulta` sin consulta de inventario configurada), acción que no está en `actuadores_v1` para el sistema operativo del agente (por ejemplo, aislar un servidor Linux), o sistema operativo que no se pudo determinar |
| `ARGUMENTO_FALTANTE` | La alerta no trae el campo que la medida necesita (la ruta del archivo, el nombre de la tarea, la IP, la cuenta, el servicio o el PID). Nunca se adivina |
| `ORDEN_INVALIDA` | El valor no pasa la validación, está protegido (cuenta, IP o carpeta) o la alerta no trae un `agent.id` válido |
| `CONSULTA_FALLIDA` | Nivel 0: la API de Wazuh no entregó el inventario del agente |
| `ACTUADOR_FALLO` | La orden no se pudo entregar |

## Contrato con VALIDATE

VALIDATE entrega la alerta de Wazuh en `detalle["alerta"]` de `registrar_alerta` (al menos
`agent.id`, `agent.ip` y los campos de `data` que usa `ordenes.py`). La persistencia la guarda
en `alertas_guardadas` y EXECUTE la recibe como `{"alerta": {...}}` (en tickets antiguos, desde
el evento `ALERTA_RECIBIDA`). Si la alerta ya fue purgada por retención, llega `{}` y el ticket
queda en `FAILED` con `ORDEN_INVALIDA`: ver `persistencia/README.md`.

## Comandos de Active Response

Cada agente necesita un script por comando, que recibe la operación y el objetivo
(`infra/wazuh/active-response/`):

| Comando | Aplicar | Revertir | Script |
| :--- | :--- | :--- | :--- |
| `kronos-bloquear-ip` | `aplicar <ip>` | `quitar <ip>` | Linux y Windows |
| `kronos-aislar-equipo` | `aplicar` | `quitar` | Windows, en la v1.0 (#57) |
| `kronos-deshabilitar-cuenta` | `aplicar <cuenta>` | `habilitar <cuenta>` | Windows, en la v1.0 (#55) |
| `kronos-detener-servicio` | `aplicar <servicio>` | `iniciar <servicio>` | Fuera de la v1.0 |
| `kronos-cerrar-sesion` | `aplicar <cuenta>` | — (la persona vuelve a entrar) | Fuera de la v1.0 |
| `kronos-terminar-proceso` | `aplicar <pid> <ejecutable>` | — | D-69 |
| `kronos-cuarentena` | `aplicar <ruta>` | `restaurar <ruta>` | D-69 |
| `kronos-bloquear-destino` | `aplicar <ip>` | `quitar <ip>` | D-69 |
| `kronos-limitar-conexiones` | `aplicar <ip>` | `quitar <ip>` | D-69 (en Windows, bloqueo de 10 min, D-71) |
| `kronos-revertir-tarea` | `aplicar <tarea>` | `habilitar <tarea>` | D-69 |

Un comando en esta tabla no basta para actuar: la acción tiene que estar además en
`actuadores_v1` del catálogo para el sistema del agente, y eso lo activa el PR de cada
script, una vez probado en la VM (D-69 y D-70).

### Campos de la alerta por acción

Se toma el primero que exista, en este orden. Si no hay ninguno, `ARGUMENTO_FALTANTE`.

| Acción | Campos | Validación |
| :--- | :--- | :--- |
| `bloquear_ip`, `limitar_conexiones` | `data.srcip`, `data.win.eventdata.ipAddress` | `ipaddress`; nunca loopback, multicast, enlace local, la IP del equipo ni las de `KRONOS_IP_PROTEGIDAS` |
| `bloquear_destino` | `data.dstip`, `data.win.eventdata.destinationIp` | Igual que la anterior |
| `deshabilitar_cuenta`, `cerrar_sesion` | `data.dstuser`, `data.win.eventdata.targetUserName`, `data.srcuser` | `[A-Za-z0-9._-]`, sin cuentas protegidas |
| `detener_servicio` | `data.win.eventdata.serviceName` | `[A-Za-z0-9._@-]` |
| `terminar_proceso` | PID: `data.win.eventdata.processId`, `data.audit.pid`. Ejecutable: `data.win.eventdata.image`, `data.audit.exe` | PID: número, 5 o más. Ejecutable: la misma forma de ruta que la cuarentena, pero **sin** las carpetas protegidas (un `powershell.exe` se puede terminar). El script confirma que el PID siga siendo ese programa |
| `cuarentena` | `syscheck.path`, `data.win.eventdata.image`, `data.audit.exe` (el orden de la categoría «programa» de la lista de exclusión) | Ruta absoluta con la forma del sistema del agente (`C:\…` o `/…`), sin `.` ni `..`, sin `~`, sin caracteres de shell ni comodines, y fuera de `C:\Windows`, las carpetas del agente, de NetBird y de Kronos, o de `/bin`, `/boot`, `/dev`, `/etc`, `/lib*`, `/proc`, `/run`, `/sbin`, `/sys`, `/usr`, `/var/lib` y `/var/ossec` |
| `revertir_tarea` | Windows: `data.win.eventdata.taskName`. Linux: `syscheck.path` | Windows: `\carpeta\tarea`, con la misma lista de caracteres. Linux: un archivo de `/etc/crontab`, `/etc/cron.*/`, `/var/spool/cron/` o un `.timer` de `/etc/systemd/system/` |

## Consulta de nivel 0 (D-72)

La acción `consulta` no tiene script: EXECUTE llama a la consulta configurada
(`ejecucion.consulta.Consulta`), que pide a la API de Wazuh el inventario del agente
(syscollector) con el usuario de EXECUTE. El resumen queda en el detalle del ticket, que
termina en `SUCCESS` sin aviso (D-50; hallazgo H1 de la prueba integral del 03-11). No
depende de `actuadores_v1` ni del sistema operativo. Si no hay consulta configurada, el
ticket queda como antes, en `FAILED` con `ACCION_NO_IMPLEMENTADA`, que en el nivel 0 no se
avisa.

## Sistema operativo del agente

La API de Wazuh confirma que la orden llegó al agente, no que el script exista ni que haya
funcionado: si el comando no tiene script en ese agente, el agente registra
`Could not launch command`, no pasa nada en el equipo y el ticket quedaría en `SUCCESS`. Por
eso, antes de armar cada orden (y cada reversión), EXECUTE:

1. **Determina el sistema operativo del agente** (`ordenes.sistema_operativo`):
   - manda el mapa `KRONOS_AGENTES_SO` (por ejemplo `001:linux,002:windows`); un formato
     inválido impide que el servicio arranque;
   - si el agente no está en el mapa, se deduce de la alerta. Windows: existe `data.win`,
     `location` es `EventChannel`, `decoder.name` empieza con `windows` o `syscheck.path`
     empieza con una letra de unidad (`C:\`). Linux: `syscheck.path` o `location` empiezan
     con `/`, o `location` es `journald`;
   - si no se puede saber, o el mapa y la alerta se contradicen, no se actúa.
2. **Comprueba que la acción tenga script en ese sistema**, según `actuadores_v1` del
   catálogo (D-60): en la v1.0, Linux sólo `bloquear_ip`; Windows `bloquear_ip`,
   `deshabilitar_cuenta` y `aislar_equipo`.

Si falla cualquiera de los dos, no se envía nada y el ticket queda en `FAILED` con
`ACCION_NO_IMPLEMENTADA` (NOTIFY avisa «esta medida no está disponible en esta versión de
Kronos»); el detalle de la bitácora dice cuál de los dos fue. En una reversión, la reversión
queda registrada como fallida y se avisa.

`KRONOS_WAZUH_USUARIO` no puede consultar la API de agentes (sólo tiene
`active-response:command`), y ampliarle el permiso iría contra el mínimo privilegio: por eso
el sistema va en la configuración y no se pregunta a Wazuh.

**Windows necesita la extensión.** El agente sólo encuentra el script si el comando la lleva,
así que para un agente Windows se envía `!kronos-bloquear-ip.cmd` (prueba del 21-10-2026 en
EP-WKS-01) y para uno Linux `!kronos-bloquear-ip`. La orden de la bitácora guarda el sistema y
la referencia guarda el nombre enviado (`wazuh-ar:002:kronos-bloquear-ip.cmd`).

## Servicio

| Variable | Qué es |
| :--- | :--- |
| `KRONOS_DSN` | Conexión como `kronos_worker`, **sin** contraseña (`host=db dbname=kronos user=kronos_worker`) |
| `KRONOS_DB_CLAVE_ARCHIVO` | Archivo con la contraseña de `kronos_worker` (secreto de Docker) |
| `KRONOS_INQUILINOS` | Inquilinos a atender, separados por coma |
| `KRONOS_INTERVALO_SEGUNDOS` | Pausa entre ciclos (10 por omisión) |
| `KRONOS_WAZUH_URL` | `https://<host>:55000` |
| `KRONOS_WAZUH_USUARIO` | Usuario de API `kronos-execute` |
| `KRONOS_WAZUH_CLAVE_ARCHIVO` | Archivo con su contraseña |
| `KRONOS_WAZUH_CA` | Certificado (o CA) de la API de Wazuh |
| `KRONOS_WAZUH_NOMBRE_SERVIDOR` | Nombre del certificado, si no es el host de la URL |
| `KRONOS_AGENTES_SO` | Sistema operativo de cada agente, `agente:linux` o `agente:windows` separados por coma (opcional; ver arriba) |
| `KRONOS_IP_PROTEGIDAS` | IP sobre las que nunca se actúa, separadas por coma: el manager y la puerta de enlace (opcional, recomendado). Una IP inválida impide que el servicio arranque |

## Lo que necesita Wazuh

Paso a paso en la [parte 08 de la guía de instalación](../../../Instalacion/04-Wazuh/08-active-response.md).

1. **Usuario de API de permisos mínimos.** `kronos-execute`, con un rol propio unido a la
   política de fábrica `agents_commands_agents` (sólo `active-response:command` sobre
   `agent:id:*`). Creado el 20-10-2026. Su contraseña va al gestor del equipo y al archivo de
   secreto, nunca al repositorio.
2. **Sin cambios en el manager.** Wazuh 4.14.8 acepta el comando con el prefijo `!` sin
   declarar un `<command>` en su configuración, y entrega `arguments` al script en
   `parameters.extra_args` (verificado el 20-10-2026). No hay bloques `<active-response>`: el
   Active Response automático sigue apagado y Kronos es el único actuador.
3. **Scripts en los agentes**, uno por comando, en `active-response/bin` (tabla de arriba).
   En Windows el agente sólo encuentra el script si el comando lleva la extensión:
   `!kronos-bloquear-ip.cmd` (prueba del 21-10-2026 en EP-WKS-01, #43). EXECUTE la agrega
   según `KRONOS_AGENTES_SO` (sección «Sistema operativo del agente»).
4. **Certificado de la API.** El que presenta el 55000, como `KRONOS_WAZUH_CA`. El de fábrica
   dice CN `wazuh.com` y SAN `localhost`, por eso `KRONOS_WAZUH_NOMBRE_SERVIDOR=localhost`.
