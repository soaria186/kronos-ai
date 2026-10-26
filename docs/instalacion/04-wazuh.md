# 04 · Wazuh 4.14.8: compose, puertos y certificados

| Campo | Valor |
| :--- | :--- |
| Parte | 04 de 15 |
| Responsable | Nicolás Zamora (revisa: Rodrigo Riveros) |
| Versión | 0.9, 26-10-2026 |
| Estado | Borrador para revisión: sigue `infra/wazuh/docker-compose.yml.example` y la instalación oficial de Wazuh con Docker. Nicolás confirma la ruta, el cambio de contraseñas y el respaldo de Wazuh tal como se hicieron |
| Requisitos | Partes 01 a 03 |

Wazuh es SOAR-DETECT: recibe los eventos de los agentes, los correlaciona y escribe las alertas en
`alerts.json`. Se instala en un solo nodo (manager, indexador y dashboard) con el compose oficial de Wazuh y los
puertos que fija Kronos.

| Puerto | Servicio | Dónde escucha |
| :--- | :--- | :--- |
| 1514/TCP | Eventos de los agentes | Todas las interfaces (único puerto público de Kronos) |
| 1515/TCP | Registro automático de agentes | **No se publica**: los agentes se registran desde el servidor (partes 09 y 10) |
| 55000/TCP | API del manager | Sólo IP de NetBird |
| 9200/TCP | Indexador | Sólo IP de NetBird |
| 5601/TCP | Dashboard (uso interno del equipo, nunca se muestra a la PyME) | Sólo IP de NetBird |

---

## 1. Requisito del indexador

```
[servidor] echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/90-wazuh.conf
[servidor] sudo sysctl --system | grep max_map_count
```

**Debe mostrar:** `vm.max_map_count = 262144`.

## 2. Compose oficial, versión 4.14.8

```
[servidor] sudo git clone https://github.com/wazuh/wazuh-docker.git -b v4.14.8 /opt/wazuh-docker
[servidor] cd /opt/wazuh-docker/single-node
```

La carpeta tiene que seguir llamándose `single-node`: Compose toma de ahí el nombre del proyecto, y Kronos usa
el volumen de logs `single-node_wazuh_logs` (SOAR-VALIDATE lee ahí `alerts.json`) y la red
`single-node_default` (SOAR-EXECUTE llega por ella a la API). Si cambia, hay que cambiar `KRONOS_WAZUH_LOGS` y
`KRONOS_WAZUH_RED` (parte 07).

## 3. Certificados internos

```
[servidor] sudo docker compose -f generate-indexer-certs.yml run --rm generator
[servidor] ls config/wazuh_indexer_ssl_certs/
```

**Debe mostrar:** `root-ca.pem`, `admin.pem`, `wazuh.indexer.pem`, `wazuh.manager.pem`, `wazuh.dashboard.pem` y sus
llaves. No salen del servidor ni van al repositorio (`.gitignore`).

## 4. Compose de Kronos

Copiar `infra/wazuh/docker-compose.yml.example` del repositorio sobre `docker-compose.yml`. Difiere del oficial
en los puertos: 1514 público, 1515 sin publicar y el resto sólo en la IP de NetBird.

```
[PC]       scp infra/wazuh/docker-compose.yml.example soar-core-01:~/
[servidor] sudo install -m 600 ~/docker-compose.yml.example /opt/wazuh-docker/single-node/docker-compose.yml
[servidor] rm ~/docker-compose.yml.example
[servidor] echo 'NETBIRD_IP=XXXX' | sudo tee /opt/wazuh-docker/single-node/.env >/dev/null
```

`XXXX` es la IP de NetBird del servidor (parte 02).

## 5. Contraseñas propias

El ejemplo trae `CAMBIAR` donde van las contraseñas de los usuarios internos de Wazuh: `admin` del indexador,
`kibanaserver` del dashboard y `wazuh-wui` de la API. Se cambian **antes de exponer nada**, con el
procedimiento oficial de Wazuh para Docker («Changing the default password of Wazuh users»):

1. Generar cada contraseña nueva en el gestor del equipo: de 8 a 64 caracteres, con mayúsculas, minúsculas,
   números y símbolos. Usar sólo los símbolos `! @ $ % * ? & - _ .`: con otros, la API de Wazuh rechaza la
   contraseña con «Insecure user password provided» (lección del 20-10-2026).
