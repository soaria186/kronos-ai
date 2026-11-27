# Pruebas de los scripts de Active Response de Windows en EP-WKS-01 (02-11-2026)

Prueba de los tres scripts de Windows (`kronos-bloquear-ip`, `kronos-deshabilitar-cuenta` y
`kronos-aislar-equipo`) en EP-WKS-01, agente 002, Wazuh 4.14.8: primero a mano dentro de la VM y después por la
API de Wazuh con el usuario `kronos-execute`. Los scripts de prueba están en
[`infra/wazuh/active-response/pruebas/`](../../../infra/wazuh/active-response/pruebas/README.md).

Las horas van en UTC; la VM está en hora local de Chile (UTC−3), que es la que muestran el nombre de cada archivo
y la línea «== Kronos, prueba …».

## Preparación de EP-WKS-01

- Auditoría de inicios de sesión fallidos activada con el GUID `{0CCE9215-69AE-11D9-BED3-505054503030}`.
- Cuenta local `usuario.demo` en el grupo Usuarios.
- Los 3 scripts de `develop` (`e90710c`) instalados en `active-response\bin`, con tamaños 614, 6693, 770, 9361,
  618 y 11122 bytes, y permisos heredados de SYSTEM y Administradores.
- Snapshot `listo-demo` de la VM, desde el que se parte.

## Archivos

| Archivo | Parte | Resultado |
| :--- | :--- | :--- |
| [`prueba-ar-bloquear-20261102-151027.txt`](prueba-ar-bloquear-20261102-151027.txt) | `bloquear`, **sin** consola de administrador | 3 fallas: `aplicar` sale con 1 y no crea la regla. Es el hallazgo 1 |
| [`prueba-ar-bloquear-20261102-151600.txt`](prueba-ar-bloquear-20261102-151600.txt) | `bloquear`, como administrador | Todo OK |
| [`prueba-ar-cuenta-20261102-151724.txt`](prueba-ar-cuenta-20261102-151724.txt) | `cuenta` | Todo OK |
| [`prueba-ar-aislar-20261102-152156.txt`](prueba-ar-aislar-20261102-152156.txt) | `aislar` | Todo OK |
| [`prueba-ar-verificar-20261102-152815.txt`](prueba-ar-verificar-20261102-152815.txt) | `verificar`, después de quitar el aislamiento por la API | Todo OK |

Cada archivo es la transcripción de PowerShell de una parte, con las últimas líneas de `active-responses.log` al
final. Las pruebas por la API se corrieron en la consola del servidor y no tienen archivo; sus resultados están
en la segunda tabla.

## Resultados a mano, como administrador

| Script | Resultado |
| :--- | :--- |
| `kronos-bloquear-ip` | Aplica, aplica de nuevo, quita y quita de nuevo, con salida 0. Rechaza 9 casos con salida 1: `127.0.0.1`, la IP propia (`10.0.2.15`), la puerta de enlace (`10.0.2.2`), `1`, `203.0.113.50 & calc`, 3 argumentos, `borrar`, entrada vacía y JSON roto. No quedan reglas `Kronos-bloqueo-*` |
| `kronos-deshabilitar-cuenta` | Aplica y habilita `usuario.demo`, y las dos órdenes son idempotentes. No habilita una cuenta deshabilitada por otra persona. Rechaza 8 casos con salida 1: `Administrador`, `labadmin` (miembro de Administradores), `usuario.demo & calc`, cuenta inexistente (`noexiste01`), 3 argumentos, `borrar`, entrada vacía y JSON roto. Al final, `labadmin` y `usuario.demo` siguen habilitadas |
| `kronos-aislar-equipo` | Rechaza 5 casos sin tocar el firewall: dos argumentos, sin argumentos, `borrar`, entrada vacía y JSON roto. A las 18:23:12 aísla: `1.1.1.1:443` falla y quedan 3 excepciones (canal al manager TCP/1514, DHCP de salida y DHCP de entrada). Aplicar de nuevo no cambia nada (18:23:39, «ya estaba aislado»). El servicio del agente sigue en marcha |

## Resultados por la API

Con `probar-ar-api.sh` en SOAR-CORE-01, contra el agente 002:

| Prueba | Resultado |
| :--- | :--- |
| Agente durante el aislamiento | `Active` a las 18:24:55 y a las 18:25:55, con el keep-alive subiendo |
| `quitar` del aislamiento | La orden se envió a las 18:26:51, 3 min 39 s después de aislar, y llegó (`affected_items ["002"]`). El agente la aplicó a las 18:26:55, a los 3 min 43 s: «quitar OK; politica restaurada». La guía pedía 5 minutos de aislamiento; se repite en E4 de la prueba integral |
| Después de quitar (parte `verificar`) | Las mismas 494 reglas, 240 activas y los mismos perfiles que antes de aislar. No quedan reglas `Kronos-aislamiento-*`, `1.1.1.1:443` responde y quitar de nuevo sale con 0 («no estaba aislado») |
| Bloquear `203.0.113.60` | Aparece la regla de entrada que bloquea (18:29:42) y desaparece al quitar (18:30:44) |
| Deshabilitar `usuario.demo` | `Enabled` pasa a False (18:35:53) y después a True (18:36:22) |

## Hallazgos

1. **Las pruebas a mano tienen que correr como administrador.** Sin consola de administrador, `aplicar` sale con
   1 porque `netsh` no puede crear la regla, y el script avisa por la salida de error que no pudo escribir en el
   registro. En cada orden, la consola mostró:

   ```text
   kronos-bloquear-ip no pudo escribir en el registro: Excepción al llamar a "Open" con los argumentos "4": "Acceso denegado a la ruta de acceso 'C:\Program Files (x86)\ossec-agent\active-response\active-responses.log'."
   ```

   Por eso no hay líneas nuevas en `active-responses.log` de esa corrida. El aviso no está en la transcripción,
   porque `Start-Transcript` no captura la salida de error de los comandos que lanza `cmd`. Los rechazos y
   `quitar` sin regla salen bien, porque no necesitan permisos. En producción no pasa: el agente corre como
   SYSTEM. Quedó anotado en el README de los scripts de Windows.
2. En `kronos-deshabilitar-cuenta.ps1`, la variable local `$nombre` tapa a `$NOMBRE` (PowerShell no distingue
   mayúsculas), y la línea del rechazo por nombre protegido sale como
   `Administrador: ERROR cuenta protegida: Administrador` en vez de `kronos-deshabilitar-cuenta: ERROR …`. No
   cambia lo que hace el script: rechaza la cuenta y sale con 1. Lo corrige Rodrigo.
3. La línea de `aplicar` del aislamiento muestra la IP pública del manager. En esta evidencia se reemplazó por
   `203.0.113.10`.
4. Al pegar bloques largos en la consola de la VM se pierden caracteres. Los scripts se pasan con `scp`.
