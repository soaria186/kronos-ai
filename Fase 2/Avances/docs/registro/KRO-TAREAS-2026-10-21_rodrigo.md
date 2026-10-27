# KRO-TAREAS-2026-10-21 · Rodrigo Riveros (Scrum Master)

Tareas hacia la instalación del primer agente en la farmacia. Generado en el chat principal «kronos maestro» el 21-10-2026 a las 18:45.
**Leer antes:**
- `KRO-ACTA-2026-10-21_punto_de_encuentro_1.md` (decisiones D-44 a D-56);
- `KRO-LOG-RR-2026-10-21_bloque_a_rodrigo.md`;
- `KRO-REV-RR-2026-10-21_revision_cruzada.md`.

## Estado de partida (21-10)
- **Bloque A completo.** PR #32 (script de Windows) y #34 (retención, desplegada) mezclados. NOTIFY funcionando con los 3 y 2FA.
- **PR #35** (recuperador de tickets huérfanos): **abierto, espera la revisión de Patricio.**
- **El servidor no es una copia de git:** `/opt/kronos/audit` se actualiza copiando archivos.
- **Decisiones que te tocan:**
  - D-50: el nivel 0 sin comando se desactiva y no se avisa;
  - D-51: aviso manual de la reversión fallida;
  - D-52: corregir las reglas que se pierden al reiniciar;
  - D-54: regla de merge;
  - D-55: despliegue con `git clone`;
  - D-56: eres el Scrum Master.

## Tareas, por prioridad

| # | Tarea | Dónde | Coordinación |
| :-: | :--- | :--- | :--- |
| 1 | **Como Scrum Master:** pegar en GitHub, desde tu cuenta personal, los comentarios de tu revisión cruzada (#31, #33 y #25 al #30). Anotar la excepción R-04 (PR #7 al #34) y escribir la regla de merge D-54 en `CONTRIBUTING.md` o en el README. | GitHub | 📢 Recordarla en el grupo de Telegram |
| 2 | **Desplegar el PR #35** después de la aprobación de Patricio: migración, recrear `execute` y `notify`. Antes, revisar si el inquilino 1 tiene `PENDING` sin playbook (los #1, #2 y #5 no se ven afectados porque son de otros inquilinos). | servidor | ✅ **Necesita la aprobación de Patricio.** 🤝 **Después** del despliegue de VALIDATE (Patricio y Nicolás), avisando en Telegram |
| 3 | **Pasar `/opt/kronos/audit` a `git clone`** con etiquetas de versión (D-55): respaldo previo, conservar `.env`, `secrets/`, `initdb/03_roles.sql` y `05_clave_consola.sql`, y documentar el procedimiento en la guía (parte 07). | servidor | 🤝 **Avisar a Nicolás y Patricio**: nadie despliega mientras tanto. Hacerlo **después** de las tareas 2 y del despliegue de VALIDATE |
| 4 | **EXECUTE con `.cmd` para Windows**, si la prueba de Nicolás muestra que `!kronos-bloquear-ip` no encuentra el `.cmd`. Usar el sistema operativo del agente (`os.platform` desde la API o desde la alerta). | PC | 📥 **Depende del resultado de Nicolás.** ✅ PR que revisa Patricio |
| 5 | **Nivel 0 sin comando: desactivado y sin aviso** (D-50). Que EXECUTE no lo intente (o que lo cierre sin `FAILED` ruidoso) y que NOTIFY no avise. | PC | ✅ PR que revisa Patricio |
| 6 | **Aviso de reversión fallida** (D-51): NOTIFY avisa cada `REVERSION_FALLIDA` con el equipo, la medida y el comando para revertir a mano. Sin reintento automático. | PC | ✅ PR que revisa Patricio |
| 7 | **Volver a aplicar las medidas vigentes** cuando un agente se reconecta o reinicia (D-52). Afecta sobre todo al nivel 2. Alternativa: reglas persistentes en los scripts. | PC | 🤝 **Decidir el enfoque con Nicolás** (dueño de los scripts). ✅ PR que revisa Patricio |
| 8 | **Scripts de Windows (y Linux, si faltan)** de los otros 5 comandos: `kronos-aislar-equipo`, `kronos-deshabilitar-cuenta`, `kronos-detener-servicio`, `kronos-cerrar-sesion` y `kronos-terminar-proceso`, con las mismas barreras que `kronos-bloquear-ip`. **Entregar de a uno.** | PC | 🔁 **Nicolás prueba cada uno** en EP-WKS-01 y EP-SRV-01. ✅ PR que revisa Patricio |
| 9 | **Las 5 acciones sin comando** (`consulta`, `cuarentena`, `bloquear_destino`, `limitar_conexiones` y `revertir_tarea`) para cubrir las 25 medidas (D-47). **Pueden esperar a la semana de observación**, pero tienen que estar **antes de salir** de ella. | PC | 🤝 **Con Patricio** (catálogo). Nicolás prueba |
| 10 | **Sumar el inquilino 2** (farmacia) en `KRONOS_INQUILINOS` de EXECUTE y NOTIFY cuando Patricio y Nicolás lo creen. | servidor | 📥 **Depende de Patricio y Nicolás** |
| 11 | **Plan de desinstalación** y texto del correo a la persona afectada (D-35). | PC | 🤝 **Con Nicolás** |
| 12 | Imagen `kronos-servicios:local` construida dos veces: `pull_policy: never` en `execute`. Desconectar Ollama de la red `salida` y anotarlo en el modelo de amenazas. | PC | 💬 Lo de Ollama, avisarlo a Nicolás |

## Tareas en conjunto (los tres)
- **Punto de encuentro 2: prueba integral** (unas 2 h). **Tú miras EXECUTE, NOTIFY y la consola**, incluidos los botones del nivel 3 en Telegram. **Como Scrum Master, propón la fecha** en cuanto estén desplegados VALIDATE y el #35.
- **Lista de «sí o no»** antes de la farmacia. **Te tocan los puntos 1 y 5:** servicios en marcha y respaldo restaurable.
- **Instalación del primer agente** en la farmacia.

## Lo que otros esperan de ti
| Quién | Qué |
| :--- | :--- |
| Nicolás | Revisar su PR de correcciones al script Linux y la guía 08; los scripts de Windows de a uno; el enfoque de la tarea 7 |
| Patricio | Aviso de cuándo despliegas el #35 (para no cruzarlo con VALIDATE); el inquilino 2 en EXECUTE y NOTIFY |

## Reglas
- Nada de secretos en el chat ni en el repositorio. No abrir `getUpdates` en el navegador.
- **No convertir el grupo de Telegram en supergrupo**: cambiaría su id.
- **Regla de merge (D-54):** nadie mezcla desde `soaria186`, nunca mezcla el autor y siempre hay una aprobación previa desde la cuenta personal.
- Avisar en Telegram antes de tocar el servidor.

## Al terminar
Pide a tu chat un `KRO-LOG-RR-<fecha>_<tema>.md` con:
- tareas hechas y no hechas;
- PR y revisiones;
- despliegues (con hora UTC);
- hallazgos;
- lo que necesitas de los otros.

Súbelo al proyecto y tráelo al chat principal «kronos maestro».
