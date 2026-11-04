# 08 · Active Response: instalar `kronos-bloquear-ip` y crear el usuario de API `kronos-execute`

| Campo | Valor |
| :--- | :--- |
| Parte | 08 de 15 |
| Versión de Wazuh | 4.14.8 |
| Responsable | Nicolás Zamora (revisa: Rodrigo Riveros) |
| Estado | Vigente. Script probado en EP-SRV-01 el 20-10-2026 y reversión automática confirmada el 21-10-2026 (a los 60 minutos y 3 segundos). La sección 3 se reconstruyó desde el historial: en una instalación nueva, seguirla paso a paso y corregirla si algo cambia |

> Esta guía no contiene contraseñas, tokens, llaves ni direcciones IP reales. La IP `203.0.113.50` pertenece al rango reservado para documentación y se usa sólo como ejemplo.

## 1. Cómo se conectan las piezas

```
SOAR-EXECUTE ──(API de Wazuh, usuario kronos-execute)──▶ manager ──(Active Response)──▶ agente ──▶ script kronos-*
```

1. SOAR-EXECUTE elige el comando de una **tabla fija** (nunca de la alerta) y llama a `PUT /active-response` en la API del manager.
2. El cuerpo lleva `"command": "!kronos-bloquear-ip"` y `"arguments": ["aplicar", "<ip>"]`.
3. En Wazuh 4.14.8 la API acepta el prefijo `!` **sin** declarar un bloque `<command>` en la configuración del manager, así que no hace falta tocarla.
4. El agente recibe por la entrada estándar un JSON de una línea. Los argumentos llegan en `parameters.extra_args`.
5. El script se ejecuta como `root` desde `/var/ossec/active-response/bin/` y escribe en `/var/ossec/logs/active-responses.log`.

## 2. Instalar el script en un agente Linux

Script: `infra/wazuh/active-response/linux/kronos-bloquear-ip` (Python 3, sin dependencias externas).

### 2.1 Qué hace

- Recibe exactamente dos argumentos, `aplicar <ip>` o `quitar <ip>`; cualquier otra cosa se rechaza.
- Valida la IP con el módulo `ipaddress` (IPv4 o IPv6).
- **Rechaza** direcciones de loopback, la no especificada (`0.0.0.0`), las IP del propio equipo y **su puerta de enlace** (la lee con `ip -j route show default`; si no puede leerla, no actúa).
- Inserta o borra la regla `INPUT -s <ip> -m comment --comment kronos -j DROP` con `iptables` (o `ip6tables`).
- Es **idempotente**: comprueba con `-C` antes de insertar o borrar y responde «sin cambios (ya estaba)» o «sin cambios (no estaba)» si no hay nada que hacer.
- Registra cada intento con hora UTC.

### 2.2 Instalación

**[PC escritorio]** o equipo donde está el repositorio: copiar el archivo al agente (en el laboratorio, EP-SRV-01 escucha por `127.0.0.1:2222` del notebook).

```bash
scp -P 2222 infra/wazuh/active-response/linux/kronos-bloquear-ip USUARIO@127.0.0.1:/tmp/
```

**[agente Linux]** instalar con dueño `root`, grupo `wazuh` y permisos `750`:

```bash
sudo install -o root -g wazuh -m 750 /tmp/kronos-bloquear-ip /var/ossec/active-response/bin/kronos-bloquear-ip
sudo rm /tmp/kronos-bloquear-ip
ls -l /var/ossec/active-response/bin/kronos-bloquear-ip
sha256sum /var/ossec/active-response/bin/kronos-bloquear-ip | cut -c1-16
```

La huella corta de esta versión es `f6ed73769449e130`. Si cambia el script, se actualiza aquí en el mismo PR.

No hace falta reiniciar el agente.

### 2.3 Prueba manual

> **Nunca** pruebes con la puerta de enlace de la red (por ejemplo `10.0.50.1` en el laboratorio) ni con la IP desde la que estás conectado por SSH: te quedas sin acceso a la VM.

```bash
echo '{"parameters":{"extra_args":["aplicar","203.0.113.50"]}}' | sudo /var/ossec/active-response/bin/kronos-bloquear-ip
sudo iptables -S | grep kronos
sudo tail -n 3 /var/ossec/logs/active-responses.log
```

Resultado esperado: una regla `-A INPUT -s 203.0.113.50/32 -m comment --comment kronos -j DROP` y una línea `aplicar 203.0.113.50: OK`.

Para revertir:

```bash
echo '{"parameters":{"extra_args":["quitar","203.0.113.50"]}}' | sudo /var/ossec/active-response/bin/kronos-bloquear-ip
sudo iptables -S | grep kronos; echo "codigo: $?"
```

Debe quedar sin regla (`codigo: 1`) y una línea `quitar 203.0.113.50: OK`.

### 2.4 Comportamiento que hay que conocer

