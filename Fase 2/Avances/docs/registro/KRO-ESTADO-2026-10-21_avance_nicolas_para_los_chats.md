# KRO-ESTADO-2026-10-21 · Avance de Nicolás (Bloque A) para los chats de Rodrigo y Patricio

Versión del 21-10-2026, 14:15 (hora de Chile; UTC−3). Autor: Nicolás Zamora, con su chat del asistente de IA. Complementa `KRO-LOG-NZ-2026-10-21_bloque_a_nicolas.md` (el registro corto) y continúa `KRO-ESTADO-2026-10-20_ejecucion_y_plan_paralelo.md`.

> Este documento no contiene contraseñas, llaves, tokens ni direcciones IP reales. La IP `203.0.113.50` es del rango reservado para documentación y se usa sólo en pruebas.

## 0. Para quién es y cómo leerlo

- Es para el **chat del asistente de IA de Rodrigo** y el **de Patricio**, y para el **chat principal («kronos maestro»)**, que juntará los tres avances. Cada chat arranca sin memoria de los otros: aquí está todo lo que hizo Nicolás, cómo lo hizo y qué espera de ustedes.
- Nombres oficiales: **EP-WKS-01** (Windows 11) y **EP-SRV-01** (Ubuntu). En el chat de laboratorio de Nicolás se llamaron «máquina Windows» y «máquina Linux» sólo para entenderse; en documentos y proyecto valen los oficiales.
- Dónde corre cada cosa: **SOAR-CORE-01** (Contabo) tiene Wazuh, PostgreSQL, Ollama, VALIDATE, EXECUTE y la consola. **EP-SRV-01** corre en el **notebook** de Nicolás. **EP-WKS-01** corre desde hoy en su **PC de escritorio**.

## 1. Estado al 21-10-2026, 14:15

| Pieza | Estado |
| :--- | :--- |
| Agente 001 (EP-SRV-01, Ubuntu 24.04) | `Active`, con **llave regenerada** (mismo ID 001) |
| Agente 002 (EP-WKS-01, Windows 11) | `Active`, agente Wazuh 4.14.8, snapshots `base-limpia` y `con-agente` |
| Script `kronos-bloquear-ip` (Linux) | Instalado en EP-SRV-01; **PR n.º 31** abierto (checks en verde, falta la aprobación de Rodrigo) |
| Guía `08-active-response.md` | En el mismo PR n.º 31 |
| Reversión automática del nivel 1 | **Confirmada** de punta a punta en la prueba del 21-10 |
| Documentación del laboratorio (contexto maestro del repositorio) | **PR n.º 33** abierto (falta la aprobación de Rodrigo) |
| Usuario de API `kronos-execute` | Existe y autentica; contraseña en el gestor de contraseñas |
| Scripts de Windows (Rodrigo) | En su rama `feat/e3-ar-windows-bloquear-ip`; Nicolás los prueba en EP-WKS-01 cuando estén listos |

## 2. Lo que hizo Nicolás

### 2.1 Reversión automática del bloqueo (tarea 1)

- **Primera prueba (20-10).** Ticket 20 (fuerza bruta SSH desde `203.0.113.50`, regla 100101, PB-F1-02, nivel 1). `EJECUCION_OK` a las 22:36:13 UTC; la reversión programada a las 23:36 UTC quedó como `REVERSION_FALLIDA` («agent is not active»): Nicolás había apagado la VM de EP-SRV-01. Al reiniciarse la VM, las reglas de iptables se perdieron.
- **Segunda prueba (21-10).** Ráfaga de alertas simuladas con `logger` desde EP-SRV-01 (15:34:39 a 15:34:52 UTC), con el notebook enchufado, sin suspensión y la VM encendida.
  - Primer ticket: `aplicar 203.0.113.50: OK` a las **15:35:15Z** y `quitar 203.0.113.50: OK` a las **16:35:18Z** (60 min y 3 s después).
  - Segundo ticket de la misma ráfaga: `aplicar … sin cambios (ya estaba)` a las 15:35:26Z y `quitar … sin cambios (ya estaba)` a las 16:35:28Z.
  - `iptables` no muestra ninguna regla para esa IP después de la reversión.
  - La consola no muestra fallas nuevas a las 16:35 UTC (su lista sólo trae las del 20-10 y los playbooks de consulta). No se revisó el detalle de cada ticket (eventos `REVERSION_OK`).
