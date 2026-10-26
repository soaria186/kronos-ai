-- Migración 2026-10-21
--
-- Motivo de rechazo nuevo: DECISION_NO_REGISTRADA. Lo usa SOAR-EXECUTE para pasar a
-- revisión manual los tickets huérfanos: PENDING sin playbook ni decisión 10 minutos
-- después de creados (VALIDATE falló entre crear el ticket y registrar la decisión).
--
-- Es idempotente: se puede ejecutar dos veces sin error.
-- Ejecutar como kronos_admin:
--   docker exec -i <contenedor-db> psql -U kronos_admin -d kronos -v ON_ERROR_STOP=1 < 2026-10-21_motivo_decision_no_registrada.sql

BEGIN;

ALTER TABLE tickets DROP CONSTRAINT IF EXISTS tickets_rechazo_motivo_check;
ALTER TABLE tickets ADD CONSTRAINT tickets_rechazo_motivo_check CHECK (rechazo_motivo IN (
    'ESQUEMA_INVALIDO',
    'CONFIANZA_BAJA',
    'PLAYBOOK_FUERA_DE_CATALOGO',
    'ACTIVO_EXCLUIDO',
    'LIMITE_DE_TASA',
    'CORTACIRCUITO_ABIERTO',
    'NIVEL_NO_PERMITIDO_POR_SEVERIDAD',
    'MOTOR_INFERENCIA_NO_DISPONIBLE',
    'TIEMPO_EXCEDIDO',
    'FAMILIA_NO_COINCIDE',
    'APROBACION_VENCIDA',
    'DECISION_NO_REGISTRADA'
));

COMMIT;

-- Verificación: la restricción debe incluir DECISION_NO_REGISTRADA.
SELECT conname, pg_get_constraintdef(oid) AS definicion
FROM pg_constraint
WHERE conrelid = 'tickets'::regclass
  AND conname = 'tickets_rechazo_motivo_check';
