# KRO-LOG-NZ-2026-10-21 · Bloque A de Nicolás (reversión, EP-WKS-01, PR del script, llave 001)

Versión del 21-10-2026, 14:00 (hora de Chile), con la reversión y la llave del agente 001 ya completadas.

## Tarea 1 · Reversión automática del bloqueo (ticket 20)
- **Primera prueba (20-10):** la reversión de las 23:36 UTC quedó como `REVERSION_FALLIDA` («agent is not active»): la VM EP-SRV-01 estaba apagada. Al reiniciar la VM las reglas de iptables se perdieron.
- **Segunda prueba (21-10): reversión correcta.** Ráfaga de alertas simuladas con `logger` desde EP-SRV-01 (15:34:39–15:34:52 UTC), con el notebook enchufado, sin suspensión y la VM encendida.
  - `aplicar 203.0.113.50: OK` a las 15:35:15Z; el segundo ticket de la ráfaga: `aplicar … sin cambios (ya estaba)` a las 15:35:26Z.
  - `quitar 203.0.113.50: OK` a las 16:35:18Z (**60 min y 3 s después**); el segundo ticket: `quitar … sin cambios (ya estaba)` a las 16:35:28Z.
  - `iptables` no muestra ninguna regla para esa IP.
  - La consola no muestra fallas nuevas a las 16:35 UTC. No se revisó el detalle de cada ticket (eventos `REVERSION_OK`).
- **Conclusión:** el camino de éxito de la reversión del nivel 1 queda confirmado. Lo que falló el 20-10 fue por el agente apagado.

## Tarea 2 · EP-WKS-01 (Windows 11) con agente Wazuh 4.14.8
- **Cambio de lugar:** EP-WKS-01 se construyó en el **PC de escritorio** y no en el notebook, porque en el notebook iba demasiado lenta. EP-SRV-01 sigue en el notebook.
- **Estado:** equipo renombrado, agente 4.14.8 instalado y registrado desde el servidor con `manage_agents` (agente 002, `Active`). La llave se importó sin pasar por el chat.
- **Snapshots en VirtualBox:** `base-limpia` (Windows con SSH, sin agente) y `con-agente` (con el agente registrado).
- **Verificación del instalador:** el MSI no se conservó en la VM, así que no se comparó su SHA512. El ejecutable instalado tiene **firma válida** (Wazuh, Inc, emitida por DigiCert, vigente hasta 12-08-2027).
- **VirtualBox en el escritorio:** para que la instalación de Windows 11 fuera estable hubo que desactivar la integridad de memoria (HVCI) y el hipervisor. **Pendiente:** revertirlo al cerrar el laboratorio.

## Tarea 3 · PR n.º 31: script `kronos-bloquear-ip` (Linux) y guía 08
- Rama `feat/e1-ar-bloquear-ip` hacia `develop`, 2 commits, 2 archivos: `infra/wazuh/active-response/linux/kronos-bloquear-ip` (huella `089a23e5533dd17f`, sin cambios respecto del instalado en EP-SRV-01) y `docs/instalacion/08-active-response.md`.
- Los 4 checks pasan (gitleaks, lint, pruebas unitarias, R1). Revisor: Rodrigo. **No se mezcla sin su aprobación.**
- La guía explica la instalación de un script de Active Response en un agente Linux y la creación del usuario de API `kronos-execute` (rol con la política de fábrica `agents_commands_agents`).
- **Advertencia:** la sección 3 (usuario de API) está reconstruida desde el historial y **no se ejecutó de nuevo**. Alguien debe seguirla paso a paso para validarla.

