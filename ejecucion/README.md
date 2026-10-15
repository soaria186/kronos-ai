# Ejecución (SOAR-EXECUTE)

Ejecuta las decisiones aprobadas de SOAR-VALIDATE como Active Response de Wazuh y
programa sus reversiones. Es el único actuador de Kronos.

| Módulo | Qué hace |
| :--- | :--- |
| `medidas.py` | Carga el catálogo KRO-CAT-01 (validado con `validacion.catalogo`) y entrega, por playbook, la acción, el nivel y cómo se revierte |
| `ordenes.py` | Traduce una acción a una orden cerrada: comando de una tabla fija, argumentos tomados de campos fijos de la alerta y validados (IP con `ipaddress`, cuentas y servicios con lista blanca de caracteres). Nunca el agente 000, nunca la IP del propio equipo, nunca cuentas como `root` o `Administrator` |
| `actuador.py` | Interfaz del actuador. El actuador real (API de Wazuh por NetBird, usuario de permisos mínimos) va en un PR aparte |
| `ejecutor.py` | Un ciclo por inquilino: vence aprobaciones de nivel 3, ejecuta los tickets `PENDING` y las reversiones vencidas |

## Falla segura

El ticket queda en `FAILED`, con el motivo en la bitácora, y nada se reintenta solo, si:

| Motivo | Cuándo |
| :--- | :--- |
| `PLAYBOOK_SIN_MEDIDA` | El playbook no está en el catálogo cargado |
| `PLAZO_DE_REVERSION_SIN_DEFINIR` | Reversión automática sin `plazo_minutos` en el catálogo (hoy, todos los de nivel 1) |
| `ACCION_NO_IMPLEMENTADA` | Acción sin comando todavía: `consulta`, `cuarentena`, `bloquear_destino`, `limitar_conexiones`, `revertir_tarea` |
| `ORDEN_INVALIDA` | La alerta no trae un objetivo válido o el valor no pasa la validación |
| `ACTUADOR_FALLO` | La orden no se pudo entregar |

## Contrato con VALIDATE

EXECUTE lee la alerta del evento `ALERTA_RECIBIDA` del ticket: VALIDATE debe guardar la
alerta de Wazuh en `detalle["alerta"]` (al menos `agent.id`, `agent.ip` y los campos de
`data` que usa `ordenes.py`).

## Comandos de Active Response

Cada agente necesita un script por comando, que recibe la operación y el objetivo:

| Comando | Aplicar | Revertir |
| :--- | :--- | :--- |
| `kronos-bloquear-ip` | `aplicar <ip>` | `quitar <ip>` |
| `kronos-aislar-equipo` | `aplicar` | `quitar` |
| `kronos-deshabilitar-cuenta` | `aplicar <cuenta>` | `habilitar <cuenta>` |
| `kronos-detener-servicio` | `aplicar <servicio>` | `iniciar <servicio>` |
| `kronos-cerrar-sesion` | `aplicar <cuenta>` | — (la persona vuelve a entrar) |
| `kronos-terminar-proceso` | `aplicar <pid>` | — |
