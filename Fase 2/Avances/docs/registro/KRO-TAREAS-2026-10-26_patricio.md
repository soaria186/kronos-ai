# KRO-TAREAS-2026-10-26 · Patricio González (decisión, IA y calidad)

Semana de cierre: lunes 26-10 a domingo 01-11-2026. Generado en el chat principal «kronos maestro».

**Leer antes:**
- `KRO-PLAN-2026-10-26_replanteamiento_pyme_y_cierre.md`: replanteamiento PyME, diagnóstico, alcance congelado y escenarios E1 a E7.
- `KRO-LOG-PG-2026-10-21_avance_patricio.md`.
- `KRO-REV-RR-2026-10-21_revision_cruzada.md`, hallazgo del cortacircuito en el #28.

## Contexto en tres líneas
- El profesor descartó la farmacia: Kronos se presenta como solución para **PyMEs sin especialista en ciberseguridad**, validada en una **PyME simulada**.
- Tu parte es la que más pesa en la defensa: **la IA es el «analista» que la PyME no puede contratar**, y la comisión va a preguntar cuánto acierta y qué pasa cuando se equivoca.
- **Pendiente comprometido desde la Fase 1:** la prueba de estrés (30 alertas en 10 minutos abren el cortacircuito). Hoy el cortacircuito cuenta las alertas procesadas, no las que llegan.
- Si el lunes se aprueba la D-61, ya no aplican el modo observación (D-48) ni el `validate.json` de la farmacia, y el inquilino por grupo (D-49) queda **sólo si sobra tiempo**.

## Tareas, por día

| Día | Tarea | Dónde | Coordinación |
| :--- | :--- | :--- | :--- |
| **Lun 26** | **1. Cortacircuito por alertas recibidas:** que cuente las alertas que llegan por inquilino, incluidas las agrupadas, y no los tickets procesados. Que se abra con 30 en 10 minutos. Pruebas unitarias y de integración (en `kronos_pruebas`). PR a `develop` | PC | ✅ **Aprueba Nicolás**. No lo mezcles tú |
| Lun 26 | **2. Arranque (30 min):** aprobar D-57 a D-65 en el chat principal | Chat principal | 🤝 **Los tres** |
| **Mar 27** | **3. Medir qué medida elige la IA en los escenarios E1 a E4**, con alertas con la forma real de cada uno (fuerza bruta externa e interna, inicios de sesión fallidos en Windows, registro de auditoría borrado). **Avisar a los dos** qué medida y qué nivel salen, sobre todo en E3 (¿deshabilitar cuenta?) y en E4 (¿aislar puesto?) | PC, o servidor con el Ollama real coordinado con Nicolás | 📤 **Antes de que Rodrigo termine los scripts** |
| Mar 27 | **4. Precisión de punta a punta:** etiquetar el playbook esperado en **al menos 50** de los 150 casos (con playbooks de un solo paso, D-44) y medir familia, medida y producto de los dos pasos. Actualizar `decision/mediciones/resultados/README.md`. **No ajustar el prompt sobre los mismos casos medidos** | PC o servidor | ✅ PR, **aprueba Nicolás** |
| **Mié 28** | **5. Desplegar el cortacircuito** con `git pull` (Rodrigo deja el servidor como clon de git el lunes). Avisar en Telegram antes | Servidor | 📥 Depende del clon de Rodrigo |
| Mié 28 | **6. Prueba de estrés (E6) y prueba de la ráfaga:** guion con `logger` (30 alertas en 10 min con distintas IP; y una ráfaga repetida que debe dar **un solo** ticket y «agrupada» en el registro). Anotar los resultados para el documento 6.5 | Servidor | 🤝 **Con Nicolás, 1 h** (él genera las alertas) |
| **Jue 29** | **7. Prueba integral (punto de encuentro 2):** mirar VALIDATE y llenar la **tabla de métricas** por escenario (alerta → decisión, decisión → ejecución, total, acierto de familia y de medida, falla segura) | Servidor | 🤝 **Los tres, 2 a 3 h** |
| **Vie 30** | **8. Tus documentos de los 31:** 1.3 Carta Gantt (con el replanteamiento y esta semana), 1.4, 1.7, 2.2, 2.3, 2.4, 2.6, 4.1, 6.1, 6.4 y 6.5. Reemplazar la farmacia por la PyME simulada y resolver las marcas. En 2.6, 4.1 y 6.5 incluir: medidas de nivel 3 inalcanzables por severidad (PB-F6-04 y PB-F6-05), meta de 60 s frente a plazo de 120 s, y medidas fuera de la v1.0 con falla segura | PC | ✅ **Revisa Nicolás** |
| Vie 30 | **9. Integrar el informe final de Duoc**, con las secciones de cada uno (piden: relevancia, objetivos, metodología, desarrollo, evidencias, intereses y proyecciones). Agregar el **resumen en inglés** (*abstract*) y los apartados en inglés que pida la guía de la Fase 3 | PC | 📥 Secciones de Nicolás y Rodrigo el jueves en la noche |
| **Sáb 31** | **10. Ramas de experimentos:** `feat/e1-mediciones-servidor`, `feat/e2-mediciones-prompt-v1`, `feat/e2-mediciones-prompt-v2` y `feat/e2-prompt-confianza`. Decidir con Rodrigo si se archivan como etiqueta, y dejar una línea en el registro de mediciones (qué se probó y por qué no se integró) | GitHub | 🤝 **Con Rodrigo** |
| Sáb 31 | **11. Revisión cruzada** de los documentos de Rodrigo y aprobación del PR de versión `develop` → `main` | GitHub | 🤝 **Los tres, 2 h**, con el primer ensayo |
| **Dom 01** | **12.** Pedirle a tu chat un `KRO-LOG-PG-2026-11-01_cierre_semana.md` y traerlo al chat principal | — | — |
| *Si sobra tiempo* | Inquilino por grupo de Wazuh (D-49): dos PyMEs simuladas, una por equipo, para mostrar el SaaS con dos inquilinos | PC | 🤝 Grupos de Wazuh con Nicolás; inquilino 2 en EXECUTE y NOTIFY con Rodrigo |

