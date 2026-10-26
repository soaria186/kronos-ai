# Active Response de Kronos en Windows

Scripts que SOAR-EXECUTE ejecuta en los puestos de trabajo Windows por Active Response
de Wazuh. Cada comando son dos archivos: un lanzador `.cmd` (lo que ejecuta el agente) y
el script `.ps1` que hace el trabajo. Compatibles con Windows PowerShell 5.1.

| Comando | Archivos | Aplicar | Revertir |
| :--- | :--- | :--- | :--- |
| `kronos-bloquear-ip` | `kronos-bloquear-ip.cmd` + `.ps1` | `aplicar <ip>`: regla de entrada `Kronos-bloqueo-<ip>` con `netsh advfirewall` | `quitar <ip>`: borra esa regla |

## Cómo recibe la orden

El agente entrega por la entrada estándar una línea JSON y Kronos pone la operación y
el objetivo en `parameters.extra_args` (verificado con el script de Linux en Wazuh 4.14.8,
20-10-2026):

```json
{"version":1,"command":"add","parameters":{"extra_args":["aplicar","203.0.113.50"]}}
```

## Barreras del script

Son una segunda línea de defensa: EXECUTE (`ejecucion/ordenes.py`) ya valida lo mismo.

- Sólo `aplicar` o `quitar` y exactamente un objetivo.
- La IP debe estar en su forma canónica (`1` o `0x7f.1` se rechazan, aunque Windows las acepte).
- Nunca bloquea loopback, `0.0.0.0`, multicast, enlace local, difusión, una IP del propio
  equipo ni **su puerta de enlace**.
- `netsh` recibe los argumentos como lista; no se arma texto para un intérprete.
- Aplicar y quitar son idempotentes.
- Si el firewall está apagado en algún perfil, deja una ADVERTENCIA en el registro (la
  regla existe, pero no bloquea en ese perfil).

Resultado en `C:\Program Files (x86)\ossec-agent\active-response\active-responses.log`.
Wazuh no devuelve el código de salida a la API: EXECUTE sólo sabe que la orden llegó.

## Instalar en un agente

En una consola de **administrador** del equipo:

```powershell
$bin = 'C:\Program Files (x86)\ossec-agent\active-response\bin'
Copy-Item .\kronos-bloquear-ip.cmd, .\kronos-bloquear-ip.ps1 -Destination $bin
icacls "$bin\kronos-bloquear-ip.*"   # deben heredar sólo Administradores y SYSTEM
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

## Prueba en EP-WKS-01 (21-10-2026)

Agente 002, Wazuh 4.14.8, por la API con el usuario `kronos-execute` (#43):

| Prueba | Resultado |
| :--- | :--- |
| `"command": "!kronos-bloquear-ip"`, sin extensión | El agente no encuentra el script: `ERROR: (1317): Could not launch command` en su `ossec.log`, y no se crea la regla |
| `"command": "!kronos-bloquear-ip.cmd"` | Aplicar y quitar funcionan |
| A mano: aplicar, aplicar de nuevo, quitar y quitar de nuevo | Salida 0; la regla `Kronos-bloqueo-<ip>` queda de entrada, bloquear y en los tres perfiles |
| A mano: casos de rechazo de la sección anterior | Salida 1, sin crear reglas |
| Registro en `active-responses.log` | **No escribe.** `Add-Content` falla porque `wazuh-agent` tiene el archivo abierto, y el `catch` vacío esconde el error. Funciona si se abre en modo compartido: `[System.IO.File]::Open($LOG, 'Append', 'Write', 'ReadWrite, Delete')` con un `StreamWriter` UTF-8 sin BOM |

Por eso EXECUTE debe enviar el nombre con `.cmd` a los agentes Windows, y el registro del
`.ps1` se abre en modo compartido. Los dos cambios están en #56. Los scripts nuevos
(`kronos-deshabilitar-cuenta` y `kronos-aislar-equipo`) siguen el mismo patrón.
