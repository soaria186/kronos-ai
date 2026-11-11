# 05 · Reglas de sobre

| Campo | Valor |
| :--- | :--- |
| Parte | 05 de 15 |
| Responsable | Nicolás Zamora (revisa: Patricio González) |
| Versión | 1.0, 11-11-2026 |
| Estado | Vigente. Las 28 reglas están instaladas en el manager y probadas con alertas reales en la prueba integral 2 y en los escenarios por familia (10 y 11-11-2026) |
| Requisitos | Parte 04. Para las reglas que leen Sysmon y auditd: partes 09 y 10 |

Las reglas de sobre son reglas propias de Wazuh montadas sobre reglas nativas. Cada una etiqueta la alerta con su
**familia candidata** (`kronos_f1` a `kronos_f6`, en `rule.groups`) y le da una **severidad** (`rule.level`).
SOAR-VALIDATE sólo procesa las alertas que pasaron por una de ellas, y con eso:

- comprueba que la familia que dice el modelo coincida con la de la regla (`FAMILIA_NO_COINCIDE`);
- limita el nivel de la medida según la severidad (sección 2).

Archivo: `Fase 2/Avances/infra/wazuh/reglas/kronos_reglas_sobre.xml`. Son **28 reglas**: 26 que generan alertas
para Kronos y 2 que descartan casos conocidos (nivel 0).

---

## 1. Las reglas, por familia

La columna «Playbooks demostrados» indica qué medidas eligió Kronos con alertas reales de esa regla, con el ticket
de evidencia. La IA elige el playbook dentro de la familia; la regla no lo fija.

### F1 · Abuso de credenciales

