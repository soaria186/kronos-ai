-- Migración 2026-10-15
--
-- Aplica sobre una base creada con la versión anterior de 02_esquema.sql:
--   1. Dos motivos de rechazo nuevos: FAMILIA_NO_COINCIDE y APROBACION_VENCIDA.
--   2. Una alerta sólo puede crear un ticket por inquilino: UNIQUE (tenant_id, alerta_ref).
--
-- Es idempotente: se puede ejecutar dos veces sin error.
-- Ejecutar como kronos_admin:
--   docker exec -i <contenedor-db> psql -U kronos_admin -d kronos -v ON_ERROR_STOP=1 < 2026-10-15_motivos_y_alerta_unica.sql

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
    'APROBACION_VENCIDA'
));

ALTER TABLE tickets DROP CONSTRAINT IF EXISTS tickets_tenant_id_alerta_ref_key;
ALTER TABLE tickets ADD CONSTRAINT tickets_tenant_id_alerta_ref_key UNIQUE (tenant_id, alerta_ref);

COMMIT;

-- Verificación: deben aparecer las dos restricciones.
SELECT conname, pg_get_constraintdef(oid) AS definicion
FROM pg_constraint
WHERE conrelid = 'tickets'::regclass
  AND conname IN ('tickets_rechazo_motivo_check', 'tickets_tenant_id_alerta_ref_key')
ORDER BY conname;
