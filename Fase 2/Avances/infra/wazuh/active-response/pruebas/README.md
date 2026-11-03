# Pruebas de los scripts de Active Response en Windows

Dos scripts para probar los tres scripts de [`../windows/`](../windows/README.md) en EP-WKS-01: a mano dentro
de la VM y por la API de Wazuh desde el servidor. Se usaron el 02-11-2026; las salidas están en
[`docs/evidencia/2026-11-02_ar-windows/`](../../../../docs/evidencia/2026-11-02_ar-windows/README.md).

| Script | Dónde se corre | Qué prueba |
| :--- | :--- | :--- |
| `probar-ar-windows.ps1` | EP-WKS-01, en PowerShell **como administrador** | Cada script a mano, con la línea JSON por la entrada estándar como lo llama el agente: aplicar, revertir, idempotencia y casos de rechazo |
| `probar-ar-api.sh` | SOAR-CORE-01 | Las órdenes por la API de Wazuh con el usuario `kronos-execute`, contra el agente 002 |

Usar sólo IP de documentación (`203.0.113.0/24`).

## A mano, en EP-WKS-01

Antes: partir del snapshot `listo-demo`, con los tres scripts instalados en `active-response\bin` y la cuenta
`usuario.demo` creada (ver [`../windows/README.md`](../windows/README.md)).

Pasar el script desde el PC con `scp`, no pegándolo en la consola de la VM, donde se pierden caracteres:

```powershell
scp -P 2223 probar-ar-windows.ps1 labadmin@127.0.0.1:
```

En la VM, en una consola de PowerShell **como administrador** (sin elevación, `aplicar` sale con 1 y el script
avisa por la salida de error que no pudo escribir en el registro: «Acceso denegado»):

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\labadmin\probar-ar-windows.ps1 -Parte bloquear
```

Las partes van en este orden: `bloquear`, `cuenta`, `aislar` y `verificar`. Entre `aislar` y `verificar`, el
aislamiento se quita **por la API** (abajo), para probar que el canal con el manager sigue abierto. Cada parte
deja `C:\Users\labadmin\prueba-ar-<parte>-<fecha>.txt` y termina con «RESULTADO: todo OK» o con el número de
fallas.

Para traer las salidas al PC:

```powershell
scp -P 2223 "labadmin@127.0.0.1:prueba-ar-*.txt" $HOME\evidencia-ar\
```

Antes de publicarlas, reemplazar la IP pública del manager, que sale en la línea de `aplicar` del aislamiento,
por `203.0.113.10`.

## Por la API, en el servidor

Con un usuario con `sudo` en SOAR-CORE-01:

```bash
bash probar-ar-api.sh estado
bash probar-ar-api.sh orden kronos-aislar-equipo.cmd quitar
bash probar-ar-api.sh orden kronos-bloquear-ip.cmd aplicar 203.0.113.60
bash probar-ar-api.sh orden kronos-deshabilitar-cuenta.cmd aplicar usuario.demo
```

- `estado` muestra el nombre, el estado y el último keep-alive del agente 002 (`agent_control -i` en el
  contenedor del manager).
- `orden <script.cmd> <argumentos…>` envía la orden al agente 002. Lee la contraseña de `kronos-execute` del
  secreto `wazuh_api_password` sin mostrarla, y rechaza nombres de script o argumentos fuera de
  `^[A-Za-z0-9._-]{1,64}$`.
- La API sólo dice si la orden llegó (`affected_items`); si el script funcionó se ve en
  `active-responses.log` del agente o comprobándolo en la VM.

Las variables del comienzo (`M`, el contenedor del manager; `CLAVE`, la ruta del secreto, y `AGENTE`) son las
de la guía de instalación; se cambian si el servidor es otro.
