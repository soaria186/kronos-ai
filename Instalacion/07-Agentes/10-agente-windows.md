# 10 · Agente Windows

| Campo | Valor |
| :--- | :--- |
| Parte | 10 de 15 |
| Responsable | Nicolás Zamora (revisa: Rodrigo Riveros) |
| Versión | 1.0, 11-11-2026 |
| Estado | Vigente: instalación de EP-WKS-01 (21-10-2026), `infra/wazuh/active-response/windows/README.md` y configuración de la prueba integral 2 (10 y 11-11-2026) |
| Requisitos | Partes 04, 05 y 08 |

En la PyME simulada, **EP-WKS-01** es el puesto de trabajo: Windows 11 con el agente de Wazuh 4.14.8 (agente
002). Como en Linux, el agente se registra desde el servidor y la llave no pasa por ningún chat.

---

## 1. La máquina virtual del laboratorio

| Dato | Valor |
| :--- | :--- |
| Dónde | VirtualBox 7.2 en el PC de escritorio de Nicolás (`H:\Kronos-VM`) |
| Sistema | Windows 11, ISO `es-mx`, build 26300 |
| Recursos | 4 CPU, 8 GB de RAM, disco de 80 GB, EFI y TPM 2.0 |
| Red | Red NAT `kronos-lab` con la IP `10.0.50.3` (SSH por el `127.0.0.1:2223` del PC) y red interna `kronos-ext` con `198.51.100.10`, que hace de internet en el laboratorio |
| Acceso remoto | Escritorio remoto (RDP) activado, para los escenarios de F3 |
| Instantáneas | `base-limpia` (sin agente), `con-agente` y `listo-demo` (para E3 y E4) |

Para que VirtualBox corra Windows 11, el PC anfitrión tiene apagados la integridad de memoria (HVCI) y el
hipervisor de Windows. Se vuelven a encender **después de la defensa**, no antes.

Dentro de la VM: equipo renombrado a `EP-WKS-01`, una cuenta local de administración y el servidor OpenSSH, con
su regla de firewall en todos los perfiles.

## 2. Instalar el agente

En PowerShell **como administrador**:

```
[agente Windows] $msi = "$env:TEMP\wazuh-agent-4.14.8-1.msi"
[agente Windows] Invoke-WebRequest -Uri https://packages.wazuh.com/4.x/windows/wazuh-agent-4.14.8-1.msi -OutFile $msi
[agente Windows] (Get-AuthenticodeSignature $msi).Status
[agente Windows] msiexec.exe /i $msi /q WAZUH_MANAGER="XXXX" WAZUH_AGENT_NAME="EP-WKS-01"
```

**Debe mostrar:** `Valid` (firmado por Wazuh, Inc). `XXXX` es la IP pública del servidor. El 21-10-2026 el MSI
no se conservó, así que se comprobó la firma del ejecutable ya instalado:

```
[agente Windows] Get-AuthenticodeSignature 'C:\Program Files (x86)\ossec-agent\wazuh-agent.exe' | Format-List Status, SignerCertificate
```

## 3. Registrar el agente e importar la llave

En el servidor, como en la parte 09:

```
[servidor] sudo docker exec single-node-wazuh.manager-1 /var/ossec/bin/manage_agents -a any -n EP-WKS-01
[servidor] sudo sh -c 'umask 077; docker exec single-node-wazuh.manager-1 /var/ossec/bin/manage_agents -e 002 | grep -E "^[A-Za-z0-9+/]+=*$" > /dev/shm/llave-002'
[servidor] sudo chown "$USER" /dev/shm/llave-002
```

Copia en dos saltos y borrado en los tres lados:

```
[PC]             scp soar-core-01:/dev/shm/llave-002 .
[PC]             scp -P 2223 llave-002 XXXX@127.0.0.1:llave-002
[PC]             Remove-Item llave-002
[servidor]       shred -u /dev/shm/llave-002
```

En la VM, como administrador:

```
[agente Windows] $llave = Get-Content "$HOME\llave-002"
[agente Windows] 'y' | & 'C:\Program Files (x86)\ossec-agent\manage_agents.exe' -i $llave
[agente Windows] Remove-Item "$HOME\llave-002"; Remove-Variable llave
[agente Windows] Restart-Service -Name WazuhSvc
```

## 4. Comprobar

```
[servidor] sudo docker exec single-node-wazuh.manager-1 /var/ossec/bin/agent_control -l
[agente Windows] Get-Content 'C:\Program Files (x86)\ossec-agent\ossec.log' -Tail 5
```

**Debe mostrar:** `ID: 002, Name: EP-WKS-01, IP: any, Active` y, en el agente, `Connected to the server`.

## 5. Registro de eventos para los escenarios E3 y E4