- **Conclusión:** el camino de éxito de la reversión del nivel 1 funciona. Lo que falló el 20-10 fue por el agente apagado, no por el diseño.

### 2.2 EP-WKS-01 (Windows 11) con agente Wazuh 4.14.8 (tarea 2)

**Cambio de lugar.** En el notebook iba demasiado lenta, así que Nicolás construyó EP-WKS-01 en su **PC de escritorio** (16 CPU, 32 GB). Se anuló la decisión previa «los 2 agentes de laboratorio van en VM del notebook» (D-16, actualizada en el PR n.º 33).

**VM en VirtualBox 7.2.22** (PowerShell con `VBoxManage`):
- Tipo `Windows11_64`, 4 CPU, 8 GB de RAM, disco VDI de 80 GB en SATA, EFI, TPM 2.0, tarjeta gráfica `vboxsvga` con 128 MB, una tarjeta de red NAT.
- DVD con el ISO en un controlador IDE (en SATA no arrancaba).
- Para Secure Boot: `VBoxManage modifynvram … inituefivarstore`, `enrollmssignatures` y `enrollorclpk`.
- SSH hacia la VM por reenvío de puertos: `ssh-windows,tcp,127.0.0.1,2223,,22` (EP-SRV-01, en el notebook, usa el 2222).
- ISO: `Windows11_Client_x64_es-mx_26300_9457` (build 26300, 8,1 GB), **no** el Enterprise de evaluación que decía la documentación.
- La sintaxis exacta quedó en el historial de PowerShell de Nicolás.

**Problema grave y su solución.** Con el hipervisor de Windows encendido, la instalación de Windows 11 dentro de VirtualBox se reiniciaba sola («reinicio inesperado») y la VM se quedaba en negro. Causa: **VBS e integridad de memoria (HVCI)**. Nicolás los apagó en el escritorio:
- integridad de memoria (HVCI) a 0 en el registro y `bcdedit /set hypervisorlaunchtype off`, con reinicio.
- Comprobado: `HypervisorPresent = False` y VBS en 0. Después la instalación terminó sin problemas.
- **Hay que revertirlo cuando terminen las pruebas con Windows:** `Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity" -Name Enabled -Value 1`, `bcdedit /set hypervisorlaunchtype auto` y reiniciar. Mientras las pruebas sigan, no revertirlo.

**Dentro de Windows.** Equipo renombrado a EP-WKS-01, usuario local `labadmin`, servidor OpenSSH instalado (con la regla de firewall en todos los perfiles y el servicio reiniciado; sin eso daba «Connection reset»).

**Agente.**
- Agente Wazuh 4.14.8 instalado con `msiexec`.
- Registrado **desde el servidor** con `manage_agents` (nombre EP-WKS-01, IP `any`) y llave importada en el agente **sin pasarla por el chat**. Quedó como agente **002**, `Active`. Hacia el manager sale por 1514/tcp.
- El MSI no se conservó, así que no se comparó su SHA512. En su lugar se comprobó la **firma digital** del ejecutable instalado: `Valid`, firmante Wazuh, Inc (DigiCert).

**Snapshots.** `base-limpia` (Windows con SSH, sin agente) y `con-agente` (con el agente registrado). Sirven para volver atrás si una prueba de scripts deja la VM sucia.

### 2.3 PR n.º 31: `kronos-bloquear-ip` (Linux) y guía 08 (tarea 3)

Rama `feat/e1-ar-bloquear-ip` hacia `develop`, 2 commits, 2 archivos, checks en verde (gitleaks, lint, pruebas unitarias, R1).

**`infra/wazuh/active-response/linux/kronos-bloquear-ip`** (Python 3, sin dependencias):
- Recibe por la entrada estándar el JSON de Active Response; los argumentos llegan en `parameters.extra_args` como `["aplicar" | "quitar", "<ip>"]`.
- Valida la IP con `ipaddress`, rechaza loopback, `0.0.0.0` y las IP del propio equipo (`hostname -I`).
- Inserta o borra `INPUT -s <ip> -m comment --comment kronos -j DROP` con `iptables` (o `ip6tables`); es **idempotente** (comprueba con `-C`).
- Registra en `/var/ossec/logs/active-responses.log`, con hora UTC.
- Instalado con `sudo install -o root -g wazuh -m 750 …/bin/kronos-bloquear-ip`; huella corta `089a23e5533dd17f`.

