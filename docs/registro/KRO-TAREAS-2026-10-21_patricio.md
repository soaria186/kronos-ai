# KRO-TAREAS-2026-10-21 · Patricio González (decisión e IA)

Tareas hacia la instalación del primer agente en la farmacia. Generado en el chat principal «kronos maestro» el 21-10-2026 a las 18:45.
**Leer antes:**
- `KRO-ACTA-2026-10-21_punto_de_encuentro_1.md` (decisiones D-44 a D-56);
- `KRO-LOG-PG-2026-10-20_bloque_a_patricio.md`;
- `KRO-REV-RR-2026-10-21_revision_cruzada.md` (lo que Rodrigo encontró en tus PR #25 al #30).

## Estado de partida (21-10)
- **Rama `feat/validate-mejoras-prueba-20-10`** (agrupación, nota de ámbito de IP, plazo de 120 s, exclusión de `10.0.50.1`, pruebas en `kronos_pruebas`, documento 02 §8.1): **existe, pero el PR no está abierto.** Sin desplegar.
- **En el servidor:** VALIDATE y EXECUTE encendidos. La ejecución del nivel 1 con reversión está probada en Linux.
- **PR #35 de Rodrigo** (recuperador de tickets huérfanos): **espera tu revisión.**
- **Decisiones que te tocan:** playbooks de un solo paso (D-44), modo observación de 1 semana (D-48), inquilino por grupo de Wazuh (D-49) y las 25 medidas en la farmacia (D-47).

## Tareas, por prioridad

| # | Tarea | Dónde | Coordinación |
| :-: | :--- | :--- | :--- |
| 1 | **Abrir el PR de `feat/validate-mejoras-prueba-20-10`** hacia `develop`. Hoy bloquea a Nicolás (revisión y despliegue). | GitHub | ✅ **Necesita la aprobación de Nicolás.** No mezclarlo tú (D-54). **RUTA CRÍTICA** |
| 2 | **Revisar el PR #35 de Rodrigo** desde tu cuenta personal: `recuperar_huerfanos` (10 min, `FOR UPDATE SKIP LOCKED`, motivo `DECISION_NO_REGISTRADA`), el aviso «[SIN DECISIÓN]» y la migración. | GitHub | ✅ **Rodrigo necesita tu aprobación** para desplegar |
| 3 | **Desplegar VALIDATE** después del merge. Comprobar `ollama ps` («Forever»), el log («cargando el modelo», «agrupada») y que una ráfaga dé **un solo** ticket. | servidor | 🤝 **Juntos con Nicolás.** Avisar en Telegram. **Antes** del despliegue del #35 de Rodrigo, uno a la vez |
| 4 | **Modo observación por inquilino** (D-48): un ajuste en `validate.json` por inquilino que lleve **todo nivel mayor que 0 a aprobación** (`AWAITING_APPROVAL`) durante la semana de observación, con pruebas. | PC | ✅ PR que revisa Nicolás. 💬 Avisar a Rodrigo: EXECUTE no cambia, porque solo toma `PENDING` |
| 5 | **Inquilino por grupo de Wazuh** (D-49): leer el grupo del agente desde la alerta y asignarlo a un inquilino según `validate.json` (laboratorio → 1, `farmacia` → 2). Definir qué pasa con un agente sin grupo (propuesta: no se procesa y se avisa). | PC | 🤝 **El número del grupo e inquilino, con Nicolás** (él crea el grupo). 💬 Rodrigo debe sumar el inquilino 2 en `KRONOS_INQUILINOS` de EXECUTE y NOTIFY |
| 6 | **Cortacircuito por alertas recibidas** (hallazgo del #28): que cuente alertas que llegan, incluidas las agrupadas, y no tickets creados. Prueba: 30 alertas en 10 min abren el cortacircuito. | PC | ✅ PR que revisa Nicolás. Antes de la prueba de estrés |
| 7 | **Catálogo y prompt para playbooks de un solo paso** (D-44) con las 25 medidas (D-47). Etiquetar el playbook esperado de los 150 casos y **medir el acierto del paso 2**, incluida la nota de ámbito con el modelo de 7B. | PC + servidor (Ollama) | ✅ PR que revisa Nicolás. 💬 Coordinar con Nicolás si la medición usa el Ollama del servidor |
| 8 | **Decirle a Nicolás qué eventos de Windows necesitas** para probar las reglas de sobre de Windows en EP-WKS-01 (agente 002). | Chat o Telegram | 🤝 **Con Nicolás** |
| 9 | **`validate.json` de la farmacia:** redes internas y lista de exclusión (**incluida la puerta de enlace**), con lo que traiga Nicolás. | PC | 📥 **Depende de Nicolás** (datos de la farmacia) |
| 10 | **Documentos:** registrar D-44 a D-56; cambiar 60 s por 120 s; cerrar las marcas POR CONFIRMAR de los documentos 09 §11, 17 §3 y 19 §3 y §4.1; cerrar la fila 3 (D-34) de `preguntas-abiertas.md`; documentar los tickets de prueba #1, #2 y #5 como evidencia (D-53). | PC | — |

## Tareas en conjunto (los tres)
- **Punto de encuentro 2: prueba integral** (unas 2 h). **Tú miras VALIDATE.** Comprobar el modo observación, la agrupación, el inquilino por grupo y el cortacircuito. Fecha por definir.
- **Lista de «sí o no»** antes de la farmacia. **Te toca el punto 3:** una alerta del inquilino de la farmacia queda en aprobación y no se ejecuta.
- **Instalación del primer agente** en la farmacia.

## Lo que otros esperan de ti
| Quién | Qué |
| :--- | :--- |
| Nicolás | Que abras el PR (tarea 1) para revisarlo y desplegarlo contigo; la lista de eventos de Windows (tarea 8) |
| Rodrigo | La revisión del #35 (tarea 2); aviso de cuándo existe el inquilino 2 (tarea 5) |

## Reglas
- Nada de secretos en el chat ni en el repositorio.
- **Regla de merge (D-54):** nadie mezcla desde `soarai2026`, nunca mezcla el autor y siempre hay una aprobación previa desde la cuenta personal.
- Avisar en Telegram antes de tocar el servidor. VALIDATE y EXECUTE están encendidos y actúan sobre EP-SRV-01.
- Las pruebas de integración solo contra `kronos_pruebas`.

## Al terminar
Pide a tu chat un `KRO-LOG-PG-<fecha>_<tema>.md` con:
- tareas hechas y no hechas;
- PR y su estado de revisión;
- resultados de las pruebas;
- hallazgos;
- lo que necesitas de los otros.

Súbelo al proyecto y tráelo al chat principal «kronos maestro».
