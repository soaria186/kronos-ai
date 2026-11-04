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

### 2.7 `kronos-deshabilitar-cuenta` en Linux

Script: `infra/wazuh/active-response/linux/kronos-deshabilitar-cuenta` (Python 3, sin dependencias externas). Todavía no está activo en el catálogo (`actuadores_v1`): se activa después de probarlo en EP-SRV-01.

- Recibe exactamente dos argumentos, `aplicar <cuenta>` o `habilitar <cuenta>`. La cuenta debe calzar con `^[A-Za-z0-9._-]{1,32}$` y existir como cuenta local.
- **Aplicar** bloquea la contraseña (`usermod -L`) y vence la cuenta (`chage -E 0`), para que tampoco entre con llave SSH. **Habilitar** hace lo contrario (`usermod -U` y `chage -E -1`).
- Sólo hace lo que falta, y responde «sin cambios» si la cuenta ya estaba deshabilitada o habilitada. El estado lo lee con `passwd -S` y con la fecha de vencimiento de `getent shadow`.
- **Nunca toca** `root`, `labadmin`, `wazuh`, `kronos`, `nobody` ni las cuentas con UID menor que 1000: responde `cuenta protegida`, código 1.
- **Nunca deshabilita ni habilita a un administrador**: un miembro de `sudo`, `wheel` o `admin`, o una cuenta que tenga uno de ellos como grupo primario. Responde `cuenta protegida: <cuenta> (administrador)`, código 1, para no dejar al equipo sin quien lo administre. Los grupos que no existen en el equipo se ignoran.
- **Sólo revierte lo que hizo Kronos.** Lo anota en `/var/ossec/active-response/kronos-cuentas.json` (`root:wazuh 640`), con una entrada por cuenta: `{"bloqueo": …, "vencio": …, "desde": "<hora UTC>"}`.
  - `aplicar` marca cada paso **antes** de hacerlo (`bloqueo` si corre `usermod -L`, `vencio` si corre `chage -E 0`) y lo desmarca si el comando falla. Si no hace nada, no crea entrada.
  - `habilitar` deshace sólo los pasos marcados y borra la entrada. Sin entrada responde «sin cambios: no la deshabilitó Kronos» y no toca la cuenta: una contraseña que bloqueó otra persona sigue bloqueada.
  - El archivo se escribe en un temporal de la misma carpeta y se cambia con `os.replace`, así que nunca queda a medio escribir. Si no es JSON válido, el script registra `ERROR` y sale con 1 sin tocar la cuenta. Si no puede guardarlo, tampoco toca la cuenta.
- Si un comando falla, registra `ERROR` con su código y sale con 1. Los comandos van siempre como lista, sin shell.

**[agente Linux]** se instala igual que `kronos-bloquear-ip` (sección 2.2), con dueño `root`, grupo `wazuh` y permisos `750`:

```bash
sudo install -o root -g wazuh -m 750 /tmp/kronos-deshabilitar-cuenta /var/ossec/active-response/bin/kronos-deshabilitar-cuenta
sudo rm /tmp/kronos-deshabilitar-cuenta
ls -l /var/ossec/active-response/bin/kronos-deshabilitar-cuenta
sha256sum /var/ossec/active-response/bin/kronos-deshabilitar-cuenta | cut -c1-16
```

La huella corta de esta versión es `9c935ac289ef66ce`. Para probarlo a mano, con una cuenta local de prueba que no sea de administración ni miembro de `sudo`:

```bash
echo '{"parameters":{"extra_args":["aplicar","usuario.demo"]}}' | sudo /var/ossec/active-response/bin/kronos-deshabilitar-cuenta
sudo passwd -S usuario.demo; sudo chage -l usuario.demo | grep -i expir
sudo cat /var/ossec/active-response/kronos-cuentas.json; sudo ls -l /var/ossec/active-response/kronos-cuentas.json
echo '{"parameters":{"extra_args":["habilitar","usuario.demo"]}}' | sudo /var/ossec/active-response/bin/kronos-deshabilitar-cuenta
sudo tail -n 2 /var/ossec/logs/active-responses.log
```

