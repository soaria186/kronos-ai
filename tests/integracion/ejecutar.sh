#!/usr/bin/env bash
# Pruebas de integración contra una base de pruebas aparte (kronos_pruebas), nunca la real.
#
# Las pruebas escriben filas que no se pueden borrar (la bitácora es de sólo inserción), así
# que no deben correr contra la base «kronos». Este script:
#   1. crea la base kronos_pruebas con el MISMO esquema que la real (pg_dump --schema-only:
#      tablas, funciones, disparadores, RLS, permisos y migraciones ya aplicadas; sin datos);
#   2. corre las pruebas dentro de la red interna de Docker (la base no publica puertos);
#   3. borra kronos_pruebas al terminar, pasen o fallen.
#
# Uso, con la base levantada (docker compose ... up -d db), desde la raíz del repositorio:
#   bash tests/integracion/ejecutar.sh
#
# Opcional: KRONOS_OLLAMA_URL=http://... para incluir test_validate_ciclo (modelo real);
# sin ella esa prueba se omite. Las contraseñas se leen de infra/docker/secrets/ y viajan
# por variables de entorno (-e NOMBRE, sin valor): no quedan en la línea de comandos.
set -euo pipefail

RAIZ=$(cd "$(dirname "$0")/../.." && pwd)
COMPOSE=(docker compose -f "$RAIZ/infra/docker/docker-compose.yml")
SECRETOS="$RAIZ/infra/docker/secrets"
REAL=kronos
PRUEBAS=kronos_pruebas
RED=${KRONOS_RED_INTERNA:-kronos_interna}
IMAGEN=kronos-pruebas

# Git Bash en Windows convierte las rutas de «-v»; esto lo evita (en Linux no hace nada).
export MSYS_NO_PATHCONV=1

psql_admin() { # base [args psql...]
	local base=$1
	shift
	"${COMPOSE[@]}" exec -T db psql -X -q -v ON_ERROR_STOP=1 -U kronos_admin -d "$base" "$@"
}

borrar_base() {
	psql_admin postgres -c "DROP DATABASE IF EXISTS $PRUEBAS WITH (FORCE)" >/dev/null 2>&1 || true
}
trap borrar_base EXIT

for secreto in kronos_worker_password kronos_console_password; do
	if [ ! -s "$SECRETOS/$secreto" ]; then
		echo "Falta infra/docker/secrets/$secreto (bash infra/docker/generar_secretos.sh)." >&2
		exit 1
	fi
done

echo "== Creando $PRUEBAS con el esquema de $REAL"
borrar_base
psql_admin postgres -c "CREATE DATABASE $PRUEBAS"
"${COMPOSE[@]}" exec -T db pg_dump -U kronos_admin -d "$REAL" --schema-only |
	psql_admin "$PRUEBAS" >/dev/null

echo "== Construyendo la imagen de pruebas"
docker build -q -t "$IMAGEN" -f "$RAIZ/tests/integracion/Dockerfile" "$RAIZ" >/dev/null

KRONOS_DSN="host=db dbname=$PRUEBAS user=kronos_worker password=$(cat "$SECRETOS/kronos_worker_password")"
KRONOS_DSN_CONSOLA="host=db dbname=$PRUEBAS user=kronos_console password=$(cat "$SECRETOS/kronos_console_password")"
export KRONOS_DSN KRONOS_DSN_CONSOLA

echo "== Corriendo las pruebas de integración en $PRUEBAS"
docker run --rm --network "$RED" -v "$RAIZ:/app" \
	-e KRONOS_DSN -e KRONOS_DSN_CONSOLA -e KRONOS_OLLAMA_URL -e KRONOS_MODELO \
	"$IMAGEN"
echo "== Listo: $PRUEBAS se borra al salir; $REAL no se tocó"
