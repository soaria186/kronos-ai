-- b) Un inquilino con varias conexiones concurrentes: la cadena debe quedar íntegra.
--    Se ejecuta como kronos_worker.
-- Variables: tc (inquilino), conexiones, filas (por conexión).
\set ON_ERROR_STOP on
SELECT set_config('prueba.tc', :'tc', false) AS tc,
       set_config('prueba.conexiones', :'conexiones', false) AS conexiones,
       set_config('prueba.filas', :'filas', false) AS filas \gset
SET app.tenant_id = :'tc';

SELECT current_user AS rol, :tc AS inquilino, count(*) AS filas,
       count(DISTINCT seq) AS seq_distintas, min(seq) AS seq_min, max(seq) AS seq_max,
       count(DISTINCT actor) AS conexiones,
       fn_verificar_cadena(:tc) AS discontinuidad,
       fn_verificar_cadena(:tc) IS NULL AS cadena_integra
  FROM auditoria;

SELECT actor AS conexion, count(*) AS filas, min(seq) AS primera_seq, max(seq) AS ultima_seq
  FROM auditoria GROUP BY actor ORDER BY actor;

-- Cuántas veces cambia la conexión entre dos seq consecutivas: muestra que las
-- inserciones se intercalaron de verdad.
SELECT count(*) FILTER (WHERE actor <> anterior) AS cambios_de_conexion_entre_seq_consecutivas
  FROM (SELECT actor, lag(actor) OVER (ORDER BY seq) AS anterior FROM auditoria) s;

DO $$
DECLARE
    tc         int := current_setting('prueba.tc')::int;
    conexiones bigint := current_setting('prueba.conexiones')::bigint;
    esperadas  bigint := conexiones * current_setting('prueba.filas')::bigint;
    n          bigint;
    distintas  bigint;
    seq_min    bigint;
    seq_max    bigint;
    actores    bigint;
BEGIN
    SELECT count(*), count(DISTINCT seq), min(seq), max(seq), count(DISTINCT actor)
      INTO n, distintas, seq_min, seq_max, actores
      FROM auditoria;
    IF n <> esperadas OR distintas <> n OR seq_min <> 1 OR seq_max <> n THEN
        RAISE EXCEPTION 'FALLO: % filas, % seq distintas, rango %..%, se esperaban % contiguas',
            n, distintas, seq_min, seq_max, esperadas;
    END IF;
    IF actores <> conexiones THEN
        RAISE EXCEPTION 'FALLO: escribieron % conexiones, se esperaban %', actores, conexiones;
    END IF;
    IF fn_verificar_cadena(tc) IS NOT NULL THEN
        RAISE EXCEPTION 'FALLO: cadena rota: %', fn_verificar_cadena(tc);
    END IF;
    RAISE NOTICE 'OK % filas de % conexiones, seq 1..% sin huecos ni duplicados, cadena íntegra',
        n, actores, seq_max;
END;
$$;
\echo 'PRUEBA B: OK'
