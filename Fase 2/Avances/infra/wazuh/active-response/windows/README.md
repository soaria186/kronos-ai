# Active Response de Kronos en Windows

Scripts que SOAR-EXECUTE ejecuta en los puestos de trabajo Windows por Active Response
de Wazuh. Cada comando son dos archivos: un lanzador `.cmd` (lo que ejecuta el agente) y
el script `.ps1` que hace el trabajo. Compatibles con Windows PowerShell 5.1.

| Comando | Archivos | Aplicar | Revertir |
| :--- | :--- | :--- | :--- |
| `kronos-bloquear-ip` | `kronos-bloquear-ip.cmd` + `.ps1` | `aplicar <ip>`: regla de entrada `Kronos-bloqueo-<ip>` con `netsh advfirewall` | `quitar <ip>`: borra esa regla |
| `kronos-deshabilitar-cuenta` | `kronos-deshabilitar-cuenta.cmd` + `.ps1` | `aplicar <cuenta>`: deshabilita la cuenta **local** (`Disable-LocalUser`) | `habilitar <cuenta>`: la vuelve a habilitar, **sólo si la deshabilitó Kronos** |
| `kronos-aislar-equipo` | `kronos-aislar-equipo.cmd` + `.ps1` | `aplicar`: corta todo el tráfico del equipo **salvo el canal del agente con el manager** | `quitar`: deja el firewall exactamente como estaba |

El agente es de 32 bits: el `.cmd` lanza la PowerShell de 64 bits por `Sysnative`. Para
`kronos-deshabilitar-cuenta` es indispensable, porque el módulo `LocalAccounts`
(`Get-LocalUser`, `Disable-LocalUser`) sólo existe en la de 64 bits.

EXECUTE envía el comando con la extensión (`!kronos-bloquear-ip.cmd`) a los agentes
Windows: sin ella el agente no encuentra el script (ver la prueba del 21-10-2026, abajo).

## Cómo recibe la orden

El agente entrega por la entrada estándar una línea JSON y Kronos pone la operación y
el objetivo en `parameters.extra_args` (verificado con el script de Linux en Wazuh 4.14.8,
20-10-2026):

```json
{"version":1,"command":"add","parameters":{"extra_args":["aplicar","203.0.113.50"]}}
```

## Barreras de los scripts

Son una segunda línea de defensa: EXECUTE (`ejecucion/ordenes.py`) ya valida lo mismo.

### `kronos-bloquear-ip`

- Sólo `aplicar` o `quitar` y exactamente un objetivo.
- La IP debe estar en su forma canónica (`1` o `0x7f.1` se rechazan, aunque Windows las acepte).
- Nunca bloquea loopback, `0.0.0.0`, multicast, enlace local, difusión, una IP del propio
  equipo ni **su puerta de enlace**.
- `netsh` recibe los argumentos como lista; no se arma texto para un intérprete.
- Aplicar y quitar son idempotentes.
- Si el firewall está apagado en algún perfil, deja una ADVERTENCIA en el registro (la
  regla existe, pero no bloquea en ese perfil).

### `kronos-deshabilitar-cuenta`

- Sólo `aplicar` o `habilitar` (comparación exacta) y exactamente una cuenta.
- Nombre con `^[A-Za-z0-9._-]{1,64}$`: si no calza, se rechaza (no se limpia ni se recorta).
- Sólo cuentas **locales** (`Get-LocalUser`); las de dominio no se tocan.
- **Cuentas protegidas, rechazadas siempre:** por nombre (`Administrator`, `Administrador`,
  `Guest`, `Invitado`, `SYSTEM`, `LocalSystem`, `DefaultAccount`, `WDAGUtilityAccount`,
  `kronos` y cualquier nombre que termine en `$`) y por SID (las cuentas integradas que
  terminan en `-500`, `-501`, `-503` y `-504`, porque el nombre cambia con el idioma).
- **Nunca deshabilita a un miembro del grupo local Administradores** (`S-1-5-32-544`), para
  no dejar a la PyME sin quien administre el equipo (en el laboratorio protege a la cuenta
  de administración). Si no puede leer el grupo, no actúa.
- **Sólo revierte lo que hizo Kronos.** Al aplicar deja la marca
  `active-response\kronos-estado\cuenta-<nombre>.txt` (antes de deshabilitar, para no
  dejar una cuenta deshabilitada que Kronos no sepa revertir). Si la cuenta ya estaba
  deshabilitada, sale con 0 y no deja marca. `habilitar` sólo actúa si existe la marca; si
  no, sale con 0 y la cuenta queda como está.
- Después de actuar vuelve a leer `Enabled` y sale con 1 si no quedó como se pidió.

### `kronos-aislar-equipo`

