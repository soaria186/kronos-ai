# Pruebas de los scripts de Active Response en Windows

Dos scripts para probar los tres scripts de [`../windows/`](../windows/README.md) en EP-WKS-01: a mano dentro
de la VM y por la API de Wazuh desde el servidor. Se usaron el 02-11-2026; las salidas están en
[`docs/evidencia/2026-11-02_ar-windows/`](../../../../docs/evidencia/2026-11-02_ar-windows/README.md).

| Script | Dónde se corre | Qué prueba |
| :--- | :--- | :--- |
| `probar-ar-windows.ps1` | EP-WKS-01, en PowerShell **como administrador** | Cada script a mano, con la línea JSON por la entrada estándar como lo llama el agente: aplicar, revertir, idempotencia y casos de rechazo |
| `probar-ar-api.sh` | SOAR-CORE-01 | Las órdenes por la API de Wazuh con el usuario `kronos-execute`, contra el agente 002 (EP-WKS-01, Windows) por omisión o, con `AGENTE=001`, contra EP-SRV-01 (Linux) |

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

Con un usuario con `sudo` en SOAR-CORE-01. Por omisión las órdenes van al agente 002 (EP-WKS-01, Windows):

```bash
bash probar-ar-api.sh estado
bash probar-ar-api.sh orden kronos-aislar-equipo.cmd quitar
bash probar-ar-api.sh orden kronos-bloquear-ip.cmd aplicar 203.0.113.60
bash probar-ar-api.sh orden kronos-deshabilitar-cuenta.cmd aplicar usuario.demo
```

Con `AGENTE=001` van a EP-SRV-01 (Linux). En Linux el script **no lleva extensión**:

```bash
AGENTE=001 bash probar-ar-api.sh estado
AGENTE=001 bash probar-ar-api.sh orden kronos-bloquear-ip aplicar 203.0.113.60
AGENTE=001 bash probar-ar-api.sh orden kronos-bloquear-ip quitar 203.0.113.60
```

Una ruta de Windows va entre comillas simples, para que bash no se coma las barras invertidas
(`kronos-cuarentena.cmd` todavía no existe; es el ejemplo de una orden con ruta):

```bash
bash probar-ar-api.sh orden kronos-cuarentena.cmd aplicar 'C:\Users\usuario.demo\Downloads\muestra.exe'
```

- `estado` muestra el nombre, el estado y el último keep-alive del agente (`agent_control -i` en el contenedor
  del manager).
- `orden <script> <argumentos…>` envía la orden al agente. Lee la contraseña de `kronos-execute` del secreto
  `wazuh_api_password` sin mostrarla.
- **Script:** `kronos-<nombre>` para Linux o `kronos-<nombre>.cmd` para Windows (`^kronos-[a-z-]+(\.cmd)?$`).
- **Argumentos:** de 1 a 256 caracteres, con letras, números, `.`, `_`, `-` y, para las rutas de la cuarentena,
  `/`, `\` y `:` (equivale a `^[A-Za-z0-9._:/\\-]{1,256}$`). Se rechazan los espacios, `;`, `|`, `&`, `$`, las
  comillas, los backticks y cualquier otro carácter, también los acentos; por eso no se puede pasar una ruta
  con espacios, como `C:\Program Files\…`. Al armar el JSON, cada `\` se escribe `\\`.
- `AGENTE` debe tener tres dígitos (`001`, `002`); si no, el script termina con error antes de enviar nada.
- La API sólo dice si la orden llegó (`affected_items`); si el script funcionó se ve en
  `active-responses.log` del agente o comprobándolo en el equipo.

Las variables del comienzo son las de la guía de instalación: `M`, el contenedor del manager, y `CLAVE`, la
ruta del secreto, se cambian si el servidor es otro. `AGENTE` se da al correr el script (`AGENTE=001 bash …`)
y vale 002 si no se da.