Después de aplicar, `passwd -S` muestra `L`, la cuenta vence el 01-01-1970 y el archivo de marcas (`-rw-r----- root wazuh`) tiene la entrada de `usuario.demo` con `"bloqueo": true` y `"vencio": true`. Después de habilitar, vuelve a `P` y `never`, la entrada desaparece y el registro tiene `aplicar usuario.demo OK` y `habilitar usuario.demo OK`.

### 2.8 `kronos-aislar-equipo` en Linux

Script: `infra/wazuh/active-response/linux/kronos-aislar-equipo` (Python 3, sin dependencias externas), con la misma lógica que el de Windows. Todavía no está activo en el catálogo (`actuadores_v1`): se activa después de probarlo en EP-SRV-01.

- Recibe exactamente un argumento, `aplicar` o `quitar` (la medida no lleva objetivo).
- **El agente sigue conectado al manager mientras el equipo está aislado.** Antes de tocar nada lee la dirección del manager en `<client><server><address>` de `/var/ossec/etc/ossec.conf`; si es un nombre, lo resuelve a IPv4. Si no obtiene una IPv4 válida, sale con 1 **sin tocar nada**.
- Todo va en la cadena propia `KRONOS-AISLAR`, que se arma completa **antes** de engancharla al comienzo de `INPUT` y `OUTPUT`. Sus reglas, en orden: loopback; el manager por TCP 1514 y 1515, y su respuesta (`ESTABLISHED`); las direcciones de administración; la interfaz `wt0` de NetBird si existe; y al final `DROP`. En IPv6 sólo deja pasar loopback.
- Si algo falla a mitad, deshace lo que alcanzó a hacer y sale con 1.
- `quitar` desengancha y borra sólo `KRONOS-AISLAR`, en IPv4 e IPv6; nunca toca otras reglas ni cadenas. Aplicar y quitar son idempotentes.

**Direcciones de administración (opcional).** `/var/ossec/etc/kronos-aislar.permitidos`, una IP o red IPv4 por línea, con `#` para comentarios. Se permiten en los dos sentidos mientras dura el aislamiento. Una línea inválida, una red IPv6 o `0.0.0.0/0` impiden aislar. En el laboratorio, para no perder el SSH a EP-SRV-01:

```text
10.0.2.2  # NAT de VirtualBox: SSH del laboratorio
```

**[agente Linux]** se instala igual que `kronos-bloquear-ip` (sección 2.2), con dueño `root`, grupo `wazuh` y permisos `750`, y el archivo de permitidos con `root:wazuh 640`:

```bash
sudo install -o root -g wazuh -m 750 /tmp/kronos-aislar-equipo /var/ossec/active-response/bin/kronos-aislar-equipo
sudo rm /tmp/kronos-aislar-equipo
echo '10.0.2.2  # NAT de VirtualBox: SSH del laboratorio' | sudo tee /var/ossec/etc/kronos-aislar.permitidos >/dev/null
sudo chown root:wazuh /var/ossec/etc/kronos-aislar.permitidos; sudo chmod 640 /var/ossec/etc/kronos-aislar.permitidos
ls -l /var/ossec/active-response/bin/kronos-aislar-equipo /var/ossec/etc/kronos-aislar.permitidos
sha256sum /var/ossec/active-response/bin/kronos-aislar-equipo | cut -c1-16
```

La huella corta de esta versión es `739e6529287fc6b0`.

> **Probarlo siempre desde un snapshot de la VM**, con `kronos-aislar.permitidos` creado antes y una consola de VirtualBox abierta: si el SSH queda fuera de los permitidos, sólo se vuelve atrás desde la consola o con el snapshot. Al aislar, también se pierde todo lo que no está en la lista (actualizaciones, DNS, la consola web).