**`docs/instalacion/08-active-response.md`** (parte 08 de 15):
1. Cómo se conectan las piezas (EXECUTE → API de Wazuh → manager → agente → script).
2. Instalar el script en un agente Linux, probarlo a mano y tabla de comportamientos.
3. Crear el usuario de API `kronos-execute`: rol propio unido a la política de fábrica `agents_commands_agents` (sólo `active-response:command` sobre `agent:id:*`); contraseña cargada con `read -rs`, nunca en el comando.
4. Lista de comprobación.

**Advertencias de la guía:** la sección 3 está **reconstruida desde el historial y no se ejecutó de nuevo**; alguien debe seguirla paso a paso. El texto de `quitar` dice «ya estaba» aunque la regla no existiera.

### 2.4 Regeneración de la llave del agente 001 (tarea 4)

La llave anterior había quedado escrita en el chat el 15-10. `manage_agents -i` sólo **importa** una llave en el agente; **no permite fijar el ID**, así que borrar y volver a agregar con `-a` habría dejado el agente con otro ID (el 003) y los tickets y el historial dejarían de apuntar al mismo agente. Se usó la API (`POST /agents/insert`: acepta `name` obligatorio, `id`, `ip` y una `key` de exactamente 64 caracteres).

Procedimiento seguido (la llave nunca se mostró ni pasó por el chat):
1. **[servidor]** Autenticar con `wazuh-wui` (contraseña con `read -rs`) y comprobar el agente con `GET /agents?agents_list=001`.
2. **[servidor]** `manage_agents -r 001`; generar `KEY=$(openssl rand -hex 32)`; insertar con `POST /agents/insert` y cuerpo `{"name":"EP-SRV-01","ip":"any","id":"001","key":"<KEY>"}` enviado por entrada estándar (`-d @-`), mostrando de la respuesta sólo `id` y `error`.
3. **[servidor]** Extraer la llave con `manage_agents -e 001`, filtrando la línea con la llave, a un archivo en memoria (`/dev/shm`) con permisos 600 (113 bytes).
4. **[notebook]** Copiarla con `scp` en dos saltos (servidor → notebook → VM) y borrar la copia temporal del notebook.
5. **[EP-SRV-01]** `echo y | sudo /var/ossec/bin/manage_agents -i "$(cat /tmp/k001)"`, `shred -u`, `systemctl restart wazuh-agent`.
6. **[servidor]** `agent_control -l`: agentes 001 y 002 `Active`; `shred -u` del archivo en memoria; `unset TOKEN`; `history -c`.

Resultado: el agente 001 conectó con la llave nueva a las 16:49:36 UTC. Mientras el manager no tuvo al 001 (unos minutos), el agente intentó registrarse solo y su `ossec.log` mostró errores `(1208) Unable to connect to enrollment service … :1515`: es esperado y se corta al importar la llave.

La llave escrita en el chat el 15-10 ya no sirve; Nicolás la borró del gestor de contraseñas.

### 2.5 Gestor de contraseñas

- `kronos-execute`: guardada.
- `wazuh-wui`: se verificó contra la API del manager con un `read -rs` y una consulta de autenticación que sólo imprime el código HTTP (200 con la correcta, 401 con la antigua). La entrada del gestor debe guardar la que autentica. El 20-10 la vigente era la que usa el dashboard (`wazuh.yml`), no la que estaba en el gestor.

### 2.6 PR n.º 33: documentación del laboratorio