| Situación | Resultado |
| :--- | :--- |
| `aplicar` de una regla que ya existe | `sin cambios (ya estaba)`, código 0 |
| `quitar` de una regla que no existe | `sin cambios (no estaba)`, código 0 |
| IP inválida, operación desconocida o una cantidad de argumentos distinta de 2 | `entrada invalida` u `operacion invalida`, código 1 |
| La puerta de enlace del equipo, o no se puede leer la puerta de enlace | `rechazada`, código 1 |
| IP del propio equipo o loopback | `rechazada`, código 1 |
| Reinicio del agente o del equipo | **Las reglas se pierden**: `iptables` guarda las reglas en memoria y este script no las hace persistentes |
| Agente apagado cuando vence la reversión | SOAR-EXECUTE registra `REVERSION_FALLIDA` («agent is not active») y **no reintenta** |

> Las dos últimas filas se observaron en el laboratorio el 20-10-2026 (ticket n.º 20). En la v1.0 quedan como limitaciones documentadas: una reversión fallida se avisa para hacerla a mano (D-51), y las reglas no se vuelven a aplicar tras un reinicio (D-52).

### 2.5 Lo que el script no decide

El script sólo protege al propio equipo. **No** conoce la lista de exclusión de la organización (puerta de enlace, servidores propios, destinos permitidos): esa decisión es de SOAR-VALIDATE antes de que la orden llegue a EXECUTE.

### 2.6 Agentes Windows