## Revisiones que te tocan (regla D-54)
- **Apruebas** los PR de **Rodrigo**: `kronos-deshabilitar-cuenta` (martes), `kronos-aislar-equipo` y avisos en lenguaje claro (miércoles). Hazlo el mismo día, porque Nicolás necesita los scripts para probarlos.
- **Tus PR los aprueba Nicolás.** No mezcles tus propios PR (el #36 lo mezclaste tú: que no se repita).

## Para la defensa: preguntas que te van a hacer
- ¿Cuánto acierta la IA? Familia, medida y punta a punta, con el tamaño de la muestra.
- ¿Qué pasa si la IA se equivoca o la engañan? Coincidencia con la regla de sobre, catálogo cerrado, severidad, exclusiones, contadores, cortacircuito y falla segura.
- ¿Por qué un modelo local y no uno en la nube? Datos de la PyME y costo.
- ¿Es determinista? Temperatura 0, esquema JSON y validador; y la prueba de reproducibilidad del documento 6.4.

## Cuidado
- Las pruebas de integración, **sólo** contra `kronos_pruebas`.
- Desde el lunes no más copias desde Windows: despliegue con `git pull` y la etiqueta que deje Rodrigo.
- Avisar en Telegram antes de tocar el servidor. Si la medición usa el Ollama del servidor, coordinarlo con Nicolás.
- Nada de secretos en el chat ni en el repositorio.

## Terminado significa
- Cortacircuito por alertas recibidas mezclado (con aprobación de Nicolás) y desplegado.
- Prueba de estrés y de la ráfaga hechas, con resultados.
- Medición de punta a punta con al menos 50 casos, registrada.
- Tabla de métricas de la prueba integral.
- Tus 11 documentos sin la farmacia; informe final integrado, con resumen en inglés.

## Puntos de la lista de corrección del GitHub que te tocan
Detalle en `KRO-CHECKLIST-2026-10-26_github_100.md`:
- **B2:** ramas de experimentos, con Rodrigo.
- **C5:** README de `conectores/` (corregir «SIEM, EDR, ticketing»), `decision/` y `validacion/`.
- **C7:** evidencias.
- **C8:** diagramas `02_casos_uso`, `02_tratamiento_niveles` y `04_cronograma`.
- **C9:** guía 06.
- **D1:** catálogo v1.0.
- **D2:** `validate.json` v1.0, después de aprobar la D-65.
- **D5:** versión de Ollama, con Nicolás.
- **D7:** latencia.
- **D8:** códigos D-44 a D-46.
