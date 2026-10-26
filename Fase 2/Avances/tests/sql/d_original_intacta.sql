-- d) Paso 3 (kronos_worker, sobre la base original): las cadenas siguen íntegras.
-- Variables: ta, tb, tc.
\set ON_ERROR_STOP on
SELECT set_config('prueba.inquilinos', concat_ws(',', :'ta', :'tb', :'tc'), false) AS i \gset
DO $$
DECLARE
    t int;
BEGIN
    FOREACH t IN ARRAY string_to_array(current_setting('prueba.inquilinos'), ',')::int[] LOOP
        PERFORM set_config('app.tenant_id', t::text, false);
        IF fn_verificar_cadena(t) IS NOT NULL THEN
            RAISE EXCEPTION 'FALLO: la base original quedó alterada para %: %',
                t, fn_verificar_cadena(t);
        END IF;
        RAISE NOTICE 'OK base %: cadena del inquilino % íntegra', current_database(), t;
    END LOOP;
END;
$$;
\echo 'PRUEBA D: OK'
