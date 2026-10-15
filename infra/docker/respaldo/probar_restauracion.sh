#!/usr/bin/env bash
# Prueba que un respaldo de kronos-respaldo-postgres.sh se puede restaurar.
#
#   probar_restauracion.sh <respaldo.tar.age> <llave-privada-age>
#
# Descifra el respaldo, revisa las sumas SHA-256, lo restaura en una base nueva
# (kronos_prueba_restauracion) del mismo contenedor, compara el número de filas con
# la base original, verifica la cadena de hash de todos los inquilinos y borra la
# base de prueba. No toca la base original.
#
# Usa las mismas variables KRONOS_PG_* que el script de respaldo.
set -euo pipefail
umask 077

[ $# -eq 2 ] || {
	echo "uso: $0 <respaldo.tar.age> <llave-privada-age>" >&2
	exit 2
}
RESPALDO="$1"
LLAVE="$2"
CONTENEDOR="${KRONOS_PG_CONTENEDOR:-kronos-db-1}"
BASE="${KRONOS_PG_BASE:-kronos}"
USUARIO="${KRONOS_PG_USUARIO:-kronos_admin}"
PRUEBA="kronos_prueba_restauracion"

psql_en() {
	docker exec -i "$CONTENEDOR" psql -U "$USUARIO" -d "$1" -v ON_ERROR_STOP=1 -Atq "${@:2}"
}

tmp="$(mktemp -d)"
limpiar() {
	rm -rf "$tmp"
	psql_en postgres -c "DROP DATABASE IF EXISTS $PRUEBA" >/dev/null 2>&1 || true
}
trap limpiar EXIT

echo "1. Descifrar y revisar sumas"
age -d -i "$LLAVE" "$RESPALDO" | tar -C "$tmp" -xf -
(cd "$tmp" && sha256sum -c SHA256SUMS)
cat "$tmp/version.txt"

echo "2. Restaurar en $PRUEBA"
psql_en postgres -c "DROP DATABASE IF EXISTS $PRUEBA"
psql_en postgres -c "CREATE DATABASE $PRUEBA"
# Los disparadores de auditoria se crean después de cargar los datos (sección
# post-data de pg_restore), así que seq, creado_en y hash quedan como estaban.
docker exec -i "$CONTENEDOR" pg_restore -U "$USUARIO" -d "$PRUEBA" --exit-on-error <"$tmp/$BASE.dump"

echo "3. Comparar filas (original / restaurada)"
conteo="SELECT concat_ws(' ', (SELECT count(*) FROM tickets), (SELECT count(*) FROM auditoria), (SELECT count(*) FROM cortacircuito))"
read -r t1 a1 c1 <<<"$(psql_en "$BASE" -c "$conteo")"
read -r t2 a2 c2 <<<"$(psql_en "$PRUEBA" -c "$conteo")"
printf '   tickets       %s / %s\n   auditoria     %s / %s\n   cortacircuito %s / %s\n' \
	"$t1" "$t2" "$a1" "$a2" "$c1" "$c2"
for n in "$t1" "$a1" "$c1" "$t2" "$a2" "$c2"; do
	[[ "$n" =~ ^[0-9]+$ ]] || {
		echo "FALLA: no se pudieron contar las filas" >&2
		exit 1
	}
done
# La base original puede haber crecido después del respaldo, pero nunca tener menos.
if [ "$t2" -gt "$t1" ] || [ "$a2" -gt "$a1" ] || [ "$c2" -gt "$c1" ] || [ "$a2" -eq 0 ]; then
	echo "FALLA: los conteos no cuadran o la auditoría restaurada está vacía" >&2
	exit 1
fi

echo "4. Verificar la cadena de hash de cada inquilino"
inquilinos="$(psql_en "$PRUEBA" -c "SELECT count(DISTINCT tenant_id) FROM auditoria")"
rotas="$(psql_en "$PRUEBA" -c "SELECT count(*) FROM (SELECT DISTINCT tenant_id FROM auditoria) t WHERE fn_verificar_cadena(t.tenant_id) IS NOT NULL")"
echo "   inquilinos: $inquilinos, cadenas rotas: $rotas"
[ "$rotas" = 0 ] || {
	echo "FALLA: hay cadenas de auditoría rotas en la copia restaurada" >&2
	exit 1
}

echo "5. Los disparadores de inmutabilidad quedaron activos"
psql_en "$PRUEBA" -c "SELECT tgname || ' ' || tgenabled::text FROM pg_trigger WHERE tgname LIKE 'trg_%' ORDER BY 1"
if psql_en "$PRUEBA" -c "DELETE FROM auditoria" >/dev/null 2>&1; then
	echo "FALLA: la copia restaurada permitió DELETE en auditoria" >&2
	exit 1
fi
echo "   DELETE en auditoria rechazado"

echo "RESTAURACIÓN OK"
