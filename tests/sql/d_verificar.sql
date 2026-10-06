-- d) Paso 2 (kronos_worker, sobre la copia): fn_verificar_cadena debe señalar cada
--    manipulación en la primera fila afectada.
-- Variables: ta, tb, tc.
\set ON_ERROR_STOP on
SELECT set_config('prueba.ta', :'ta', false) AS ta,
       set_config('prueba.tb', :'tb', false) AS tb,
       set_config('prueba.tc', :'tc', false) AS tc \gset

SELECT current_database() AS base, current_user AS rol;

SET app.tenant_id = :'tc';
SELECT :tc AS inquilino, 'detalle de seq 400 alterado' AS manipulacion, d.*
  FROM fn_verificar_cadena(:tc) d;
SET app.tenant_id = :'ta';
SELECT :ta AS inquilino, 'seq 100 alterada y su hash recalculado' AS manipulacion, d.*
  FROM fn_verificar_cadena(:ta) d;
SET app.tenant_id = :'tb';
SELECT :tb AS inquilino, 'seq 50 eliminada' AS manipulacion, d.*
  FROM fn_verificar_cadena(:tb) d;

DO $$
DECLARE
    casos text[] := ARRAY[
        [current_setting('prueba.tc'), '400', 'el hash no coincide%'],
        [current_setting('prueba.ta'), '101', 'hash_anterior no enlaza%'],
        [current_setting('prueba.tb'), '50', 'falta seq 50%']
    ];
    i int;
    d auditoria_discontinuidad;
BEGIN
    FOR i IN 1 .. array_length(casos, 1) LOOP
        PERFORM set_config('app.tenant_id', casos[i][1], false);
        d := fn_verificar_cadena(casos[i][1]::int);
        IF d IS NULL OR d.seq <> casos[i][2]::bigint OR d.motivo NOT LIKE casos[i][3] THEN
            RAISE EXCEPTION 'FALLO: inquilino % devolvió %, se esperaba seq % (%)',
                casos[i][1], d, casos[i][2], casos[i][3];
        END IF;
        RAISE NOTICE 'OK inquilino %: discontinuidad detectada en seq % (%)',
            casos[i][1], d.seq, d.motivo;
    END LOOP;
END;
$$;
\echo 'Manipulaciones detectadas en la copia.'
