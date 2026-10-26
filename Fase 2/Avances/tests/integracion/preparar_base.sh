#!/usr/bin/env bash
# Crea la base de las pruebas de integración (kronos_pruebas) en un PostgreSQL al que llega
# psql, sin Docker. Aplica infra/docker/initdb en el mismo orden que el contenedor de la base,
# con contraseñas aleatorias para los roles. Lo usa el CI (servicio postgres) y sirve en un PC
# con PostgreSQL instalado. Con la base del compose, se usa ejecutar.sh.
#
# Variables de psql: PGHOST, PGPORT, PGUSER (un superusuario, por ejemplo kronos_admin) y, si
# hace falta, PGPASSWORD. KRONOS_BASE_PRUEBAS cambia el nombre de la base, que debe terminar
# en «_pruebas» (tests/integracion/_base.py rechaza cualquier otra).
#
# Imprime las tres conexiones (KRONOS_DSN, KRONOS_DSN_CONSOLA y KRONOS_DSN_ADMIN), una por
# línea y como NOMBRE=valor, para «>> "$GITHUB_ENV"» en el CI. Los roles son de todo el
# servidor: si ya existen, sólo se les cambia la contraseña. En un PC, desde la raíz:
#
#   while IFS= read -r linea; do export "$linea"; done < <(bash tests/integracion/preparar_base.sh)
#   python -m unittest discover -s tests/integracion
set -euo pipefail

RAIZ=$(cd "$(dirname "$0")/../.." && pwd)
INITDB="$RAIZ/infra/docker/initdb"
BASE="${KRONOS_BASE_PRUEBAS:-kronos_pruebas}"

case "$BASE" in
*_pruebas) ;;
*)
	echo "La base de pruebas debe terminar en _pruebas: $BASE" >&2
	exit 1
	;;
esac

psql_q() { psql -X -q -v ON_ERROR_STOP=1 "$@" >/dev/null; }
aleatoria() { openssl rand -hex 16; }
existe_rol() {
	[ "$(psql -X -At -d postgres -c "SELECT 1 FROM pg_roles WHERE rolname = '$1'")" = "1" ]
}

psql_q -d postgres -c "DROP DATABASE IF EXISTS $BASE WITH (FORCE)"
psql_q -d postgres -c "CREATE DATABASE $BASE"

clave_worker=$(aleatoria)
clave_frontend=$(aleatoria)
clave_consola=$(aleatoria)

psql_q -d "$BASE" -f "$INITDB/01_extensiones.sql"
psql_q -d "$BASE" -f "$INITDB/02_esquema.sql"

# 03_roles.sql nace de la plantilla, como en generar_secretos.sh. Si los roles ya existen (otra
# corrida en el mismo servidor), su CREATE ROLE pasa a ser un ALTER ROLE con la clave nueva.
roles=$(sed -e "s/PLACEHOLDER_KRONOS_WORKER/$clave_worker/" \
	-e "s/PLACEHOLDER_KRONOS_FRONTEND/$clave_frontend/" "$INITDB/03_roles.sql.example")
for rol in kronos_worker kronos_frontend; do
	if existe_rol "$rol"; then
		roles=$(printf '%s\n' "$roles" | python3 -c '
import re, sys
rol = sys.argv[1]
texto = sys.stdin.read()
patron = re.compile(r"CREATE ROLE " + rol + r"\s+LOGIN PASSWORD (\x27[^\x27]*\x27)[^;]*;")
print(patron.sub(lambda m: "ALTER ROLE " + rol + " LOGIN PASSWORD " + m.group(1) + ";", texto))
' "$rol")
	fi
done
printf '%s\n' "$roles" | psql_q -d "$BASE"

psql_q -d "$BASE" -f "$INITDB/04_consola.sql"
psql_q -d "$BASE" -c "ALTER ROLE kronos_console LOGIN PASSWORD '$clave_consola'"
psql_q -d "$BASE" -f "$INITDB/06_alertas_guardadas.sql"

# Las migraciones son idempotentes: sobre el esquema nuevo no cambian nada, y así se prueba.
for migracion in "$RAIZ"/infra/docker/migraciones/*.sql; do
	psql_q -d "$BASE" -f "$migracion"
done

conexion="host=${PGHOST:-localhost} port=${PGPORT:-5432} dbname=$BASE"
echo "KRONOS_DSN=$conexion user=kronos_worker password=$clave_worker"
echo "KRONOS_DSN_CONSOLA=$conexion user=kronos_console password=$clave_consola"
admin="KRONOS_DSN_ADMIN=$conexion user=${PGUSER:-kronos_admin}"
if [ -n "${PGPASSWORD:-}" ]; then
	admin="$admin password=$PGPASSWORD"
fi
echo "$admin"