- Sólo `aplicar` o `quitar` y **exactamente un argumento** (esta medida no lleva objetivo).
- **El agente sigue conectado al manager mientras el equipo está aislado.** Si perdiera el
  canal, la orden `quitar` nunca llegaría. Por eso, antes de bloquear:
  1. guarda la política completa (`netsh advfirewall export`) en
     `active-response\kronos-estado\aislamiento.wfw`; si no puede, sale con 1 sin tocar nada;
  2. lee el o los manager de `ossec.conf` (`<client><server>`: `<address>`, `<port>`,
     `<protocol>`; si la dirección es un nombre, la resuelve); si no obtiene ninguna IP, sale
     con 1 sin tocar nada;
  3. crea las excepciones `Kronos-aislamiento-*` (grupo «Kronos AI aislamiento»): salida al
     manager por su puerto (1514/TCP por omisión), DHCP (salida UDP 67 y entrada UDP 68, para
     no perder la IP si vence el préstamo) y, sólo si el manager es un nombre, DNS (UDP y TCP
     53) hacia los servidores configurados.
- **Bloquea así:** deshabilita las reglas de permitir activas que no son de Kronos (en el
  firewall de Windows una regla de permitir le gana a la acción por omisión) y deja los tres
  perfiles encendidos con entrada y salida en `Block`. No crea una regla «bloquear todo»:
  las reglas de bloqueo le ganan a las de permitir y cortarían también el canal del manager.
- Si algo falla a mitad, restaura la copia y sale con 1.
- `quitar` importa la copia (`netsh advfirewall import`: reglas, estado de cada regla y
  perfiles), borra las reglas `Kronos-aislamiento-*` y la copia. Si el import falla, sale
  con 1 y **conserva la copia**.
- Aplicar y quitar son idempotentes: la copia es la marca de «aislado».

**Limitaciones conocidas:**

- `quitar` vuelve el firewall **al momento de aplicar**: un cambio hecho mientras el equipo
  estaba aislado (por ejemplo, un bloqueo de IP de Kronos en ese lapso) se pierde.
- Si el manager se alcanza por IPv6, el aislamiento no deja pasar el descubrimiento de
  vecinos (ICMPv6). En la PyME simulada el manager se alcanza por IPv4.

### Registro

Resultado en `C:\Program Files (x86)\ossec-agent\active-response\active-responses.log`,
una línea por orden (`… kronos-deshabilitar-cuenta: aplicar usuario.demo OK`,
`… ERROR cuenta protegida: Administrador`). El agente tiene el archivo abierto, así que los
scripts lo abren en modo compartido; si aun así no pueden escribir, lo dicen por la salida
de error. Wazuh no devuelve el código de salida a la API: EXECUTE sólo sabe que la orden llegó.

## Instalar en un agente

En una consola de **administrador** del equipo:

```powershell
$bin = 'C:\Program Files (x86)\ossec-agent\active-response\bin'
Copy-Item .\kronos-*.cmd, .\kronos-*.ps1 -Destination $bin
icacls "$bin\kronos-*"   # deben heredar sólo Administradores y SYSTEM
```

## Probar a mano

En una consola de PowerShell **como administrador**, en la carpeta de los scripts.
Usar sólo IP de documentación (`203.0.113.0/24`); nunca la puerta de enlace.

```powershell
$e = '{"version":1,"command":"add","parameters":{"extra_args":["aplicar","203.0.113.50"]}}'
$e | cmd /c kronos-bloquear-ip.cmd; "salida: $LASTEXITCODE"          # 0
netsh advfirewall firewall show rule name=Kronos-bloqueo-203.0.113.50   # existe, Bloquear, Entrada
$e | cmd /c kronos-bloquear-ip.cmd; "salida: $LASTEXITCODE"          # 0 (ya existía)
$e.Replace('aplicar','quitar') | cmd /c kronos-bloquear-ip.cmd; "salida: $LASTEXITCODE"   # 0
netsh advfirewall firewall show rule name=Kronos-bloqueo-203.0.113.50   # «No hay reglas…»
```

Casos que deben salir con 1 sin crear reglas: `127.0.0.1`, la IP propia, la puerta de
enlace, `1`, `203.0.113.50 & calc`, tres argumentos, operación `borrar`, entrada vacía.

### `kronos-deshabilitar-cuenta`

Con una cuenta local de prueba que **no** sea administradora (en el laboratorio,
`usuario.demo`):

```powershell
$a = '{"version":1,"command":"add","parameters":{"extra_args":["aplicar","usuario.demo"]}}'
$a | cmd /c kronos-deshabilitar-cuenta.cmd; "salida: $LASTEXITCODE"            # 0
(Get-LocalUser usuario.demo).Enabled                                              # False
$a | cmd /c kronos-deshabilitar-cuenta.cmd; "salida: $LASTEXITCODE"            # 0 (ya la había deshabilitado Kronos)
$a.Replace('aplicar','habilitar') | cmd /c kronos-deshabilitar-cuenta.cmd; "salida: $LASTEXITCODE"   # 0
(Get-LocalUser usuario.demo).Enabled                                              # True
$a.Replace('aplicar','habilitar') | cmd /c kronos-deshabilitar-cuenta.cmd; "salida: $LASTEXITCODE"   # 0 (no la deshabilitó Kronos)
Get-Content 'C:\Program Files (x86)\ossec-agent\active-response\active-responses.log' -Tail 6
```

