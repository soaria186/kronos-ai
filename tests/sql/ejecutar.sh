#!/usr/bin/env bash
# Ejecuta las pruebas a-d del esquema de persistencia contra el contenedor de
# infra/docker. Se conecta con "docker compose exec" (no hay puertos publicados).
#
# Las pruebas corren como kronos_worker: el superusuario se salta la RLS. Sólo se usa
# kronos_admin para elegir inquilinos nuevos, para la parte de la prueba c que
# comprueba que el administrador tampoco puede modificar, y para crear y manipular
# la copia de prueba de la prueba d.
#
# Uso (con la base levantada):  bash tests/sql/ejecutar.sh
set -euo pipefail

RAIZ=$(cd "$(dirname "$0")/../.." && pwd)
DIR="$RAIZ/tests/sql"
COMPOSE=(docker compose -f "$RAIZ/infra/docker/docker-compose.yml")
BASE=kronos
COPIA=kronos_copia_prueba

psql_como() { # rol base [args psql...]
	local rol=$1 base=$2
	shift 2
	"${COMPOSE[@]}" exec -T db psql -X -q -v ON_ERROR_STOP=1 -U "$rol" -d "$base" "$@"
}

pgbench_worker() { # inquilino conexiones filas_por_conexion
	"${COMPOSE[@]}" exec -T db pgbench -n -U kronos_worker \
		-c "$2" -j "$2" -t "$3" -D tenant="$1" -f - "$BASE" \
		<"$DIR/pgbench_auditoria.sql"
}

resumen_pgbench() {
	grep -E 'number of clients|number of transactions actually processed|number of failed transactions|^tps' "$1" |
		sed 's/^/    /'
}

titulo() { printf '\n==================== %s ====================\n' "$1"; }

borrar_copia() {
	psql_como kronos_admin postgres -c "DROP DATABASE IF EXISTS $COPIA" >/dev/null 2>&1 || true
}
trap borrar_copia EXIT

TMP=$(mktemp -d)

# Inquilinos nuevos en cada ejecución: la auditoría es inmutable y no se puede vaciar.
ULTIMO=$(psql_como kronos_admin "$BASE" -tA -c "SELECT coalesce(max(tenant_id), 0) FROM auditoria")
TA=$((ULTIMO + 1))
TB=$((ULTIMO + 2))
TC=$((ULTIMO + 3))
echo "Inquilinos de esta ejecución: a=$TA y $TB, b=$TC"

titulo "a) Dos inquilinos en paralelo"
pgbench_worker "$TA" 4 250 >"$TMP/a1.log" 2>&1 &
P1=$!
pgbench_worker "$TB" 4 250 >"$TMP/a2.log" 2>&1 &
P2=$!
ERR=0
wait "$P1" || ERR=1
wait "$P2" || ERR=1
echo "  pgbench inquilino $TA:"
resumen_pgbench "$TMP/a1.log"
echo "  pgbench inquilino $TB:"
resumen_pgbench "$TMP/a2.log"
if [ "$ERR" -ne 0 ]; then
	cat "$TMP/a1.log" "$TMP/a2.log"
	exit 1
fi
psql_como kronos_worker "$BASE" -v ta="$TA" -v tb="$TB" -v filas=1000 <"$DIR/a_dos_inquilinos.sql"

titulo "b) Un inquilino, 8 conexiones x 100 filas"
pgbench_worker "$TC" 8 100 >"$TMP/b.log" 2>&1 || {
	cat "$TMP/b.log"
	exit 1
}
resumen_pgbench "$TMP/b.log"
psql_como kronos_worker "$BASE" -v tc="$TC" -v conexiones=8 -v filas=100 <"$DIR/b_concurrencia.sql"

titulo "c) UPDATE/DELETE/TRUNCATE rechazados"
psql_como kronos_worker "$BASE" -v tc="$TC" <"$DIR/c_inmutabilidad.sql"
psql_como kronos_admin "$BASE" -v tc="$TC" <"$DIR/c_inmutabilidad.sql"

titulo "d) Manipulación detectada (sobre una copia)"
borrar_copia
psql_como kronos_admin postgres -c "CREATE DATABASE $COPIA TEMPLATE $BASE"
psql_como kronos_admin "$COPIA" -v ta="$TA" -v tb="$TB" -v tc="$TC" <"$DIR/d_manipular.sql"
psql_como kronos_worker "$COPIA" -v ta="$TA" -v tb="$TB" -v tc="$TC" <"$DIR/d_verificar.sql"
psql_como kronos_worker "$BASE" -v ta="$TA" -v tb="$TB" -v tc="$TC" <"$DIR/d_original_intacta.sql"

rm -rf "$TMP"
titulo "Todas las pruebas pasaron"