Rama `docs/lab-ep-wks-01-escritorio` hacia `develop`, 1 commit, +9 −5, sólo `docs/00-indice/KRONOS_CONTEXTO_MAESTRO.md` **del repositorio**:
- **D-16:** EP-SRV-01 en el notebook de Nicolás y EP-WKS-01 en su PC de escritorio.
- **Sección 6.4:** acceso por SSH (puertos 2222 y 2223 hacia `127.0.0.1`), especificaciones reales de EP-WKS-01 (Windows 11 ISO build 26300, 4 núcleos, 8 GB, 80 GB, TPM 2.0, EFI), estado al 21-10 y nota sobre HVCI y el hipervisor.
- **Fila de SOAR-COLLECT:** agentes 001 y 002 activos.
- No se tocaron los diagramas (siguen siendo correctos) ni la copia del contexto maestro del proyecto (versión 3.1 del 15-10): sigue desactualizada en D-16, SOAR-COLLECT y el estado del laboratorio de la sección A6. Decisión de Nicolás: dejarla como está y que este documento y el PR n.º 33 sean la referencia vigente.

## 3. Hallazgos técnicos y a quién tocan

| # | Hallazgo | Toca a |
| :-: | :--- | :--- |
| 1 | Si el agente está apagado cuando vence la reversión, EXECUTE deja `REVERSION_FALLIDA` y **no reintenta**. | Rodrigo (EXECUTE) |
| 2 | Las reglas de iptables **no persisten** tras reiniciar el agente o el equipo, y nadie las reaplica. | Rodrigo, Nicolás (scripts) |
| 3 | Una ráfaga de alertas del mismo origen creó **2 tickets**; el segundo `aplicar` y el segundo `quitar` responden «sin cambios (ya estaba)». Falta ver cómo se comporta la reversión de los tickets duplicados cuando se despliegue la agrupación. | Patricio (agrupación), Rodrigo |
| 4 | Los playbooks de nivel 0 de consulta terminan en `FAILED` con `ACCION_NO_IMPLEMENTADA` (tickets 19, 21 y 22): es lo esperado hasta que exista esa acción. | Rodrigo |
| 5 | El texto de `quitar` dice «ya estaba» aunque la regla no existiera. | Nicolás (script) |
| 6 | Regenerar la llave de un agente conservando el ID exige `POST /agents/insert`; con `manage_agents` el ID cambia. Conviene dejarlo en la guía de instalación. | Nicolás (guía) |
| 7 | Los tickets 14 a 18 (origen `10.0.50.1`, puerta de enlace NAT de VirtualBox) terminaron en revisión manual (`PLAYBOOK_FUERA_DE_CATALOGO` y un `TIEMPO_EXCEDIDO`), como se esperaba. | Patricio |
| 8 | Los tickets 1, 2 y 5 siguen `PENDING` (datos de las pruebas de integración de Patricio; EXECUTE sólo atiende el inquilino 1). | Patricio |
| 9 | Para la VM de Windows en VirtualBox hay que apagar VBS/HVCI y el hipervisor del anfitrión; no sirve con ellos encendidos. | Quien monte otra VM de Windows |

## 4. Decisiones de Nicolás en esta jornada

- EP-WKS-01 se construye en su PC de escritorio; EP-SRV-01 sigue en el notebook.
- **No** se autoriza una llave SSH propia de Rodrigo en el servidor, porque Rodrigo ya no usa el notebook de Nicolás (avísenle si la necesitan).
- La documentación del laboratorio se actualiza con el PR n.º 33 y no se reescribe la copia del proyecto.
- El HVCI y el hipervisor del escritorio se revierten **al terminar las pruebas con Windows**, no antes.

## 5. Reglas de trabajo vigentes (para los chats)

- **Nunca secretos en el chat ni en el repositorio.** Contraseñas y llaves se cargan con `read -rs` y van al gestor de contraseñas.
- Antes de comandos con `!` en Bash: `set +H`.
- Archivos hacia las VM: `scp -P 2222` (EP-SRV-01) o `scp -P 2223` (EP-WKS-01 desde el escritorio); **no** pegar scripts largos en la terminal de la VM, se corta.
- En pruebas manuales, nunca bloquear `10.0.50.1` ni la IP desde la que se está conectado por SSH.
- No tocar la configuración de Wazuh del servidor sin avisar a Nicolás.
- Ramas desde `develop`, PR hacia `develop`, **revisión cruzada antes de mezclar**: Rodrigo revisa los PR de Nicolás, Nicolás los de Patricio, Patricio los de Rodrigo.
- Commits en español, formato `tipo(ámbito): descripción`. Nicolás pidió que sus commits y PR **no lleven marcas ni coautoría de herramientas de IA**.
- Nicolás marca sus comandos como [PC escritorio], [notebook], [servidor] o [VM] (en su chat de laboratorio, [máquina Windows] y [máquina Linux]). Conviene que los demás chats indiquen en qué equipo se ejecuta cada comando.

