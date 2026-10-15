-- Migración 2026-10-15 (b)
--
-- Aplica sobre una base que ya tiene la migración 2026-10-15_motivos_y_alerta_unica.sql:
--   1. Estado nuevo AWAITING_APPROVAL: un ticket de nivel 3 espera ahí la aprobación
--      del equipo. SOAR-EXECUTE sólo toma tickets en PENDING, así que un nivel 3
--      nunca se ejecuta sin aprobación.
--   2. El índice de tickets activos incluye el estado nuevo.
--
-- Es idempotente: se puede ejecutar dos veces sin error.
-- Ejecutar como kronos_admin:
--   docker exec -i <contenedor-db> psql -U kronos_admin -d kronos -v ON_ERROR_STOP=1 < 2026-10-15_estado_espera_aprobacion.sql

BEGIN;

ALTER TABLE tickets DROP CONSTRAINT IF EXISTS tickets_execution_status_check;
ALTER TABLE tickets ADD CONSTRAINT tickets_execution_status_check CHECK (execution_status IN (
    'PENDING', 'AWAITING_APPROVAL', 'EXECUTING', 'SUCCESS', 'FAILED', 'REJECTED',
    'MANUAL_TRIAGE'
));

DROP INDEX IF EXISTS tickets_activos_idx;
CREATE INDEX tickets_activos_idx
    ON tickets (tenant_id, execution_status)
    WHERE execution_status IN ('PENDING', 'AWAITING_APPROVAL', 'EXECUTING');

COMMIT;

-- Verificación: la restricción debe incluir AWAITING_APPROVAL y el índice también.
SELECT pg_get_constraintdef(oid) AS estados
  FROM pg_constraint
 WHERE conrelid = 'tickets'::regclass AND conname = 'tickets_execution_status_check';
SELECT indexdef FROM pg_indexes WHERE indexname = 'tickets_activos_idx';
