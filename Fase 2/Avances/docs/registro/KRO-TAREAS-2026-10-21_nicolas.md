# KRO-TAREAS-2026-10-21 · Nicolás Zamora (Product Owner)

Tareas hacia la instalación del primer agente en la farmacia. Generado en el chat principal «kronos maestro» el 21-10-2026 a las 18:45.
**Leer antes:**
- `KRO-ACTA-2026-10-21_punto_de_encuentro_1.md` (decisiones D-44 a D-56);
- `KRO-ESTADO-2026-10-21_avance_nicolas_para_los_chats.md`;
- `KRO-LOG-RR-2026-10-21_bloque_a_rodrigo.md`.

## Estado de partida (21-10)
- **Agentes:** 001 (EP-SRV-01, notebook, Ubuntu) y 002 (EP-WKS-01, PC de escritorio, Windows 11) están `Active`.
- **Servicios en SOAR-CORE-01:** VALIDATE, EXECUTE, NOTIFY (los 3 en Telegram, con 2FA) y consola. Retención de alertas (#34) desplegada.
- **Probado de punta a punta en Linux:** nivel 1, bloqueo de la IP y reversión a los 60 min.
- **PR #31, #32, #33 y #34:** mezclados sin revisión (excepción R-04).
- **PR #35** (recuperador de tickets huérfanos, Rodrigo): abierto.
- **PR de VALIDATE de Patricio:** la rama existe, pero el PR no está abierto.

## Tareas, por prioridad

| # | Tarea | Dónde | Coordinación |
| :-: | :--- | :--- | :--- |
| 1 | **Probar `kronos-bloquear-ip` de Windows** (`infra/wazuh/active-response/windows/`) en EP-WKS-01: desde el snapshot `con-agente`, copiar con `scp -P 2223`, aplicar y quitar a mano, y después por la API con `kronos-execute`. **Confirmar si `!kronos-bloquear-ip` sin extensión encuentra el `.cmd`.** Comprobar la regla `Kronos-bloqueo-<ip>` y el `active-responses.log`. | PC escritorio + EP-WKS-01 + servidor | ⚠️ **Avisar a Rodrigo el resultado**: si no encuentra el `.cmd`, él ajusta EXECUTE. **RUTA CRÍTICA** |
| 2 | **Revisar el PR de VALIDATE de Patricio** cuando lo abra: agrupación (ventana de 10 min), nota de ámbito de IP en el paso 2, plazo de 120 s, exclusión de `10.0.50.1` y pruebas solo en `kronos_pruebas`. Aprobar desde tu cuenta personal. | GitHub | ✅ **Patricio necesita tu aprobación** para mezclar |
| 3 | **Desplegar VALIDATE** en el servidor después del merge. Comprobar `ollama ps` («Forever»), que el log diga «cargando el modelo» y «agrupada», y repetir la ráfaga de `logger` para confirmar que sale **un solo** ticket. | servidor + EP-SRV-01 | 🤝 **Juntos con Patricio.** Avisar en Telegram antes. Uno a la vez con el despliegue del #35 |
| 4 | **PR de correcciones al script Linux** (revisión de Rodrigo): rechazar la puerta de enlace (`ip -j route show default`), exigir exactamente 2 argumentos, corregir el texto de `quitar` y, opcional, rechazar multicast, enlace local y difusión. En la guía 08: regeneración de llave sin cambiar el ID (`POST /agents/insert`), JSON seguro para la clave y probar la sección 3 paso a paso. Actualizar el script en EP-SRV-01. | PC escritorio + EP-SRV-01 | ✅ **Necesita la aprobación de Rodrigo** |
| 5 | **Grupo `farmacia` en Wazuh** (inquilino 2, decisión D-49) y un grupo para el laboratorio. Coordinar el número de inquilino con Patricio. | servidor | 🤝 **Con Patricio** (él lo usa en VALIDATE) |
| 6 | **Probar en EP-WKS-01 cada script de Windows nuevo** que entregue Rodrigo (aplicar y revertir), de a uno, volviendo al snapshot si queda sucio. | PC escritorio + EP-WKS-01 | 🔁 Depende de las entregas de Rodrigo |
| 7 | **Copia del respaldo fuera del servidor** (D-26, a tu PC de escritorio por NetBird, cifrada) y prueba de restauración desde ahí. | PC escritorio + servidor | — |
| 8 | **Con la farmacia (Product Owner):** inventario (equipo, sistema operativo, IP y función), **lista de exclusión con la puerta de enlace** y los equipos críticos, redes internas, que el firewall deje salir el 1514, fecha, contacto y elegir el **primer equipo, el menos crítico** (no la caja). | farmacia | 📤 **Entregar a Patricio** las redes y exclusiones para `validate.json` |
| 9 | **Plan de desinstalación** del agente (menos de 10 min) y texto del correo a la persona afectada (D-35). | PC | 🤝 **Con Rodrigo** |
| 10 | **Registrar los agentes de la farmacia** desde el servidor, en el grupo `farmacia`, sin pasar la llave por el chat. | servidor | Después de la prueba integral |
| 11 | **Instalar el primer agente** en la farmacia (4.14.8, `apt-mark hold` o equivalente en Windows, y los scripts `kronos-*`) y comprobar que queda `Active`. | farmacia | 🤝 **Los tres**, después de la lista de «sí o no» |
| 12 | Al terminar las pruebas con Windows: **revertir HVCI y el hipervisor** del escritorio. Restaurar la suspensión del notebook. | PC escritorio, notebook | — |

## Tareas en conjunto (los tres)
- **Punto de encuentro 2: prueba integral en el laboratorio** (unas 2 h). Niveles 1, 2 y 3, reversión, vencimiento del nivel 3, botones de Telegram y modo observación. **Fecha por definir**, en cuanto estén desplegados VALIDATE y el #35. **Tú generas los ataques en las VM.**
- **Lista de «sí o no»** el día antes de la farmacia (8 puntos, en el chat principal).
- **Acuerdo de datos con el proveedor del servidor (BR-05):** cerrarlo o fijar postura antes de la farmacia.

## Lo que otros esperan de ti
| Quién | Qué |
| :--- | :--- |
| Rodrigo | El resultado de la tarea 1 (`.cmd` sin extensión) y probar sus scripts de Windows |
| Patricio | Tu aprobación de su PR (tarea 2), el despliegue conjunto (tarea 3), el número del grupo e inquilino (tarea 5) y los datos de la farmacia (tarea 8) |

## Reglas
- Nunca claves en el chat: `read -rs`. Usa `set +H` antes de comandos con `!`. Copia archivos a las VM con `scp -P 2222` (EP-SRV-01) o `-P 2223` (EP-WKS-01).
- Nunca bloquear `10.0.50.1` ni tu IP de SSH.
- **Regla de merge (D-54):** nadie mezcla desde `soarai2026`, nunca mezcla el autor y siempre hay una aprobación previa desde la cuenta personal.
- Avisar en Telegram antes de tocar el servidor.
- Tus commits y PR van sin marcas ni coautoría de herramientas de IA.

## Al terminar
Pide a tu chat un `KRO-LOG-NZ-<fecha>_<tema>.md` con:
- tareas hechas y no hechas;
- evidencias (horas UTC, números de ticket, PR);
- hallazgos;
- lo que necesitas de los otros.

Súbelo al proyecto y tráelo al chat principal «kronos maestro».
