-- Esquema consola: las únicas escrituras que hace una persona (D-31, RF-14, RF-19).
--
-- SOAR-CONSOLE se conecta como kronos_console, que lee las vistas de frontend y sólo
-- puede escribir llamando a estas cuatro funciones:
--   consola.aprobar(ticket, persona)                    nivel 3 -> PENDING
--   consola.denegar(ticket, persona, motivo)            nivel 3 -> REJECTED
--   consola.solicitar_reversion(ticket, persona)        reversión de una medida en SUCCESS
--   consola.cerrar_cortacircuito(persona, motivo, ámbito)
-- SOAR-NOTIFY (respuestas de Telegram) usa las mismas funciones desde kronos_worker, así
-- que cada transición está escrita una sola vez.
--
-- Las funciones son SECURITY DEFINER: corren con los permisos de su propietario, así que
-- filtran el inquilino de app.tenant_id en cada consulta. Sin app.tenant_id fijado,
-- fallan cerrado. Errores:
--   KR001  el ticket no existe para el inquilino o no está en el estado que se pide
--   KR002  falta la persona o el motivo
--
-- Idempotente: sirve en una base nueva (initdb, después de 03_roles.sql) y como
-- migración en una existente. La contraseña de kronos_console no va aquí: la pone
-- 05_clave_consola.sql, que genera generar_secretos.sh y no se versiona.

SET client_min_messages = warning;

CREATE SCHEMA IF NOT EXISTS consola;
REVOKE ALL ON SCHEMA consola FROM PUBLIC;

-- ---------------------------------------------------------------------------
-- Apoyo (sin EXECUTE para nadie salvo el propietario)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION consola._inquilino()
RETURNS integer
LANGUAGE sql
STABLE
AS $$ SELECT current_setting('app.tenant_id')::int $$;

CREATE OR REPLACE FUNCTION consola._texto(p_valor text, p_que text, p_largo integer)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    IF p_valor IS NULL OR btrim(p_valor) = '' THEN
        RAISE EXCEPTION 'falta %', p_que USING ERRCODE = 'KR002';
    END IF;
    RETURN left(btrim(p_valor), p_largo);
END;
$$;

CREATE OR REPLACE FUNCTION consola._evento(
    p_tenant integer, p_ticket bigint, p_evento text, p_actor text, p_detalle jsonb)
RETURNS void
LANGUAGE sql
SET search_path = pg_catalog, public
AS $$
    INSERT INTO public.auditoria (tenant_id, ticket_id, evento, actor, detalle)
    VALUES (p_tenant, p_ticket, p_evento, p_actor, p_detalle)
$$;

