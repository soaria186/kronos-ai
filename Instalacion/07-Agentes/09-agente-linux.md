# 09 · Agente Linux

| Campo | Valor |
| :--- | :--- |
| Parte | 09 de 15 |
| Responsable | Nicolás Zamora (revisa: Rodrigo Riveros) |
| Versión | 0.9, 26-10-2026 |
| Estado | Borrador para revisión: sale de la instalación de EP-SRV-01 (15-10-2026) y de la regeneración de su llave (21-10-2026). Nicolás lo compara con su historial y lo corrige |
| Requisitos | Partes 04 y 05; parte 08 para el script de Active Response |

El agente de Wazuh 4.14.8 es SOAR-COLLECT en un servidor Linux de la PyME: envía sus eventos al manager por el
1514 y ejecuta los scripts `kronos-*` cuando SOAR-EXECUTE lo ordena. En la PyME simulada es **EP-SRV-01**
(Ubuntu 24.04), agente 001.

El agente se **registra desde el servidor**: el puerto de registro automático (1515) no se publica, así que la
llave del agente se genera en el manager y se importa en el equipo. La llave nunca pasa por un chat ni queda en
la pantalla.

---

## 1. Instalar el agente

El manager está en la IP pública del servidor (`XXXX`). El agente se fija en 4.14.8 para que no quede más nuevo
que el manager.

```
[agente Linux] curl -fsSL https://packages.wazuh.com/key/GPG-KEY-WAZUH | sudo gpg --dearmor -o /usr/share/keyrings/wazuh.gpg
[agente Linux] echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" | sudo tee /etc/apt/sources.list.d/wazuh.list
[agente Linux] sudo apt-get update
[agente Linux] sudo WAZUH_MANAGER="XXXX" apt-get install -y wazuh-agent=4.14.8-1
[agente Linux] sudo apt-mark hold wazuh-agent
[agente Linux] sudo systemctl enable wazuh-agent
```

Todavía no se inicia: sin llave, intentaría registrarse por el 1515 y llenaría su registro de errores `(1208)
Unable to connect to enrollment service`.

## 2. Registrar el agente desde el servidor

```
[servidor] M=single-node-wazuh.manager-1
[servidor] sudo docker exec "$M" /var/ossec/bin/manage_agents -a any -n EP-SRV-01
[servidor] sudo docker exec "$M" /var/ossec/bin/manage_agents -l
```

**Debe mostrar:** el agente nuevo con su número (`ID: 001, Name: EP-SRV-01, IP: any`).

Sacar su llave a un archivo **en memoria** (`/dev/shm`), legible sólo por quien la va a copiar:

```
[servidor] sudo sh -c 'umask 077; docker exec single-node-wazuh.manager-1 /var/ossec/bin/manage_agents -e 001 | grep -E "^[A-Za-z0-9+/]+=*$" > /dev/shm/llave-001'
[servidor] sudo chown "$USER" /dev/shm/llave-001
[servidor] wc -c /dev/shm/llave-001
```

**Debe mostrar:** un solo número de unos 100 a 120 bytes (una línea).

## 3. Importar la llave en el agente

Se copia en dos saltos (servidor → PC → agente) y se borra en los tres lados. En el laboratorio, EP-SRV-01
escucha SSH en el `127.0.0.1:2222` del notebook.

```
[PC]           scp soar-core-01:/dev/shm/llave-001 .
[PC]           scp -P 2222 llave-001 XXXX@127.0.0.1:/tmp/
[PC]           shred -u llave-001
[agente Linux] echo y | sudo /var/ossec/bin/manage_agents -i "$(cat /tmp/llave-001)"
[agente Linux] shred -u /tmp/llave-001
[agente Linux] sudo systemctl start wazuh-agent
[servidor]     shred -u /dev/shm/llave-001
```

En un PC con Windows, en vez de `shred -u` se usa `Remove-Item llave-001`.

## 4. Comprobar

```
[servidor] sudo docker exec single-node-wazuh.manager-1 /var/ossec/bin/agent_control -l
[agente Linux] sudo tail -n 5 /var/ossec/logs/ossec.log
```

**Debe mostrar:** `ID: 001, Name: EP-SRV-01, IP: any, Active` y, en el agente, `Connected to the server`.

Con su configuración por defecto, el agente lee los registros del sistema (SSH, sudo, PAM) y vigila la
integridad de archivos: alcanza para las reglas 100101, 100102, 100110 y 100111. La prueba de punta a punta está
en la parte 15 (escenarios E1 y E2).

## 5. Script de Active Response

Instalar `kronos-bloquear-ip` como dice la parte 08, sección 2: dueño `root`, grupo `wazuh`, permiso 750, en
`/var/ossec/active-response/bin/`. No hace falta reiniciar el agente.

## 6. Regenerar la llave sin cambiar el número del agente

Si una llave se expone (por ejemplo, si quedó escrita en un chat), se reemplaza. Con `manage_agents` el agente
volvería con otro número y los tickets dejarían de apuntar a él; por eso se usa la API (`POST /agents/insert`),
que acepta el número. Con `TOKEN` y la función `api` de la parte 08 (sección 3.2):

```
[servidor] sudo docker exec "$M" /var/ossec/bin/manage_agents -r 001
[servidor] LLAVE=$(openssl rand -hex 32)
[servidor] printf '{"name":"EP-SRV-01","ip":"any","id":"001","key":"%s"}' "$LLAVE" | api -X POST https://localhost:55000/agents/insert -d @- | grep -o '"error": *[0-9]*'; unset LLAVE
```

**Debe mostrar:** `"error": 0`. Después se repiten las secciones 2 (sólo la extracción), 3 y 4 con la llave
nueva, y se borra la antigua del gestor de contraseñas. Hecho así el 21-10-2026 con el agente 001: volvió
`Active` con el mismo número.

## 7. En el laboratorio

- EP-SRV-01 es una máquina virtual de VirtualBox en el notebook de Nicolás, en la red NAT `kronos-lab`
  (10.0.50.0/24). Su puerta de enlace, `10.0.50.1`, está en la lista de exclusión de `validate.json`: bloquearla
  deja la VM sin red.
- Si la VM se apaga cuando vence una reversión, ésta falla (`REVERSION_FALLIDA`) y no se reintenta: en las
  pruebas, el notebook va enchufado y sin suspensión.
- Las reglas de `iptables` no sobreviven al reinicio de la VM (D-52).

## 8. Lista de comprobación

- [ ] `wazuh-agent` 4.14.8 instalado y retenido (`apt-mark hold`).
- [ ] Registrado desde el servidor; llave importada sin pasar por un chat; copias temporales borradas.
- [ ] Agente `Active` en el manager.
- [ ] `kronos-bloquear-ip` instalado (parte 08).