El script equivalente (`.cmd` más PowerShell con `netsh advfirewall`) está en `infra/wazuh/active-response/windows/` (PR #32). Su instalación y prueba van en la parte 10. En Windows, el agente sólo encuentra el script si el comando lleva la extensión (`!kronos-bloquear-ip.cmd`): prueba del 21-10-2026 en EP-WKS-01 (#43).

### 2.9 `kronos-detener-servicio` (Linux y Windows)

Detiene un servicio (`aplicar <servicio>`) y lo vuelve a poner en marcha (`iniciar <servicio>`). Lo usan PB-F6-04 (servidor) y PB-F6-05 (puesto).

- **Linux:** `infra/wazuh/active-response/linux/kronos-detener-servicio` (Python 3). Usa `systemctl stop` y `systemctl start`; acepta el nombre con o sin `.service` y comprueba que la unidad exista (`LoadState=loaded`).
- **Windows:** `infra/wazuh/active-response/windows/kronos-detener-servicio.cmd` + `.ps1`. Usa `Stop-Service` (sin `-Force`) y `Start-Service`. No detiene un servicio con dependientes en marcha. Barreras completas en el README de `windows/`.
- **Servicios protegidos, nunca se detienen:** el agente de Wazuh, SSH, NetBird, la red, el firewall, systemd y los servicios básicos de Windows, el registro del sistema, cron, la base de datos, Docker y Ollama.
- **Sólo revierte lo que hizo Kronos:** antes de detener deja una marca (Linux: `/var/ossec/active-response/kronos-servicios.json`, `root:wazuh 640`, escritura atómica; Windows: `active-response\kronos-estado\servicio-<nombre>.txt`). `iniciar` sin marca responde «sin cambios: no lo detuvo Kronos».
- Aplicar e iniciar son idempotentes, y después de actuar se comprueba el estado.

**Instalación en Linux** (mismo procedimiento de la sección 2.2):

```bash
sudo install -o root -g wazuh -m 750 /tmp/kronos-detener-servicio /var/ossec/active-response/bin/kronos-detener-servicio
sha256sum /var/ossec/active-response/bin/kronos-detener-servicio | cut -c1-16
```

Huella corta de esta versión: `cd3d6f3a47748a14`.

**Prueba a mano en Linux**, con un servicio que no sea crítico (en EP-SRV-01, por ejemplo `cups` o uno instalado para la prueba). Antes, tomar un snapshot:

```bash
echo '{"parameters":{"extra_args":["aplicar","cups"]}}' | sudo /var/ossec/active-response/bin/kronos-detener-servicio
systemctl is-active cups
echo '{"parameters":{"extra_args":["iniciar","cups"]}}' | sudo /var/ossec/active-response/bin/kronos-detener-servicio
systemctl is-active cups
sudo tail -n 2 /var/ossec/logs/active-responses.log
```

Esperado: `inactive` y luego `active`, con las líneas `aplicar cups.service OK` e `iniciar cups.service OK`.

**Limitación:** en Linux, `systemctl stop` también detiene los servicios que dependen del detenido. La lista de protegidos cubre los que mantienen al equipo conectado con Kronos.

Todavía **no está activo** en `actuadores_v1` del catálogo: se activa después de probarlo en EP-SRV-01 y EP-WKS-01.

## 3. Crear el usuario de API `kronos-execute`

Objetivo: que SOAR-EXECUTE tenga una identidad propia en la API de Wazuh con **un solo permiso**: `active-response:command` sobre los agentes.

Valores del laboratorio (los identificadores cambian en cada instalación): usuario `100`, rol `100` (`kronos-execute`) y política de fábrica `6` (`agents_commands_agents`).

### 3.1 Reglas

- Las contraseñas se cargan con `read -rs`: nunca se escriben en el comando, en el historial ni en este repositorio.
- Se reutiliza la política **de fábrica** `agents_commands_agents` (permite `active-response:command` sobre `agent:id:*`) en vez de crear una propia.
- La contraseña de `kronos-execute` debe cumplir la política de Wazuh (de 8 a 64 caracteres, con mayúsculas, minúsculas, número y símbolo) y se guarda en el gestor de contraseñas del equipo.
- Los pasos se hacen en el **servidor**, contra el contenedor del manager.

### 3.2 Pasos

**[servidor]** variables y una función auxiliar. El token de administrador dura poco tiempo y se pasa al contenedor como variable de entorno:

```bash
M=single-node-wazuh.manager-1
api() { sudo docker exec -i -e T="$TOKEN" "$M" sh -c 'curl -sk -H "Authorization: Bearer $T" -H "Content-Type: application/json" "$@"' sh "$@"; }
```

**1. Token de administrador** (usuario administrador de la API, `wazuh-wui`). La contraseña se lee sin mostrarla:

```bash
read -rs ADMIN_PW; echo
TOKEN=$(printf '%s\n' "$ADMIN_PW" | sudo docker exec -i "$M" sh -c 'IFS= read -r A; curl -sk -u "wazuh-wui:$A" -X POST "https://localhost:55000/security/user/authenticate?raw=true"')
unset ADMIN_PW
echo "${TOKEN:0:12}"
```

Debe mostrar los primeros caracteres de un token. Si muestra un error, la contraseña de `wazuh-wui` no es la vigente: la que vale es la del dashboard (`config/wazuh_dashboard/wazuh.yml`, parte 04), y el gestor de contraseñas debe guardar esa.

**2. Rol**

```bash
api -X POST https://localhost:55000/security/roles -d '{"name":"kronos-execute"}'; echo
```

Anotar el `id` del rol y guardarlo: `ROL=<id>`.

**3. Política de fábrica**

```bash
api "https://localhost:55000/security/policies?search=agents_commands_agents" | grep -o '"id": *[0-9]*, *"name": *"[^"]*"'; echo
```

Anotar el `id` y guardarlo: `POL=<id>`.

**4. Unir rol y política**

```bash
api -X POST "https://localhost:55000/security/roles/$ROL/policies?policy_ids=$POL"; echo
```

**5. Crear el usuario** (contraseña por entrada estándar, sin mostrarla):

```bash
read -rs KX_PW; echo
printf '{"username":"kronos-execute","password":"%s"}' "$KX_PW" | api -X POST https://localhost:55000/security/users -d @-; echo
```

Anotar el `id` del usuario: `USR=<id>`.

**6. Unir usuario y rol**

```bash
api -X POST "https://localhost:55000/security/users/$USR/roles?role_ids=$ROL"; echo
```

**7. Comprobar que el usuario autentica**

```bash
printf '%s\n' "$KX_PW" | sudo docker exec -i "$M" sh -c 'IFS= read -r K; curl -sk -u "kronos-execute:$K" -X POST "https://localhost:55000/security/user/authenticate?raw=true"' | cut -c1-12; echo
```

**8. Limpiar**

```bash
unset KX_PW TOKEN
history -c
```

Guardar la contraseña de `kronos-execute` en el gestor de contraseñas y cargarla en SOAR-EXECUTE como secreto de Docker (`wazuh_api_password`), junto con el certificado de la API (`wazuh_api_ca.pem`).

### 3.3 Comprobar el permiso efectivo

```bash
api "https://localhost:55000/security/users/$USR"; echo
api "https://localhost:55000/security/roles/$ROL"; echo
```

El rol debe tener únicamente la política `agents_commands_agents`. La prueba de punta a punta es una orden real de EXECUTE sobre el agente de laboratorio (ver sección 2.3 y el ticket de ejemplo).

## 4. Lista de comprobación

- [ ] Script instalado con `root:wazuh 750` y huella `f6ed73769449e130`.
- [ ] Prueba manual: `aplicar` y `quitar` correctos.
- [ ] Rol `kronos-execute` unido a la política `agents_commands_agents`.
- [ ] Usuario `kronos-execute` creado, unido al rol y autenticando.
- [ ] Contraseña en el gestor de contraseñas; ninguna en el chat, el historial ni el repositorio.
- [ ] Prueba de reversión automática a los 60 minutos, con el agente encendido (en el laboratorio se confirmó el 21-10-2026; la del ticket n.º 20 había fallado porque el agente estaba apagado).

## Referencias

- Documentación de Wazuh 4.14: Active Response y API (`/active-response`, `/security/users`, `/security/roles`, `/security/policies`).
- Documentos del proyecto: estado al 20-10-2026 y contexto maestro (A4.9, seguridad de EXECUTE).