```bash
echo '{"parameters":{"extra_args":["aplicar"]}}' | sudo /var/ossec/active-response/bin/kronos-aislar-equipo
sudo iptables -S KRONOS-AISLAR; sudo iptables -S INPUT | head -n 3
curl -m 5 -sI https://example.com; echo "codigo: $?"
echo '{"parameters":{"extra_args":["quitar"]}}' | sudo /var/ossec/active-response/bin/kronos-aislar-equipo
sudo tail -n 2 /var/ossec/logs/active-responses.log
```

Durante el aislamiento la cadena termina en `-j DROP`, `INPUT` empieza con `-j KRONOS-AISLAR`, `curl` falla (código distinto de 0) y en el servidor el agente 001 sigue `Active` (`AGENTE=001 bash probar-ar-api.sh estado`). El registro tiene `aplicar OK; manager permitido: <ip> TCP/1514,1515; administracion: 10.0.2.2/32` y, al final, `quitar OK; aislamiento quitado`.

**Limitaciones conocidas:**

- Las reglas viven en memoria: **un reinicio del equipo quita el aislamiento** (como los bloqueos de `kronos-bloquear-ip`, D-52).
- Si el manager está configurado por nombre, se deja pasar la IP que tenía al aislar. Si el agente necesita resolver el nombre otra vez (por ejemplo, al reconectarse), el DNS está bloqueado y puede perder el canal. En la PyME simulada el manager se configura por IP.
- No deja pasar DHCP. Si vence el préstamo durante el aislamiento, el equipo puede perder la IP.

### 2.9 `kronos-detener-servicio` (Linux y Windows)

Detiene un servicio (`aplicar <servicio>`) y lo vuelve a poner en marcha (`iniciar <servicio>`). Lo usan PB-F6-04 (servidor) y PB-F6-05 (puesto).

- **Linux:** `infra/wazuh/active-response/linux/kronos-detener-servicio` (Python 3). Usa `systemctl stop` y `systemctl start`; acepta el nombre con o sin `.service` y comprueba que la unidad exista (`LoadState=loaded`).
- **Windows:** `infra/wazuh/active-response/windows/kronos-detener-servicio.cmd` + `.ps1`. Usa `Stop-Service` (sin `-Force`) y `Start-Service`. No detiene un servicio con dependientes en marcha. Barreras completas en el README de `windows/`.
- **Servicios protegidos, nunca se detienen:** el agente de Wazuh, SSH, NetBird, la red, el firewall, systemd y los servicios básicos de Windows, el registro del sistema, cron, la base de datos, Docker y Ollama.
- **Sólo revierte lo que hizo Kronos:** antes de detener deja una marca (Linux: `/var/ossec/active-response/kronos-servicios.json`, `root:wazuh 640`, escritura atómica; Windows: `active-response\kronos-estado\servicio-<nombre>.txt`). `iniciar` sin marca responde «sin cambios: no lo detuvo Kronos».
- Aplicar e iniciar son idempotentes, y después de actuar se comprueba el estado.

**Instalación en Linux** (mismo procedimiento de la sección 2.2):

```bash
sudo install -o root -g wazuh -m 750 /tmp/kronos-cerrar-sesion /var/ossec/active-response/bin/kronos-cerrar-sesion
sha256sum /var/ossec/active-response/bin/kronos-cerrar-sesion | cut -c1-16
```

Huella corta de esta versión: `6b2b6cb6ea414c97`.

**Prueba a mano en Linux**, con una cuenta de prueba que **no** sea administradora y que tenga una sesión abierta (por ejemplo, `ssh` con esa cuenta desde otra terminal):

