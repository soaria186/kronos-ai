-- Alertas guardadas: la alerta completa de Wazuh, fuera de la bitácora, con tope y retención.
--
-- Por qué: auditoria es de sólo inserción y su cadena de hash incluye el detalle, así que
-- lo que se escribe ahí no se puede borrar nunca. La alerta de Wazuh trae datos personales
-- (cuentas, IP, nombres de equipo, líneas de registro) y debe poder eliminarse al vencer
-- su plazo (R-09). Por eso:
--   - la alerta completa vive en alertas_guardadas, que SÍ se puede purgar;
--   - el evento ALERTA_RECIBIDA de la bitácora guarda sólo su SHA-256, su tamaño, el
--     agente y la regla: la cadena sigue probando qué alerta fue, sin conservar sus datos.
--
-- Tope: 64 KiB por alerta (CHECK). SOAR-VALIDATE recorta antes de guardar
-- (persistencia/alertas.py) y marca la fila como recortada.
--
-- Retención: fn_purgar_alertas(dias) borra las alertas más antiguas que el plazo, salvo
-- las de tickets cuya medida podría tener que revertirse todavía. La ejecuta kronos_admin
-- una vez al día (infra/docker/retencion/). Cada purga deja el evento ALERTAS_PURGADAS en
-- la bitácora del inquilino.
--
-- Idempotente: sirve como script de initdb (base nueva) y como migración de una base que
-- ya existe:
--   docker exec -i kronos-db-1 psql -U kronos_admin -d kronos -v ON_ERROR_STOP=1 \
--       < initdb/06_alertas_guardadas.sql

SET client_min_messages = warning;

CREATE TABLE IF NOT EXISTS public.alertas_guardadas (
    tenant_id      integer     NOT NULL,
    ticket_id      bigint      NOT NULL,
    alerta         jsonb       NOT NULL,
    bytes_original integer     NOT NULL,
    recortada      boolean     NOT NULL DEFAULT false,
    guardada_en    timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT alertas_guardadas_pkey PRIMARY KEY (tenant_id, ticket_id),
    CONSTRAINT alertas_guardadas_ticket_fkey FOREIGN KEY (tenant_id, ticket_id)
        REFERENCES public.tickets (tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT alertas_guardadas_tope_check CHECK (octet_length(alerta::text) <= 65536),
    CONSTRAINT alertas_guardadas_bytes_check CHECK (bytes_original >= 0)
);

CREATE INDEX IF NOT EXISTS alertas_guardadas_fecha_idx
    ON public.alertas_guardadas (guardada_en);

ALTER TABLE public.alertas_guardadas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alertas_guardadas FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS alertas_guardadas_inquilino ON public.alertas_guardadas;
CREATE POLICY alertas_guardadas_inquilino ON public.alertas_guardadas
    USING (tenant_id = current_setting('app.tenant_id')::int)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::int);

-- Los servicios guardan y leen; nunca modifican ni borran (sólo la purga de kronos_admin).
REVOKE ALL ON public.alertas_guardadas FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kronos_worker') THEN
        GRANT SELECT, INSERT ON public.alertas_guardadas TO kronos_worker;
        REVOKE UPDATE, DELETE, TRUNCATE ON public.alertas_guardadas FROM kronos_worker;
    END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- Purga por retención
-- ---------------------------------------------------------------------------

-- Una alerta se conserva, aunque haya vencido su plazo, si su ticket:
--   - sigue en curso (PENDING, AWAITING_APPROVAL o EXECUTING);
--   - tiene un temporizador sin disparar (reversión del nivel 1, revisión del nivel 2 o
--     plazo de aprobación del nivel 3): EXECUTE necesitará la alerta para revertir;
--   - quedó en SUCCESS y su última reversión falló: una persona puede volver a pedirla.
-- Devuelve, por inquilino, cuántas alertas borró. Un plazo menor a 7 días se rechaza,
-- para que un error de tipeo no borre todo.
CREATE OR REPLACE FUNCTION public.fn_purgar_alertas(p_dias integer)
RETURNS TABLE (inquilino integer, purgadas bigint)
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_corte timestamptz;
    r       record;
