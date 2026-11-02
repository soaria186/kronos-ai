#!/usr/bin/env bash
# Despliega Kronos AI en SOAR-CORE-01 desde un clon de git, en una etiqueta de versión (D-55).
#
# Uso, en el servidor, con un usuario con sudo:
#   bash desplegar.sh <etiqueta>          por ejemplo: bash desplegar.sh v1.0.0
#
# - Primera vez (caso a de la parte 07 de la guía): clona en /opt/kronos/kronos-ai con la llave de
#   despliegue de sólo lectura, copia lo que vive sólo en el servidor (.env, secrets/, 03_roles.sql y
#   05_clave_consola.sql), aparta la copia vieja y deja /opt/kronos/audit como enlace al proyecto.
# - Las siguientes: fetch de las etiquetas y checkout de la pedida.
# - Siempre: respaldo previo, KRONOS_AGENTES_SO en el .env si falta, migraciones (idempotentes),
#   reconstrucción de los servicios y su comprobación.
#
# Se detiene en el primer error y dice dónde. Todo queda en ~/kronos-despliegue-<fecha UTC>.log.
# Antes y después: aviso en el grupo del equipo. No muestra secretos.
#
# El cuerpo va en una función: así bash lo lee completo antes de que el checkout cambie este archivo.

principal() {
	set -uo pipefail
	local etiqueta="${1:?falta la etiqueta, por ejemplo: bash desplegar.sh v1.0.0}"
	local log
	log="$HOME/kronos-despliegue-$(date -u +%Y%m%dT%H%M%SZ).log"
	exec > >(tee -a "$log") 2>&1
	local clon=/opt/kronos/kronos-ai
	local llave=/root/.ssh/kronos_despliegue_soaria186
	fallo() {
		echo
		echo "ERROR: $*"
		echo "Se detuvo aquí. Registro: $log"
		exit 1
	}

	echo "== $(date -u +%FT%TZ) despliegue de $etiqueta"
	sudo -v || fallo "sudo"

	echo
	echo "== 1. Respaldo previo"
	sudo systemctl start kronos-respaldo-postgres.service || fallo "respaldo"
	sudo journalctl -u kronos-respaldo-postgres.service -n 3 --no-pager | grep -E "Respaldo creado|Finished|Failed" || true

	if [ ! -d "$clon" ]; then
		echo
		echo "== 2. Clon nuevo en $clon"
		[ -L /opt/kronos/audit ] && fallo "/opt/kronos/audit ya es un enlace, pero no existe el clon"
		[ -e /opt/kronos/audit.antes-del-clon ] && fallo "ya existe /opt/kronos/audit.antes-del-clon"
		sudo GIT_SSH_COMMAND="ssh -i $llave" git clone -q git@github.com:soaria186/kronos-ai.git "$clon" || fallo "git clone"
		sudo git -C "$clon" config core.sshCommand "ssh -i $llave"
		sudo git -C "$clon" -c advice.detachedHead=false checkout -q "$etiqueta" || fallo "checkout de $etiqueta"
		local nuevo="$clon/Fase 2/Avances/infra/docker" viejo=/opt/kronos/audit/infra/docker
		sudo cp -a "$viejo/.env" "$viejo/secrets" "$nuevo/" || fallo "copiar .env y secrets"
		sudo cp -a "$viejo/initdb/03_roles.sql" "$viejo/initdb/05_clave_consola.sql" "$nuevo/initdb/" || fallo "copiar initdb"
		sudo mv /opt/kronos/audit /opt/kronos/audit.antes-del-clon || fallo "apartar la copia vieja"
		sudo ln -s "$clon/Fase 2/Avances" /opt/kronos/audit || fallo "crear el enlace"
	else
		echo
		echo "== 2. Clon existente: cambio a $etiqueta"
		sudo git -C "$clon" fetch -q --tags origin || fallo "git fetch"
		sudo git -C "$clon" -c advice.detachedHead=false checkout -q "$etiqueta" || fallo "checkout de $etiqueta"
	fi
	echo "versión desplegada: $(sudo git -C "$clon" describe --tags)"
	echo "fuera de git (deben ser sólo .env, secrets/, 03_roles.sql y 05_clave_consola.sql):"
	sudo git -C "$clon" status --short --ignored

	cd /opt/kronos/audit/infra/docker || fallo "cd infra/docker"
	local dc="sudo docker compose -f docker-compose.yml -f servicios.yml"

	echo
	echo "== 3. Variables del .env"
	if ! sudo grep -q '^KRONOS_AGENTES_SO=' .env; then
		[ -n "$(sudo tail -c1 .env)" ] && echo | sudo tee -a .env >/dev/null
		echo 'KRONOS_AGENTES_SO=001:linux,002:windows' | sudo tee -a .env >/dev/null
		echo "agregada: KRONOS_AGENTES_SO=001:linux,002:windows"
	else
		echo "ya estaba: KRONOS_AGENTES_SO"
	fi
	echo "nombres del ejemplo que faltan en el .env (los que tienen valor por omisión en servicios.yml pueden faltar):"
	diff <(grep -oE '^[A-Z_]+' servicios/.env.example | sort -u) <(sudo grep -oE '^[A-Z_]+' .env | sort -u) | grep '^<' || echo "(ninguno)"

	echo
	echo "== 4. Migraciones"
	local m
	for m in migraciones/*.sql; do
		echo "-- $m"
		sudo docker exec -i kronos-db-1 psql -U kronos_admin -d kronos -v ON_ERROR_STOP=1 -q <"$m" >/dev/null || fallo "migración $m"
	done

	echo
	echo "== 5. Servicios"
	$dc up -d --build 2>&1 | tail -12
	echo "esperando 30 s a que arranquen..."
	sleep 30
	$dc ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'
	echo
	echo "registros de arranque:"
	$dc logs --since 5m validate execute notify consola 2>&1 | grep -E "en marcha|no arranca|equipo de|sistema operativo|Traceback|ERROR" | tail -20

	echo
	echo "== $(date -u +%FT%TZ) fin. Versión: $(sudo git -C "$clon" describe --tags). Registro: $log"
}

principal "$@"
exit
