-- d) Paso 1 (superusuario, SÓLO sobre la copia de prueba): desactiva el trigger de
--    inmutabilidad y altera filas a mano de tres formas distintas.
-- Variables: ta, tb, tc.
\set ON_ERROR_STOP on
DO $$
BEGIN
    IF current_database() <> 'kronos_copia_prueba' THEN
        RAISE EXCEPTION 'd_manipular.sql sólo se ejecuta sobre kronos_copia_prueba, no sobre %',
            current_database();
    END IF;
END;
$$;

SELECT current_database() AS base, current_user AS rol;

ALTER TABLE auditoria DISABLE TRIGGER trg_auditoria_inmutable;

-- 1) Contenido alterado sin tocar el hash.
UPDATE auditoria SET detalle = detalle || '{"manipulado": true}'
 WHERE tenant_id = :tc AND seq = 400;

-- 2) Contenido alterado y hash de la fila recalculado (falsificación "cuidadosa").
UPDATE auditoria SET evento = 'evento.falsificado' WHERE tenant_id = :ta AND seq = 100;
UPDATE auditoria a SET hash = fn_auditoria_hash(a) WHERE tenant_id = :ta AND seq = 100;

-- 3) Fila eliminada.
DELETE FROM auditoria WHERE tenant_id = :tb AND seq = 50;

ALTER TABLE auditoria ENABLE ALWAYS TRIGGER trg_auditoria_inmutable;
\echo 'Manipulaciones aplicadas en la copia.'
