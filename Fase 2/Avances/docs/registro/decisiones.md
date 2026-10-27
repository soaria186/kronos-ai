# Registro de decisiones

Todas las decisiones del proyecto con su código `D-NN`. El código, los README, los PR y los documentos las
citan por ese código; aquí está qué dice cada una y de dónde sale.

| Campo | Valor |
| :--- | :--- |
| Actualizado | 26-10-2026 |
| Fuentes | Contexto maestro 3.1 (15-10) para D-01 a D-46a, y 2.1 (14-10, en [`docs/archivo/`](../archivo/)) para D-07, D-21, D-29 y D-30, que la 3.1 no trae; [acta del 21-10](KRO-ACTA-2026-10-21_punto_de_encuentro_1.md) para D-44 a D-56; [plan del 26-10](KRO-PLAN-2026-10-26_replanteamiento_pyme_y_cierre.md) para D-57 a D-65 |
| Cómo se agrega una | Se toma en una reunión y queda en su acta. Después se agrega aquí, por PR |
| Cómo cambia una | No se borra ni se reescribe: la decisión nueva dice a cuál reemplaza o anula, y la antigua lo anota en «Después» |

> **Códigos repetidos.** D-44, D-45 y D-46 se usaron dos veces: en el contexto maestro del 15-10 y en el acta del
> 21-10. Valen los del acta. Los del contexto maestro se citan como **D-44a, D-45a y D-46a**.

Estados: ✅ vigente · 🟡 vigente con condiciones, recomendada o en curso · ❓ sin responder · ⏳ por definir ·
📝 propuesta, sin aprobar.

## 1. Hasta el 15-10-2026

