# Persistencia

Acceso a SOAR-AUDIT (PostgreSQL) desde los servicios de Kronos.

## `repositorio.py`

Capa que usa SOAR-VALIDATE, conectada como `kronos_worker`:

| Método | Qué hace |
| :--- | :--- |
| `registrar_alerta` | Crea el ticket de una alerta y el evento `ALERTA_RECIBIDA`. Si la alerta ya se había leído, devuelve el ticket existente (`UNIQUE (tenant_id, alerta_ref)`) |
| `registrar_decision` | Escribe el evento `DECISION` y actualiza el ticket en la misma transacción (R3). Aprobada: `PENDING` con playbook y nivel. Rechazada: `MANUAL_TRIAGE` con su motivo. Un ticket se decide una sola vez |
| `usos` | Uso de los contadores de tasa de `validate.json`, contando decisiones aprobadas de nivel 1 y 2 en su ventana |
| `alertas_en_ventana` | Tickets creados en la ventana: lo que mide el disparo del cortacircuito |
| `cortacircuito_abierto` / `abrir_cortacircuito` | Estado vigente y apertura, con su evento en la bitácora. Cerrarlo lo hace una persona desde SOAR-CONSOLE |

Reglas:

- Cada operación es una transacción que fija `app.tenant_id` sólo para esa transacción. Sin inquilino fijado, RLS falla cerrado.
- No importa `validacion` ni `decision`: recibe y entrega tipos simples.
- Un contador que no se puede calcular (desconocido, o sin equipo o playbook) no aparece en el resultado; `validacion.configuracion` lo trata como si estuviera en su tope.

## Pruebas

`tests/integracion/test_repositorio.py`, contra la base de `infra/docker` (ver el Dockerfile de esa carpeta). Sin la variable `KRONOS_DSN`, se omiten.
