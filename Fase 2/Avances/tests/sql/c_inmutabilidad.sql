-- c) UPDATE, DELETE y TRUNCATE sobre auditoria y cortacircuito fallan.
--    Se ejecuta dos veces: como kronos_worker y como kronos_admin (superusuario).
--    Con el superusuario se repite con session_replication_role = replica.
-- Variables: tc (inquilino con filas de la prueba b).
\set ON_ERROR_STOP on
SELECT set_config('prueba.tc', :'tc', false) AS tc \gset
SET app.tenant_id = :'tc';

INSERT INTO cortacircuito (tenant_id, ambito, abierto, motivo)
VALUES (:tc, 'playbook:aislar_host', true, 'prueba de inmutabilidad');

SELECT current_user AS rol, rolsuper AS superusuario, rolbypassrls AS salta_rls
  FROM pg_roles WHERE rolname = current_user;

DO $$
DECLARE
    sentencias text[] := ARRAY[
        'UPDATE auditoria SET evento = ''alterado'' WHERE seq = 1',
        'UPDATE auditoria SET evento = ''alterado'' WHERE false',
        'DELETE FROM auditoria WHERE seq = 1',
        'DELETE FROM auditoria WHERE false',
        'TRUNCATE auditoria',
        'UPDATE cortacircuito SET abierto = false',
        'DELETE FROM cortacircuito',
        'TRUNCATE cortacircuito'
    ];
    es_super  boolean := (SELECT rolsuper FROM pg_roles WHERE rolname = current_user);
    modos     text[] := ARRAY['origin'];
    modo      text;
    s         text;
    rechazado boolean;
    estado    text;
    mensaje   text;
BEGIN
    IF es_super THEN
        modos := modos || 'replica'::text;
    END IF;
    FOREACH modo IN ARRAY modos LOOP
        IF es_super THEN
            PERFORM set_config('session_replication_role', modo, true);
        END IF;
        FOREACH s IN ARRAY sentencias LOOP
            rechazado := false;
            BEGIN
                EXECUTE s;
            EXCEPTION WHEN OTHERS THEN
                rechazado := true;
                GET STACKED DIAGNOSTICS estado = RETURNED_SQLSTATE, mensaje = MESSAGE_TEXT;
            END;
            IF NOT rechazado THEN
                RAISE EXCEPTION 'FALLO: "%" se ejecutó como % (session_replication_role=%)',
                    s, current_user, modo;
            END IF;
            -- Al superusuario no lo frenan los permisos: debe frenarlo el trigger.
            IF es_super AND mensaje NOT LIKE '%sólo admite INSERT%' THEN
                RAISE EXCEPTION 'FALLO: "%" falló por otra causa: %', s, mensaje;
            END IF;
            RAISE NOTICE 'OK rechazado | % | replication_role=% | % | [%] %',
                current_user, modo, s, estado, mensaje;
        END LOOP;
    END LOOP;
END;
$$;

SELECT count(*) AS filas_auditoria_inquilino,
       fn_verificar_cadena(:tc) IS NULL AS cadena_integra
  FROM auditoria WHERE tenant_id = :tc;
\echo 'PRUEBA C: OK para' :USER