## Tarea 4 · Llave del agente 001 y gestor de contraseñas
- Llave SSH de Rodrigo en el servidor: **descartada** por decisión de Nicolás, porque Rodrigo ya no usa su notebook.
- Gestor: `kronos-execute` guardada; `wazuh-wui` verificada contra la API del manager (respuesta 200). La contraseña de `wazuh-wui` guardada antes no era la vigente.
- **Llave del agente 001 regenerada (21-10, hacia las 13:50 hora de Chile), conservando el ID 001.** `manage_agents -i` sólo importa una llave en el agente y no permite fijar el ID, así que se hizo con la API: `manage_agents -r 001`, luego `POST /agents/insert` con id `001`, nombre `EP-SRV-01`, IP `any` y una llave aleatoria de 64 caracteres generada con `openssl` sin mostrarla. La llave se extrajo con `manage_agents -e` a un archivo en memoria, se copió con `scp` en dos saltos (servidor, notebook, VM), se importó con `manage_agents -i` y los archivos temporales se destruyeron. La llave nunca pasó por el chat.
- **Resultado:** el agente 001 y el 002 figuran `Active` en el manager; el agente conectó con la llave nueva a las 16:49:36 UTC.
- La llave del agente 001 escrita en el chat el 15-10 ya no sirve. Falta borrar su entrada del gestor de contraseñas si la guardaste ahí.

## Tarea 5 · Documentación del laboratorio (EP-WKS-01 en el escritorio)
- **PR n.º 33** (`docs/lab-ep-wks-01-escritorio` hacia `develop`, 1 commit, +9 −5), revisor: Rodrigo. Cambia sólo `docs/00-indice/KRONOS_CONTEXTO_MAESTRO.md` del repositorio:
  - **D-16:** EP-SRV-01 en el notebook de Nicolás y EP-WKS-01 en su PC de escritorio.
  - **Sección 6.4:** acceso por SSH (puertos 2222 y 2223), especificaciones reales de EP-WKS-01 (Windows 11 ISO build 26300, 4 núcleos, 8 GB, 80 GB, TPM 2.0, EFI), estado al 21-10 y nota sobre HVCI y el hipervisor.
  - **Fila de SOAR-COLLECT:** agentes 001 y 002 activos.
- Los diagramas siguen siendo correctos. La parte del laboratorio de la guía de instalación todavía no existe en el repositorio.
- La copia del contexto maestro que está en el proyecto (versión 3.1 del 15-10) **no se actualizó**; ver pendientes.

## Hallazgos
1. **Sin reintento:** si el agente está apagado al vencer la reversión, queda `REVERSION_FALLIDA` y no se vuelve a intentar.
2. **Reglas no persistentes:** `iptables` guarda las reglas en memoria; un reinicio las borra y nadie las reaplica.
3. **Varios tickets por ráfaga:** un mismo ataque genera más de un ticket (el segundo `aplicar` responde «ya estaba»). Patricio tiene en su rama la agrupación; falta ver cómo se comporta la reversión de los tickets duplicados.
4. **Texto del script:** `quitar` sobre una regla inexistente dice «ya estaba», aunque la regla no existía.
5. **Playbooks de nivel 0:** terminan en `FAILED` con `ACCION_NO_IMPLEMENTADA`, y es lo esperado.
6. **Regenerar la llave sin cambiar el ID:** con `manage_agents` solo, el agente reinsertado habría quedado con otro ID (el 003) y los tickets y el historial dejarían de apuntar al mismo agente. Hay que usar `POST /agents/insert`. Conviene dejarlo en la guía de instalación.
7. **Mientras el manager no tiene al agente,** éste intenta registrarse solo y su `ossec.log` se llena de errores `(1208) Unable to connect to enrollment service … :1515`. Es esperado y se corta al importar la llave.

## Pendientes
- Aprobación de Rodrigo en el PR n.º 31 y merge.
- Probar la sección 3 de la guía 08 paso a paso, y agregar a la guía el procedimiento de regeneración de llave sin cambiar el ID.
- Restaurar la configuración de suspensión del notebook, que se dejó en «nunca» para la prueba.
- Pruebas en EP-WKS-01 (aplicar y quitar) de los scripts de Windows de Rodrigo (rama `feat/e3-ar-windows-bloquear-ip`).
- Revisar los PR de Patricio (revisión cruzada) y coordinar el despliegue de VALIDATE en SOAR-CORE-01.
- Revertir HVCI e hipervisor en el PC de escritorio.
- Aprobación de Rodrigo en el PR n.º 33 (documentación del laboratorio) y merge.
- Copia del contexto maestro del proyecto (versión 3.1 del 15-10): quedan por corregir D-16, la fila de SOAR-COLLECT y el estado del laboratorio de la sección A6.
