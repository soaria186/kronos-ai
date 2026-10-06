-- Esquema de persistencia de Kronos AI.
--
-- Todas las tablas son multiinquilino (tenant_id) y quedan protegidas por RLS.
-- auditoria y cortacircuito son de sólo inserción; auditoria además forma una
-- cadena de hash por inquilino ordenada por seq.

SET client_min_messages = warning;

-- ---------------------------------------------------------------------------
-- Tablas
-- ---------------------------------------------------------------------------

CREATE TABLE tickets (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id          integer     NOT NULL,
    alerta_ref         text        NOT NULL,
    titulo             text        NOT NULL,
    severidad          smallint    NOT NULL,
    playbook           text,
    confianza          numeric(4, 3),
    autonomia_aplicada smallint,
    execution_status   text        NOT NULL DEFAULT 'PENDING',
    rechazo_motivo     text,
    creado_en          timestamptz NOT NULL DEFAULT now(),
    actualizado_en     timestamptz NOT NULL DEFAULT now(),

    -- Destino de las FK compuestas: impide referenciar tickets de otro inquilino.
    CONSTRAINT tickets_tenant_id_id_key UNIQUE (tenant_id, id),

    CONSTRAINT tickets_execution_status_check CHECK (execution_status IN (
        'PENDING', 'EXECUTING', 'SUCCESS', 'FAILED', 'REJECTED', 'MANUAL_TRIAGE'
    )),
    CONSTRAINT tickets_autonomia_aplicada_check CHECK (autonomia_aplicada BETWEEN 0 AND 3),
    CONSTRAINT tickets_rechazo_motivo_check CHECK (rechazo_motivo IN (
        'ESQUEMA_INVALIDO',
        'CONFIANZA_BAJA',
        'PLAYBOOK_FUERA_DE_CATALOGO',
        'ACTIVO_EXCLUIDO',
        'LIMITE_DE_TASA',
        'CORTACIRCUITO_ABIERTO',
        'NIVEL_NO_PERMITIDO_POR_SEVERIDAD',
        'MOTOR_INFERENCIA_NO_DISPONIBLE',
        'TIEMPO_EXCEDIDO'
    ))
);

-- Sin FK a tickets: el registro de auditoría debe sobrevivir a cualquier borrado
-- y, al ser inmutable, no admite ON DELETE SET NULL.
CREATE TABLE auditoria (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id     integer     NOT NULL,
    seq           bigint      NOT NULL,
    ticket_id     bigint,
    evento        text        NOT NULL,
    actor         text        NOT NULL,
    detalle       jsonb       NOT NULL DEFAULT '{}'::jsonb,
    creado_en     timestamptz NOT NULL,
    hash_anterior bytea       NOT NULL,
    hash          bytea       NOT NULL,

    CONSTRAINT auditoria_tenant_id_seq_key UNIQUE (tenant_id, seq)
);