2. Calcular su hash con la herramienta del indexador y ponerlo en `config/wazuh_indexer/internal_users.yml`.
3. Poner las mismas contraseñas en las variables `INDEXER_PASSWORD`, `DASHBOARD_PASSWORD` y `API_PASSWORD` del
   `docker-compose.yml`, y la de `wazuh-wui` también en `config/wazuh_dashboard/wazuh.yml`.
4. Recrear los contenedores y aplicar la seguridad del indexador (`securityadmin.sh`), como dice el procedimiento.

`internal_users.yml`, `wazuh.yml` y el `docker-compose.yml` del servidor llevan secretos: no van al
repositorio. La contraseña de `wazuh-wui` que vale es la de `wazuh.yml`: si la API la rechaza, revisar que el
gestor tenga esa (lección del 20-10-2026).

## 6. Levantar

```
[servidor] cd /opt/wazuh-docker/single-node
[servidor] sudo docker compose up -d
[servidor] sudo docker compose ps --format '{{.Name}}\t{{.Status}}'
```

**Debe mostrar,** después de uno o dos minutos: `single-node-wazuh.manager-1`, `single-node-wazuh.indexer-1` y
`single-node-wazuh.dashboard-1` en `Up`.

## 7. Comprobar

API, desde dentro del manager (la contraseña se lee sin mostrarla):

```
[servidor] M=single-node-wazuh.manager-1
[servidor] read -rs CLAVE; echo
[servidor] printf '%s\n' "$CLAVE" | sudo docker exec -i "$M" sh -c 'IFS= read -r C; curl -sk -o /dev/null -w "%{http_code}\n" -u "wazuh-wui:$C" -X POST "https://localhost:55000/security/user/authenticate"'; unset CLAVE
```

**Debe mostrar:** `200`.

Dashboard: desde un PC con NetBird, `https://<IP de NetBird del servidor>:5601`, con el usuario `admin`.

Puertos:

```
[servidor] sudo ss -tlnp | grep -E ':(1514|1515|55000|9200|5601) '
```

**Debe mostrar:** 1514 en `0.0.0.0`; 55000, 9200 y 5601 en la IP de NetBird; ningún 1515.

## 8. Certificado de la API, para SOAR-EXECUTE

EXECUTE verifica el certificado de la API. Se copia el que presenta el manager y se mira su nombre:

```
[servidor] sudo docker exec single-node-wazuh.manager-1 cat /var/ossec/api/configuration/ssl/server.crt > ~/wazuh_api_ca.pem
[servidor] openssl x509 -in ~/wazuh_api_ca.pem -noout -subject -ext subjectAltName
```

**Debe mostrar,** con el certificado de fábrica: `CN = wazuh.com` y `DNS:localhost`. Por eso EXECUTE usa
`KRONOS_WAZUH_NOMBRE_SERVIDOR=localhost`. El archivo va a `infra/docker/secrets/wazuh_api_ca.pem` (parte 07).

## 9. Lo que Kronos no toca en Wazuh

- **No hay bloques `<active-response>`** en la configuración del manager: el Active Response automático de Wazuh
  queda apagado y Kronos es el único que ordena medidas, por la API (parte 08).
- La configuración del manager del servidor no se cambia sin avisar a Nicolás.

## 10. Respaldo de Wazuh

La configuración de Wazuh, los certificados y `client.keys` (las llaves de los agentes) se respaldan a diario a
las 04:00 UTC, cifrados con `age` con los mismos destinatarios que el respaldo de la base (parte 12). Ese script
corre en el servidor y todavía no está en el repositorio: conviene versionarlo en `infra/wazuh/respaldo/`.

## 11. Lista de comprobación

- [ ] `vm.max_map_count` persistente.
- [ ] Wazuh 4.14.8 en `/opt/wazuh-docker/single-node`, con el compose de Kronos.
- [ ] Contraseñas de `admin`, `kibanaserver` y `wazuh-wui` cambiadas y en el gestor.
- [ ] Tres contenedores `Up`; API responde 200; dashboard por NetBird.
- [ ] 1514 público, 1515 sin publicar, el resto sólo en NetBird.
- [ ] Certificado de la API copiado para EXECUTE.
