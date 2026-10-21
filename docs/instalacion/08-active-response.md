# 08 · Active Response: instalar `kronos-bloquear-ip` y crear el usuario de API `kronos-execute`

| Campo | Valor |
| :--- | :--- |
| Parte de la guía | 08 de 15 (borrador) |
| Versión de Wazuh | 4.14.8 |
| Responsable | Nicolás Zamora (revisa: Rodrigo Riveros) |
| Estado | Borrador para revisión. Script probado en el laboratorio (EP-SRV-01) el 20-10-2026; sección 3 reconstruida desde el historial, sin repetir; reversión automática pendiente de confirmar |

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

- Recibe `aplicar <ip>` o `quitar <ip>`; cualquier otra operación se rechaza.
- Valida la IP con el módulo `ipaddress` (IPv4 o IPv6).
- **Rechaza** direcciones de loopback, la no especificada (`0.0.0.0`) y las IP del propio equipo.
- Inserta o borra la regla `INPUT -s <ip> -m comment --comment kronos -j DROP` con `iptables` (o `ip6tables`).
- Es **idempotente**: comprueba con `-C` antes de insertar o borrar y responde «sin cambios» si no hay nada que hacer.
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

La huella corta de esta versión es `089a23e5533dd17f`. Si cambia el script, se actualiza aquí en el mismo PR.

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
| `quitar` de una regla que no existe | `sin cambios (ya estaba)`, código 0 (el texto dice «ya estaba» aunque la regla no existía) |
| IP inválida u operación desconocida | `entrada invalida` u `operacion invalida`, código 1 |
| IP del propio equipo o loopback | `rechazada`, código 1 |
| Reinicio del agente o del equipo | **Las reglas se pierden**: `iptables` guarda las reglas en memoria y este script no las hace persistentes |
| Agente apagado cuando vence la reversión | SOAR-EXECUTE registra `REVERSION_FALLIDA` («agent is not active») y **no reintenta** |

> Las dos últimas filas se observaron en el laboratorio el 20-10-2026 (ticket n.º 20) y quedan como pendientes de diseño: reintento de la reversión y persistencia o reaplicación de las reglas tras un reinicio.

### 2.5 Lo que el script no decide

El script sólo protege al propio equipo. **No** conoce la lista de exclusión de la organización (puerta de enlace, servidores propios, destinos permitidos): esa decisión es de SOAR-VALIDATE antes de que la orden llegue a EXECUTE.

### 2.6 Agentes Windows

El script equivalente (`.cmd` más PowerShell con `netsh advfirewall`) lo escribe Rodrigo y está en `infra/wazuh/active-response/windows/` (rama `feat/e3-ar-windows-bloquear-ip`, en revisión). Se prueba en EP-WKS-01 (aplicar y quitar) antes de darlo por válido.

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

Debe mostrar los primeros caracteres de un token. Si muestra un error, la contraseña de `wazuh-wui` del manager no es la vigente (en el laboratorio hubo que usar la del dashboard, ver `wazuh.yml`; ese desajuste es un pendiente del gestor de contraseñas).

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

- [ ] Script instalado con `root:wazuh 750` y huella `089a23e5533dd17f`.
- [ ] Prueba manual: `aplicar` y `quitar` correctos.
- [ ] Rol `kronos-execute` unido a la política `agents_commands_agents`.
- [ ] Usuario `kronos-execute` creado, unido al rol y autenticando.
- [ ] Contraseña en el gestor de contraseñas; ninguna en el chat, el historial ni el repositorio.
- [ ] Prueba de reversión automática a los 60 minutos, con el agente encendido: **pendiente** (la del ticket n.º 20 falló porque el agente estaba apagado).

## Referencias

- Documentación de Wazuh 4.14: Active Response y API (`/active-response`, `/security/users`, `/security/roles`, `/security/policies`).
- Documentos del proyecto: estado al 20-10-2026 y contexto maestro (A4.9, seguridad de EXECUTE).