```bash
loginctl list-sessions
echo '{"parameters":{"extra_args":["aplicar","usuario.demo"]}}' | sudo /var/ossec/active-response/bin/kronos-cerrar-sesion
loginctl list-sessions
sudo tail -n 1 /var/ossec/logs/active-responses.log
```

Esperado: la sesión de `usuario.demo` desaparece de la lista y queda la línea `aplicar usuario.demo OK (1 sesion(es) cerrada(s))`.

Todavía **no está activo** en `actuadores_v1` del catálogo: se activa después de probarlo en EP-SRV-01 y EP-WKS-01.
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

### 2.10 `kronos-cerrar-sesion` (Linux y Windows)

Cierra todas las sesiones de una cuenta local (`aplicar <cuenta>`). Lo usa PB-F1-04. **No se revierte**: la persona puede volver a entrar, y para impedirlo está `kronos-deshabilitar-cuenta`.

- **Linux:** `infra/wazuh/active-response/linux/kronos-cerrar-sesion` (Python 3). Usa `loginctl terminate-user`, que cierra las sesiones de consola, SSH y escritorio y termina sus procesos.
- **Windows:** `infra/wazuh/active-response/windows/kronos-cerrar-sesion.cmd` + `.ps1`. Usa `quser` y `logoff`. Barreras completas en el README de `windows/`.
- **Cuentas protegidas, nunca se tocan:** root, las cuentas del sistema (UID menor que 1000 en Linux; cuentas integradas por SID en Windows), las cuentas de administración y de servicio del laboratorio, y **los administradores** (miembros de `sudo`, `wheel` o `admin` en Linux; del grupo local Administradores en Windows).
- Si la cuenta no tiene sesiones abiertas, responde «sin cambios». Es idempotente.



### 2.11 `kronos-cuarentena` (D-69)

Pone en cuarentena el archivo de la alerta (playbooks PB-F2-02, PB-F5-01 y PB-F5-03) y lo restaura desde la consola. Scripts: `linux/kronos-cuarentena` (Python 3, como `kronos-bloquear-ip`) y `windows/kronos-cuarentena.cmd` + `.ps1`.