BEGIN
    IF p_dias IS NULL OR p_dias < 7 THEN
        RAISE EXCEPTION 'fn_purgar_alertas: el plazo debe ser de al menos 7 días (llegó %)',
            p_dias;
    END IF;
    v_corte := now() - make_interval(days => p_dias);

    FOR r IN
        WITH borradas AS (
            DELETE FROM public.alertas_guardadas ag
             WHERE ag.guardada_en < v_corte
               AND NOT EXISTS (
                     SELECT 1 FROM public.tickets t
                      WHERE t.tenant_id = ag.tenant_id AND t.id = ag.ticket_id
                        AND t.execution_status IN ('PENDING', 'AWAITING_APPROVAL', 'EXECUTING'))
               AND NOT EXISTS (
                     SELECT 1 FROM public.temporizadores tm
                      WHERE tm.tenant_id = ag.tenant_id AND tm.ticket_id = ag.ticket_id
                        AND tm.disparado_en IS NULL)
               AND NOT EXISTS (
                     SELECT 1 FROM public.tickets t
                      WHERE t.tenant_id = ag.tenant_id AND t.id = ag.ticket_id
                        AND t.execution_status = 'SUCCESS'
                        AND (SELECT a.evento FROM public.auditoria a
                              WHERE a.tenant_id = ag.tenant_id AND a.ticket_id = ag.ticket_id
                                AND a.evento IN ('REVERSION_OK', 'REVERSION_FALLIDA')
                              ORDER BY a.seq DESC LIMIT 1) = 'REVERSION_FALLIDA')
            RETURNING ag.tenant_id, ag.ticket_id
        )
        SELECT b.tenant_id, count(*) AS n, min(b.ticket_id) AS desde, max(b.ticket_id) AS hasta
          FROM borradas b
         GROUP BY b.tenant_id
    LOOP
        INSERT INTO public.auditoria (tenant_id, ticket_id, evento, actor, detalle)
        VALUES (r.tenant_id, NULL, 'ALERTAS_PURGADAS', 'soar-retencion',
                jsonb_build_object(
                    'dias', p_dias,
                    'antes_de', to_char(v_corte AT TIME ZONE 'UTC',
                                        'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                    'alertas', r.n,
                    'desde_ticket', r.desde,
                    'hasta_ticket', r.hasta));
        inquilino := r.tenant_id;
        purgadas := r.n;
        RETURN NEXT;
    END LOOP;
END;
$$;

REVOKE ALL ON FUNCTION public.fn_purgar_alertas(integer) FROM PUBLIC;

-- Verificación: alertas guardadas cuyo SHA-256 no coincide con el de su ALERTA_RECIBIDA.
-- Vacía si todo calza. Las alertas de antes de esta migración (dentro de la bitácora) y las
-- ya purgadas no aparecen.
CREATE OR REPLACE FUNCTION public.fn_verificar_alertas(p_tenant integer)
RETURNS TABLE (ticket_id bigint, motivo text)
LANGUAGE sql
STABLE
SET search_path = pg_catalog, public
AS $$
    SELECT ag.ticket_id,
           CASE WHEN a.detalle IS NULL THEN 'sin evento ALERTA_RECIBIDA'
                ELSE 'el SHA-256 no coincide con la bitácora' END
      FROM public.alertas_guardadas ag
      LEFT JOIN public.auditoria a
        ON a.tenant_id = ag.tenant_id AND a.ticket_id = ag.ticket_id
       AND a.evento = 'ALERTA_RECIBIDA'
     WHERE ag.tenant_id = p_tenant
       AND (a.detalle IS NULL
            OR a.detalle #>> '{alerta_guardada,sha256}'
               IS DISTINCT FROM encode(digest(ag.alerta::text, 'sha256'), 'hex'))
     ORDER BY ag.ticket_id
$$;

REVOKE ALL ON FUNCTION public.fn_verificar_alertas(integer) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kronos_worker') THEN
        GRANT EXECUTE ON FUNCTION public.fn_verificar_alertas(integer) TO kronos_worker;
    END IF;
END;
$$;
