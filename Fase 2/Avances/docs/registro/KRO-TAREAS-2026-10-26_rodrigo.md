# KRO-TAREAS-2026-10-26 · Rodrigo Riveros (Scrum Master)

Semana de cierre: lunes 26-10 a domingo 01-11-2026. Generado en el chat principal «kronos maestro».

**Leer antes:**
- `KRO-PLAN-2026-10-26_replanteamiento_pyme_y_cierre.md`: replanteamiento PyME, diagnóstico del repositorio (sección 4), alcance congelado y escenarios.
- `KRO-LOG-RR-2026-10-21_bloque_a_rodrigo.md`.

## Contexto en tres líneas
- El profesor descartó la farmacia: Kronos se presenta como solución para **PyMEs sin especialista en ciberseguridad**, validada en una **PyME simulada**. El usuario principal pasa a ser el **encargado de TI generalista** de la PyME.
- **Hoy no se puede mostrar un nivel 3 ejecutado:** las medidas de nivel 3 no tienen script. Tus dos scripts nuevos completan los cuatro niveles en Windows.
- **El GitHub que verá la comisión hoy está vacío:** `main` tiene un solo commit del 06-10. Como Scrum Master, la versión 1.0.0 y el orden del repositorio quedan a tu cargo.

## Tareas, por día

| Día | Tarea | Dónde | Coordinación |
| :--- | :--- | :--- | :--- |
| **Lun 26** | **1. Servidor como clon de git (D-55), primero que todo.** Respaldo previo (base y `/opt/kronos/audit`); clon de `develop` en la ruta de despliegue; conservar `.env`, `secrets/`, `initdb/03_roles.sql` e `initdb/05_clave_consola.sql` fuera de git; `docker compose … up -d --build`; comprobar los cinco servicios. Aplicar la migración del #35 si falta. Desde aquí, desplegar es `git pull` más una etiqueta | Servidor | 📢 **Avisar en Telegram antes y después.** Patricio y tú lo necesitan para desplegar el miércoles y el jueves |
| Lun 26 | **2. Arranque (30 min):** aprobar D-57 a D-65 en el chat principal | Chat principal | 🤝 **Los tres** |
| Lun–Mar | **3. `kronos-deshabilitar-cuenta` para Windows** (`.cmd` y `.ps1`, como `kronos-bloquear-ip`): `aplicar <cuenta>` y `habilitar <cuenta>` con `net user <cuenta> /active:no` y `/active:yes`. Validar el nombre, negarse con cuentas protegidas (`Administrator`, `Administrador`, `SYSTEM` y la cuenta con la que corre el agente), ser idempotente y registrar en `active-responses.log`. EXECUTE ya saca la cuenta de `targetUserName`. PR a `develop` | PC | ✅ **Aprueba Patricio.** Entregar el archivo a Nicolás para probarlo el miércoles |
| Mar 27 | **4. EXECUTE con `.cmd` para Windows,** sólo si la prueba de Nicolás del lunes muestra que `!kronos-bloquear-ip` sin extensión no encuentra el script. Ojo: `kronos-execute` sólo tiene permiso de `active-response:command`, así que el sistema operativo del agente no se puede consultar por la API; sale de la alerta (por ejemplo `location: EventChannel`) | PC | 📥 **Depende del resultado de Nicolás.** ✅ PR, aprueba Patricio |
| Mar–Mié | **5. `kronos-aislar-equipo` para Windows:** `aplicar` guarda la política actual del firewall (`netsh advfirewall export`), bloquea toda la entrada y la salida, y **deja permitida la salida TCP 1514 hacia el manager** (dirección tomada del `ossec.conf` del agente; DNS si es un nombre). `quitar` restaura la política guardada. Si el agente pierde el canal con el manager, la reversión no llega: es lo primero que hay que probar | PC | ✅ PR, **aprueba Patricio.** Nicolás lo prueba en EP-WKS-01 |
| **Mié 28** | **6. Avisos en lenguaje claro para el encargado de TI** (`notificacion/mensajes.py`): nombre de la medida del catálogo en vez de «PB-F5-04», equipo afectado, qué pasó, qué hizo Kronos y qué tiene que hacer la persona. Quitar «D-35» y mostrar el nombre de la PyME en vez de «Inquilino 1». Más **D-50: no avisar los `FAILED` de nivel 0 sin comando**. Con pruebas | PC | ✅ PR, **aprueba Patricio** |
| **Jue 29** | **7. Desplegar la versión candidata** por la mañana (`git pull`, etiqueta `v1.0.0-rc1`) con todo lo mezclado hasta el miércoles. Comprobar los servicios | Servidor | 📢 Avisar en Telegram. Patricio despliega antes el cortacircuito (miércoles): **uno a la vez** |
| Jue 29 | **8. Prueba integral (punto de encuentro 2):** mirar EXECUTE, NOTIFY y la consola, incluidos **los botones de aprobación del nivel 3 en Telegram (E4)** y la reversión desde la consola (E2) | Servidor y Telegram | 🤝 **Los tres, 2 a 3 h** |
| **Vie 30** | **9. Correcciones** de lo que falle en la prueba integral | PC | ✅ PR, aprueba Patricio |
| Vie 30 | **10. Manual del encargado de TI** (6 a 8 páginas, con el asistente de IA y capturas del jueves): qué es Kronos, qué significa cada nivel, cómo leer un aviso, cómo aprobar o rechazar, cómo revertir en la consola, qué hacer ante una reversión fallida o un cortacircuito abierto, y cómo avisar a la persona afectada | PC | — |
| Vie 30 | **11. Tus documentos de los 31:** 1.5, 1.6, 1.8 y 1.9 (gestión), 2.5, 3.1, 4.2, 5.3, 5.4, 5.5 y 6.3. Reemplazar la farmacia y resolver las marcas. En 4.2 y 1.8, el aprobador del nivel 3 pasa a ser el encargado de TI (D-59) | PC | ✅ **Revisa Patricio** |
| Vie 30 | **12. Tus secciones del informe final:** desarrollo de persistencia, ejecución, notificación y consola; respaldo y retención | PC | 📤 A Patricio, que integra |
| Vie 30 | **13. Guía de instalación, partes 07, 11 y 12** (servicios, Telegram, respaldo y retención), desde los README que ya existen. Incluir el despliegue con clon de git | PC | ✅ PR, **aprueba Patricio** |
| **Sáb 31** | **14. Versión 1.0.0:** PR `develop` → `main` («Versión 1.0.0, entrega final»), mezcla con commit de merge (sin aplastar el historial), etiqueta `v1.0.0` y notas de la versión en GitHub | GitHub | ✅ **Aprueban Nicolás y Patricio**. Tú no lo mezclas sin las dos aprobaciones |
| Sáb 31 | **15. Orden del repositorio** (detalle abajo de la tabla) | GitHub | 📥 Los PDF de cada uno el viernes en la noche; las ramas de experimentos, con Patricio |
| Sáb 31 | **16. Revisión cruzada** de los documentos de Nicolás y primer ensayo de la presentación | — | 🤝 **Los tres, 2 h** |
| **Dom 01** | **17.** Pedirle a tu chat un `KRO-LOG-RR-2026-11-01_cierre_semana.md` y traerlo al chat principal | — | — |
| *Si sobra tiempo* | Dependencias de la consola en el CI, para que no se omitan sus 13 pruebas. Desconectar Ollama de la red `salida` y anotarlo en el modelo de amenazas | PC y servidor | Lo de Ollama, avisarlo a Nicolás |