- **E3, inicios de sesión fallidos (evento 4625 → regla 100103).** Activar la auditoría de fallos de inicio de
  sesión. Se usa el identificador de la subcategoría, porque en un Windows en español su nombre cambia:

  ```
  [agente Windows] auditpol /set /subcategory:"{0CCE9215-69AE-11D9-BED3-505054503030}" /failure:enable
  [agente Windows] auditpol /get /subcategory:"{0CCE9215-69AE-11D9-BED3-505054503030}"
  ```

  **Debe mostrar:** la subcategoría de inicio de sesión con «Error» (o «Failure») activado.
- **E4, registro de auditoría borrado (evento 1102 → regla 100113).** Windows lo registra siempre; no hay que
  activar nada.
- **Tareas programadas nuevas (evento 4698 → regla 100112, PB-F5-02).** Activar «Otros eventos de acceso a
  objetos», también por su identificador:

  ```
  [agente Windows] auditpol /set /subcategory:"{0CCE9227-69AE-11D9-BED3-505054503030}" /success:enable
  ```
- **Cuenta de prueba para E3**, que nunca es la de administración ni `Administrator`. La contraseña se escribe
  en la ventana, no en el comando:

  ```
  [agente Windows] New-LocalUser -Name usuario.demo -Password (Read-Host -AsSecureString 'Clave de usuario.demo')
  ```

Con todo listo, tomar la instantánea `listo-demo`.

## 6. Sysmon, integridad de archivos y servicios

Las reglas 100104 a 100109 y 100117 (PowerShell codificado, ejecución sospechosa, ejecutables en carpetas de
usuario, acceso y ejecución remota, conexiones de salida) salen de eventos de **Sysmon** (reglas nativas 91xxx y
92xxx). En EP-WKS-01 se instaló **Sysmon 15.22** con la configuración pública `sysmonconfig-export.xml` de
SwiftOnSecurity, como administrador y desde la carpeta donde se descomprimió:

```
[agente Windows] .\Sysmon64.exe -accepteula -i sysmonconfig-export.xml
[agente Windows] Get-Service Sysmon64
```

**Debe mostrar:** `Running`. Después, agregar su canal al `ossec.conf` del agente
(`C:\Program Files (x86)\ossec-agent\ossec.conf`, guardando antes una copia `ossec.conf.bak`):

```xml
<localfile>
  <location>Microsoft-Windows-Sysmon/Operational</location>
  <log_format>eventchannel</log_format>
</localfile>
```

Para PB-F5-01 (persistencia en la carpeta Inicio, regla 100110), la integridad de archivos vigila esa carpeta:

```xml
<syscheck>
  <directories realtime="yes" check_all="yes">C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp</directories>
</syscheck>
```

La regla 100120 (servicio terminado de forma inesperada, evento 7031) no necesita nada: el agente ya lee el
registro del sistema. Reiniciar el agente después de cambiar `ossec.conf`:

```
[agente Windows] Restart-Service -Name WazuhSvc
```

## 7. Scripts de Active Response

Los scripts de Windows son un lanzador `.cmd` más un `.ps1` por cada una de las 10 acciones
(`infra/wazuh/active-response/windows/`).
Copiarlos a la VM y, como administrador, a la carpeta del agente:

```
[PC]             scp -P 2223 infra/wazuh/active-response/windows/kronos-*.cmd infra/wazuh/active-response/windows/kronos-*.ps1 XXXX@127.0.0.1:
[agente Windows] $bin = 'C:\Program Files (x86)\ossec-agent\active-response\bin'
[agente Windows] Copy-Item "$HOME\kronos-*.cmd", "$HOME\kronos-*.ps1" -Destination $bin
[agente Windows] icacls "$bin\kronos-*"
```

**Debe mostrar:** permisos heredados sólo de Administradores y SYSTEM.

Probarlos a mano como dice el README de esa carpeta (aplicar, aplicar de nuevo, quitar y los casos que deben
rechazarse) y después por la API (parte 08, sección 3), con un detalle que sólo vale en Windows: **el comando
lleva la extensión**, `!kronos-bloquear-ip.cmd`. Sin ella, el agente no encuentra el script (`(1317) Could not
launch command`; prueba del 21-10-2026, #43).

## 8. Lista de comprobación

- [ ] Agente 4.14.8 instalado, con firma válida, registrado desde el servidor y `Active`.
- [ ] Llave importada sin pasar por un chat; copias temporales borradas.
- [ ] Auditoría de fallos de inicio de sesión y de «Otros eventos de acceso a objetos» activadas.
- [ ] Sysmon 15.22 en marcha y su canal en `ossec.conf`; integridad de archivos sobre la carpeta Inicio.
- [ ] RDP activado y la red interna `kronos-ext` configurada (escenarios de F3).
- [ ] Cuenta `usuario.demo` creada; instantánea `listo-demo` tomada.
- [ ] Scripts `kronos-*` en `active-response\bin`, probados a mano y por la API con `.cmd`.
