# Persistencia

Acceso a SOAR-AUDIT (PostgreSQL) desde los servicios de Kronos.

## `repositorio.py`

Capa que usan SOAR-VALIDATE, SOAR-EXECUTE y SOAR-NOTIFY, conectada como `kronos_worker`.

### VALIDATE

| Método | Qué hace |
| :--- | :--- |
| `registrar_alerta` | Crea el ticket de una alerta y el evento `ALERTA_RECIBIDA`. Si la alerta ya se había leído, devuelve el ticket existente (`UNIQUE (tenant_id, alerta_ref)`) |
| `registrar_decision` | Escribe el evento `DECISION` y actualiza el ticket en la misma transacción (R3). Aprobada de nivel 0 a 2: `PENDING` con playbook y nivel. Aprobada de nivel 3: `AWAITING_APPROVAL` con un temporizador de 2 días (D-32). Rechazada: `MANUAL_TRIAGE` con su motivo. Un ticket se decide una sola vez |
| `usos` | Uso de los contadores de tasa de `validate.json`, contando decisiones aprobadas de nivel 1 y 2 en su ventana |
| `alertas_en_ventana` | Tickets creados en la ventana: lo que mide el disparo del cortacircuito |
| `cortacircuito_abierto` / `abrir_cortacircuito` | Estado vigente y apertura, con su evento en la bitácora. Cerrarlo lo hace una persona desde SOAR-CONSOLE |

### EXECUTE, aprobaciones y avisos

| Método | Qué hace |
| :--- | :--- |
| `tomar_para_ejecutar` | Pasa a `EXECUTING` el `PENDING` con playbook más antiguo (`FOR UPDATE SKIP LOCKED`) y deja `EJECUCION_INICIADA` antes de enviar la orden. Devuelve la alerta que guardó VALIDATE |
| `registrar_ejecucion` | `EXECUTING` → `SUCCESS` o `FAILED`, con `EJECUCION_OK` o `EJECUCION_FALLIDA`. Si salió bien: temporizador `REVERSION` (nivel 1 con plazo) o `REVISION` de 2 días (nivel 2, D-33) |
| `aprobar` / `denegar` | Nivel 3: `AWAITING_APPROVAL` → `PENDING` o `REJECTED`. La persona queda como actor del evento |
| `vencer_aprobaciones` | Nivel 3 sin respuesta en 2 días → `MANUAL_TRIAGE` con `APROBACION_VENCIDA` (D-34) |
| `solicitar_reversion` | Una persona pide revertir una medida en `SUCCESS` (nivel 2, o nivel 1 antes de su plazo) |
| `tomar_reversion` / `registrar_reversion` | Reversión vencida o pedida: `REVERSION_INICIADA` y luego `REVERSION_OK` o `REVERSION_FALLIDA`. Tras revertir, terminan los recordatorios |
| `tomar_recordatorios` | Nivel 2 con el plazo de revisión vencido: `RECORDATORIO_REVISION` y el siguiente en un día. La medida nunca se revierte sola |
| `eventos_para_avisar` / `registrar_aviso` | SOAR-NOTIFY: eventos a avisar desde el último `AVISO_ENVIADO`, y la constancia de cada aviso |

### Estados del ticket

```
PENDING sin playbook ── rechazada ──> MANUAL_TRIAGE
     │ aprobada nivel 0-2          │ aprobada nivel 3
     v                             v
PENDING con playbook <── aprobar ── AWAITING_APPROVAL ── denegar ──> REJECTED
     │ EXECUTE la toma                   └── vence ──> MANUAL_TRIAGE (APROBACION_VENCIDA)
     v
EXECUTING ──> SUCCESS | FAILED
```

- `FAILED` no se reintenta solo; una persona decide.
- Un ticket que quedó en `EXECUTING` (EXECUTE se cayó tras enviar) no se retoma solo: la orden pudo haber llegado.
- La reversión no cambia el estado: queda en la bitácora y en `temporizadores`.

Reglas:

- Cada operación es una transacción que fija `app.tenant_id` sólo para esa transacción. Sin inquilino fijado, RLS falla cerrado.
- No importa `validacion` ni `decision`: recibe y entrega tipos simples.
- Un contador que no se puede calcular (desconocido, o sin equipo o playbook) no aparece en el resultado; `validacion.configuracion` lo trata como si estuviera en su tope.

## Pruebas

`tests/integracion/test_repositorio.py`, `test_ejecucion.py` y `test_notificacion.py`, contra la base de `infra/docker` (ver el Dockerfile de esa carpeta). Sin la variable `KRONOS_DSN`, se omiten.