| Regla | Severidad | Sobre las nativas | Qué detecta | Playbooks demostrados |
| :-: | :-: | :--- | :--- | :--- |
| 100101 | 10 | 5712, 5720, 5763 | Fuerza bruta por SSH | PB-F1-02 desde internet (#83, #128); PB-F1-03 desde un equipo interno (#150) |
| 100102 | 10 | 5551, 5404 | Fallos repetidos de autenticación local (PAM o sudo) | PB-F1-01 (#90) |
| 100103 | 10 | 60204, 60115 | Fallos repetidos de inicio de sesión en Windows o cuenta bloqueada | PB-F1-05 (#149); PB-F1-01 (#84) |
| 100116 | 10 | 5715 tras 5 de la 5760 | Inicio de sesión correcto después de varios fallos desde el mismo origen (4 minutos) | PB-F1-04 (#157) |

### F2 · Proceso sospechoso en ejecución

| Regla | Severidad | Sobre las nativas | Qué detecta | Playbooks demostrados |
| :-: | :-: | :--- | :--- | :--- |
| 100104 | 12 | 91809, 92057, 92071 | PowerShell con comando codificado en Base64 | PB-F2-03 (#131); PB-F2-01 (#109) |
| 100105 | 12 | 92047, 92048, 92018, 92403, 92900 | Office lanza mshta, certutil decodifica o acceso a LSASS | — |
| 100106 | 10 | 92204, 92207, 92601 | Ejecutable o script en carpeta temporal o de usuario | PB-F2-02 (#153); PB-F2-03 (#152); PB-F2-01 (#110) |

### F3 · Movimiento lateral y acceso remoto

| Regla | Severidad | Sobre las nativas | Qué detecta | Playbooks demostrados |
| :-: | :-: | :--- | :--- | :--- |
| 100107 | 10 | 92652, 92653, 92657 | Inicio de sesión remoto en Windows (RDP o NTLM de red) | PB-F3-01 desde internet (#188); PB-F3-02 desde un equipo interno (#192) |
| 100108 | 12 | 92068, 92650, 92202, 92218, 92220, 92602, 92656 | Ejecución remota o recursos administrativos (PsExec, servicios, WinRM, Impacket) | PB-F3-03: sin demostración de punta a punta (limitación de la v1.0.0) |
| 100125 | 10 | 5715 desde 10.0.0.0/8 | Acceso por SSH desde otro equipo de la red interna | PB-F3-02 en Linux (#193) |
| 100126 | 0 | Hija de la 100125 | **Descarta** el SSH desde el equipo de administración del laboratorio (10.0.50.1) | — |
| 100127 | 12 | 5402 tras una 100125 (10 min) | `sudo` a root después de un SSH desde otro equipo interno | Revisión manual: el modelo la clasifica como F1 (#194, #196, #198) |
| 100128 | 12 | 80700 con la clave `kronos_salto_ssh` | El servidor se conecta por SSH a otro equipo interno (salto entre equipos) | PB-F3-04 (#199) |

### F4 · Salida anómala

| Regla | Severidad | Sobre las nativas | Qué detecta | Playbooks demostrados |
| :-: | :-: | :--- | :--- | :--- |
| 100109 | 12 | 92104 | Binario con carácter RLO en el nombre abre una conexión de salida | PB-F4-02 (#161) |
| 100117 | 12 | Grupo `sysmon_event3` | Un programa en `Users\Public`, `Downloads` o `AppData\Local\Temp` conecta hacia un destino externo | PB-F4-01 (#119) |
| 100124 | 12 | 80700 con la clave `kronos_salida` | Una herramienta de transferencia del servidor abre una conexión hacia fuera | PB-F4-03 (#180) |

### F5 · Integridad y persistencia

| Regla | Severidad | Sobre las nativas | Qué detecta | Playbooks demostrados |
| :-: | :-: | :--- | :--- | :--- |
| 100110 | 7 | 550, 553, 554 | Archivo vigilado modificado, agregado o borrado | PB-F5-02 en Linux, `/etc/cron.d` (#102); PB-F5-01, carpeta Inicio de Windows (#139) |
| 100121 | 12 | Hija de la 100110, ruta `/var/www/` | Archivo de una aplicación publicada modificado o agregado | PB-F5-03 (#122) |
| 100111 | 10 | 5902, 2961, 60138, 92040 | Cuenta o grupo nuevo, o usuario agregado a sudo | Frenada por severidad: la IA propuso aislar (#91) |
| 100112 | 10 | 60228, 2832, 2833, 92301, 92303 | Persistencia programada (tarea, cron o arranque automático) | PB-F5-02 en Windows (#108) |
| 100122 | 0 | Hija de la 100112 | **Descarta** las tareas propias de Windows (`\Microsoft\`, `\SoftLanding\` y las de OneDrive por usuario) | — |
| 100113 | 12 | 60117, 18118, 63103, 592, 593 | Registro de auditoría borrado o vaciado | PB-F5-04 en un puesto (#86); PB-F5-05 en un servidor (#165) |

### F6 · Disponibilidad del servicio

| Regla | Severidad | Sobre las nativas | Qué detecta | Playbooks demostrados |
| :-: | :-: | :--- | :--- | :--- |
| 100114 | 7 | 531, 1007 | Disco lleno | — |
| 100115 | 7 | 504, 506 | Agente de Wazuh desconectado o detenido | PB-F6-01 (#88, #89) |
| 100118 | 12 | 31151 | Inundación de peticiones contra el servicio web desde una misma IP | PB-F6-02 desde internet (#130); PB-F6-03 desde un equipo interno (#163); PB-F6-04 (#166) |
| 100119 | 12 | 31152, 31153, 31154 | Ataques repetidos contra el servicio web desde una misma IP | Revisión manual: el modelo la clasifica como F4 (#138, #151) |
| 100123 | 12 | 31106 | Un ataque contra el servicio web obtuvo respuesta 200 (servicio comprometido) | Revisión manual: el modelo la clasifica como F4 (#164) |
| 100120 | 12 | 61107 (evento 7031) | Un servicio de Windows terminó de forma inesperada | PB-F6-05 (#132) |

Los números de las reglas nativas corresponden a Wazuh 4.14.8 y se verificaron en el manager. Las 92xxx salen de
Sysmon y las 80700 de auditd: sin la configuración de las partes 09 y 10, esas reglas no se activan nunca.

### Reglas que dependen de la configuración de cada equipo

| Regla | Qué necesita en el agente | Parte |
| :-: | :--- | :-: |
| 100104 a 100109, 100117 | Sysmon con su canal en `ossec.conf` | 10 |
| 100112 (Windows) | Auditoría de «Otros eventos de acceso a objetos» (evento 4698) | 10 |
| 100110 (Inicio) y 100121 | Integridad de archivos sobre la carpeta Inicio de Windows y sobre `/var/www` | 09 y 10 |
| 100124 | auditd con `-a always,exit -F arch=b64 -S connect -F exe=/usr/bin/curl -k kronos_salida` | 09 |
| 100128 | auditd con `-w /usr/bin/ssh -p x -k kronos_salto_ssh` | 09 |
| 100118, 100119, 100123 | El registro de acceso del servidor web leído por el agente | 09 |

## 2. Severidad y nivel máximo

`Fase 2/Avances/validacion/configuracion/validate.json` fija qué nivel de medida permite cada severidad:

| Severidad (`rule.level`) | Nivel máximo | Reglas de sobre |
| :-: | :-: | :--- |
| 0 | — | 100122 y 100126: descartan, no generan alerta |
| 1 a 6 | 0 | — |
| 7 a 9 | 1 | 100110, 100114, 100115 |
| 10 y 11 | 2 | 100101 a 100103, 100106, 100107, 100111, 100112, 100116, 100125 |
| 12 a 15 | 3 | 100104, 100105, 100108, 100109, 100113, 100117 a 100121, 100123, 100124, 100127, 100128 |

Desde el 11-11-2026, el paso 2 de la IA ya no recibe las medidas de un nivel mayor al que permite la severidad (si
en la familia queda otra permitida). El chequeo de severidad de VALIDATE se mantiene como segunda barrera.

**Lo que hay que conocer:**

- Las medidas de nivel 3 de F6 (PB-F6-04 y PB-F6-05) se alcanzan con las reglas 100118 a 100120 (severidad 12).
- La 100110 tiene severidad 7, pero su hija 100121 (aplicación web) sube a 12: un cambio en `/var/www` puede pedir
  aprobación.
- La 100115 (agente detenido) puede ser un atacante apagando el agente. Apagar o trasladar una máquina virtual
  también la dispara: es esperable.
- Los dos descartes son límites conocidos: un atacante podría esconder una tarea en `\Microsoft\` o
  `\SoftLanding\`, o entrar desde el equipo de administración.

## 3. Instalar en el manager

Las reglas se instalan desde el clon del servidor, después de desplegar la versión (parte 07). Avisar en el grupo
de Telegram antes de tocar el manager.

```
[servidor] M=single-node-wazuh.manager-1
[servidor] R="/opt/kronos/kronos-ai/Fase 2/Avances/infra/wazuh/reglas/kronos_reglas_sobre.xml"
[servidor] sudo docker cp "$R" "$M":/var/ossec/etc/rules/kronos_reglas_sobre.xml
[servidor] sudo docker exec "$M" chown wazuh:wazuh /var/ossec/etc/rules/kronos_reglas_sobre.xml
[servidor] sudo docker exec "$M" chmod 660 /var/ossec/etc/rules/kronos_reglas_sobre.xml
[servidor] sudo docker exec "$M" /var/ossec/bin/wazuh-control restart
```

La carpeta `/var/ossec/etc` es el volumen `wazuh_etc`: las reglas sobreviven a que se recree el contenedor.

```
[servidor] sudo docker exec "$M" sh -c 'grep -iE "error|critical" /var/ossec/logs/ossec.log | tail -n 5'
[servidor] sudo docker exec "$M" grep -c '<rule id=' /var/ossec/etc/rules/kronos_reglas_sobre.xml
```

**Debe mostrar:** ningún error nuevo sobre `kronos_reglas_sobre.xml`, y `28`.

En el manager no debe quedar ningún otro archivo de reglas de prueba. Si existe `kronos_prueba_correlacion.xml`
(se usó con `wazuh-logtest` el 10-11-2026), se borra antes del reinicio:

```
[servidor] sudo docker exec "$M" rm -f /var/ossec/etc/rules/kronos_prueba_correlacion.xml
```

## 4. Probar con `wazuh-logtest`

```
[servidor] sudo docker exec -it single-node-wazuh.manager-1 /var/ossec/bin/wazuh-logtest
```

**Fuerza bruta (100101).** Pegar **ocho veces** esta línea (la regla nativa cuenta intentos de la misma IP):

```
Oct 26 12:00:00 ep-srv-01 sshd[4242]: Failed password for invalid user prueba from 203.0.113.50 port 51234 ssh2
```

**Debe mostrar,** en la última: `id: '100101'`, `level: '10'`, `description: 'Kronos F1: fuerza bruta por SSH
desde 203.0.113.50'` y `kronos_f1` entre los grupos.

**SSH desde otro equipo interno (100125).** En una sesión nueva de `wazuh-logtest`, una sola vez:

```
Nov 11 12:00:00 ep-srv-01 sshd[4243]: Accepted password for labadmin from 10.0.50.4 port 51235 ssh2
```

**Debe mostrar:** `id: '100125'`, `level: '10'` y `kronos_f3` entre los grupos. Con `10.0.50.1` en lugar de
`10.0.50.4` debe salir la 100126, con nivel 0.

Las reglas de Windows, Sysmon y auditd se prueban con eventos reales de los agentes, en los escenarios de la
parte 15. Para ver qué regla tomó cada ticket:

```
[servidor] sudo docker exec -i kronos-db-1 psql -U kronos_admin -d kronos -c "SELECT t.id, a.alerta->'rule'->>'id' AS regla, t.playbook, t.execution_status, t.rechazo_motivo FROM tickets t JOIN alertas_guardadas a ON a.ticket_id = t.id ORDER BY t.id DESC LIMIT 10"
```

## 5. Cambiar una regla

Las reglas son configuración versionada: se cambian por PR en `infra/wazuh/reglas/`, con la prueba de
`wazuh-logtest` en la descripción, y se instalan con la sección 3 después de desplegar. Si cambia la severidad de
una regla, cambia qué medidas puede aplicar Kronos: hay que revisar la tabla de la sección 2 y la prueba
`test_niveles_que_permite_cada_regla_de_sobre` (`tests/unit/test_configuracion.py`).

Lo aprendido en la prueba integral 2:

- El texto de la descripción llega a la IA. Palabras como «salida» la llevaron a clasificar como F4 un salto por
  SSH; con «salto entre equipos» lo clasifica como F3 (regla 100128).
- Una regla hija (100121, 100122, 100126) se evalúa después de la madre y la reemplaza: así se afina una regla sin
  tocar la nativa.
- En las reglas, la ruta de integridad de archivos se llama `file`, no `syscheck.path`.

## 6. Lista de comprobación

- [ ] `kronos_reglas_sobre.xml` en `/var/ossec/etc/rules/`, dueño `wazuh`, permiso 660 y 28 reglas.
- [ ] Sin `kronos_prueba_correlacion.xml` en el manager.
- [ ] El manager reinició sin errores.
- [ ] `wazuh-logtest`: ocho intentos de SSH dan la 100101 con `kronos_f1`.
- [ ] `wazuh-logtest`: un SSH aceptado desde 10.0.50.4 da la 100125 con `kronos_f3`.
- [ ] Sysmon, auditd e integridad de archivos configurados en los agentes (partes 09 y 10).