| Orden | Qué hace |
| :--- | :--- |
| `aplicar <ruta>` | Copia el archivo a la carpeta de cuarentena, comprueba su SHA-256, borra el original y deja un registro con la ruta, la huella y los permisos. Linux: `/var/lib/kronos/cuarentena/` (700, root), el archivo queda sin permisos. Windows: `C:\ProgramData\Kronos\cuarentena\` (sólo Administradores y SYSTEM), sin permiso de ejecución |
| `restaurar <ruta>` | Lo devuelve a su ruta con sus permisos, si la huella sigue igual y nadie ocupó la ruta |

Barreras: sólo esas dos órdenes y una ruta; lista blanca de caracteres, sin `.`, `..` ni `~`; nunca carpetas del sistema, del agente, de NetBird ni de Kronos (`/etc`, `/usr`, `/var/ossec`, `C:\Windows`, `C:\Program Files (x86)\ossec-agent`, etc.), ni a través de un enlace; sólo archivos regulares; en Windows, un archivo en uso se rechaza (primero hay que terminar el proceso). Aplicar y restaurar son idempotentes («sin cambios»).

**[EP-SRV-01]** instalación, después de copiarlo con `scp -P 2222`:

```bash
sudo install -o root -g wazuh -m 750 kronos-cuarentena /var/ossec/active-response/bin/kronos-cuarentena
```

**[servidor]** prueba por la API con `probar-ar-api.sh` (parte `pruebas/`): `aplicar` sobre un archivo de prueba en `/tmp` (o en `C:\Users\Public\` para EP-WKS-01), comprobar que desapareció y que está en la carpeta de cuarentena, `restaurar` y comprobar que volvió con la misma huella (`sha256sum` o `Get-FileHash`). Las dos líneas de `active-responses.log` van al PR.

> **Limitación:** en Linux las alertas de integridad de archivos (F5) suelen ser de `/etc` o `/usr`, que están protegidas: esas medidas terminan en falla segura (`ORDEN_INVALIDA`) y se avisan, en vez de dejar el sistema sin un archivo que necesita. Y el borrado del registro de seguridad de Windows (E4) no trae archivo: termina en `ARGUMENTO_FALTANTE`.


### 2.14 `kronos-bloquear-destino` (D-69)

Corta la comunicación del equipo con una IP externa (PB-F4-01, por ejemplo el servidor de comando y control de un malware). Scripts: `linux/kronos-bloquear-destino` (Python 3) y `windows/kronos-bloquear-destino.cmd` + `.ps1`. Órdenes: `aplicar <ip>` y `quitar <ip>`. EXECUTE manda la IP de destino de la alerta (`dstip`, o `destinationIp` de Sysmon); si no viene, `ARGUMENTO_FALTANTE`.

- **Linux:** `iptables -I OUTPUT -d <ip> -m comment --comment kronos -j DROP` (`ip6tables` para IPv6). **Windows:** regla de salida `Kronos-destino-<ip>` con `netsh advfirewall`.
- **Nunca bloquea:** loopback, la dirección no especificada, multicast, enlace local, una IP del propio equipo, su puerta de enlace, sus servidores DNS, la red de NetBird (`100.64.0.0/10`) ni **el manager de Wazuh** (la dirección de `<server>` en `ossec.conf`): sin el manager no llegaría la orden de quitar. Si no puede leer la puerta de enlace o el manager, no actúa.
- Aplicar y quitar son idempotentes («sin cambios»).

**[EP-SRV-01]** instalación, después de copiarlo con `scp -P 2222`:

```bash
sudo install -o root -g wazuh -m 750 kronos-bloquear-destino /var/ossec/active-response/bin/kronos-bloquear-destino
sha256sum /var/ossec/active-response/bin/kronos-bloquear-destino | cut -c1-16
```

Huella corta de esta versión: `2cf839e8bd69ba98`.

**[servidor]** prueba por la API: `AGENTE=001 bash probar-ar-api.sh orden kronos-bloquear-destino aplicar 198.51.100.66`. **[EP-SRV-01]** comprobar con `sudo iptables -S OUTPUT | grep kronos` y que `curl -m 5 http://198.51.100.66` no sale; después `quitar` y comprobar que la regla ya no está. Un rechazo: la IP del manager. En EP-WKS-01, con `kronos-bloquear-destino.cmd` y `Get-NetFirewallRule -DisplayName 'Kronos-destino-*'`.

Todavía **no está activo** en `actuadores_v1` del catálogo: se activa después de probarlo en EP-SRV-01 y EP-WKS-01.

### 2.15 `kronos-limitar-conexiones` (D-69 y D-71)

Frena una denegación de servicio desde una IP (PB-F6-03). Scripts: `linux/kronos-limitar-conexiones` (Python 3) y `windows/kronos-limitar-conexiones.cmd` + `.ps1`. Órdenes: `aplicar <ip>` y `quitar <ip>`. EXECUTE manda la IP de origen de la alerta (`srcip`, o `ipAddress` de Windows); si no viene, `ARGUMENTO_FALTANTE`.

- **Linux:** la IP puede seguir conectándose, pero con a lo más **10 conexiones TCP abiertas a la vez**: `iptables -I INPUT -s <ip> -p tcp --syn -m connlimit --connlimit-above 10 -m comment --comment kronos -j DROP` (`ip6tables` para IPv6).
- **Windows (D-71):** el firewall no limita conexiones por IP, así que **bloquea la entrada desde la IP por 10 minutos**: regla `Kronos-limite-<ip>` y tarea programada `\Kronos\Kronos-limite-<ip>` que la borra al vencer. Si la tarea no se puede crear, borra la regla y falla: nunca queda un bloqueo sin vencimiento.
- **Nunca actúa sobre:** loopback, la dirección no especificada, multicast, enlace local, una IP del propio equipo, su puerta de enlace, la red de NetBird (`100.64.0.0/10`) ni el manager de Wazuh (en Windows, tampoco los DNS). Si no puede leer la puerta de enlace o el manager, no actúa.
- Aplicar y quitar son idempotentes («sin cambios»).

