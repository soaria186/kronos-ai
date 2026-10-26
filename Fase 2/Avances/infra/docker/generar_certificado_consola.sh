#!/usr/bin/env bash
# Certificado TLS autofirmado para SOAR-CONSOLE, válido para la IP donde escucha.
#
#   bash generar_certificado_consola.sh <IP>     (en el servidor, la IP de NetBird)
#
# Crea secrets/consola_certificado.pem y secrets/consola_llave.pem. El navegador avisará
# que el certificado no es de una autoridad conocida: la primera vez se revisa que la
# huella SHA-256 que muestra el navegador sea la que imprime este script.
set -euo pipefail
# En Git Bash (Windows) evita que «/CN=...» se convierta en una ruta de Windows.
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")"
umask 077

ip="${1:?uso: $0 <IP>}"
[[ "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || { echo "IP inválida: $ip" >&2; exit 1; }
mkdir -p secrets
if [ -f secrets/consola_certificado.pem ]; then
	echo "Ya existe secrets/consola_certificado.pem; bórralo antes para generar otro." >&2
	exit 1
fi
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -days 825 \
	-subj "/CN=Kronos AI consola" -addext "subjectAltName=IP:$ip" \
	-keyout secrets/consola_llave.pem -out secrets/consola_certificado.pem 2>secrets/.openssl.log ||
	{ cat secrets/.openssl.log >&2; rm -f secrets/.openssl.log secrets/consola_llave.pem; exit 1; }
rm -f secrets/.openssl.log
echo "Creado el certificado de la consola para $ip."
openssl x509 -in secrets/consola_certificado.pem -noout -fingerprint -sha256