| Código | Decisión | De quién o de dónde | Estado al 15-10 | Después |
| :---: | :--- | :--- | :--- | :--- |
| D-01 | Nube: Cloud VDS XL de Contabo del profesor | Replanteamiento (25-09) | ✅ | |
| D-02 | SOAR-CLASSIFY en SOAR-CORE-01, modelo local, sin API de pago | Replanteamiento (25-09) | ✅ | |
| D-03 | Python (FastAPI) en vez de n8n | Replanteamiento (25-09) | ✅ | |
| D-04 | Dos vías de equipos: máquinas virtuales propias y equipos de la farmacia | Replanteamiento (25-09) | ✅ | Sin cliente real, queda sólo la vía de las máquinas virtuales: D-57 (📝) |
| D-05 | Contención real, sin modo observación en producción | Replanteamiento (25-09) | ✅ | |
| D-06 | LAB-01 como contingencia | Replanteamiento (25-09) | 🟡 | |
| D-07 | Acordar con el profesor por escrito el alcance y los límites | Replanteamiento (25-09) | 🟡 | |
| D-08 | Seis familias por comportamiento observable y clasificación en dos pasos | Repositorio | ✅ | |
| D-09 | Active Response de Wazuh como actuador único | Replanteamiento (25-09) | ✅ | |
| D-10 | Multiinquilino con `tenant_id`, RLS y cadena por inquilino | Repositorio | ✅ | |
| D-11 | Dashboard de Wazuh sólo como herramienta interna | Replanteamiento (25-09) | ✅ | |
| D-12 | Red privada del equipo: NetBird | Tareas por integrante (14-10) | ✅ | |
| D-13 | Servidor en UTC | Equipo | ✅ | |
| D-14 | 2FA en Contabo descartado por el momento | Nicolás | ✅ riesgo aceptado | |
| D-15 | Primero la nube y el laboratorio; la farmacia al final | Equipo | ✅ | D-61 propone anularla (📝) |
| D-16 | Laboratorio en máquinas virtuales del notebook de Nicolás, sin NetBird | Equipo | ✅ | EP-WKS-01 pasó al PC de escritorio de Nicolás el 21-10 (#33) |
| D-17 | Agentes registrados desde el servidor; 1514 público; 55000, 9200 y 5601 sólo por NetBird | Tareas por integrante (14-10) | ✅ por implementar | |
| D-18 | Guía de instalación en `docs/instalacion/`, 15 partes | Tareas por integrante (14-10) | ✅ | |
| D-19 | Sin prueba de regresión del hash por zona horaria | Rodrigo | ✅ | |
| D-20 | PR integrados sin revisión cruzada: excepciones registradas | Equipo | ✅ | Desde el 21-10 rige la regla de merge D-54 |
| D-21 | Docker Desktop en el PC para pruebas previas | Rodrigo (registro del 08-10) | ✅ | |
| D-22 | Secretos generados en el servidor | Rodrigo | ✅ | |
| D-23 | Documentos en Word, con diseño cuidado y en español de Chile | Equipo (14 y 15-10) | ✅ | |
| D-24 | Entrega de documentos el 16-10-2026 | Equipo (14 y 15-10) | ✅ | Se entregaron los 31 documentos, con sus marcas en [`pendientes_entrega_2026-10-16.md`](pendientes_entrega_2026-10-16.md) |
| D-25 | Servidor en Francia | Equipo (14 y 15-10) | ✅ | |
| D-26 | Copia de respaldo en el PC de escritorio de Nicolás | Equipo (14 y 15-10) | ✅ con condiciones | |
| D-27 | Retención de 2 años, fundada en la Ley 21.663 (decisión interna; la ley no fija ese plazo) | Equipo (14 y 15-10) | ✅ | Para las alertas guardadas, D-46 la baja a 90 días; la bitácora sigue en 2 años |
| D-28 | Lo que necesita datos de la farmacia se completa después de instalar ahí | Equipo (14 y 15-10) | ✅ | D-61 propone anularla (📝) |
| D-29 | Gestor de contraseñas: el equipo respondió «MFA». Falta saber qué gestor guarda los secretos | Equipo (14-10) | ❓ | El equipo guarda los secretos en un gestor común (registro del 21-10) |
| D-30 | Numeración de etapas | Equipo (14-10) | ⏳ | |
| D-31 | Sólo el equipo aprueba el nivel 3 y recibe avisos | Nicolás | ✅ | D-59 propone reemplazarla: aprueba el encargado de TI de la PyME (📝) |
| D-32 | Plazo de 2 días para aprobar el nivel 3 | Nicolás | ✅ | |
| D-33 | Plazo de revisión de 2 días para el nivel 2, con recordatorio diario y sin reversión automática | Nicolás | ✅ | |
| D-34 | Nivel 3 sin respuesta en 2 días: `APROBACION_VENCIDA`, sin ejecutar | Patricio y Rodrigo | ✅ | |
| D-35 | Aviso a la persona afectada por correo, a mano | Nicolás | ✅ | |
| D-36 | Modelo qwen2.5:7b | Patricio | 🟡 recomendado | Es el modelo por omisión de VALIDATE (`infra/docker/servicios.yml`) |
| D-37 | La familia del modelo debe coincidir con la regla de sobre (`FAMILIA_NO_COINCIDE`) | Patricio | ✅ integrado | |
| D-38 | El nivel 3 espera en `AWAITING_APPROVAL`; `FAILED` no se reintenta; la reversión sólo queda en la bitácora | Rodrigo | 🟡 en PR | Integrada (#20, 15-10) |
| D-39 | La consola escribe con el rol mínimo `kronos_console` | Rodrigo | 🟡 en PR | Integrada (#23, 15-10) |
| D-40 | Consola sólo por NetBird, con TLS, contraseña y TOTP | Rodrigo | 🟡 en PR | Integrada (#24, 15-10) |
| D-41 | Respaldo de PostgreSQL a las 04:15 UTC, cifrado con age, 14 copias | Rodrigo | 🟡 en PR | Integrada (#19, 15-10) |
| D-42 | Contraseñas de los servicios como secretos de Docker | Rodrigo | 🟡 propuesta | Integrada (#22, 15-10) |
| D-43 | Kick-off el 10-08-2026 con el equipo y el profesor guía | Equipo (15-10) | 🟡 asumido | |
| D-44a | No se envía el mensaje al profesor sobre el contrato del servidor | Nicolás (14-10) | ✅ | |
| D-45a | Los 31 documentos (Parte B del contexto maestro 3.1) reemplazan a la lista de 17 basada en la bibliografía | Equipo (15-10) | ✅ | D-62 propone publicarlos en PDF y archivar los 17 Word (📝) |
| D-46a | Configuración de VALIDATE (mapa de severidad, exclusiones, contadores, cortacircuito) | Patricio | 🟡 propuesta 0.1 sin aprobar | D-65 aprueba la versión 1.0 (26-10) |

## 2. Punto de encuentro 1 (21-10-2026)

Con los tres integrantes. Detalle y consecuencias en el [acta](KRO-ACTA-2026-10-21_punto_de_encuentro_1.md).

| Código | Tema | Decisión | Después |
| :---: | :--- | :--- | :--- |
| D-44 | Playbooks | De un solo paso | |
| D-45 | Reversión del nivel 1 | 60 minutos, confirmados | Comprobada el 21-10: la regla se quitó a los 60 minutos y 3 segundos |
| D-46 | Retención de las alertas guardadas | 90 días. La bitácora se mantiene 2 años | Integrada (#34); purga diaria a las 04:45 UTC desde el 21-10 |
| D-47 | Medidas en la farmacia | Las 25 del catálogo KRO-CAT-01. Se agregarán más en el futuro | D-61 propone anularla en lo que toca a la farmacia, (📝), y D-60 fija las medidas de la v1.0 (26-10) |
| D-48 | Inicio en la farmacia | Modo observación durante 1 semana | D-61 propone anularla (📝) |
| D-49 | Inquilino de cada alerta | Por grupo de agentes de Wazuh | D-61 propone dejarla como deseable (📝). En la v1.0 hay una PyME por servidor |
| D-50 | Nivel 0 sin comando (por ejemplo, 100115 → PB-F6-01) | Se desactiva y no se avisa | El «no se avisa» llega con #78 |
| D-51 | Reversión con el agente apagado | Aviso manual, sin reintento automático | |
| D-52 | Reglas que se pierden al reiniciar el equipo | Se corrige: deben volver a aplicarse | D-61 propone dejarla como limitación documentada (📝) |
| D-53 | Tickets de prueba #1, #2 y #5 | Se dejan como evidencia | |
| D-54 | Regla de merge | Nadie mezcla desde `soaria186`; nunca mezcla el autor; siempre hay una aprobación previa desde la cuenta personal. Los PR #7 al #34 quedan como excepción R-04 | Las excepciones están en `CONTRIBUTING.md` |
| D-55 | Despliegue en SOAR-CORE-01 | Rodrigo pasa `/opt/kronos/audit` a un `git clone` con etiquetas de versión. Nadie despliega sin avisar en el grupo de Telegram | Se hace en la semana de cierre (#54) |
| D-56 | Roles de Scrum | Product Owner: Nicolás. Scrum Master: Rodrigo. Equipo de desarrollo: los tres, con Patricio a cargo de la calidad de la decisión (IA y mediciones) | |

## 3. Arranque de la semana de cierre (26-10-2026)

Propuestas del [plan del 26-10](KRO-PLAN-2026-10-26_replanteamiento_pyme_y_cierre.md) (sección 2.6), por la
retroalimentación del profesor guía. Al aprobarlas, su estado cambia a ✅ y se completa la columna «Después» de
las que reemplazan o anulan. D-60 y D-65 se dieron por aprobadas el 26-10, al integrar el catálogo 1.0 (#83) y
`validate.json` 1.0 (#84); las demás esperan el acta del arranque.

| Código | Propuesta | Estado |
| :---: | :--- | :---: |
| D-57 | Registrar la decisión del profesor: sin cliente real; validación en una PyME simulada | 📝 |
| D-58 | Nombre y perfil de la PyME simulada (empresa ficticia, sin nombre de una empresa real) | 📝 |
| D-59 | Quién aprueba el nivel 3: el encargado de TI de la PyME, con el equipo Kronos como respaldo. Reemplaza a D-31 | 📝 |
| D-60 | Alcance congelado de la v1.0 (sección 5 del plan): bloquear IP (niveles 1 y 2), deshabilitar cuenta (nivel 2) y aislar un puesto (nivel 3). Las demás medidas siguen en el catálogo y, si se eligen, terminan en falla segura con aviso | ✅ 26-10 |
| D-61 | Se anulan D-15, D-28, D-47 (en lo que toca a la farmacia) y D-48 (modo observación). D-49 (inquilino por grupo) pasa a deseable. D-52 (volver a aplicar reglas tras un reinicio) pasa a limitación documentada | 📝 |
| D-62 | Documentación oficial: los 31 documentos más el informe final de Duoc. Se publican en PDF en `docs/entregables/` y los 17 Word v0.1 se archivan. Desde la reestructuración del 26-10, los PDF van en `Fase 2/Documentación Grupal` | 📝 |
| D-63 | Acceso de la comisión al repositorio: invitar al profesor guía o hacerlo público al publicar la v1.0. También licencia | 📝 |
| D-64 | Versión 1.0.0 el sábado 31-10: `main` pasa a ser la versión entregable | 📝 |
| D-65 | Aprobar la configuración de VALIDATE v1.0 (mapa de severidad, exclusiones, contadores, agrupación y disparo del cortacircuito) | ✅ 26-10 |