**[EP-SRV-01]** instalación, después de copiarlo con `scp -P 2222`:

```bash
sudo install -o root -g wazuh -m 750 kronos-limitar-conexiones /var/ossec/active-response/bin/kronos-limitar-conexiones
sha256sum /var/ossec/active-response/bin/kronos-limitar-conexiones | cut -c1-16
```

Huella corta de esta versión: `29c9ab973844fd82`.

**[servidor]** prueba por la API: `AGENTE=001 bash probar-ar-api.sh orden kronos-limitar-conexiones aplicar 198.51.100.66`. **[EP-SRV-01]** comprobar con `sudo iptables -S INPUT | grep connlimit`; después `quitar` y comprobar que la regla ya no está. En EP-WKS-01, con `kronos-limitar-conexiones.cmd`: `Get-NetFirewallRule -DisplayName 'Kronos-limite-*'` y `Get-ScheduledTask -TaskPath '\Kronos\'`; a los 10 minutos las dos deben haber desaparecido solas.

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

## 3b. `kronos-revertir-tarea` (D-69)

Deshabilita la tarea programada de la alerta (PB-F5-02) y la vuelve a habilitar desde la consola. Scripts: `linux/kronos-revertir-tarea` (Python 3) y `windows/kronos-revertir-tarea.cmd` + `.ps1`. Órdenes: `aplicar <tarea>` y `habilitar <tarea>`.

| Sistema | Qué es la tarea (lo manda EXECUTE) | `aplicar` | `habilitar` |
| :--- | :--- | :--- | :--- |
| Windows | `data.win.eventdata.taskName` del evento 4698, por ejemplo `\Actualizador0` | `Disable-ScheduledTask` (como `schtasks /Change /TN … /DISABLE`) | `Enable-ScheduledTask`, sólo si la deshabilitó Kronos |
| Linux, cron | `syscheck.path`: `/etc/crontab`, `/etc/cron.d/<archivo>` o `/var/spool/cron/…` | Comenta las líneas de tareas con la marca `#kronos# `. No toca las variables (`PATH=`, `MAILTO=`) ni, en `/etc/crontab`, las líneas `run-parts` del sistema | Quita sólo la marca `#kronos# ` |
| Linux, run-parts | `/etc/cron.hourly|daily|weekly|monthly/<script>` | Le quita el permiso de ejecución (`run-parts` lo salta) | Le devuelve sus permisos |
| Linux, systemd | `/etc/systemd/system/<nombre>.timer` | `systemctl disable --now` | Lo deja como estaba: habilitado y/o en marcha |

Barreras: argumentos exactos; lista blanca de caracteres, sin `.` ni `..`; sólo esas carpetas y archivos regulares (nunca enlaces); nunca las tareas del agente de Wazuh, de Kronos, de NetBird, de systemd ni de Windows Defender; sólo revierte lo que hizo Kronos (la marca en las líneas, `kronos-tareas.json` en Linux o `kronos-estado\tarea-*.txt` en Windows); idempotente. Deshabilitar no detiene una ejecución en curso (eso es `kronos-terminar-proceso`).

**[EP-SRV-01]** instalación, después de copiarlo con `scp -P 2222`:

```bash
sudo install -o root -g wazuh -m 750 kronos-revertir-tarea /var/ossec/active-response/bin/kronos-revertir-tarea
```

