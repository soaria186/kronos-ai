"""Lecturas y acciones de SOAR-CONSOLE, conectada como kronos_console.

Lee sólo las vistas de ``frontend`` y escribe sólo con las funciones de ``consola``
(infra/docker/initdb/04_consola.sql). Cada operación fija el inquilino dentro de su
transacción, igual que persistencia/repositorio.py.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

DIAS_RECIENTES = 7


class AccionRechazada(RuntimeError):
    """La base rechazó la acción (estado que ya cambió, motivo vacío, etc.)."""


class Datos:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def panel(self, tenant_id: int) -> dict[str, list[dict[str, Any]]]:
        with self._transaccion(tenant_id) as cur:
            return {
                "pendientes": _filas(
                    cur,
                    """
                    SELECT t.id, t.titulo, t.playbook, t.severidad, t.creado_en,
                           tm.vence_en
                      FROM frontend.tickets t
                      LEFT JOIN frontend.temporizadores tm
                        ON tm.ticket_id = t.id AND tm.tipo = 'APROBACION'
                       AND tm.disparado_en IS NULL
                     WHERE t.execution_status = 'AWAITING_APPROVAL'
                     ORDER BY t.creado_en
                    """,
                ),
                # RF-19: medidas de nivel 2 vigentes, con su antigüedad frente al plazo.
                "activas": _filas(
                    cur,
                    """
                    SELECT t.id, t.titulo, t.playbook,
                           (SELECT min(a.creado_en) FROM frontend.auditoria a
                             WHERE a.ticket_id = t.id AND a.evento = 'EJECUCION_OK')
                               AS ejecutada_en,
                           (SELECT min(tm.vence_en) FROM frontend.temporizadores tm
                             WHERE tm.ticket_id = t.id AND tm.tipo = 'REVISION')
                               AS revisar_antes_de,
                           EXISTS (SELECT 1 FROM frontend.temporizadores tm
                                    WHERE tm.ticket_id = t.id AND tm.tipo = 'REVERSION'
                                      AND tm.disparado_en IS NULL) AS reversion_pedida
                      FROM frontend.tickets t
                     WHERE t.execution_status = 'SUCCESS' AND t.autonomia_aplicada = 2
                       AND NOT EXISTS (SELECT 1 FROM frontend.auditoria a
                                        WHERE a.ticket_id = t.id
                                          AND a.evento = 'REVERSION_OK')
                     ORDER BY t.actualizado_en
                    """,
                ),
                "fallidas": _filas(
                    cur,
                    """
                    SELECT a.ticket_id AS id, a.evento, a.creado_en,
                           a.detalle->>'motivo' AS motivo, a.detalle->>'error' AS error,
                           t.titulo, t.playbook
                      FROM frontend.auditoria a
                      LEFT JOIN frontend.tickets t ON t.id = a.ticket_id
                     WHERE a.evento IN ('EJECUCION_FALLIDA', 'REVERSION_FALLIDA')
                       AND a.creado_en >= now() - make_interval(days => %s)
                     ORDER BY a.seq DESC
                    """,
                    DIAS_RECIENTES,
                ),
                "triage": _filas(
                    cur,
                    """
                    SELECT id, titulo, playbook, rechazo_motivo, creado_en
                      FROM frontend.tickets
                     WHERE execution_status = 'MANUAL_TRIAGE'
                       AND creado_en >= now() - make_interval(days => %s)
                     ORDER BY creado_en DESC
                    """,
                    DIAS_RECIENTES,
                ),
                "cortacircuito": _filas(
                    cur,
                    "SELECT ambito, abierto, motivo, creado_en FROM frontend.cortacircuito",
                ),
            }

    def aprobar(self, tenant_id: int, ticket_id: int, persona: str) -> None:
        self._accion(tenant_id, "SELECT consola.aprobar(%s, %s)", ticket_id, persona)

    def denegar(
        self, tenant_id: int, ticket_id: int, persona: str, motivo: str
    ) -> None:
        self._accion(
            tenant_id, "SELECT consola.denegar(%s, %s, %s)", ticket_id, persona, motivo
        )

    def revertir(self, tenant_id: int, ticket_id: int, persona: str) -> None:
        self._accion(
            tenant_id, "SELECT consola.solicitar_reversion(%s, %s)", ticket_id, persona
        )

    def cerrar_cortacircuito(self, tenant_id: int, persona: str, motivo: str) -> None:
        self._accion(
            tenant_id, "SELECT consola.cerrar_cortacircuito(%s, %s)", persona, motivo
        )

    def _accion(self, tenant_id: int, sql: str, *parametros: Any) -> None:
        try:
            with self._transaccion(tenant_id) as cur:
                cur.execute(sql, parametros)
        except psycopg.Error as exc:
            if exc.sqlstate in ("KR001", "KR002"):
                diag = getattr(exc, "diag", None)
                raise AccionRechazada(
                    (diag.message_primary if diag else None) or "acción rechazada"
                ) from None
            raise

    @contextmanager
    def _transaccion(self, tenant_id: int) -> Iterator[psycopg.Cursor]:
        if (
            isinstance(tenant_id, bool)
            or not isinstance(tenant_id, int)
            or tenant_id <= 0
        ):
            raise ValueError(f"tenant_id inválido: {tenant_id!r}")
        with (
            psycopg.connect(self._dsn) as conn,
            conn.transaction(),
            conn.cursor(row_factory=dict_row) as cur,
        ):
            cur.execute(
                "SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),)
            )
            yield cur


def _filas(cur: psycopg.Cursor, sql: str, *parametros: Any) -> list[dict[str, Any]]:
    cur.execute(sql, parametros)
    return cur.fetchall()