**Sólo revierte lo que hizo Kronos:** deshabilitar la cuenta a mano
(`Disable-LocalUser usuario.demo`), aplicar (sale 0, «no la deshabilitó Kronos»), habilitar
(sale 0) y comprobar que la cuenta **sigue deshabilitada**. Al terminar,
`Enable-LocalUser usuario.demo`.

Casos que deben salir con 1 sin tocar ninguna cuenta: `Administrador`, la cuenta de
administración del equipo (miembro de Administradores), `usuario.demo & calc`,
`una cuenta que no existe`, `noexiste01`, tres argumentos, operación `borrar`, entrada
vacía y JSON roto.

## Prueba en EP-WKS-01 (21-10-2026)

Agente 002, Wazuh 4.14.8, por la API con el usuario `kronos-execute` (#43):

| Prueba | Resultado |
| :--- | :--- |
| `"command": "!kronos-bloquear-ip"`, sin extensión | El agente no encuentra el script: `ERROR: (1317): Could not launch command` en su `ossec.log`, y no se crea la regla |
| `"command": "!kronos-bloquear-ip.cmd"` | Aplicar y quitar funcionan |
| A mano: aplicar, aplicar de nuevo, quitar y quitar de nuevo | Salida 0; la regla `Kronos-bloqueo-<ip>` queda de entrada, bloquear y en los tres perfiles |
| A mano: casos de rechazo de la sección anterior | Salida 1, sin crear reglas |
| Registro en `active-responses.log` | **No escribe.** `Add-Content` falla porque `wazuh-agent` tiene el archivo abierto, y el `catch` vacío esconde el error. Funciona si se abre en modo compartido: `[System.IO.File]::Open($LOG, 'Append', 'Write', 'ReadWrite, Delete')` con un `StreamWriter` UTF-8 sin BOM |

Por eso EXECUTE envía el nombre con `.cmd` a los agentes Windows, y el registro de los
`.ps1` se abre en modo compartido (#56). `kronos-deshabilitar-cuenta` y
`kronos-aislar-equipo` siguen el mismo patrón.

### `kronos-aislar-equipo`

**Siempre desde el snapshot `listo-demo`** de EP-WKS-01, para volver atrás si algo queda
raro. Lo primero que se prueba es que el agente siga `Active`.

```powershell
(Get-NetFirewallRule).Count; @(Get-NetFirewallRule -Enabled True).Count
Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction, DefaultOutboundAction
$a = '{"version":1,"command":"add","parameters":{"extra_args":["aplicar"]}}'
$a | cmd /c kronos-aislar-equipo.cmd; "salida: $LASTEXITCODE"                  # 0
Test-NetConnection 1.1.1.1 -Port 443                                             # TcpTestSucceeded: False
Get-NetFirewallRule -DisplayName 'Kronos-aislamiento-*' | Select-Object DisplayName, Direction
$a | cmd /c kronos-aislar-equipo.cmd; "salida: $LASTEXITCODE"                  # 0 (ya estaba aislado)
Get-Content 'C:\Program Files (x86)\ossec-agent\active-response\active-responses.log' -Tail 3
```

Durante al menos 5 minutos, **en el servidor** el agente 002 debe seguir `Active`
(`agent_control -l` en el contenedor del manager). Después, **quitar por la API, no a
mano** (así se prueba que el canal funciona durante el aislamiento): `!kronos-aislar-equipo.cmd`
con `["quitar"]`. Al final, mismas cuentas de reglas y mismos perfiles que al comienzo,
navegar funciona, y quitar de nuevo sale con 0 («no estaba aislado»).

Casos que deben salir con 1 sin tocar el firewall: `["aplicar","203.0.113.50"]` (dos
argumentos), `[]`, operación `borrar`, entrada vacía y JSON roto.

## Prueba de `kronos-deshabilitar-cuenta` en EP-WKS-01

Agente 002, con la cuenta `usuario.demo`. Se completa con la prueba de Nicolás:

| Prueba | Fecha | Resultado |
| :--- | :--- | :--- |
| A mano: aplicar, aplicar de nuevo, habilitar y habilitar de nuevo | | |
| A mano: cuenta deshabilitada por otra persona; habilitar no la toca | | |
| A mano: casos de rechazo | | |
| Por la API (`!kronos-deshabilitar-cuenta.cmd`), aplicar y habilitar | | |
| Registro en `active-responses.log` | | |

## Prueba de `kronos-aislar-equipo` en EP-WKS-01

Agente 002, desde el snapshot `listo-demo`. Se completa con la prueba de Nicolás:

| Prueba | Fecha | Resultado |
| :--- | :--- | :--- |
| A mano: aplicar; `Test-NetConnection 1.1.1.1 -Port 443` falla | | |
| El agente 002 sigue `Active` en el manager durante al menos 5 minutos | | |
| Quitar **por la API** durante el aislamiento | | |
| Después: mismas reglas, mismos perfiles, navegación normal | | |
| Aplicar dos veces y quitar dos veces (idempotente) | | |
| Casos de rechazo | | |