**[EP-SRV-01]** tarea de prueba (el nombre no puede llevar «kronos» ni «wazuh», que están protegidos): `echo '*/5 * * * * root /bin/true' | sudo tee /etc/cron.d/prueba-tarea`. **[servidor]** `AGENTE=001 bash probar-ar-api.sh orden kronos-revertir-tarea aplicar /etc/cron.d/prueba-tarea`; con `cat` la línea queda con `#kronos# `; `habilitar` y vuelve como estaba. **[EP-WKS-01]** `schtasks /Create /TN PruebaTarea /TR notepad.exe /SC DAILY /ST 03:00` y probar con `\PruebaTarea` (`Get-ScheduledTask PruebaTarea` pasa a `Disabled` y vuelve a `Ready`).

## 4. Lista de comprobación

- [ ] Script instalado con `root:wazuh 750` y huella `f6ed73769449e130`.
- [ ] Prueba manual: `aplicar` y `quitar` correctos.
- [ ] Rol `kronos-execute` unido a la política `agents_commands_agents`.
- [ ] Usuario `kronos-execute` creado, unido al rol y autenticando.
- [ ] Contraseña en el gestor de contraseñas; ninguna en el chat, el historial ni el repositorio.
- [ ] Prueba de reversión automática a los 60 minutos, con el agente encendido (en el laboratorio se confirmó el 21-10-2026; la del ticket n.º 20 había fallado porque el agente estaba apagado).

## 5. `kronos-terminar-proceso` (D-69)

Termina el proceso de la alerta (PB-F2-03). Scripts: `linux/kronos-terminar-proceso` (Python 3) y `windows/kronos-terminar-proceso.cmd` + `.ps1`. Orden: `aplicar <pid> <ejecutable>`; no tiene inversa (la persona vuelve a abrir el programa si corresponde). EXECUTE manda el PID y el ejecutable de la alerta (`processId` e `image` de Sysmon, o `pid` y `exe` de auditd); si falta alguno, `ARGUMENTO_FALTANTE`.

- **El PID tiene que seguir siendo el mismo programa.** En Linux, `/proc/<pid>/exe` debe ser la ruta de la alerta (también si el archivo se borró, como hace el malware), y la señal va por un `pidfd` abierto antes de comprobar: el PID no puede pasar a otro proceso entre la comprobación y la señal. En Windows, `Win32_Process.ExecutablePath`, comprobado de nuevo con la misma hora de inicio justo antes de terminar.
- **Nunca** PID menores que 5, el agente de Wazuh (todo lo que corre desde `/var/ossec/` o `C:\Program Files (x86)\ossec-agent\`), SSH, NetBird, systemd, la auditoría y el registro, la base, Ollama y los contenedores; en Windows, además, los procesos del sistema, Defender y Sysmon; ni el propio script ni su padre.
- Linux: primero `SIGTERM` y, si a los 5 s sigue vivo, `SIGKILL`. Windows: `Kill()` y hasta 10 s de espera.
- Si el proceso ya no existe: «sin cambios».

**[EP-SRV-01]** instalación, después de copiarlo con `scp -P 2222`:

```bash
sudo install -o root -g wazuh -m 750 kronos-terminar-proceso /var/ossec/active-response/bin/kronos-terminar-proceso
```

**[EP-SRV-01]** proceso de prueba: `sleep 600 & echo $! ; readlink /proc/$!/exe`. **[servidor]** `AGENTE=001 bash probar-ar-api.sh orden kronos-terminar-proceso aplicar <pid> /usr/bin/sleep` y comprobar con `ps -p <pid>` que terminó. Un rechazo: el mismo PID con otra ruta. En EP-WKS-01, con `notepad.exe` (`C:\Windows\System32\notepad.exe`) y `Get-Process -Id`.

## Referencias

- Documentación de Wazuh 4.14: Active Response y API (`/active-response`, `/security/users`, `/security/roles`, `/security/policies`).
- Documentos del proyecto: estado al 20-10-2026 y contexto maestro (A4.9, seguridad de EXECUTE).