### Detalle de la tarea 15: orden del repositorio
- Borrar las 37 ramas ya mezcladas (todas menos `main`, `develop` y las 4 de experimentos).
- Archivar las 4 ramas de experimentos como etiquetas, con Patricio.
- Subir a `docs/registro/` todos los KRO-LOG, KRO-REV, KRO-ACTA, KRO-TAREAS y KRO-PLAN del proyecto.
- Mover a `docs/archivo/` los 17 Word v0.1, el contexto maestro v2.1, `pendientes-farmacia.md` y `preguntas-abiertas.md`.
- Publicar los 31 documentos en PDF en `docs/entregables/`, con su índice.
- Corregir en `CONTRIBUTING.md` el rol del Product Owner (ya no es el contacto con la farmacia).
- Crear el milestone «v1.0», con las tareas de la semana como issues cerradas.
- Poner la descripción y los temas del repositorio.

## Revisiones que te tocan (regla D-54)
- **Apruebas** los PR de **Nicolás**: README y guía (martes y miércoles), correcciones al script Linux y documentos. El mismo día.
- **Tus PR los aprueba Patricio.**
- **Como Scrum Master:**
  - cero PR mezclados sin aprobación esta semana;
  - recordar el avance diario por WhatsApp (tres líneas);
  - si un PR espera más de 12 horas, avisar.

## Cuidado
- Un solo despliegue a la vez y siempre avisado en Telegram. Desde el lunes no se copian archivos desde Windows al servidor.
- No convertir el grupo de Telegram en supergrupo y no abrir `getUpdates` en el navegador.
- Nada de secretos en el chat ni en el repositorio. Antes de publicar la versión, gitleaks en verde.
- Ninguna herramienta de IA figura como colaborador ni coautor en tus commits ni en tus PR.

## Terminado significa
- Servidor desplegado desde un clon de git, con la etiqueta `v1.0.0-rc1` el jueves.
- `kronos-deshabilitar-cuenta` y `kronos-aislar-equipo` mezclados y probados por Nicolás.
- Avisos en lenguaje claro y D-50 desplegados.
- E2 y E4 mostrados en la prueba integral.
- Manual del encargado de TI, tus 11 documentos y las partes 07, 11 y 12 de la guía listos.
- `main` con la v1.0.0, sus notas y el repositorio ordenado.

## Puntos de la lista de corrección del GitHub que te tocan
Detalle en `KRO-CHECKLIST-2026-10-26_github_100.md`. Muchos son ediciones cortas; conviene adelantar los README y el `.env.example` al miércoles, junto con D3 y D4, para no cargar el sábado:
- **Portada y ramas:** A1, A2, A4, A7, B1, B3, B4 y B5.
- **Documentación:** C1, C2, C3, C5 (`docs/`, `infra/` y `tools/`) y C6, quitando los identificadores de Telegram de tu registro del 21-10.
- **Diagramas (C8):** `09_despliegue`, `19_respaldo`, `14_flujo_ci`, `05_ramas` y el README de diagramas.
- **Textos pendientes (C9):** `ejecucion/`, `windows/`, `notificacion/`, `retencion/`, `persistencia/`, `consola/` y `CONTRIBUTING.md`.
- **Coherencia:** D3, D4, D6 y D9.
- **Proceso, seguridad y CI:** E1 a E4, F2 a F4 y G1 a G4.
