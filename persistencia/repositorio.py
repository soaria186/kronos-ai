"""Acceso a SOAR-AUDIT para SOAR-VALIDATE y SOAR-EXECUTE.

Reglas de esta capa:

- Cada operación es una transacción propia que fija el inquilino con
  ``set_config('app.tenant_id', …, true)``. El valor vive sólo dentro de esa
  transacción, así que una conexión reutilizada no arrastra el inquilino anterior.
  Sin inquilino fijado, las políticas RLS fallan cerrado.
- R3: la decisión queda en la bitácora antes de que alguien actúe.
  ``registrar_decision`` inserta el evento y actualiza el ticket en la misma
  transacción: o quedan las dos cosas, o ninguna.
- Esta capa no importa ``validacion`` ni ``decision``: recibe y entrega tipos
  simples, para que la persistencia no dependa de la lógica que la usa.
- Se conecta como ``kronos_worker``, que puede insertar en ``auditoria`` y
  ``cortacircuito`` pero nunca modificarlas.

Estados del ticket (``tickets.execution_status``):

    PENDING sin playbook ── decisión rechazada ──> MANUAL_TRIAGE
         │ aprobada nivel 0-2           │ aprobada nivel 3
         v                              v
    PENDING con playbook <── aprobar ── AWAITING_APPROVAL ── denegar ──> REJECTED
         │ EXECUTE la toma                    └── vence el plazo ──> MANUAL_TRIAGE
         v                                                     (APROBACION_VENCIDA)
    EXECUTING ──> SUCCESS | FAILED

- FAILED no se reintenta solo: una persona decide (falla segura).
- Un ticket que queda en EXECUTING (EXECUTE se cayó tras enviar la orden) tampoco se
  retoma solo, porque la orden pudo haber llegado al equipo.
- La reversión no cambia el estado: queda en la bitácora (REVERSION_*) y en
  ``temporizadores``. El ticket sigue en SUCCESS.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

ACTOR_VALIDATE = "soar-validate"
ACTOR_EXECUTE = "soar-execute"
ACTOR_NOTIFY = "soar-notify"

EVENTO_ALERTA = "ALERTA_RECIBIDA"
EVENTO_DECISION = "DECISION"
EVENTO_CORTACIRCUITO = "CORTACIRCUITO_ABIERTO"
EVENTO_EJECUCION_INICIADA = "EJECUCION_INICIADA"
EVENTO_EJECUCION_OK = "EJECUCION_OK"
EVENTO_EJECUCION_FALLIDA = "EJECUCION_FALLIDA"
EVENTO_APROBACION_CONCEDIDA = "APROBACION_CONCEDIDA"
EVENTO_APROBACION_DENEGADA = "APROBACION_DENEGADA"
EVENTO_APROBACION_VENCIDA = "APROBACION_VENCIDA"
EVENTO_REVERSION_SOLICITADA = "REVERSION_SOLICITADA"
EVENTO_REVERSION_INICIADA = "REVERSION_INICIADA"
EVENTO_REVERSION_OK = "REVERSION_OK"
EVENTO_REVERSION_FALLIDA = "REVERSION_FALLIDA"
EVENTO_RECORDATORIO = "RECORDATORIO_REVISION"
EVENTO_AVISO_ENVIADO = "AVISO_ENVIADO"

# Eventos que SOAR-NOTIFY avisa siempre. Además: DECISION aprobada de nivel 3
# (solicitud de aprobación) y EJECUCION_OK de nivel 2 (D-31).
EVENTOS_AVISABLES = (
    EVENTO_EJECUCION_FALLIDA,
    EVENTO_REVERSION_FALLIDA,
    EVENTO_RECORDATORIO,
    EVENTO_APROBACION_VENCIDA,
    EVENTO_CORTACIRCUITO,
)

# Tipos de temporizadores.
TEMPORIZADOR_APROBACION = "APROBACION"  # nivel 3: plazo para aprobar (D-32)
TEMPORIZADOR_REVERSION = "REVERSION"  # nivel 1 al vencer, o pedida por una persona
TEMPORIZADOR_REVISION = "REVISION"  # nivel 2: plazo de revisión y recordatorios (D-33)

PLAZO_APROBACION_MINUTOS = 2 * 24 * 60  # D-32
PLAZO_REVISION_MINUTOS = 2 * 24 * 60  # D-33
INTERVALO_RECORDATORIO_MINUTOS = 24 * 60  # D-33: recordatorio diario al vencer

# Ámbito del cortacircuito que detiene toda acción automática de un inquilino.
AMBITO_INQUILINO = "inquilino"

SEVERIDAD_MINIMA = 0
SEVERIDAD_MAXIMA = 15

# Niveles que cuentan como «acción automática» para los contadores de tasa: el 0
# sólo reúne contexto y el 3 nunca se ejecuta sin una persona.
NIVELES_AUTOMATICOS = (1, 2)


class TicketYaDecidido(RuntimeError):
    """El ticket no existe para este inquilino o ya tiene una decisión registrada."""


class EstadoInvalido(RuntimeError):
    """El ticket no existe para este inquilino o no está en el estado que pide la operación."""


@dataclass(frozen=True)
class TicketRegistrado:
    ticket_id: int
    # False si la alerta ya había creado un ticket (relectura tras rotación o reinicio).
    nuevo: bool


@dataclass(frozen=True)
class Decision:
    """Resultado de SOAR-VALIDATE para un ticket.

    ``motivo`` en None significa aprobada; si no, es uno de los valores de
    ``tickets.rechazo_motivo`` y el ticket pasa a revisión humana.
    """

    familia: str | None
    playbook_id: str | None
    confianza: float | None
    nivel: int | None
    motivo: str | None = None
    detalle: str = ""
    # Equipo sobre el que actuaría la medida; alimenta el contador por equipo.
    equipo: str | None = None

    @property
    def aprobada(self) -> bool:
        return self.motivo is None


@dataclass(frozen=True)
class TicketAEjecutar:
    """Ticket que SOAR-EXECUTE acaba de pasar a EXECUTING."""

    ticket_id: int
    playbook_id: str
    nivel: int
    # Detalle del evento ALERTA_RECIBIDA que escribió VALIDATE.
    alerta: dict[str, Any]


@dataclass(frozen=True)
class ReversionPendiente:
    """Reversión que SOAR-EXECUTE debe ejecutar ahora."""

    ticket_id: int
    playbook_id: str
    alerta: dict[str, Any]


@dataclass(frozen=True)
class EventoAvisable:
    """Evento de la bitácora que SOAR-NOTIFY puede tener que avisar."""

    seq: int
    evento: str
    ticket_id: int | None
    detalle: dict[str, Any]
    titulo: str | None
    playbook_id: str | None
    nivel: int | None


@dataclass(frozen=True)
class DefinicionUso:
    """Un contador de tasa: nombre (de validate.json) y ventana en minutos."""

    nombre: str
    ventana_minutos: int


class Repositorio:
    def __init__(self, dsn: str, actor: str = ACTOR_VALIDATE) -> None:
        self._dsn = dsn
        self._actor = actor

    # ------------------------------------------------------------------ alertas

    def registrar_alerta(
        self,
        tenant_id: int,
        alerta_ref: str,
        titulo: str,
        severidad: int,
        detalle: Mapping[str, Any] | None = None,
    ) -> TicketRegistrado:
        """Crea el ticket de una alerta, o devuelve el existente si ya se leyó antes.

        La restricción UNIQUE (tenant_id, alerta_ref) hace que leer dos veces la
        misma alerta no cree dos tickets ni dos eventos.
        """
        if not alerta_ref:
            raise ValueError("alerta_ref vacío")
        if not SEVERIDAD_MINIMA <= severidad <= SEVERIDAD_MAXIMA:
            raise ValueError(f"severidad fuera de 0 a 15: {severidad}")

        with self._transaccion(tenant_id) as cur:
            cur.execute(
                """
                INSERT INTO tickets (tenant_id, alerta_ref, titulo, severidad)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, alerta_ref) DO NOTHING
                RETURNING id
                """,
                (tenant_id, alerta_ref, titulo, severidad),
            )
            fila = cur.fetchone()
            if fila is None:
                cur.execute(
                    "SELECT id FROM tickets WHERE tenant_id = %s AND alerta_ref = %s",
                    (tenant_id, alerta_ref),
                )
                return TicketRegistrado(cur.fetchone()[0], nuevo=False)

            ticket_id = fila[0]
            self._evento(cur, tenant_id, ticket_id, EVENTO_ALERTA, dict(detalle or {}))
            return TicketRegistrado(ticket_id, nuevo=True)

    # ---------------------------------------------------------------- decisiones

    def registrar_decision(self, tenant_id: int, ticket_id: int, decision: Decision) -> int:
        """Escribe la decisión en la bitácora y actualiza el ticket. Devuelve el seq.

        Aprobada de nivel 0 a 2: el ticket queda en PENDING con su playbook y su nivel,
        a la espera de SOAR-EXECUTE.
        Aprobada de nivel 3: queda en AWAITING_APPROVAL, con un temporizador de 2 días
        para que el equipo la apruebe (D-32).
        Rechazada: el ticket pasa a MANUAL_TRIAGE con su motivo.

        Un ticket se decide una sola vez. Si ya tenía decisión, se lanza
        TicketYaDecidido y la transacción se deshace entera, evento incluido.
        """
        if decision.aprobada and decision.nivel not in (0, 1, 2, 3):
            raise ValueError("una decisión aprobada necesita un nivel de 0 a 3")

        detalle = {
            "resultado": "aprobada" if decision.aprobada else "rechazada",
            "familia": decision.familia,
            "playbook": decision.playbook_id,
            "confianza": decision.confianza,
            "nivel": decision.nivel,
            "motivo": decision.motivo,
            "detalle": decision.detalle,
            "equipo": decision.equipo,
        }
        if not decision.aprobada:
            estado = "MANUAL_TRIAGE"
        elif decision.nivel == 3:
            estado = "AWAITING_APPROVAL"
        else:
            estado = "PENDING"
        confianza = None if decision.confianza is None else round(decision.confianza, 3)

        with self._transaccion(tenant_id) as cur:
            seq = self._evento(cur, tenant_id, ticket_id, EVENTO_DECISION, detalle)
            cur.execute(
                """
                UPDATE tickets
                   SET playbook = %s,
                       confianza = %s,
                       autonomia_aplicada = %s,
                       execution_status = %s,
                       rechazo_motivo = %s,
                       actualizado_en = now()
                 WHERE tenant_id = %s
                   AND id = %s
                   AND execution_status = 'PENDING'
                   AND playbook IS NULL
                   AND rechazo_motivo IS NULL
                """,
                (
                    decision.playbook_id,
                    confianza,
                    decision.nivel if decision.aprobada else None,
                    estado,
                    decision.motivo,
                    tenant_id,
                    ticket_id,
                ),
            )
            if cur.rowcount != 1:
                raise TicketYaDecidido(
                    f"ticket {ticket_id}: no existe para el inquilino {tenant_id} "
                    "o ya tiene una decisión"
                )
            if estado == "AWAITING_APPROVAL":
                _temporizador(
                    cur, tenant_id, ticket_id, TEMPORIZADOR_APROBACION, PLAZO_APROBACION_MINUTOS
                )
            return seq

    # ---------------------------------------------------------------- ejecución

    def tomar_para_ejecutar(self, tenant_id: int) -> TicketAEjecutar | None:
        """Pasa a EXECUTING el ticket PENDING más antiguo con playbook y lo devuelve.

        FOR UPDATE SKIP LOCKED: dos procesos de EXECUTE nunca toman el mismo ticket.
        El evento EJECUCION_INICIADA queda en la bitácora antes de enviar la orden.
        """
        with self._transaccion(tenant_id) as cur:
            cur.execute(
                """
                SELECT id, playbook, autonomia_aplicada
                  FROM tickets
                 WHERE tenant_id = %s
                   AND execution_status = 'PENDING'
                   AND playbook IS NOT NULL
                 ORDER BY creado_en, id
                 LIMIT 1
                   FOR UPDATE SKIP LOCKED
                """,
                (tenant_id,),
            )
            fila = cur.fetchone()
            if fila is None:
                return None
            ticket_id, playbook_id, nivel = fila
            _cambiar_estado(cur, tenant_id, ticket_id, "PENDING", "EXECUTING")
            self._evento(
                cur,
                tenant_id,
                ticket_id,
                EVENTO_EJECUCION_INICIADA,
                {"playbook": playbook_id, "nivel": nivel},
            )
            return TicketAEjecutar(ticket_id, playbook_id, nivel, _alerta(cur, tenant_id, ticket_id))

    def registrar_ejecucion(
        self,
        tenant_id: int,
        ticket_id: int,
        exito: bool,
        detalle: Mapping[str, Any],
        reversion_en_minutos: int | None = None,
    ) -> None:
        """Cierra la ejecución: EXECUTING pasa a SUCCESS o FAILED, con su evento.

        Si salió bien:
        - ``reversion_en_minutos`` programa la reversión automática (nivel 1).
        - Un nivel 2 abre su plazo de revisión de 2 días (D-33).
        """
        if reversion_en_minutos is not None and reversion_en_minutos <= 0:
            raise ValueError("reversion_en_minutos debe ser positivo")
        with self._transaccion(tenant_id) as cur:
            nivel = _cambiar_estado(
                cur, tenant_id, ticket_id, "EXECUTING", "SUCCESS" if exito else "FAILED"
            )
            self._evento(
                cur,
                tenant_id,
                ticket_id,
                EVENTO_EJECUCION_OK if exito else EVENTO_EJECUCION_FALLIDA,
                dict(detalle),
            )
            if not exito:
                return
            if reversion_en_minutos is not None:
                _temporizador(
                    cur, tenant_id, ticket_id, TEMPORIZADOR_REVERSION, reversion_en_minutos
                )
            if nivel == 2:
                _temporizador(
                    cur, tenant_id, ticket_id, TEMPORIZADOR_REVISION, PLAZO_REVISION_MINUTOS
                )

    # ------------------------------------------------------------- nivel 3

    def aprobar(self, tenant_id: int, ticket_id: int, aprobador: str) -> None:
        """Un integrante aprueba un nivel 3: pasa a PENDING y EXECUTE lo tomará."""
        self._resolver_aprobacion(
            tenant_id, ticket_id, aprobador, "PENDING", EVENTO_APROBACION_CONCEDIDA, ""
        )

    def denegar(self, tenant_id: int, ticket_id: int, aprobador: str, motivo: str) -> None:
        """Un integrante rechaza un nivel 3: queda en REJECTED y no se ejecuta."""
        self._resolver_aprobacion(
            tenant_id, ticket_id, aprobador, "REJECTED", EVENTO_APROBACION_DENEGADA, motivo
        )

    def vencer_aprobaciones(self, tenant_id: int) -> list[int]:
        """Niveles 3 sin respuesta en 2 días: MANUAL_TRIAGE con APROBACION_VENCIDA (D-34)."""
        vencidos: list[int] = []
        with self._transaccion(tenant_id) as cur:
            for temporizador_id, ticket_id in _temporizadores_vencidos(
                cur, tenant_id, TEMPORIZADOR_APROBACION
            ):
                _disparar(cur, temporizador_id)
                cur.execute(
                    """
                    UPDATE tickets
                       SET execution_status = 'MANUAL_TRIAGE',
                           rechazo_motivo = 'APROBACION_VENCIDA',
                           actualizado_en = now()
                     WHERE tenant_id = %s AND id = %s
                       AND execution_status = 'AWAITING_APPROVAL'
                    """,
                    (tenant_id, ticket_id),
                )
                if cur.rowcount == 1:
                    self._evento(
                        cur,
                        tenant_id,
                        ticket_id,
                        EVENTO_APROBACION_VENCIDA,
                        {"plazo_minutos": PLAZO_APROBACION_MINUTOS},
                    )
                    vencidos.append(ticket_id)
        return vencidos

    # ------------------------------------------------------------- reversión

    def solicitar_reversion(self, tenant_id: int, ticket_id: int, solicitante: str) -> None:
        """Una persona pide revertir una medida (nivel 2, o un nivel 1 antes de su plazo).

        Deja un temporizador de reversión vencido ahora mismo; EXECUTE lo toma en su
        próximo ciclo. Si ya había uno pendiente, lo adelanta.
        """
        solicitante = _persona(solicitante)
        with self._transaccion(tenant_id) as cur:
            cur.execute(
                """
                SELECT 1 FROM tickets
                 WHERE tenant_id = %s AND id = %s AND execution_status = 'SUCCESS'
                   FOR UPDATE
                """,
                (tenant_id, ticket_id),
            )
            if cur.fetchone() is None:
                raise EstadoInvalido(f"ticket {ticket_id}: sólo se revierte una medida en SUCCESS")
            if _revertido(cur, tenant_id, ticket_id):
                raise EstadoInvalido(f"ticket {ticket_id}: la medida ya fue revertida")
            cur.execute(
                """
                UPDATE temporizadores SET vence_en = now()
                 WHERE tenant_id = %s AND ticket_id = %s AND tipo = %s
                   AND disparado_en IS NULL
                """,
                (tenant_id, ticket_id, TEMPORIZADOR_REVERSION),
            )
            if cur.rowcount == 0:
                _temporizador(cur, tenant_id, ticket_id, TEMPORIZADOR_REVERSION, 0)
            self._evento(
                cur, tenant_id, ticket_id, EVENTO_REVERSION_SOLICITADA, {}, actor=solicitante
            )

    def tomar_reversion(self, tenant_id: int) -> ReversionPendiente | None:
        """Toma la reversión vencida más antigua y la marca como disparada."""
        with self._transaccion(tenant_id) as cur:
            cur.execute(
                """
                SELECT tm.id, tm.ticket_id, t.playbook
                  FROM temporizadores tm
                  JOIN tickets t ON t.tenant_id = tm.tenant_id AND t.id = tm.ticket_id
                 WHERE tm.tenant_id = %s AND tm.tipo = %s
                   AND tm.disparado_en IS NULL AND tm.vence_en <= now()
                 ORDER BY tm.vence_en, tm.id
                 LIMIT 1
                   FOR UPDATE OF tm SKIP LOCKED
                """,
                (tenant_id, TEMPORIZADOR_REVERSION),
            )
            fila = cur.fetchone()
            if fila is None:
                return None
            temporizador_id, ticket_id, playbook_id = fila
            _disparar(cur, temporizador_id)
            self._evento(
                cur,
                tenant_id,
                ticket_id,
                EVENTO_REVERSION_INICIADA,
                {"temporizador": temporizador_id},
            )
            return ReversionPendiente(ticket_id, playbook_id, _alerta(cur, tenant_id, ticket_id))

    def registrar_reversion(
        self, tenant_id: int, ticket_id: int, exito: bool, detalle: Mapping[str, Any]
    ) -> None:
        """Resultado de una reversión. Si salió bien, termina los recordatorios del nivel 2.

        Una reversión fallida no se reintenta sola: queda en la bitácora para que una
        persona la resuelva (y puede volver a pedirla).
        """
        with self._transaccion(tenant_id) as cur:
            self._evento(
                cur,
                tenant_id,
                ticket_id,
                EVENTO_REVERSION_OK if exito else EVENTO_REVERSION_FALLIDA,
                dict(detalle),
            )
            if exito:
                cur.execute(
                    """
                    UPDATE temporizadores SET disparado_en = now()
                     WHERE tenant_id = %s AND ticket_id = %s AND tipo = %s
                       AND disparado_en IS NULL
                    """,
                    (tenant_id, ticket_id, TEMPORIZADOR_REVISION),
                )

    def tomar_recordatorios(self, tenant_id: int) -> list[int]:
        """Niveles 2 con el plazo de revisión vencido: un recordatorio diario (D-33).

        Cada uno deja el evento RECORDATORIO_REVISION y programa el siguiente para
        dentro de un día. La medida sigue vigente: nunca se revierte sola.
        Devuelve los tickets a recordar (los avisa SOAR-NOTIFY).
        """
        tickets: list[int] = []
        with self._transaccion(tenant_id) as cur:
            for temporizador_id, ticket_id in _temporizadores_vencidos(
                cur, tenant_id, TEMPORIZADOR_REVISION
            ):
                _disparar(cur, temporizador_id)
                _temporizador(
                    cur,
                    tenant_id,
                    ticket_id,
                    TEMPORIZADOR_REVISION,
                    INTERVALO_RECORDATORIO_MINUTOS,
                )
                self._evento(cur, tenant_id, ticket_id, EVENTO_RECORDATORIO, {})
                tickets.append(ticket_id)
        return tickets

    # ------------------------------------------------- contadores y cortacircuito

    def usos(
        self,
        tenant_id: int,
        definiciones: Sequence[DefinicionUso],
        equipo: str | None = None,
        playbook_id: str | None = None,
    ) -> dict[str, int]:
        """Cuántas acciones automáticas lleva cada contador en su ventana.

        Cuenta las decisiones aprobadas de nivel 1 y 2 registradas en la bitácora.
        Un contador que esta capa no conoce, o que necesita un equipo o un playbook
        que no se entregó, no aparece en el resultado: la configuración de VALIDATE
        lo trata como si estuviera en su tope (falla segura).
        """
        resultado: dict[str, int] = {}
        with self._transaccion(tenant_id) as cur:
            for d in definiciones:
                filtro, parametros = _filtro_contador(d.nombre, equipo, playbook_id)
                if filtro is None:
                    continue
                cur.execute(
                    f"""
                    SELECT count(*)
                      FROM auditoria
                     WHERE tenant_id = %s
                       AND evento = %s
                       AND detalle->>'resultado' = 'aprobada'
                       AND (detalle->>'nivel')::int = ANY(%s)
                       AND creado_en >= now() - make_interval(mins => %s)
                       {filtro}
                    """,
                    (
                        tenant_id,
                        EVENTO_DECISION,
                        list(NIVELES_AUTOMATICOS),
                        d.ventana_minutos,
                        *parametros,
                    ),
                )
                resultado[d.nombre] = cur.fetchone()[0]
        return resultado

    def alertas_en_ventana(self, tenant_id: int, ventana_minutos: int) -> int:
        """Tickets creados en la ventana: es lo que mide el disparo del cortacircuito."""
        with self._transaccion(tenant_id) as cur:
            cur.execute(
                """
                SELECT count(*)
                  FROM tickets
                 WHERE tenant_id = %s
                   AND creado_en >= now() - make_interval(mins => %s)
                """,
                (tenant_id, ventana_minutos),
            )
            return cur.fetchone()[0]

    def cortacircuito_abierto(self, tenant_id: int, ambito: str = AMBITO_INQUILINO) -> bool:
        """Estado vigente del cortacircuito: su fila más reciente. Sin filas, cerrado."""
        with self._transaccion(tenant_id) as cur:
            return _cortacircuito_abierto(cur, tenant_id, ambito)

    def abrir_cortacircuito(
        self, tenant_id: int, motivo: str, ambito: str = AMBITO_INQUILINO
    ) -> bool:
        """Abre el cortacircuito y lo deja en la bitácora. Devuelve False si ya estaba abierto.

        Cerrarlo es decisión de una persona (SOAR-CONSOLE); esta capa no lo ofrece.
        """
        with self._transaccion(tenant_id) as cur:
            # Serializa las aperturas de un mismo inquilino para no duplicar la fila.
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('cortacircuito'), %s)", (tenant_id,))
            if _cortacircuito_abierto(cur, tenant_id, ambito):
                return False
            cur.execute(
                """
                INSERT INTO cortacircuito (tenant_id, ambito, abierto, motivo)
                VALUES (%s, %s, true, %s)
                """,
                (tenant_id, ambito, motivo),
            )
            self._evento(
                cur, tenant_id, None, EVENTO_CORTACIRCUITO, {"ambito": ambito, "motivo": motivo}
            )
            return True

    # ------------------------------------------------------------- avisos

    def eventos_para_avisar(self, tenant_id: int, limite: int = 50) -> list[EventoAvisable]:
        """Eventos a avisar posteriores al último aviso registrado, en orden de seq.

        El punto de avance es el mayor ``seq_origen`` de los eventos AVISO_ENVIADO: un
        aviso que no se pudo enviar se vuelve a ofrecer en el ciclo siguiente.
        Supone un único proceso de SOAR-NOTIFY.
        """
        with self._transaccion(tenant_id) as cur:
            cur.execute(
                """
                SELECT a.seq, a.evento, a.ticket_id, a.detalle,
                       t.titulo, t.playbook, t.autonomia_aplicada
                  FROM auditoria a
                  LEFT JOIN tickets t ON t.tenant_id = a.tenant_id AND t.id = a.ticket_id
                 WHERE a.tenant_id = %s
                   AND (a.evento = ANY(%s)
                        OR (a.evento = %s AND a.detalle->>'resultado' = 'aprobada'
                            AND a.detalle->>'nivel' = '3')
                        OR (a.evento = %s AND t.autonomia_aplicada = 2))
                   AND a.seq > (
                        SELECT coalesce(max((detalle->>'seq_origen')::bigint), 0)
                          FROM auditoria
                         WHERE tenant_id = %s AND evento = %s)
                 ORDER BY a.seq
                 LIMIT %s
                """,
                (
                    tenant_id,
                    list(EVENTOS_AVISABLES),
                    EVENTO_DECISION,
                    EVENTO_EJECUCION_OK,
                    tenant_id,
                    EVENTO_AVISO_ENVIADO,
                    limite,
                ),
            )
            return [EventoAvisable(*fila) for fila in cur.fetchall()]

    def registrar_aviso(self, tenant_id: int, seq_origen: int, referencia: str) -> None:
        """Deja en la bitácora que el evento ``seq_origen`` se avisó al equipo."""
        with self._transaccion(tenant_id) as cur:
            cur.execute(
                "SELECT ticket_id FROM auditoria WHERE tenant_id = %s AND seq = %s",
                (tenant_id, seq_origen),
            )
            fila = cur.fetchone()
            if fila is None:
                raise ValueError(f"no existe el evento {seq_origen} del inquilino {tenant_id}")
            self._evento(
                cur,
                tenant_id,
                fila[0],
                EVENTO_AVISO_ENVIADO,
                {"seq_origen": seq_origen, "referencia": referencia},
            )

    # ------------------------------------------------------------------- interno

    def _resolver_aprobacion(
        self,
        tenant_id: int,
        ticket_id: int,
        aprobador: str,
        estado: str,
        evento: str,
        motivo: str,
    ) -> None:
        aprobador = _persona(aprobador)
        with self._transaccion(tenant_id) as cur:
            _cambiar_estado(cur, tenant_id, ticket_id, "AWAITING_APPROVAL", estado)
            cur.execute(
                """
                UPDATE temporizadores SET disparado_en = now()
                 WHERE tenant_id = %s AND ticket_id = %s AND tipo = %s
                   AND disparado_en IS NULL
                """,
                (tenant_id, ticket_id, TEMPORIZADOR_APROBACION),
            )
            self._evento(cur, tenant_id, ticket_id, evento, {"motivo": motivo}, actor=aprobador)

    @contextmanager
    def _transaccion(self, tenant_id: int) -> Iterator[psycopg.Cursor]:
        if isinstance(tenant_id, bool) or not isinstance(tenant_id, int) or tenant_id <= 0:
            raise ValueError(f"tenant_id inválido: {tenant_id!r}")
        with psycopg.connect(self._dsn) as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
            yield cur

    def _evento(
        self,
        cur: psycopg.Cursor,
        tenant_id: int,
        ticket_id: int | None,
        evento: str,
        detalle: dict[str, Any],
        actor: str | None = None,
    ) -> int:
        # seq, hash_anterior, hash y creado_en los asigna el trigger de la cadena.
        cur.execute(
            """
            INSERT INTO auditoria (tenant_id, ticket_id, evento, actor, detalle)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING seq
            """,
            (tenant_id, ticket_id, evento, actor or self._actor, Jsonb(detalle)),
        )
        return cur.fetchone()[0]


def _cortacircuito_abierto(cur: psycopg.Cursor, tenant_id: int, ambito: str) -> bool:
    cur.execute(
        """
        SELECT abierto
          FROM cortacircuito
         WHERE tenant_id = %s AND ambito = %s
         ORDER BY creado_en DESC, id DESC
         LIMIT 1
        """,
        (tenant_id, ambito),
    )
    fila = cur.fetchone()
    return bool(fila and fila[0])


def _cambiar_estado(
    cur: psycopg.Cursor, tenant_id: int, ticket_id: int, desde: str, hacia: str
) -> int | None:
    """Transición de estado condicionada al estado actual. Devuelve el nivel del ticket."""
    cur.execute(
        """
        UPDATE tickets SET execution_status = %s, actualizado_en = now()
         WHERE tenant_id = %s AND id = %s AND execution_status = %s
        RETURNING autonomia_aplicada
        """,
        (hacia, tenant_id, ticket_id, desde),
    )
    fila = cur.fetchone()
    if fila is None:
        raise EstadoInvalido(
            f"ticket {ticket_id}: no existe para el inquilino {tenant_id} o no está en {desde}"
        )
    return fila[0]


def _temporizador(
    cur: psycopg.Cursor, tenant_id: int, ticket_id: int, tipo: str, minutos: int
) -> None:
    cur.execute(
        """
        INSERT INTO temporizadores (tenant_id, ticket_id, tipo, vence_en)
        VALUES (%s, %s, %s, now() + make_interval(mins => %s))
        """,
        (tenant_id, ticket_id, tipo, minutos),
    )


def _temporizadores_vencidos(
    cur: psycopg.Cursor, tenant_id: int, tipo: str
) -> list[tuple[int, int]]:
    cur.execute(
        """
        SELECT id, ticket_id
          FROM temporizadores
         WHERE tenant_id = %s AND tipo = %s
           AND disparado_en IS NULL AND vence_en <= now()
         ORDER BY vence_en, id
           FOR UPDATE SKIP LOCKED
        """,
        (tenant_id, tipo),
    )
    return cur.fetchall()


def _disparar(cur: psycopg.Cursor, temporizador_id: int) -> None:
    cur.execute(
        "UPDATE temporizadores SET disparado_en = now() WHERE id = %s", (temporizador_id,)
    )


def _alerta(cur: psycopg.Cursor, tenant_id: int, ticket_id: int) -> dict[str, Any]:
    cur.execute(
        """
        SELECT detalle FROM auditoria
         WHERE tenant_id = %s AND ticket_id = %s AND evento = %s
         ORDER BY seq LIMIT 1
        """,
        (tenant_id, ticket_id, EVENTO_ALERTA),
    )
    fila = cur.fetchone()
    return fila[0] if fila else {}


def _revertido(cur: psycopg.Cursor, tenant_id: int, ticket_id: int) -> bool:
    cur.execute(
        """
        SELECT 1 FROM auditoria
         WHERE tenant_id = %s AND ticket_id = %s AND evento = %s
         LIMIT 1
        """,
        (tenant_id, ticket_id, EVENTO_REVERSION_OK),
    )
    return cur.fetchone() is not None


def _persona(nombre: str) -> str:
    """Quien aprueba o revierte queda como actor del evento: no puede ir vacío."""
    if not isinstance(nombre, str) or not nombre.strip():
        raise ValueError("falta el nombre de la persona")
    return nombre.strip()


def _filtro_contador(
    nombre: str, equipo: str | None, playbook_id: str | None
) -> tuple[str | None, tuple[Any, ...]]:
    """Condición SQL adicional de cada contador de validate.json (nombres fijos)."""
    if nombre == "acciones_por_inquilino":
        return "", ()
    if nombre == "acciones_por_equipo":
        return ("AND detalle->>'equipo' = %s", (equipo,)) if equipo else (None, ())
    if nombre == "acciones_por_playbook":
        return ("AND detalle->>'playbook' = %s", (playbook_id,)) if playbook_id else (None, ())
    if nombre == "acciones_nivel_2":
        return "AND (detalle->>'nivel')::int = 2", ()
    return None, ()
