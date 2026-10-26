-- Script de pgbench: cada transacción inserta una fila de auditoría del inquilino
-- :tenant. :client_id identifica la conexión (0..N-1).
SET app.tenant_id = :tenant;
INSERT INTO auditoria (tenant_id, evento, actor, detalle)
VALUES (:tenant, 'prueba.concurrencia', 'conexion-' || :client_id,
        jsonb_build_object('cliente', :client_id, 'pid', pg_backend_pid()));
