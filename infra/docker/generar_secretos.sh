#!/usr/bin/env bash
# Genera los secretos locales de la base de desarrollo, sin mostrarlos:
#   - secrets/postgres_password: contraseña del superusuario kronos_admin.
#   - initdb/03_roles.sql: copia de 03_roles.sql.example con contraseñas aleatorias.
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
	sed -e "s/PLACEHOLDER_KRONOS_WORKER/$(aleatoria)/" \
		-e "s/PLACEHOLDER_KRONOS_FRONTEND/$(aleatoria)/" \
		initdb/03_roles.sql.example >initdb/03_roles.sql
	if grep -q "'PLACEHOLDER_" initdb/03_roles.sql; then
		rm -f initdb/03_roles.sql
		echo "Quedaron marcadores PLACEHOLDER sin reemplazar en 03_roles.sql." >&2
		exit 1
	fi
	echo "Creado initdb/03_roles.sql."
fi
