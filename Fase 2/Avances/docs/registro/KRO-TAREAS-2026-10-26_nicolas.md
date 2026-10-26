# KRO-TAREAS-2026-10-26 · Nicolás Zamora (Product Owner)

Semana de cierre: lunes 26-10 a domingo 01-11-2026. Generado en el chat principal «kronos maestro».

**Leer antes:**
- `KRO-PLAN-2026-10-26_replanteamiento_pyme_y_cierre.md`: replanteamiento PyME, diagnóstico, alcance congelado y escenarios.
- `KRO-ACTA-2026-10-21_punto_de_encuentro_1.md`.

## Contexto en tres líneas
- El profesor descartó la farmacia: Kronos se presenta como solución para **PyMEs sin especialista en ciberseguridad**, validada en una **PyME simulada** (EP-WKS-01 y EP-SRV-01).
- El producto ya funciona de punta a punta en Linux. Falta mostrar los niveles 2 y 3 en Windows, dejar el GitHub presentable y tener la documentación sin la farmacia.
- **Tu rol esta semana:** la parte del laboratorio que nadie más puede hacer, la narrativa (README, presentación y acta) y la guía de instalación de la infraestructura. Hoy tu trabajo casi no se ve en GitHub (5 commits), y esto lo corrige.

## Tareas, por día

