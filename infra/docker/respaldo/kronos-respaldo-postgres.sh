#!/usr/bin/env bash
# Respaldo cifrado de SOAR-AUDIT (PostgreSQL de Kronos).
#
# Genera un archivo postgres-<base>-<fecha UTC>.tar.age con:
#   - <base>.dump     pg_dump en formato personalizado (-Fc) de la base completa.
#   - globales.sql    roles y permisos del clúster (pg_dumpall --globals-only).
#   - version.txt     versión de PostgreSQL y fecha del respaldo.
#   - SHA256SUMS      sumas de los tres anteriores.
# Todo se cifra con age para los destinatarios del archivo indicado; la llave
# privada no está en el servidor. Conserva las últimas COPIAS y borra las demás.
#
# Variables (con sus valores por omisión, los del servidor):
#   KRONOS_PG_CONTENEDOR           kronos-db-1
#   KRONOS_PG_BASE                 kronos
#   KRONOS_PG_USUARIO              kronos_admin
#   KRONOS_RESPALDO_DESTINO        /var/backups/kronos
#   KRONOS_RESPALDO_DESTINATARIOS  /etc/kronos/respaldo-destinatarios.txt
#   KRONOS_RESPALDO_COPIAS         14
set -euo pipefail
umask 077

CONTENEDOR="${KRONOS_PG_CONTENEDOR:-kronos-db-1}"
BASE="${KRONOS_PG_BASE:-kronos}"
USUARIO="${KRONOS_PG_USUARIO:-kronos_admin}"
DESTINO="${KRONOS_RESPALDO_DESTINO:-/var/backups/kronos}"
DESTINATARIOS="${KRONOS_RESPALDO_DESTINATARIOS:-/etc/kronos/respaldo-destinatarios.txt}"
COPIAS="${KRONOS_RESPALDO_COPIAS:-14}"

fallar() {
	echo "kronos-respaldo-postgres: $*" >&2
	exit 1
}

command -v age >/dev/null || fallar "falta age"
command -v docker >/dev/null || fallar "falta docker"
[ -s "$DESTINATARIOS" ] || fallar "no existe o está vacío el archivo de destinatarios $DESTINATARIOS"
[[ "$COPIAS" =~ ^[1-9][0-9]*$ ]] || fallar "KRONOS_RESPALDO_COPIAS debe ser un entero positivo"
docker exec "$CONTENEDOR" pg_isready -q -U "$USUARIO" -d "$BASE" ||
	fallar "PostgreSQL no responde en el contenedor $CONTENEDOR"

mkdir -p "$DESTINO"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

fecha="$(date -u +%Y%m%dT%H%M%SZ)"
nombre="postgres-${BASE}-${fecha}.tar.age"

docker exec "$CONTENEDOR" pg_dump -U "$USUARIO" -d "$BASE" -Fc >"$tmp/$BASE.dump"
docker exec "$CONTENEDOR" pg_dumpall -U "$USUARIO" --globals-only >"$tmp/globales.sql"

# Comprueba que el volcado se puede leer antes de cifrarlo.
docker exec -i "$CONTENEDOR" pg_restore --list <"$tmp/$BASE.dump" >/dev/null ||
	fallar "pg_restore no puede leer el volcado"

{
	echo "base: $BASE"
	echo "fecha_utc: $fecha"
	docker exec "$CONTENEDOR" postgres --version
} >"$tmp/version.txt"

(cd "$tmp" && sha256sum "$BASE.dump" globales.sql version.txt >SHA256SUMS)

# Se escribe con otro nombre y se renombra al final: un respaldo a medias nunca
# tiene el nombre definitivo ni entra en la rotación.
tar -C "$tmp" -cf - "$BASE.dump" globales.sql version.txt SHA256SUMS |
	age -R "$DESTINATARIOS" -o "$DESTINO/$nombre.parcial"
chmod 640 "$DESTINO/$nombre.parcial"
if [ "$(id -u)" = 0 ] && getent group sudo >/dev/null 2>&1; then
	chgrp sudo "$DESTINO/$nombre.parcial"
fi
mv "$DESTINO/$nombre.parcial" "$DESTINO/$nombre"

# Rotación: conserva las COPIAS más recientes (el nombre lleva la fecha UTC, así
# que el orden alfabético es el cronológico).
find "$DESTINO" -maxdepth 1 -name "postgres-${BASE}-*.tar.age" -printf '%f\n' |
	sort -r | tail -n +"$((COPIAS + 1))" |
	while read -r viejo; do
		rm -f -- "$DESTINO/$viejo"
	done

echo "Respaldo creado: $DESTINO/$nombre ($(du -h "$DESTINO/$nombre" | cut -f1))"