## 6. Pendientes por persona

**Nicolás**
- Aprobación y merge de los PR n.º 31 y n.º 33.
- Probar los scripts de Windows de Rodrigo en EP-WKS-01 (aplicar y quitar), de a uno, volviendo al snapshot `con-agente` si hace falta.
- Revisar los PR de Patricio (revisión cruzada) y coordinar con él el despliegue de VALIDATE en SOAR-CORE-01.
- Probar la sección 3 de la guía 08 paso a paso y agregar a la guía el procedimiento de regeneración de llave sin cambiar el ID.
- Revertir HVCI y el hipervisor del escritorio al cerrar las pruebas con Windows.
- Restaurar la configuración de suspensión del notebook (quedó en «nunca» durante la prueba).

**Rodrigo** (lo que Nicolás le pide)
1. Revisar y aprobar los PR n.º 31 y n.º 33. En el n.º 31, mirar sobre todo la sección 3 de la guía (usuario `kronos-execute`).
2. Entregar los scripts de Windows (rama `feat/e3-ar-windows-bloquear-ip`: `kronos-bloquear-ip.cmd`, `kronos-bloquear-ip.ps1` y un README). Nicolás los prueba en EP-WKS-01; que avise si cambia algo en la rama.
3. Tener presentes los hallazgos 1, 2, 3 y 4.

**Patricio** (lo que Nicolás le pide)
1. **No desplegar VALIDATE en SOAR-CORE-01 sin coordinar con Nicolás:** VALIDATE y EXECUTE están encendidos y actúan sobre EP-SRV-01; hay que evitar cruzar el despliegue con una prueba.
2. Nicolás tiene pendiente revisar su PR de VALIDATE (rama `feat/validate-mejoras-prueba-20-10`).
3. Hay un agente Windows (el 002) para probar las reglas de sobre de Windows: que diga qué eventos necesita.
4. Tener presentes los hallazgos 3, 7 y 8.

## 7. Cómo se juntará todo

1. Cada integrante deja su avance en el proyecto con el formato `KRO-LOG-<iniciales>-<fecha>` (Nicolás: `KRO-LOG-NZ-2026-10-21_bloque_a_nicolas.md`).
2. Los tres resúmenes se traen al chat principal (**kronos maestro**) para consolidarlos.
3. Después, punto de encuentro 1 (los tres, unos 20 minutos): playbooks de un solo paso o de varios, los 60 minutos de reversión del nivel 1, medidas habilitadas en la farmacia, inquilino por grupo de agentes de Wazuh y si se parte en modo observación.

## 8. Por confirmar

- Que el revisor «TuTooH» del PR n.º 31 sea Rodrigo (si no, cambiar el revisor en GitHub).
- Número de los dos tickets de la ráfaga del 21-10 y sus eventos `REVERSION_*` (se ven en la consola; no se revisaron).

## 9. Referencias

- Repositorio `soaria186/kronos-ai`, rama `develop`. PR n.º 31 (`feat/e1-ar-bloquear-ip`) y n.º 33 (`docs/lab-ep-wks-01-escritorio`).
- Ramas vistas en el repositorio y no revisadas por Nicolás: `feat/e3-ar-windows-bloquear-ip`, `feat/e2-plazos-reversion`, `feat/e2-validate-*`, `docs/validate-permiso-secreto`, `feat/validate-mejoras-prueba-20-10`, `fix/pruebas-solo-linux`.
- Documentos del proyecto: `KRO-ESTADO-2026-10-20_ejecucion_y_plan_paralelo.md`, `KRO-LOG-PG-2026-10-20_bloque_a_patricio.md`, `KRO-LOG-NZ-2026-10-21_bloque_a_nicolas.md`, `KRONOS_CONTEXTO_MAESTRO.md` (v3.1 del 15-10, desactualizada en lo del laboratorio).
- Wazuh 4.14.8: Active Response y API (`/active-response`, `/agents/insert`, `/security/users`, `/security/roles`, `/security/policies`).
