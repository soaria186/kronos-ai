# 05 · Reglas de sobre

| Campo | Valor |
| :--- | :--- |
| Parte | 05 de 15 |
| Responsable | Nicolás Zamora (revisa: Patricio González) |
| Versión | 0.9, 26-10-2026 |
| Estado | Borrador para revisión. Las reglas se instalaron y se probaron con `wazuh-logtest` el 14-10-2026 (SSH y sudo); las de Windows, en la prueba integral |
| Requisitos | Parte 04 |

Las reglas de sobre son 15 reglas propias de Wazuh (100101 a 100115) montadas sobre reglas nativas. Cada una
etiqueta la alerta con su **familia candidata** (`kronos_f1` a `kronos_f6`, en `rule.groups`) y le da una
**severidad** (`rule.level`). SOAR-VALIDATE sólo procesa las alertas que pasaron por una de ellas, y con eso:

- comprueba que la familia que dice el modelo coincida con la de la regla (`FAMILIA_NO_COINCIDE`);
- limita el nivel de la medida según la severidad.

Archivo: `infra/wazuh/reglas/kronos_reglas_sobre.xml`.

---

## 1. Las 15 reglas

| Regla | Nivel | Familia | Sobre las nativas | Qué detecta |
| :-: | :-: | :--- | :--- | :--- |
| 100101 | 10 | F1 | 5712, 5720, 5763 | Fuerza bruta por SSH |
| 100102 | 10 | F1 | 5551, 5404 | Fallos repetidos de autenticación local (PAM o sudo) |
| 100103 | 10 | F1 | 60204, 60115 | Fallos repetidos de inicio de sesión en Windows o cuenta bloqueada |
| 100104 | 12 | F2 | 91809, 92057, 92071 | PowerShell con comando codificado en Base64 |
| 100105 | 12 | F2 | 92047, 92048, 92018, 92403, 92900 | Office lanza mshta, certutil decodifica o acceso a LSASS |
| 100106 | 10 | F2 | 92204, 92207, 92601 | Ejecutable o script en carpeta temporal o de usuario |
| 100107 | 8 | F3 | 92653, 92657 | Inicio de sesión remoto (RDP o NTLM de red) |
| 100108 | 12 | F3 | 92068, 92650, 92202, 92218, 92220, 92602, 92656 | Ejecución remota o recursos administrativos (PsExec, servicios, WinRM, Impacket) |
| 100109 | 12 | F4 | 92104 | Binario sospechoso abre una conexión de salida |
| 100110 | 7 | F5 | 550, 553, 554 | Archivo vigilado modificado, agregado o borrado |
| 100111 | 10 | F5 | 5902, 2961, 60138, 92040 | Cuenta o grupo nuevo, o usuario agregado a sudo |
| 100112 | 10 | F5 | 60228, 2832, 2833, 92301, 92303 | Persistencia programada (tarea, cron o arranque automático) |
| 100113 | 12 | F5 | 60117, 18118, 63103 | Registro de auditoría borrado |
| 100114 | 7 | F6 | 531, 1007 | Disco lleno |
| 100115 | 7 | F6 | 504, 506 | Agente de Wazuh desconectado o detenido |

Los números de las reglas nativas se verificaron en el manager el 14-10-2026. Las 92xxx salen de los eventos de
Sysmon (parte 10, sección 6).

### Severidad y nivel máximo

`validacion/configuracion/validate.json` fija qué nivel de medida permite cada severidad:

| Severidad (`rule.level`) | Nivel máximo | Reglas de sobre |
| :-: | :-: | :--- |
| 0 a 6 | 0 | — |
| 7 a 9 | 1 | 100107, 100110, 100114, 100115 |
| 10 y 11 | 2 | 100101 a 100103, 100106, 100111, 100112 |
| 12 a 15 | 3 | 100104, 100105, 100108, 100109, 100113 |

**Consecuencias que hay que conocer:**

- Las medidas de nivel 3 de F6 (PB-F6-04 y PB-F6-05) nunca se alcanzan, porque las reglas F6 tienen severidad 7.
- F4 sólo tiene una regla (100109): es la familia con menos cobertura.
- La regla 100115 (agente detenido) puede ser un atacante apagando el agente: no es siempre una falla inocente.

## 2. Instalar en el manager

```
[PC]       scp infra/wazuh/reglas/kronos_reglas_sobre.xml soar-core-01:~/
[servidor] M=single-node-wazuh.manager-1
[servidor] sudo docker cp ~/kronos_reglas_sobre.xml "$M":/var/ossec/etc/rules/kronos_reglas_sobre.xml
[servidor] sudo docker exec "$M" chown wazuh:wazuh /var/ossec/etc/rules/kronos_reglas_sobre.xml
[servidor] sudo docker exec "$M" chmod 660 /var/ossec/etc/rules/kronos_reglas_sobre.xml
[servidor] sudo docker exec "$M" /var/ossec/bin/wazuh-control restart
[servidor] rm ~/kronos_reglas_sobre.xml
```

La carpeta `/var/ossec/etc` es el volumen `wazuh_etc`: las reglas sobreviven a que se recree el contenedor.
Avisar a Nicolás antes de cambiar este archivo en el servidor.

```
[servidor] sudo docker exec "$M" sh -c 'grep -iE "error|critical" /var/ossec/logs/ossec.log | tail -n 5'
```

**Debe mostrar:** ningún error nuevo sobre `kronos_reglas_sobre.xml`.

## 3. Probar con `wazuh-logtest`

```
[servidor] sudo docker exec -it single-node-wazuh.manager-1 /var/ossec/bin/wazuh-logtest
```

Pegar **ocho veces** esta línea (la regla nativa de fuerza bruta cuenta intentos de la misma IP):

```
Oct 26 12:00:00 ep-srv-01 sshd[4242]: Failed password for invalid user prueba from 203.0.113.50 port 51234 ssh2
```

**Debe mostrar,** en la última: `id: '100101'`, `level: '10'`, `description: 'Kronos F1: fuerza bruta por SSH
desde 203.0.113.50'` y `groups: '['kronos', 'kronos_f1']'`.

Las reglas de Windows (100103 y 100113) se prueban con eventos reales del agente de Windows, en los escenarios
E3 y E4 de la parte 15.

## 4. Cambiar una regla

Las reglas son configuración versionada: se cambian por PR en `infra/wazuh/reglas/`, con la prueba de
`wazuh-logtest` en la descripción, y se instalan con la sección 2. Si cambia el nivel de una regla, hay que
revisar la tabla de severidad: cambia qué medidas puede aplicar Kronos.

## 5. Lista de comprobación

- [ ] `kronos_reglas_sobre.xml` en `/var/ossec/etc/rules/`, dueño `wazuh` y permiso 660.
- [ ] El manager reinició sin errores.
- [ ] `wazuh-logtest`: ocho intentos de SSH dan la regla 100101 con `kronos_f1`.