-- ---------------------------------------------------------------------------
-- Nivel 3
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION consola.aprobar(p_ticket bigint, p_persona text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_tenant  integer := consola._inquilino();
    v_persona text := consola._texto(p_persona, 'la persona', 100);
BEGIN
    UPDATE public.tickets
       SET execution_status = 'PENDING', actualizado_en = now()
     WHERE tenant_id = v_tenant AND id = p_ticket
       AND execution_status = 'AWAITING_APPROVAL';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'ticket %: no espera aprobación', p_ticket USING ERRCODE = 'KR001';
    END IF;
    UPDATE public.temporizadores SET disparado_en = now()
     WHERE tenant_id = v_tenant AND ticket_id = p_ticket
       AND tipo = 'APROBACION' AND disparado_en IS NULL;
    PERFORM consola._evento(v_tenant, p_ticket, 'APROBACION_CONCEDIDA', v_persona,
                            jsonb_build_object('motivo', ''));
END;
$$;

-- CU-02: el rechazo exige justificación.
CREATE OR REPLACE FUNCTION consola.denegar(p_ticket bigint, p_persona text, p_motivo text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_tenant  integer := consola._inquilino();
    v_persona text := consola._texto(p_persona, 'la persona', 100);
    v_motivo  text := consola._texto(p_motivo, 'el motivo del rechazo', 500);
BEGIN
    UPDATE public.tickets
       SET execution_status = 'REJECTED', actualizado_en = now()
     WHERE tenant_id = v_tenant AND id = p_ticket
       AND execution_status = 'AWAITING_APPROVAL';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'ticket %: no espera aprobación', p_ticket USING ERRCODE = 'KR001';
    END IF;
    UPDATE public.temporizadores SET disparado_en = now()
     WHERE tenant_id = v_tenant AND ticket_id = p_ticket
       AND tipo = 'APROBACION' AND disparado_en IS NULL;
    PERFORM consola._evento(v_tenant, p_ticket, 'APROBACION_DENEGADA', v_persona,
                            jsonb_build_object('motivo', v_motivo));
END;
$$;

-- ---------------------------------------------------------------------------
-- Reversión (nivel 2, o nivel 1 antes de su plazo)
-- ---------------------------------------------------------------------------

-- Deja un temporizador de reversión vencido ahora (o adelanta el que había);
-- SOAR-EXECUTE lo toma en su próximo ciclo.
CREATE OR REPLACE FUNCTION consola.solicitar_reversion(p_ticket bigint, p_persona text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_tenant  integer := consola._inquilino();
    v_persona text := consola._texto(p_persona, 'la persona', 100);
BEGIN
    PERFORM 1 FROM public.tickets
     WHERE tenant_id = v_tenant AND id = p_ticket AND execution_status = 'SUCCESS'
       FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'ticket %: sólo se revierte una medida en SUCCESS', p_ticket
            USING ERRCODE = 'KR001';
    END IF;
    IF EXISTS (SELECT 1 FROM public.auditoria
                WHERE tenant_id = v_tenant AND ticket_id = p_ticket
                  AND evento = 'REVERSION_OK') THEN
        RAISE EXCEPTION 'ticket %: la medida ya fue revertida', p_ticket
            USING ERRCODE = 'KR001';
    END IF;
    UPDATE public.temporizadores SET vence_en = now()
     WHERE tenant_id = v_tenant AND ticket_id = p_ticket
       AND tipo = 'REVERSION' AND disparado_en IS NULL;
    IF NOT FOUND THEN
        INSERT INTO public.temporizadores (tenant_id, ticket_id, tipo, vence_en)
        VALUES (v_tenant, p_ticket, 'REVERSION', now());
    END IF;
    PERFORM consola._evento(v_tenant, p_ticket, 'REVERSION_SOLICITADA', v_persona,
                            '{}'::jsonb);
END;
$$;

-- ---------------------------------------------------------------------------
-- Cortacircuito: abrirlo es automático; cerrarlo, sólo una persona
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION consola.cerrar_cortacircuito(
    p_persona text, p_motivo text, p_ambito text DEFAULT 'inquilino')
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_tenant  integer := consola._inquilino();
    v_persona text := consola._texto(p_persona, 'la persona', 100);
    v_motivo  text := consola._texto(p_motivo, 'el motivo del cierre', 500);
    v_abierto boolean;
BEGIN
    -- Mismo bloqueo que la apertura (persistencia/repositorio.py).
    PERFORM pg_advisory_xact_lock(hashtext('cortacircuito'), v_tenant);
    SELECT abierto INTO v_abierto
      FROM public.cortacircuito
     WHERE tenant_id = v_tenant AND ambito = p_ambito
     ORDER BY creado_en DESC, id DESC
     LIMIT 1;
    IF NOT coalesce(v_abierto, false) THEN
        RAISE EXCEPTION 'el cortacircuito % ya está cerrado', p_ambito USING ERRCODE = 'KR001';
    END IF;
    INSERT INTO public.cortacircuito (tenant_id, ambito, abierto, motivo)
    VALUES (v_tenant, p_ambito, false, v_motivo);
    PERFORM consola._evento(v_tenant, NULL, 'CORTACIRCUITO_CERRADO', v_persona,
                            jsonb_build_object('ambito', p_ambito, 'motivo', v_motivo));
END;
$$;

-- ---------------------------------------------------------------------------
-- Vista de plazos para el panel (RF-19: antigüedad frente al plazo de 2 días)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW frontend.temporizadores WITH (security_barrier = true) AS
SELECT ticket_id, tipo, vence_en, disparado_en
  FROM public.temporizadores
 WHERE tenant_id = current_setting('app.tenant_id')::int;

-- ---------------------------------------------------------------------------
-- Rol de la consola y permisos
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kronos_console') THEN
        CREATE ROLE kronos_console
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO kronos_console', current_database());
END;
$$;

-- Las funciones nacen ejecutables por PUBLIC: se quita y se concede sólo lo necesario.
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA consola FROM PUBLIC;

GRANT USAGE ON SCHEMA frontend, consola TO kronos_console;
GRANT SELECT ON ALL TABLES IN SCHEMA frontend TO kronos_console;
GRANT SELECT ON frontend.temporizadores TO kronos_frontend;

GRANT USAGE ON SCHEMA consola TO kronos_worker;
GRANT EXECUTE ON FUNCTION
    consola.aprobar(bigint, text),
    consola.denegar(bigint, text, text),
    consola.solicitar_reversion(bigint, text),
    consola.cerrar_cortacircuito(text, text, text)
    TO kronos_console, kronos_worker;