| Día | Tarea | Dónde | Coordinación |
| :--- | :--- | :--- | :--- |
| **Lun 26** | **1. Probar `kronos-bloquear-ip` de Windows** (`infra/wazuh/active-response/windows/`, PR #32): partir del snapshot `con-agente`, copiar el `.cmd` y el `.ps1` con `scp -P 2223` a `active-response\bin` del agente, probar aplicar y quitar a mano (README de esa carpeta) y luego por la API con `kronos-execute` (`set +H`), enviando `!kronos-bloquear-ip` **sin extensión** al agente 002. Comprobar la regla `Kronos-bloqueo-203.0.113.50` en el firewall y el `active-responses.log`. Si no encuentra el script, probar con `!kronos-bloquear-ip.cmd` | PC escritorio, EP-WKS-01 y servidor | ⚠️ **Avisar el resultado a Rodrigo el mismo lunes**: él decide si EXECUTE debe agregar `.cmd`. **RUTA CRÍTICA** |
| Lun 26 | **2. Preparar EP-WKS-01 para E3 y E4:** revisar que se registren los inicios de sesión fallidos (`auditpol /get /subcategory:"Logon"`; activar «Failure» si no está) y crear una **cuenta local de prueba** (por ejemplo `usuario.demo`, nunca `labadmin` ni `Administrator`). Tomar el snapshot `listo-demo` | EP-WKS-01 | — |
| Lun 26 | **3. Confirmar con el profesor guía** el nuevo alcance (PyME simulada, escenarios, encargado de TI como aprobador) y pedirle la **guía y la rúbrica de la Fase 3** y la fecha exacta de la comisión. Subirlas al proyecto | Correo o reunión | Avisar a los dos lo que diga |
| Lun 26 | **4. Arranque (30 min):** aprobar D-57 a D-65 en el chat principal | Chat principal | 🤝 **Los tres** |
| **Mar 27** | **5. README completo** (con el asistente de IA): problema, solución, usuario, arquitectura (diagramas de `docs/diagramas/`), componentes, estado, cómo instalar (enlace a la guía), cómo correr las pruebas, equipo y **resumen en inglés**. PR a `develop` | PC escritorio | ✅ **Aprueba Rodrigo** |
| Mar 27 | **6. Guía de instalación, partes 01 a 05:** servidor y endurecimiento, NetBird, Docker, Wazuh y reglas de sobre, desde tu historial y los registros. Sin IP reales, claves ni usuarios | PC escritorio | ✅ PR, **aprueba Rodrigo** |
| Mar 27 | **7. Correcciones al script Linux** (revisión de Rodrigo al #31): rechazar la puerta de enlace (`ip -j route show default`), exigir exactamente 2 argumentos y corregir el texto de `quitar` cuando la regla no existía. Instalar la versión nueva en EP-SRV-01 | PC escritorio y EP-SRV-01 | ✅ PR, **aprueba Rodrigo** |
| **Mié 28** | **8. Probar los scripts nuevos de Rodrigo** en EP-WKS-01: `kronos-deshabilitar-cuenta` (con `usuario.demo`) y `kronos-aislar-equipo`. Aplicar y revertir a mano y por la API. **En el aislamiento, comprobar que el agente 002 sigue `Active`**: si no, la reversión no llega. Volver a `listo-demo` si algo queda sucio | PC escritorio y EP-WKS-01 | 📥 Depende de las entregas de Rodrigo (mar y mié). Reportarle cada resultado |
| Mié 28 | **9. Generar las alertas** de la prueba de estrés y de la ráfaga de Patricio (`logger` en EP-SRV-01, según su guion) | Notebook y EP-SRV-01 | 🤝 **Con Patricio, 1 h** |
| Mié 28 | **10. Guía, partes 09, 10, 13 y 14:** agente Linux, agente Windows, alta de una PyME (con Patricio) y retiro o desinstalación | PC escritorio | ✅ PR, **aprueba Rodrigo** |
| **Jue 29** | **11. Prueba integral (punto de encuentro 2):** generar los escenarios E1 a E7 del plan, en orden, y **capturar la evidencia** (Telegram, consola, registros y bitácora). Notebook enchufado y sin suspensión | Notebook, PC escritorio y VM | 🤝 **Los tres, 2 a 3 h** |
| **Vie 30** | **12. Video de respaldo de la demo** (E1, E2, E3 y E4, de 3 a 5 min), por si el servidor o la red fallan el día de la defensa | PC escritorio | — |
| Vie 30 | **13. Presentación, borrador** (con el asistente de IA): problema PyME, solución, demostración, arquitectura, resultados y aprendizajes. Una parte para cada uno | PC | 📥 Cada uno revisa su parte |
| Vie 30 | **14. Tus documentos de los 31:** 1.1 FODA y PESTEL (**reescribir para PyMEs**), 1.2, 2.1 (**AS-IS de una PyME sin especialista**), 2.7, 3.2, 5.1, 5.2, 5.6 y 6.2. Reemplazar la farmacia y resolver las marcas | PC | ✅ **Revisa Rodrigo** |
| Vie 30 | **15. Tus secciones del informe final:** relevancia (problema PyME, con fuentes) e infraestructura | PC | 📤 A Patricio, que integra |
| **Sáb 31** | **16. Acta del replanteamiento** (D-57 a D-65, con fecha y justificación) | PC | — |
| Sáb 31 | **17. Exportar EP-SRV-01 y EP-WKS-01** (OVA) a un disco externo y compartirlas con un segundo integrante, como respaldo del laboratorio | Notebook y PC escritorio | — |
| Sáb 31 | **18. Revisión cruzada** de los documentos de Patricio y aprobación del PR de versión `develop` → `main` | GitHub | 🤝 **Los tres, 2 h**, con el primer ensayo |
| **Dom 01** | **19.** Pedirle a tu chat un `KRO-LOG-NZ-2026-11-01_cierre_semana.md` y traerlo al chat principal | — | — |

## Revisiones que te tocan (regla D-54)
- **Apruebas** los PR de **Patricio**: cortacircuito (martes), cambios de la medición y documentos. Hazlo el mismo día; si no alcanzas, avisa por WhatsApp.
- **Tus PR los aprueba Rodrigo.** No mezcles tus propios PR ni mezcles desde `soarai2026`.

## Decisiones que te tocan como Product Owner
- D-58: nombre y perfil de la PyME simulada (empresa **ficticia**).
- D-63: acceso de la comisión al repositorio y licencia. Si se hace público, antes cambiar la IP de NetBird de `infra/docker/servicios/.env.example` por un ejemplo.

## Cuidado
- Nunca bloquear `10.0.50.1` ni la IP desde la que te conectas por SSH. Para E2, usa una IP interna que no sea la puerta de enlace (por ejemplo `192.168.50.20`).
- **No revertir todavía el HVCI ni el hipervisor del PC de escritorio:** EP-WKS-01 se necesita hasta la defensa. Se revierte después.
- Claves sólo con `read -rs`. Archivos a las VM con `scp -P 2222` (EP-SRV-01) o `-P 2223` (EP-WKS-01).
- Tus commits y PR van sin marcas ni coautoría de herramientas de IA.
- Antes de tocar el servidor, avisar en el grupo de Telegram.

## Terminado significa
- Los tres scripts de Windows probados en EP-WKS-01, con el resultado reportado a Rodrigo.
- README y partes 01 a 05, 09, 10, 13 y 14 de la guía mezclados en `develop`, con aprobación de Rodrigo.
- Evidencia de E1 a E7 guardada y video de respaldo grabado.
- Tus 9 documentos sin la farmacia; presentación en borrador y acta escrita.

## Puntos de la lista de corrección del GitHub que te tocan
Detalle en `KRO-CHECKLIST-2026-10-26_github_100.md`:
- **A3:** README completo, con resumen en inglés.
- **A5, A6 y A7:** licencia, ficha del repositorio y acceso de la comisión (D-63, con Rodrigo).
- **C7:** evidencias de la prueba integral, con Patricio.
- **C8:** diagrama `15_ambientes`.
- **C9:** la guía 08 ya no está «pendiente».
- **D5:** versión real de Ollama en el servidor, con Patricio.
