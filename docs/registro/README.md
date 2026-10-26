# Registro de trabajo

Cómo se llevó el proyecto: registros de cada jornada, estados, actas, revisiones, planes y tareas. Es la
evidencia del control del proyecto (Scrum) y de las decisiones; lo vigente del producto está en el README del
repositorio, la guía de instalación y los 31 documentos.

- **[Registro de decisiones](decisiones.md):** todas las decisiones `D-NN`, con su fuente y lo que pasó después.
- **Copias fieles:** cada archivo es el documento del proyecto tal como quedó en su fecha. Pueden mencionar a la
  farmacia (el planteamiento anterior al 26-10) y decisiones que después cambiaron.
- **Lo que se quitó antes de subirlos:** los identificadores de Telegram (del grupo y de cada persona), el usuario
  del bot, los usuarios del servidor y la IP de NetBird del servidor. Donde estaban dice `<…>`.

## Índice

| Fecha | Archivo | Tipo | De quién | Contenido |
| :--- | :--- | :--- | :--- | :--- |
| 08-10 | [KRO-LOG-RR-2026-10-08](KRO-LOG-RR-2026-10-08_registro_de_trabajo_rodrigo.md) | Registro | Rodrigo | Despliegue y pruebas de SOAR-AUDIT en el servidor |
| 15-10 | [KRO-LOG-RR-2026-10-15](KRO-LOG-RR-2026-10-15_avance_rodrigo.md) | Registro | Rodrigo | PR #16 a #24 (EXECUTE, NOTIFY, consola y respaldo), decisiones de diseño y pendientes por persona |
| 16-10 | [KRO-ESTADO-2026-10-16](KRO-ESTADO-2026-10-16_avance_y_pendientes.md) | Estado | Equipo | Avance al día de la entrega y lo que faltaba para cerrar el sprint 2 |
| 16-10 | [pendientes_entrega_2026-10-16](pendientes_entrega_2026-10-16.md) | Revisión | Equipo | Las marcas «POR CONFIRMAR» y «PENDIENTE» de los 31 documentos entregados, con a quién preguntar |
| 20-10 | [KRO-LOG-PG-2026-10-20](KRO-LOG-PG-2026-10-20_bloque_a_patricio.md) | Registro | Patricio | Mejoras de VALIDATE tras la prueba del 20-10, pruebas de integración y documentación |
| 20-10 | [KRO-ESTADO-2026-10-20](KRO-ESTADO-2026-10-20_ejecucion_y_plan_paralelo.md) | Estado | Equipo | Primer ticket de punta a punta con alertas reales y plan de trabajo en paralelo |
| 21-10 | [KRO-LOG-NZ-2026-10-21](KRO-LOG-NZ-2026-10-21_bloque_a_nicolas.md) | Registro | Nicolás | Reversión automática, EP-WKS-01, script `kronos-bloquear-ip` (#31) y llave del agente 001 |
| 21-10 | [KRO-ESTADO-2026-10-21](KRO-ESTADO-2026-10-21_avance_nicolas_para_los_chats.md) | Estado | Nicolás | El mismo avance, con los hallazgos para Rodrigo y Patricio |
| 21-10 | [KRO-LOG-RR-2026-10-21](KRO-LOG-RR-2026-10-21_bloque_a_rodrigo.md) | Registro | Rodrigo | Script de Windows, NOTIFY en Telegram, tope y retención de alertas (#34) y recuperador de huérfanos (#35) |
| 21-10 | [KRO-REV-RR-2026-10-21](KRO-REV-RR-2026-10-21_revision_cruzada.md) | Revisión | Rodrigo | Revisión cruzada de los PR #25 a #31 y #33 |
| 21-10 | [KRO-LOG-PG-2026-10-21 (avance)](KRO-LOG-PG-2026-10-21_avance_patricio.md) | Registro | Patricio | Decisión e IA: tareas, PR, pruebas y hallazgos |
| 21-10 | [KRO-LOG-PG-2026-10-21 (despliegue)](KRO-LOG-PG-2026-10-21_despliegue_validate.md) | Registro | Patricio | Despliegue de VALIDATE (#36) en SOAR-CORE-01 |
| 21-10 | [KRO-ACTA-2026-10-21](KRO-ACTA-2026-10-21_punto_de_encuentro_1.md) | Acta | Los tres | Punto de encuentro 1: decisiones D-44 a D-56 |
| 21-10 | KRO-TAREAS-2026-10-21: [Nicolás](KRO-TAREAS-2026-10-21_nicolas.md), [Patricio](KRO-TAREAS-2026-10-21_patricio.md), [Rodrigo](KRO-TAREAS-2026-10-21_rodrigo.md) | Tareas | Equipo | Tareas de cada uno después del punto de encuentro |
| 26-10 | [KRO-PLAN-2026-10-26](KRO-PLAN-2026-10-26_replanteamiento_pyme_y_cierre.md) | Plan | Equipo | Replanteamiento PyME, alcance de la v1.0, escenarios E1 a E7 y plan de la semana de cierre (propuestas D-57 a D-65) |
| 26-10 | [KRO-CHECKLIST-2026-10-26](KRO-CHECKLIST-2026-10-26_github_100.md) | Revisión | Equipo | Lista de corrección del repositorio para la v1.0 (milestone «v1.0: cierre») |
| 26-10 | KRO-TAREAS-2026-10-26: [Nicolás](KRO-TAREAS-2026-10-26_nicolas.md), [Patricio](KRO-TAREAS-2026-10-26_patricio.md), [Rodrigo](KRO-TAREAS-2026-10-26_rodrigo.md) | Tareas | Equipo | Tareas de la semana de cierre |

## Cómo se agrega un registro

- Nombre: `KRO-<TIPO>-<iniciales>-<AAAA-MM-DD>_<tema>.md`. Tipos: `LOG` (registro de una jornada), `ESTADO`,
  `ACTA`, `REV` (revisión), `PLAN`, `TAREAS` y `CHECKLIST`. Las iniciales se omiten si es del equipo.
- Un registro dice qué se hizo y qué no, los PR y revisiones, los despliegues (con hora UTC), los hallazgos y lo
  que se necesita de los demás (ver `CONTRIBUTING.md`).
- Sin secretos, identificadores de Telegram, usuarios del servidor ni IP reales. Una decisión nueva se agrega
  también a [`decisiones.md`](decisiones.md).
- Por PR a `develop`, como todo lo demás.
