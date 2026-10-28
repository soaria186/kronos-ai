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
| `ACCION_NO_IMPLEMENTADA` | Acción sin comando todavía: `consulta`, `cuarentena`, `bloquear_destino`, `limitar_conexiones`, `revertir_tarea` |
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

**Ojo:** la API de Wazuh confirma que la orden llegó al agente, no que el script exista ni
que haya funcionado. Si el comando no tiene script en ese agente, el agente registra
`Could not launch command`, no pasa nada en el equipo y el ticket igual queda en `SUCCESS`.
Para que las medidas fuera del alcance de la v1.0 (D-60) terminen en falla segura con aviso,
EXECUTE tiene que saber qué comandos tiene cada sistema operativo (#56).

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
   `!kronos-bloquear-ip.cmd` (prueba del 21-10-2026 en EP-WKS-01, #43; el cambio en EXECUTE
   está en #56).
4. **Certificado de la API.** El que presenta el 55000, como `KRONOS_WAZUH_CA`. El de fábrica
   dice CN `wazuh.com` y SAN `localhost`, por eso `KRONOS_WAZUH_NOMBRE_SERVIDOR=localhost`.
