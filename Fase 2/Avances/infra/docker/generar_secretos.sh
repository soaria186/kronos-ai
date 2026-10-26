#!/usr/bin/env bash
# Genera los secretos locales de la base de desarrollo, sin mostrarlos:
#   - secrets/postgres_password: contraseña del superusuario kronos_admin.
#   - initdb/03_roles.sql: copia de 03_roles.sql.example con contraseñas aleatorias.
#   - secrets/kronos_worker_password: la misma contraseña de kronos_worker, para los
#     servicios.
#   - secrets/kronos_console_password e initdb/05_clave_consola.sql: contraseña del rol
#     kronos_console de SOAR-CONSOLE (el rol lo crea 04_consola.sql).
# Ambos están en .gitignore. Si ya existen, no se sobrescriben.
set -euo pipefail
cd "$(dirname "$0")"
umask 077

aleatoria() {
	openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 32
}

mkdir -p secrets
if [ ! -f secrets/postgres_password ]; then
	aleatoria >secrets/postgres_password
	echo "Creado secrets/postgres_password."
fi

if [ ! -f initdb/03_roles.sql ]; then
	worker="$(aleatoria)"
	printf '%s' "$worker" >secrets/kronos_worker_password
	sed -e "s/PLACEHOLDER_KRONOS_WORKER/$worker/" \
		-e "s/PLACEHOLDER_KRONOS_FRONTEND/$(aleatoria)/" \
		initdb/03_roles.sql.example >initdb/03_roles.sql
	if grep -q "'PLACEHOLDER_" initdb/03_roles.sql; then
		rm -f initdb/03_roles.sql
		echo "Quedaron marcadores PLACEHOLDER sin reemplazar en 03_roles.sql." >&2
		exit 1
	fi
	echo "Creado initdb/03_roles.sql y secrets/kronos_worker_password."
fi

# Bases creadas antes de que existiera este archivo: se toma la contraseña de
# kronos_worker de 03_roles.sql. La usan SOAR-EXECUTE y SOAR-NOTIFY (servicios.yml).
if [ ! -f secrets/kronos_worker_password ]; then
	awk '/CREATE ROLE kronos_worker/ { f = 1 }
		f && /LOGIN PASSWORD/ { sub(/.*LOGIN PASSWORD \047/, ""); sub(/\047.*/, ""); printf "%s", $0; exit }' \
		initdb/03_roles.sql >secrets/kronos_worker_password
	if [ ! -s secrets/kronos_worker_password ]; then
		rm -f secrets/kronos_worker_password
		echo "No se encontró la contraseña de kronos_worker en 03_roles.sql." >&2
		exit 1
	fi
	echo "Creado secrets/kronos_worker_password (tomada de 03_roles.sql)."
fi

if [ ! -f secrets/kronos_console_password ]; then
	aleatoria >secrets/kronos_console_password
	echo "Creado secrets/kronos_console_password."
fi
if [ ! -f initdb/05_clave_consola.sql ]; then
	printf "ALTER ROLE kronos_console LOGIN PASSWORD '%s';\n" \
		"$(cat secrets/kronos_console_password)" >initdb/05_clave_consola.sql
	echo "Creado initdb/05_clave_consola.sql."
fi
