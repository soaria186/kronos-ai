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
