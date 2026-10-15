"""Acceso a SOAR-AUDIT para SOAR-VALIDATE (y, más adelante, SOAR-EXECUTE).

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
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

ACTOR_VALIDATE = "soar-validate"

EVENTO_ALERTA = "ALERTA_RECIBIDA"
EVENTO_DECISION = "DECISION"
EVENTO_CORTACIRCUITO = "CORTACIRCUITO_ABIERTO"

# Ámbito del cortacircuito que detiene toda acción automática de un inquilino.
AMBITO_INQUILINO = "inquilino"

SEVERIDAD_MINIMA = 0
SEVERIDAD_MAXIMA = 15

# Niveles que cuentan como «acción automática» para los contadores de tasa: el 0
# sólo reúne contexto y el 3 nunca se ejecuta sin una persona.
NIVELES_AUTOMATICOS = (1, 2)


class TicketYaDecidido(RuntimeError):
    """El ticket no existe para este inquilino o ya tiene una decisión registrada."""


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

        Aprobada: el ticket queda en PENDING con su playbook y su nivel, a la espera
        de SOAR-EXECUTE (o de la aprobación humana, si es nivel 3).
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
        estado = "PENDING" if decision.aprobada else "MANUAL_TRIAGE"
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
            return seq

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

    # ------------------------------------------------------------------- interno

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
    ) -> int:
        # seq, hash_anterior, hash y creado_en los asigna el trigger de la cadena.
        cur.execute(
            """
            INSERT INTO auditoria (tenant_id, ticket_id, evento, actor, detalle)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING seq
            """,
            (tenant_id, ticket_id, evento, self._actor, Jsonb(detalle)),
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
