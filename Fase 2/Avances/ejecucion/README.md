# Ejecución (SOAR-EXECUTE)

Ejecuta las decisiones aprobadas de SOAR-VALIDATE como Active Response de Wazuh y
programa sus reversiones. Es el único actuador de Kronos.

| Módulo | Qué hace |
| :--- | :--- |
| `medidas.py` | Carga el catálogo KRO-CAT-01 (validado con `validacion.catalogo`) y entrega, por playbook, la acción, el nivel y cómo se revierte |
| `ordenes.py` | Traduce una acción a una orden cerrada: comando de una tabla fija, argumentos tomados de campos fijos de la alerta y validados (IP con `ipaddress`, cuentas y servicios con lista blanca de caracteres). Nunca el agente 000, nunca la IP del propio equipo, nunca cuentas como `root` o `Administrator` |
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
| `ACCION_NO_IMPLEMENTADA` | Acción sin comando todavía (`consulta`, `cuarentena`, `bloquear_destino`, `limitar_conexiones`, `revertir_tarea`), acción sin script en el sistema operativo del agente (por ejemplo, aislar un servidor Linux), o sistema operativo que no se pudo determinar |
| `ORDEN_INVALIDA` | La alerta no trae un objetivo válido o el valor no pasa la validación |
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
| `kronos-terminar-proceso` | `aplicar <pid>` | — | Fuera de la v1.0 |

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

## Lo que necesita Wazuh

Paso a paso en la parte 08 de la guía de instalación (`docs/instalacion/`).

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