CREATE TABLE cola_inferencia (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id     integer     NOT NULL,
    ticket_id     bigint      NOT NULL,
    carga         jsonb       NOT NULL,
    intentos      integer     NOT NULL DEFAULT 0,
    disponible_en timestamptz NOT NULL DEFAULT now(),
    tomado_en     timestamptz,
    tomado_por    text,
    creado_en     timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT cola_inferencia_ticket_fkey FOREIGN KEY (tenant_id, ticket_id)
        REFERENCES tickets (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE temporizadores (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id    integer     NOT NULL,
    ticket_id    bigint      NOT NULL,
    tipo         text        NOT NULL,
    vence_en     timestamptz NOT NULL,
    disparado_en timestamptz,
    creado_en    timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT temporizadores_ticket_fkey FOREIGN KEY (tenant_id, ticket_id)
        REFERENCES tickets (tenant_id, id) ON DELETE CASCADE
);

-- Registro de transiciones del cortacircuito; el estado vigente de un ámbito es
-- su fila más reciente.
CREATE TABLE cortacircuito (
    id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id integer     NOT NULL,
    ambito    text        NOT NULL,
    abierto   boolean     NOT NULL,
    motivo    text,
    creado_en timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Índices (siete, cuatro parciales; aparte de los que crean PK y UNIQUE)
-- ---------------------------------------------------------------------------

CREATE INDEX tickets_tenant_creado_idx
    ON tickets (tenant_id, creado_en DESC);

CREATE INDEX tickets_activos_idx
    ON tickets (tenant_id, execution_status)
    WHERE execution_status IN ('PENDING', 'EXECUTING');

CREATE INDEX tickets_triage_manual_idx
    ON tickets (tenant_id, creado_en)
    WHERE execution_status = 'MANUAL_TRIAGE';

CREATE INDEX auditoria_ticket_idx
    ON auditoria (tenant_id, ticket_id, seq);

CREATE INDEX cola_inferencia_pendientes_idx
    ON cola_inferencia (tenant_id, disponible_en)
    WHERE tomado_en IS NULL;

CREATE INDEX temporizadores_pendientes_idx
    ON temporizadores (tenant_id, vence_en)
    WHERE disparado_en IS NULL;

CREATE INDEX cortacircuito_estado_idx
    ON cortacircuito (tenant_id, ambito, creado_en DESC);

-- ---------------------------------------------------------------------------
-- Cadena de hash de auditoría
-- ---------------------------------------------------------------------------

-- Hash de una fila: SHA-256 de su contenido canónico seguido de hash_anterior.
-- El contenido se serializa como array JSON (sin ambigüedad de separadores) y la
-- fecha en UTC con microsegundos, para no depender de la zona horaria de la sesión.
-- No incluye id: la cadena se define por (tenant_id, seq).
CREATE FUNCTION fn_auditoria_hash(r auditoria)
RETURNS bytea
LANGUAGE sql
IMMUTABLE
SET search_path = pg_catalog, public
AS $$
    SELECT public.digest(
        convert_to(
            jsonb_build_array(
                r.tenant_id,
                r.seq,
                r.ticket_id,
                r.evento,
                r.actor,
                r.detalle,
                to_char(r.creado_en AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
            )::text,
            'UTF8'
        ) || r.hash_anterior,
        'sha256'
    )
$$;

-- Asigna seq, hash_anterior, creado_en y hash a cada inserción, ignorando lo que
-- envíe el cliente. Todo ocurre dentro del bloqueo consultivo del inquilino, que se
-- mantiene hasta el fin de la transacción: dos inserciones del mismo inquilino se
-- serializan y la segunda ve la fila confirmada de la primera (en READ COMMITTED
-- cada sentencia de la función toma una instantánea nueva tras obtener el bloqueo).
-- En REPEATABLE READ o SERIALIZABLE la instantánea es anterior al bloqueo; si
-- quedara obsoleta, UNIQUE (tenant_id, seq) rechaza la inserción en vez de bifurcar
-- la cadena.
CREATE FUNCTION fn_auditoria_encadenar()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('kronos_auditoria_chain'), NEW.tenant_id);

    SELECT coalesce(max(a.seq), 0) + 1
      INTO NEW.seq
      FROM public.auditoria a
     WHERE a.tenant_id = NEW.tenant_id;

    IF NEW.seq = 1 THEN
        NEW.hash_anterior := decode(repeat('00', 32), 'hex');
    ELSE
        SELECT a.hash
          INTO NEW.hash_anterior
          FROM public.auditoria a
         WHERE a.tenant_id = NEW.tenant_id
           AND a.seq = NEW.seq - 1;
        IF NEW.hash_anterior IS NULL THEN
            RAISE EXCEPTION 'auditoria: no se encontró seq % del inquilino %',
                NEW.seq - 1, NEW.tenant_id;
        END IF;
    END IF;

    NEW.creado_en := clock_timestamp();
    NEW.hash := public.fn_auditoria_hash(NEW);
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_auditoria_encadenar
    BEFORE INSERT ON auditoria
    FOR EACH ROW EXECUTE FUNCTION fn_auditoria_encadenar();

-- ---------------------------------------------------------------------------
-- Inmutabilidad de auditoria y cortacircuito
-- ---------------------------------------------------------------------------

-- Rechaza UPDATE, DELETE y TRUNCATE para cualquier rol, superusuario incluido.
-- Los disparadores son de sentencia, así que fallan aunque no afecten a ninguna
-- fila, y se activan con ENABLE ALWAYS para que tampoco los salte
-- session_replication_role = replica.
CREATE FUNCTION fn_auditoria_inmutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'la tabla % sólo admite INSERT: % rechazado', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege',
              HINT = 'Los registros de auditoria y cortacircuito son inmutables.';
END;
$$;

CREATE TRIGGER trg_auditoria_inmutable
    BEFORE UPDATE OR DELETE OR TRUNCATE ON auditoria
    FOR EACH STATEMENT EXECUTE FUNCTION fn_auditoria_inmutable();

CREATE TRIGGER trg_cortacircuito_inmutable
    BEFORE UPDATE OR DELETE OR TRUNCATE ON cortacircuito
    FOR EACH STATEMENT EXECUTE FUNCTION fn_auditoria_inmutable();

ALTER TABLE auditoria ENABLE ALWAYS TRIGGER trg_auditoria_encadenar;
ALTER TABLE auditoria ENABLE ALWAYS TRIGGER trg_auditoria_inmutable;
ALTER TABLE cortacircuito ENABLE ALWAYS TRIGGER trg_cortacircuito_inmutable;

-- ---------------------------------------------------------------------------
-- Verificación de la cadena
-- ---------------------------------------------------------------------------

CREATE TYPE auditoria_discontinuidad AS (seq bigint, motivo text);

-- Recorre la cadena del inquilino por seq y devuelve la primera discontinuidad,
-- o NULL si la cadena es íntegra. Corre con los permisos de quien la llama, así que
-- un rol sujeto a RLS sólo puede verificar el inquilino fijado en app.tenant_id;
-- verificar otro devolvería NULL por no ver filas, por eso se rechaza.
-- Limitación: sin un ancla externa no se detecta la eliminación de las últimas filas.
CREATE FUNCTION fn_verificar_cadena(p_tenant_id integer)
RETURNS auditoria_discontinuidad
LANGUAGE plpgsql
STABLE
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_sesion   text := current_setting('app.tenant_id', true);
    v_esperado bigint := 1;
    v_previo   bytea := decode(repeat('00', 32), 'hex');
    r          public.auditoria;
BEGIN
    IF coalesce(v_sesion, '') <> '' AND v_sesion::integer <> p_tenant_id THEN
        RAISE EXCEPTION 'fn_verificar_cadena(%): la sesión está fijada al inquilino %',
            p_tenant_id, v_sesion
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    FOR r IN
        SELECT * FROM public.auditoria WHERE tenant_id = p_tenant_id ORDER BY seq
    LOOP
        IF r.seq <> v_esperado THEN
            RETURN ROW(v_esperado,
                       format('falta seq %s (la siguiente es %s)', v_esperado, r.seq)
                   )::public.auditoria_discontinuidad;
        END IF;
        IF r.hash_anterior IS DISTINCT FROM v_previo THEN
            RETURN ROW(r.seq, 'hash_anterior no enlaza con el hash de la fila previa')
                   ::public.auditoria_discontinuidad;
        END IF;
        IF r.hash IS DISTINCT FROM public.fn_auditoria_hash(r) THEN
            RETURN ROW(r.seq, 'el hash no coincide con el contenido de la fila')
                   ::public.auditoria_discontinuidad;
        END IF;
        v_previo := r.hash;
        v_esperado := v_esperado + 1;
    END LOOP;

    RETURN NULL;
END;
$$;
