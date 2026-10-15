# Ejecución (SOAR-EXECUTE)

Ejecuta las decisiones aprobadas de SOAR-VALIDATE como Active Response de Wazuh y
programa sus reversiones. Es el único actuador de Kronos.

| Módulo | Qué hace |
| :--- | :--- |
| `medidas.py` | Carga el catálogo KRO-CAT-01 (validado con `validacion.catalogo`) y entrega, por playbook, la acción, el nivel y cómo se revierte |
| `ordenes.py` | Traduce una acción a una orden cerrada: comando de una tabla fija, argumentos tomados de campos fijos de la alerta y validados (IP con `ipaddress`, cuentas y servicios con lista blanca de caracteres). Nunca el agente 000, nunca la IP del propio equipo, nunca cuentas como `root` o `Administrator` |
| `actuador.py` | Interfaz del actuador |
| `actuador_wazuh.py` | Actuador real: `PUT /active-response` por la API de Wazuh. HTTPS con verificación obligatoria, token renovado, un solo envío por orden |
| `ejecutor.py` | Un ciclo por inquilino: vence aprobaciones de nivel 3, ejecuta los tickets `PENDING` y las reversiones vencidas |
| `__main__.py` | Servicio: `python -m ejecucion`, un ciclo por inquilino cada N segundos |

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

## Lo que falta en Wazuh (a cargo de Nicolás)

1. **Usuario de API de permisos mínimos.** Usuario `kronos-execute` con un rol cuya única
   política sea `{"actions": ["active-response:command"], "resources": ["agent:id:*"],
   "effect": "allow"}`. Contraseña al gestor y al archivo de secreto, nunca al repositorio.
2. **Comandos en el manager.** Un `<command>` por cada comando de la tabla anterior, **sin**
   bloques `<active-response>`: el Active Response automático debe seguir apagado (Kronos
   es el único actuador).
3. **Scripts en los agentes.** Uno por comando en `active-response/bin`, que reciba
   `aplicar`/`quitar` y el objetivo.
4. **Certificado de la API.** Copiar el certificado que presenta el 55000 para
   `KRONOS_WAZUH_CA` y anotar su nombre (CN o SAN).

**Por verificar en el laboratorio (Wazuh 4.14.8):** que la API acepte el comando con el
prefijo `!` y entregue `arguments` al script tal como los envía `actuador_wazuh.py`.
