#!/usr/bin/env bash
# Prueba de los scripts de Active Response de Kronos POR LA API de Wazuh, contra el agente 002 (EP-WKS-01).
# Usa el usuario de API kronos-execute (el mismo de SOAR-EXECUTE); su contrasena se lee del secreto del
# servidor y nunca se muestra.
# Uso, en SOAR-CORE-01:
#   bash probar-ar-api.sh estado
#   bash probar-ar-api.sh orden kronos-bloquear-ip.cmd aplicar 203.0.113.60
#   bash probar-ar-api.sh orden kronos-bloquear-ip.cmd quitar 203.0.113.60
#   bash probar-ar-api.sh orden kronos-deshabilitar-cuenta.cmd aplicar usuario.demo
#   bash probar-ar-api.sh orden kronos-deshabilitar-cuenta.cmd habilitar usuario.demo
#   bash probar-ar-api.sh orden kronos-aislar-equipo.cmd quitar
set -euo pipefail
M=single-node-wazuh.manager-1
CLAVE=/opt/kronos/audit/infra/docker/secrets/wazuh_api_password
AGENTE=002

estado() {
	echo "== $(date -u +%FT%TZ) agente $AGENTE"
	sudo docker exec "$M" /var/ossec/bin/agent_control -i "$AGENTE" | grep -Ei "name|status|last keep"
}

orden() {
	local script=${1:?falta el script, por ejemplo kronos-bloquear-ip.cmd}
	shift
	[[ $script =~ ^kronos-[a-z-]+\.cmd$ ]] || { echo "script no valido: $script"; exit 1; }
	local a args=""
	for a in "$@"; do
		[[ $a =~ ^[A-Za-z0-9._-]{1,64}$ ]] || { echo "argumento no valido: $a"; exit 1; }
		args+="\"$a\","
	done
	args="[${args%,}]"
	local token
	token=$(sudo cat "$CLAVE" | sudo docker exec -i "$M" sh -c 'IFS= read -r K || true; curl -sk -u "kronos-execute:$K" -X POST "https://localhost:55000/security/user/authenticate?raw=true"')
	[[ $token == ey* ]] || { echo "no se obtuvo el token de kronos-execute"; exit 1; }
	echo "== $(date -u +%FT%TZ) !$script $args -> agente $AGENTE"
	printf '{"command":"!%s","arguments":%s}' "$script" "$args" |
		sudo docker exec -i -e T="$token" "$M" sh -c 'curl -sk -X PUT -H "Authorization: Bearer $T" -H "Content-Type: application/json" "https://localhost:55000/active-response?agents_list='"$AGENTE"'" -d @-'
	echo
}

case "${1:-}" in
	estado) estado ;;
	orden) shift; orden "$@" ;;
	*) echo "uso: bash $0 estado | orden <script.cmd> <argumentos...>"; exit 1 ;;
esac
