# 14 · Retiro de una PyME y desinstalación

| Campo | Valor |
| :--- | :--- |
| Parte | 14 de 15 |
| Responsable | Nicolás Zamora (revisa: Rodrigo Riveros) |
| Versión | 0.9, 26-10-2026 |
| Estado | Borrador para revisión |
| Requisitos | Una PyME dada de alta (parte 13) |

Retirar a una PyME es dejar sus equipos como estaban antes de Kronos, quitarle el acceso a su encargado de TI y
dejar sus datos según la política de retención. Lo mismo sirve para cerrar el proyecto cuando termine el
contrato del servidor (10-12-2026).

---

## 1. Antes de desinstalar: medidas vigentes

Una medida aplicada que no se revierte antes de quitar el agente queda puesta para siempre. En la consola,
revisar las medidas de nivel 2 vigentes y los niveles 3 aplicados, y revertirlas. Las de nivel 1 se revierten
solas a los 60 minutos.

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
`sudo iptables -D INPUT -s <ip> -m comment --comment kronos -j DROP`.

## 3. En cada equipo Windows

Como administrador:

```
[agente Windows] Get-NetFirewallRule -DisplayName 'Kronos-*' | Format-Table DisplayName, Direction, Action
[agente Windows] Get-LocalUser | Where-Object { -not $_.Enabled } | Format-Table Name
[agente Windows] Stop-Service -Name WazuhSvc
[agente Windows] Get-Package -Name 'Wazuh Agent' | Uninstall-Package
```

- Las reglas `Kronos-*` que queden se borran con `Remove-NetFirewallRule -DisplayName 'Kronos-…'`.
- Una cuenta que Kronos deshabilitó y que debe volver a usarse se habilita con `Enable-LocalUser -Name <cuenta>`.
- Si el equipo quedó aislado, la política del firewall se restaura con el mismo script (`quitar`).
- Al final, borrar la carpeta `C:\Program Files (x86)\ossec-agent` si quedó.

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
- [ ] Agentes desinstalados; sin reglas `kronos` ni `Kronos-*`; cuentas habilitadas de nuevo si corresponde.
- [ ] Agentes quitados del manager; PyME fuera de la configuración.
- [ ] Encargado de TI fuera de Telegram, la consola y NetBird.
- [ ] La PyME sabe qué datos quedan y hasta cuándo.
