# 14 · Retiro de una PyME y desinstalación

| Campo | Valor |
| :--- | :--- |
| Parte | 14 de 15 |
| Responsable | Nicolás Zamora (revisa: Rodrigo Riveros) |
| Versión | 1.0, 12-11-2026 |
| Estado | Revisada, sin ejecutar: se sigue completa al cerrar el servidor (10-12-2026). La reversión de cada medida, que es la base de la sección 1, se probó en la prueba integral 2 (10-11-2026) |
| Requisitos | Una PyME dada de alta (parte 13) |

Retirar a una PyME es dejar sus equipos como estaban antes de Kronos, quitarle el acceso a su encargado de TI y
dejar sus datos según la política de retención. Lo mismo sirve para cerrar el proyecto cuando termine el
contrato del servidor (10-12-2026).

---

## 1. Antes de desinstalar: medidas vigentes

Una medida aplicada que no se revierte antes de quitar el agente queda puesta para siempre. En la consola, en
«Medidas vigentes», revertir todas las que queden:

- **Se revierten solas a los 60 minutos:** los bloqueos de nivel 1 (PB-F1-02, PB-F3-01, PB-F4-01, PB-F6-02) y
  la limitación de conexiones (PB-F6-03).
- **No se revierten solas:** las de nivel 2 y 3, y también las de persistencia de nivel 1: la cuarentena
  (PB-F2-02 y PB-F5-01) y la tarea deshabilitada (PB-F5-02). Se revierten con el botón de la consola.
- **No tienen reversión:** cerrar la sesión (PB-F1-04) y terminar un proceso (PB-F2-03). Aparecen en «Medidas
  vigentes», pero su botón «Revertir» falla: se dejan como están.

Después, detener SOAR-EXECUTE para que Kronos no actúe sobre equipos a medio desinstalar (la consola sólo
cierra el cortacircuito, no lo abre):

```
[servidor] cd /opt/kronos/audit/infra/docker
[servidor] sudo docker compose -f docker-compose.yml -f servicios.yml stop execute
```

En la v1.0 hay una PyME por servidor (parte 13), así que esto no afecta a otras.

## 2. En cada equipo Linux

```
[agente Linux] sudo iptables -S | grep -- '--comment kronos'
[agente Linux] sudo systemctl stop wazuh-agent
[agente Linux] sudo apt-mark unhold wazuh-agent
[agente Linux] sudo apt-get purge -y wazuh-agent
[agente Linux] sudo rm -rf /var/ossec
[agente Linux] sudo rm -f /etc/apt/sources.list.d/wazuh.list /usr/share/keyrings/wazuh.gpg
```

Si el primer comando muestra reglas de Kronos, quitarlas antes con el mismo script (`quitar <ip>`) o con
`sudo iptables -D INPUT -s <ip> -m comment --comment kronos -j DROP` (en `OUTPUT` para un destino bloqueado).
Antes de desinstalar, revisar también lo que dejan los otros scripts:

```
[agente Linux] sudo iptables -S | grep -E 'KRONOS-AISLAR|connlimit'
[agente Linux] sudo ls /var/lib/kronos/cuarentena/
[agente Linux] sudo grep -rl '#kronos# ' /etc/crontab /etc/cron.d /var/spool/cron 2>/dev/null
[agente Linux] sudo cat /var/ossec/active-response/kronos-cuentas.json 2>/dev/null
```

Debe salir vacío. Lo que aparezca se revierte desde la consola, con el agente todavía instalado. Al final,
borrar `/var/lib/kronos` si quedó.

## 3. En cada equipo Windows

Como administrador:

```
[agente Windows] Get-NetFirewallRule -DisplayName 'Kronos-*' | Format-Table DisplayName, Direction, Action
[agente Windows] Get-ScheduledTask -TaskPath '\Kronos\' -ErrorAction SilentlyContinue
[agente Windows] Get-ChildItem C:\ProgramData\Kronos\cuarentena -ErrorAction SilentlyContinue
[agente Windows] Get-LocalUser | Where-Object { -not $_.Enabled } | Format-Table Name
[agente Windows] Stop-Service -Name WazuhSvc
[agente Windows] Get-Package -Name 'Wazuh Agent' | Uninstall-Package
```

- Las reglas `Kronos-*` que queden se borran con `Remove-NetFirewallRule -DisplayName 'Kronos-…'`.
- Una cuenta que Kronos deshabilitó y que debe volver a usarse se habilita con `Enable-LocalUser -Name <cuenta>`.
- Si el equipo quedó aislado, la política del firewall se restaura con el mismo script (`quitar`).
- Un archivo en `C:\ProgramData\Kronos\cuarentena` se restaura desde la consola antes de desinstalar.
- Al final, borrar las carpetas `C:\Program Files (x86)\ossec-agent` y `C:\ProgramData\Kronos` si quedaron.

## 4. En el servidor

1. **Agentes:** quitarlos del manager (`manage_agents -r <número>` en el contenedor del manager, o
   `DELETE /agents` por la API).
2. **Configuración:** sacar la PyME de `KRONOS_INQUILINOS` y `KRONOS_NOMBRES_INQUILINOS`, y sus entradas de la
   lista de exclusión (por PR). Recrear los servicios.
3. **Encargado de TI:**
   - Telegram: sacarlo del grupo y de `KRONOS_TELEGRAM_EQUIPO`, y recrear `notify`.
   - Consola: borrar su entrada de `consola_usuarios.json` y recrear `consola` (parte 07, sección 6).
   - NetBird: borrar su PC de la red.

## 5. Los datos

| Dónde | Qué pasa |
| :--- | :--- |
| `alertas_guardadas` | Se purgan solas a los 90 días (parte 12). Para adelantarlo, `fn_purgar_alertas(dias)` como `kronos_admin`, con un mínimo de 7 días |
| Bitácora (`auditoria`) | No se borra: es de sólo inserción por diseño. Guarda decisiones, actores y la huella de cada alerta, no la alerta |
| Respaldos | Las 14 copias diarias rotan solas: lo purgado desaparece de ellas en 14 días más |

La PyME recibe por escrito qué datos quedan, dónde y hasta cuándo.

## 6. Cierre del proyecto

Al terminar el contrato del servidor (10-12-2026):

1. Guardar las evidencias finales en el repositorio, sin datos sensibles.
2. Retirar todas las PyME (secciones 1 a 4).
3. Un último respaldo cifrado, fuera del servidor, si el equipo decide conservarlo.
4. Borrar los volúmenes y el disco del servidor, y entregar el VPS a quien lo contrató.
5. Revocar el token de Telegram, la llave de despliegue de GitHub y las cuentas de NetBird; borrar del gestor lo
   que ya no sirve.

## 7. Lista de comprobación

- [ ] Medidas vigentes revertidas; SOAR-EXECUTE detenido durante el retiro.
- [ ] Agentes desinstalados; sin reglas `kronos` ni `Kronos-*`, sin archivos en cuarentena ni tareas
  deshabilitadas por Kronos; cuentas habilitadas de nuevo si corresponde.
- [ ] Agentes quitados del manager; PyME fuera de la configuración.
- [ ] Encargado de TI fuera de Telegram, la consola y NetBird.
- [ ] La PyME sabe qué datos quedan y hasta cuándo.
