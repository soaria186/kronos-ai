-- a) Dos inquilinos escribiendo en paralelo: cada cadena es íntegra y ninguno ve
--    las filas del otro. Se ejecuta como kronos_worker.
-- Variables: ta, tb (inquilinos), filas (filas esperadas por inquilino).
\set ON_ERROR_STOP on
SELECT set_config('prueba.ta', :'ta', false) AS ta,
       set_config('prueba.tb', :'tb', false) AS tb,
       set_config('prueba.filas', :'filas', false) AS filas \gset

\echo '--- Vista del inquilino' :ta
SET app.tenant_id = :'ta';
SELECT current_user AS rol, :ta AS inquilino, count(*) AS filas_visibles,
       count(*) FILTER (WHERE tenant_id <> :ta) AS filas_ajenas,
       min(seq) AS seq_min, max(seq) AS seq_max,
       fn_verificar_cadena(:ta) IS NULL AS cadena_integra
  FROM auditoria;
SELECT count(*) AS filas_visibles_del_otro_inquilino FROM auditoria WHERE tenant_id = :tb;

\echo '--- Vista del inquilino' :tb
SET app.tenant_id = :'tb';
SELECT current_user AS rol, :tb AS inquilino, count(*) AS filas_visibles,
       count(*) FILTER (WHERE tenant_id <> :tb) AS filas_ajenas,
       min(seq) AS seq_min, max(seq) AS seq_max,
       fn_verificar_cadena(:tb) IS NULL AS cadena_integra
  FROM auditoria;
SELECT count(*) AS filas_visibles_del_otro_inquilino FROM auditoria WHERE tenant_id = :ta;

\echo '--- Comprobaciones'
DO $$
DECLARE
    ta        int := current_setting('prueba.ta')::int;
    tb        int := current_setting('prueba.tb')::int;
    esperadas bigint := current_setting('prueba.filas')::bigint;
    propio    int;
    otro      int;
    n         bigint;
    ajenas    bigint;
    seq_max   bigint;
    desde     timestamptz;
    hasta     timestamptz;
    rangos    tstzrange[] := '{}';
    rechazado boolean;
    estado    text;
    mensaje   text;
BEGIN
    FOREACH propio IN ARRAY ARRAY[ta, tb] LOOP
        otro := CASE WHEN propio = ta THEN tb ELSE ta END;
        PERFORM set_config('app.tenant_id', propio::text, false);

        SELECT count(*), count(*) FILTER (WHERE tenant_id <> propio), max(seq),
               min(creado_en), max(creado_en)
          INTO n, ajenas, seq_max, desde, hasta
          FROM auditoria;
        rangos := rangos || tstzrange(desde, hasta, '[]');
        IF n <> esperadas OR seq_max <> esperadas THEN
            RAISE EXCEPTION 'FALLO: inquilino % ve % filas (seq máx %), se esperaban %',
                propio, n, seq_max, esperadas;
        END IF;
        IF ajenas <> 0 THEN
            RAISE EXCEPTION 'FALLO: inquilino % ve % filas ajenas', propio, ajenas;
        END IF;
        IF fn_verificar_cadena(propio) IS NOT NULL THEN
            RAISE EXCEPTION 'FALLO: cadena de % rota: %', propio, fn_verificar_cadena(propio);
        END IF;
        RAISE NOTICE 'OK inquilino %: % filas, seq 1..%, 0 filas ajenas, cadena íntegra',
            propio, n, seq_max;

        -- Verificar la cadena del otro inquilino debe rechazarse (no dar un falso "íntegra").
        rechazado := false;
        BEGIN
            PERFORM fn_verificar_cadena(otro);
        EXCEPTION WHEN OTHERS THEN
            rechazado := true;
            GET STACKED DIAGNOSTICS estado = RETURNED_SQLSTATE, mensaje = MESSAGE_TEXT;
        END;
        IF NOT rechazado THEN
            RAISE EXCEPTION 'FALLO: % pudo verificar la cadena de %', propio, otro;
        END IF;
        RAISE NOTICE 'OK inquilino % no puede verificar la cadena de %: [%] %',
            propio, otro, estado, mensaje;

        -- Escribir filas a nombre del otro inquilino debe rechazarse por RLS.
        rechazado := false;
        BEGIN
            INSERT INTO auditoria (tenant_id, evento, actor) VALUES (otro, 'intrusion', 'prueba');
        EXCEPTION WHEN OTHERS THEN
            rechazado := true;
            GET STACKED DIAGNOSTICS estado = RETURNED_SQLSTATE, mensaje = MESSAGE_TEXT;
        END;
        IF NOT rechazado THEN
            RAISE EXCEPTION 'FALLO: % pudo insertar filas del inquilino %', propio, otro;
        END IF;
        RAISE NOTICE 'OK inquilino % no puede insertar como %: [%] %', propio, otro, estado, mensaje;
    END LOOP;

    RAISE NOTICE 'Escrituras de % y % solapadas en el tiempo: %',
        ta, tb, rangos[1] && rangos[2];
END;
$$;
\echo 'PRUEBA A: OK'
