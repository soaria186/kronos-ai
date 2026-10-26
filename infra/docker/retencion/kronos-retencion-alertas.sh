#!/usr/bin/env bash
# Retención de las alertas guardadas de SOAR-AUDIT (R-09).
#
# Ejecuta fn_purgar_alertas(dias) como kronos_admin: borra de alertas_guardadas las
# alertas más antiguas que el plazo, salvo las de tickets en curso o con una medida
# que todavía podría revertirse (ver initdb/06_alertas_guardadas.sql). Cada purga deja
# el evento ALERTAS_PURGADAS en la bitácora del inquilino. La bitácora no se toca.
#
# Variables (con sus valores por omisión, los del servidor):
#   KRONOS_PG_CONTENEDOR     kronos-db-1
#   KRONOS_PG_BASE           kronos
#   KRONOS_PG_USUARIO        kronos_admin
#   KRONOS_RETENCION_DIAS    90   (D-46; mínimo 7, lo exige la función)
set -euo pipefail

CONTENEDOR="${KRONOS_PG_CONTENEDOR:-kronos-db-1}"
BASE="${KRONOS_PG_BASE:-kronos}"
USUARIO="${KRONOS_PG_USUARIO:-kronos_admin}"
DIAS="${KRONOS_RETENCION_DIAS:-90}"

fallar() {
	echo "kronos-retencion-alertas: $*" >&2
	exit 1
}

[[ "$DIAS" =~ ^[1-9][0-9]*$ ]] || fallar "KRONOS_RETENCION_DIAS debe ser un entero positivo"
command -v docker >/dev/null || fallar "falta docker"
docker exec "$CONTENEDOR" pg_isready -q -U "$USUARIO" -d "$BASE" ||
	fallar "PostgreSQL no responde en el contenedor $CONTENEDOR"

# DIAS ya se validó como entero: se puede escribir en la consulta.
resultado="$(docker exec "$CONTENEDOR" psql -U "$USUARIO" -d "$BASE" -X -q -A -t -F ' ' \
	-v ON_ERROR_STOP=1 -c "SELECT inquilino, purgadas FROM fn_purgar_alertas($DIAS)")" ||
	fallar "falló fn_purgar_alertas($DIAS)"

if [ -z "$resultado" ]; then
	echo "kronos-retencion-alertas: plazo $DIAS días; nada que purgar"
else
	while read -r inquilino purgadas; do
		echo "kronos-retencion-alertas: plazo $DIAS días; inquilino $inquilino: $purgadas alertas purgadas"
	done <<<"$resultado"
fi
