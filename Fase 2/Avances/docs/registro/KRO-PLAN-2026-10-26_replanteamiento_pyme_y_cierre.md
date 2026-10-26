# KRO-PLAN-2026-10-26 · Replanteamiento PyME y plan de cierre en una semana

| Campo | Valor |
| :--- | :--- |
| Fecha | Lunes 26-10-2026 |
| Para | Nicolás (Product Owner), Rodrigo (Scrum Master) y Patricio. Se usa en el chat principal «kronos maestro» y en los chats individuales, junto con `KRO-TAREAS-2026-10-26_<nombre>.md` |
| Qué responde | La decisión del profesor guía: **no habrá farmacia ni cliente real**. Kronos AI se presenta como solución para **PyMEs que no pueden pagar un especialista en ciberseguridad y sólo tienen un encargado de TI generalista**. Cómo terminar el proyecto en una semana y dejar el mes restante para estudiar y ensayar la defensa ante la comisión (primera semana de diciembre) |
| Fuentes revisadas | Repositorio `soarai2026/kronos-ai` completo (43 ramas, PR #1 a #38, CI), clonado y probado hoy. Documentos del proyecto: registros KRO-LOG del 08, 15, 20 y 21-10, revisión cruzada de Rodrigo, acta del punto de encuentro 1, tareas del 21-10, contexto maestro v3.1 y pendientes de la entrega del 16-10. Este chat |
| Límites | No puedo leer los chats individuales: sólo veo lo que quedó en documentos del proyecto o en GitHub. Lo hecho **después del 21-10** que no esté ahí no lo conozco (por eso hay puntos «por confirmar»). Los 31 Word están en el Drive de Rodrigo y no son visibles desde aquí: su estado sale de la lista de pendientes del 16-10. Las guías de la Fase 3 de Duoc no son públicas: hay que subirlas al proyecto |

---

## 1. Respuesta corta

1. **Sí se puede cerrar en una semana**, si se congela el alcance y se trabaja en paralelo. El cambio del profesor afecta casi sólo la documentación: **el código no menciona la farmacia ni una vez; los documentos, 186 veces**.
2. **El producto ya funciona de punta a punta** con alertas reales:
   - ataque → Wazuh → IA local → decisión determinista → bloqueo automático → reversión a los 60 minutos (pruebas del 20 y 21-10);
   - 308 pruebas unitarias en verde, verificadas hoy.
3. **Lo que falta son cinco bloques:**
   1. medidas de nivel 2 y 3 con actuador real en Windows, y escenarios de demostración;
   2. la prueba de estrés comprometida en la Fase 1 (30 alertas en 10 minutos abren el cortacircuito);
   3. un GitHub presentable: hoy la rama principal (`main`) está **vacía**;
   4. documentos sin farmacia y sin marcas pendientes;
   5. informe final, manual del encargado de TI y presentación.
4. **El cambio del profesor juega a favor si se documenta bien.** Es retroalimentación del docente, y la rúbrica premia «proponer ajustes considerando dificultades, facilitadores y retroalimentación» (indicador 1 de la autoevaluación y de la formativa).

---

## 2. El nuevo planteamiento

### 2.1 Problema
- Las PyMEs enfrentan las mismas amenazas que una empresa grande (robo de credenciales, ransomware, accesos remotos indebidos), pero no pueden pagar un especialista en ciberseguridad ni un centro de operaciones de seguridad (SOC).
- Quien se ocupa de la tecnología es un **encargado de TI generalista** (soporte, cuentas, redes, equipos). No tiene tiempo ni formación para analizar alertas de seguridad.
- Resultado: si hay monitoreo, sus alertas no se atienden. Lo más común es que no haya monitoreo y el incidente se note por sus efectos.
- **Para el informe:** respaldar con fuentes oficiales (cantidad de PyMEs en Chile, incidentes reportados, costo de un analista). No usar cifras sin fuente.

### 2.2 Solución
Kronos AI hace por la PyME el trabajo del especialista:
- recibe las alertas de Wazuh;
- las clasifica con una IA que corre en el propio servidor (los datos no salen a una IA externa);
- decide con reglas deterministas y un catálogo cerrado de 25 medidas;
- aplica respuestas reversibles y deja todo en una bitácora inalterable.

El encargado de TI interviene **sólo donde hace falta criterio humano**: recibe avisos claros en Telegram y aprueba o rechaza las medidas de alto impacto.

> **Frase para la defensa:** «Kronos es el analista de ciberseguridad que la PyME no puede contratar; el encargado de TI sigue teniendo la última palabra.»

### 2.3 Usuario principal

| Encargado de TI de la PyME | |
| :--- | :--- |
| Quién es | Una persona que hace «de todo» en tecnología; sabe de equipos y redes, no de ciberseguridad |
| Qué necesita | Saber qué pasó, qué hizo Kronos y si tiene que hacer algo, **en lenguaje claro** y desde el teléfono |
| Qué hace en Kronos | Lee los avisos de Telegram; aprueba o rechaza las medidas de nivel 3; revisa y revierte las de nivel 2 en la consola; avisa por correo a la persona afectada |
| Qué no tiene que hacer | Leer registros, escribir reglas, decidir la medida, ejecutar comandos |

### 2.4 Validación sin cliente real: PyME simulada
- **Empresa ficticia** con dos equipos, conectados por internet al servidor en la nube, igual que una PyME real:
  - **EP-WKS-01**, puesto administrativo con Windows 11;
  - **EP-SRV-01**, servidor con Ubuntu 24.04.
- **Escenarios de ataque reproducibles e inofensivos** (sección 6), con evidencia y métricas.
- En la demostración, **un integrante interpreta al encargado de TI**.
- **Recomendado para la semana 2:** pedirle a una persona que trabaje como encargado de TI (un conocido o un compañero) que use Kronos y responda un cuestionario corto de usabilidad. Es la mejor evidencia de que sirve al usuario que plantea el profesor.

### 2.5 Qué no cambia y qué sí

| No cambia | Cambia |
| :--- | :--- |
| Objetivos de la Fase 1: ninguno mencionaba la farmacia | El cliente piloto pasa a ser la PyME simulada |
| Arquitectura, componentes y código | Quién aprueba el nivel 3 (propuesta D-59) |
| Tesis: la IA sólo clasifica, el código determinista ejecuta | Los avisos deben entenderse sin conocimientos de seguridad |
| Servidor en Contabo, multiinquilino, bitácora encadenada | Se anulan las decisiones que dependían de la farmacia |
| Las 25 medidas del catálogo | Los documentos: 186 menciones a la farmacia |

### 2.6 Decisiones para aprobar hoy (D-57 a D-65)

| # | Decisión propuesta | Recomendación |
| :-: | :--- | :--- |
| D-57 | Registrar la decisión del profesor: sin cliente real; validación en una **PyME simulada** | Sí. Anotar la fecha exacta de la decisión del profesor `[POR CONFIRMAR: fecha]` |
| D-58 | Nombre y perfil de la PyME simulada (empresa **ficticia**, sin nombre de una empresa real) | Por ejemplo, «PyME de demostración», con 2 equipos y un encargado de TI |
| D-59 | **Quién aprueba el nivel 3:** el encargado de TI de la PyME, con el equipo Kronos como respaldo. Reemplaza a D-31 | Sí. Es coherente con el planteamiento del profesor y no requiere código: sólo configuración de Telegram |
| D-60 | **Alcance congelado v1.0** (sección 5): bloquear IP (niveles 1 y 2), deshabilitar cuenta (nivel 2) y aislar un puesto (nivel 3). Las demás medidas siguen en el catálogo y, si se eligen, terminan en falla segura con aviso | Sí |
| D-61 | Se anulan D-15, D-28, D-47 (en lo que toca a la farmacia) y D-48 (modo observación). D-49 (inquilino por grupo) pasa a **deseable**. D-52 (volver a aplicar reglas tras un reinicio) pasa a **limitación documentada** | Sí |
| D-62 | Documentación oficial: **los 31 documentos** más el informe final de Duoc. Se publican en PDF en `docs/entregables/` y los 17 Word v0.1 se archivan | Sí |
| D-63 | Acceso de la comisión al repositorio: invitar al profesor guía o hacerlo público al publicar la v1.0. También licencia | Decidir. Si se hace público: antes, cambiar la IP de NetBird de `.env.example` por un ejemplo |
| D-64 | **Versión 1.0.0** el sábado 31-10: `main` pasa a ser la versión entregable | Sí |
| D-65 | **Aprobar la configuración de VALIDATE v1.0** (mapa de severidad, exclusiones, contadores, agrupación y disparo del cortacircuito). Hoy `validate.json` dice «propuesta; ninguno está decidido» | Sí, con los valores probados en el laboratorio. Detalle en `KRO-CHECKLIST-2026-10-26_github_100.md` (D2) |

---

## 3. Estado del producto (verificado)

| Componente | Estado | Evidencia |
| :--- | :---: | :--- |
| Servidor SOAR-CORE-01 (Contabo, NetBird, Docker) | ✅ | En operación |
| Detección: Wazuh 4.14.8 con 15 reglas de sobre | ✅ | Reglas 100101 a 100115 cargadas |
| Agentes: 001 EP-SRV-01 (Linux) y 002 EP-WKS-01 (Windows) | ✅ | `Active` al 21-10; llave del 001 regenerada |
| IA local: Ollama con qwen2.5:7b, dos pasos | ✅ | Mediciones del 06 y 14-10; inyección: ninguna de 10 cambió la familia con el 7B |
| VALIDATE: chequeos, `FAMILIA_NO_COINCIDE`, agrupación, plazo de 120 s, precalentamiento | ✅ | Desplegado el 21-10 (PR #36) |
| EXECUTE: usuario de API mínimo, prefijo `!` y `arguments` verificados | ✅ | Prueba del 20-10 |
| Bloqueo de IP con reversión automática a los 60 min (Linux) | ✅ | Ticket #20 (20-10) y prueba del 21-10 (60 min y 3 s) |
| NOTIFY por Telegram, con los tres y verificación en dos pasos | ✅ | Registro de Rodrigo del 21-10 |
| Consola por NetBird con contraseña y TOTP | ✅ | Tres cuentas |
| Base multiinquilino, cadena de hash, respaldo cifrado y restauración | ✅ | 2822 de 2822 eventos, 12 inquilinos y 0 cadenas rotas |
| Retención de alertas a 90 días (purga diaria) | ✅ | PR #34, desplegado el 21-10 |
| Recuperador de tickets huérfanos | 🟡 | PR #35 mezclado; su migración no estaba aplicada al 21-10 `[POR CONFIRMAR]` |
| Script `kronos-bloquear-ip` para Windows | 🟡 | PR #32 mezclado; **falta probarlo en EP-WKS-01** |
| Calidad del código | ✅ | **308 pruebas unitarias OK**, ruff OK y R1 OK (verificado hoy); 53 de integración según el registro de Rodrigo |
| Prueba de estrés de la Fase 1 (30 alertas en 10 min) | ❌ | No hecha. El cortacircuito cuenta las alertas procesadas, no las que llegan |
| Prueba de la ráfaga (agrupación) | ⏳ | Pendiente desde el 21-10 |

### Catálogo: qué medidas se pueden ejecutar de verdad

| Situación | Medidas | Cantidad |
| :--- | :--- | :---: |
| Con comando en EXECUTE **y** script en el agente | Bloquear IP: PB-F1-02, PB-F1-03, PB-F3-01, PB-F3-02 y PB-F6-02 | **5** |
| Con comando en EXECUTE, **sin script** | Aislar equipo (6), detener servicio (2), deshabilitar cuenta, cerrar sesión y terminar proceso | 11 |
| **Sin comando** | Consulta (3), cuarentena (3), bloquear destino, limitar conexiones y revertir tarea | 9 |

Hoy no se puede mostrar un nivel 3 ejecutado: todas las medidas de nivel 3 son aislar, cuarentena o detener servicio, y ninguna tiene script.

---

## 4. GitHub: incoherencias y faltantes (revisado el 26-10)

🔴 La comisión lo ve de inmediato · 🟡 Corregir esta semana · ⚪ Menor

| # | | Hallazgo | Arreglo | Quién |
| :-: | :-: | :--- | :--- | :--- |
| 1 | 🔴 | **`main` está vacía:** un solo commit del 06-10, con un README de 3 líneas, `.gitignore` y la configuración de pre-commit. Todo el trabajo (129 commits y 38 PR) está en `develop`. Quien abre el repositorio ve un proyecto vacío | PR de versión `develop` → `main` y etiqueta `v1.0.0` (D-64) | Rodrigo |
| 2 | 🔴 | **README de 3 líneas**, sin problema, solución, arquitectura, instalación, pruebas ni equipo | README completo, con resumen en inglés | Nicolás |
| 3 | 🔴 | **Sin etiquetas ni versiones publicadas.** La etiqueta `v0.4.0-laboratorio` que citan los documentos no existe | `v1.0.0` con notas de la versión | Rodrigo |
| 4 | 🔴 | **Dos juegos de documentos que no calzan.** `docs/entregables/` tiene los 17 Word v0.1 que el propio equipo declaró que no sirven. Los 31 oficiales están sólo en el Drive. El índice `docs/00-indice/README.md` apunta a los 17 | Publicar los 31 en PDF; archivar los 17 (D-62) | Rodrigo, con los 31 de cada uno |
| 5 | 🔴 | **186 menciones a la farmacia:** 74 en archivos Markdown y diagramas, y 112 en los 17 Word. Incluye `CONTRIBUTING.md` (el rol del Product Owner), el diagrama `15_ambientes` y `pendientes-farmacia.md` | Reemplazar por la PyME simulada; borrar `pendientes-farmacia.md` | Cada uno en sus archivos |
| 6 | 🟡 | **Guía de instalación: 2 de 15 partes** (06 y 08) | Completar con lo que ya está en los README y registros (sección 8) | Los tres |
| 7 | 🟡 | **README de una línea** en `docs/`, `infra/`, `decision/`, `validacion/`, `conectores/` y `tools/` | Una o dos frases con qué hay y el enlace a la guía | Cada dueño |
| 8 | 🟡 | **Contexto maestro del repositorio en v2.1 (14-10)**, distinto de la v3.1 del proyecto. Los dos giran en torno a la farmacia; también `preguntas-abiertas.md` | Moverlos a `docs/archivo/` como históricos; la puerta de entrada pasa a ser el README | Rodrigo |
| 9 | 🟡 | **La evidencia de Scrum está fuera del repositorio.** `docs/registro/` tiene 1 registro; los otros 14 (KRO-LOG, KRO-ESTADO, KRO-REV, KRO-ACTA y KRO-TAREAS) están sólo en el proyecto del asistente de IA. Hay 0 issues y 0 milestones | Subir los registros; milestone «v1.0» con las tareas de esta semana como issues | Rodrigo |
| 10 | 🟡 | **26 de 38 PR sin aprobación registrada** (#1 a #16 y #25 a #34). Desde la regla D-54 se cumple, salvo el #36, que mezcló su propio autor | Ya anotado como excepción R-04. Esta semana, cero excepciones | Los tres |
| 11 | 🟡 | **El aporte individual se ve desbalanceado en los commits:** Patricio 48, Rodrigo 37 y Nicolás 5. El trabajo de Nicolás (servidor, Wazuh, laboratorio y agentes) no quedó en el repositorio | La guía de instalación y el README los escribe Nicolás, con commits propios | Nicolás |
| 12 | 🟡 | **43 ramas remotas:** además de `main` y `develop`, 37 ya mezcladas y 4 con experimentos sin mezclar (mediciones del prompt v1, v2, confianza y servidor) | Borrar las mezcladas. Las 4 de experimentos: etiqueta de archivo y una línea en el registro de mediciones | Rodrigo y Patricio |
| 13 | 🟡 | **Catálogo y severidad no calzan:** PB-F6-04 y PB-F6-05 (nivel 3) nunca se pueden aplicar, porque las reglas F6 tienen severidad 7 y eso permite como máximo el nivel 1 | Documentarlo como decisión (o ajustar el nivel de la 100114) | Patricio |
| 14 | 🟡 | **Latencia:** los documentos comprometen «60 s como máximo»; el código ahora espera hasta 120 s | Explicar la meta (60 s; en la prueba real fueron 11 s) y el plazo (120 s antes de abstenerse) | Patricio |
| 15 | 🟡 | **Los avisos de Telegram usan jerga interna** («Medida: PB-F5-04 (nivel 3)», «D-35», «Inquilino 1»): no sirven a un encargado de TI generalista | Nombre de la medida en lenguaje claro, equipo afectado, qué pasará y qué hacer | Rodrigo |
| 16 | 🟡 | **El servidor no corre desde un clon de git** (D-55 pendiente). No se puede demostrar qué versión corre, y copiar desde Windows rompió permisos el 21-10 | Pasar a clon de git con etiquetas **el lunes**, antes de los demás despliegues | Rodrigo |
| 17 | ⚪ | El CI sólo corre en PR; omite las 13 pruebas de la consola (le faltan dependencias) y no corre las 53 de integración | Si sobra tiempo: instalar las dependencias de la consola en el CI | Rodrigo |
| 18 | ⚪ | Repositorio privado, sin descripción, temas ni licencia; `.env.example` trae la IP de NetBird del servidor | D-63 | Nicolás |
| 19 | 🟡 | **Códigos de decisión repetidos:** D-44 a D-46 significan una cosa en el contexto maestro del 15-10 (mensaje al profesor, los 31 documentos y la configuración de VALIDATE) y otra en el acta del 21-10 (playbooks de un paso, 60 minutos y 90 días). El error es mío: lo cometí al numerar el acta | Valen los del acta (ya se usan en `CONTRIBUTING.md`). En los documentos, las tres antiguas se citan por su texto, o como D-44a, D-45a y D-46a | Quien edite cada documento |

---

## 5. Alcance congelado de la versión 1.0

### Medidas con actuador real en la v1.0

| Medida | Nivel | Linux | Windows |
| :--- | :-: | :-: | :-: |
| Bloquear IP externa (PB-F1-02, PB-F3-01 y PB-F6-02) | 1 | ✅ | ⏳ probar |
| Bloquear IP de un equipo interno (PB-F1-03 y PB-F3-02) | 2 | ✅ | ⏳ probar |
| Deshabilitar la cuenta local (PB-F1-05) | 2 | — | ⏳ nuevo |
| Aislar un puesto de trabajo (PB-F3-03, PB-F4-02 y PB-F5-04) | 3 | — | ⏳ nuevo |

Con esto se muestran **los cuatro niveles en los dos sistemas operativos**, incluida la aprobación por Telegram.

### Queda fuera de la v1.0 (trabajo futuro, documentado)
- Las otras medidas del catálogo: cuarentena, consultas de nivel 0, bloquear destino, limitar conexiones, revertir tarea, cerrar sesión, terminar proceso y detener servicio. Si la IA elige una de ellas, el ticket termina en falla segura con aviso, que es un comportamiento defendible.
- Modo observación, volver a aplicar reglas tras un reinicio, alta disponibilidad, un grupo de Telegram por inquilino y vista de la consola por inquilino.
- Inquilino por grupo de Wazuh (D-49): sólo si sobra tiempo. Lo multiinquilino ya está probado en la base (RLS, dos inquilinos en paralelo y restauración con 12 inquilinos).

**Regla de la semana: nada fuera de esta lista.** Lo que aparezca va a «trabajo futuro» en el informe.

---

## 6. Escenarios de demostración

Se ensayan el **jueves 29-10** (prueba integral) y son los mismos de la defensa. Todos se generan sin dañar nada.

| # | Escenario | Equipo | Cómo se genera | Regla | Nivel esperado | Qué se muestra |
| :-: | :--- | :--- | :--- | :-: | :-: | :--- |
| E1 | Fuerza bruta por SSH desde internet | EP-SRV-01 | `logger` con la IP de documentación `203.0.113.50` | 100101 | 1 | Bloqueo automático y reversión a los 60 min |
| E2 | Fuerza bruta desde otro equipo de la red | EP-SRV-01 | `logger` con una IP interna que no sea la puerta de enlace (por ejemplo `192.168.50.20`) | 100101 | 2 | Bloqueo, aviso en Telegram y reversión desde la consola |
| E3 | Alguien adivina la contraseña de una cuenta | EP-WKS-01 | Inicios de sesión fallidos de una cuenta de prueba (no `Administrator`) | 100103 | 2 | Cuenta deshabilitada y aviso al encargado de TI |
| E4 | Alguien borra el registro de auditoría | EP-WKS-01 | Borrar el registro de seguridad (evento 1102) | 100113 | 3 | Aprobación en Telegram, aislamiento del puesto y reversión |
| E5 | Inyección de instrucciones en una alerta | EP-SRV-01 | Línea de registro con una orden para la IA (reutilizar ESC-04) | — | — | La IA no obedece; si la familia cambia, `FAMILIA_NO_COINCIDE` |
| E6 | Ráfaga de 30 alertas en 10 minutos | EP-SRV-01 | Bucle de `logger` | — | — | Cortacircuito abierto, nada se ejecuta; cierre desde la consola |
| E7 | Modelo caído (opcional) | Servidor | Detener Ollama un momento, coordinado | — | — | Falla segura: `MOTOR_INFERENCIA_NO_DISPONIBLE` |

**Antes del jueves:**
- **Patricio** comprueba con su herramienta de medición qué medida elige la IA para las alertas de E3 y E4. Así el ensayo no depende del azar.
- **Nicolás** confirma que EP-WKS-01 registra los inicios de sesión fallidos (evento 4625; revisar la política de auditoría).

**Métricas que se anotan en cada escenario:**
- tiempo de la alerta a la decisión;
- tiempo de la decisión a la ejecución;
- tiempo total;
- si acertó la familia y la medida;
- si la falla segura actuó cuando correspondía.

Van al documento 6.5 y al informe final.

---

## 7. Plan de la semana (lunes 26-10 a domingo 01-11)

### 7.1 Día a día

| Día | Nicolás (PO) | Patricio | Rodrigo (SM) | Juntos |
| :--- | :--- | :--- | :--- | :--- |
| **Lun 26** | Probar `kronos-bloquear-ip` de Windows en EP-WKS-01 (a mano y por la API; ¿encuentra el `.cmd` sin extensión?) → avisar a Rodrigo. Confirmar el nuevo alcance con el profesor y pedirle la guía y la rúbrica de la Fase 3 | Cortacircuito por alertas recibidas (PR → revisa Nicolás) | **Servidor como clon de git** (D-55) y migración del #35, si falta. Empezar `kronos-deshabilitar-cuenta` (Windows) | **Arranque, 30 min:** aprobar D-57 a D-65 en el chat principal |
| **Mar 27** | README y guía, partes 01 a 05 | Medir qué medida elige la IA en E1 a E4; etiquetar el playbook esperado en al menos 50 de los 150 casos | `kronos-deshabilitar-cuenta` → PR (revisa Patricio). Ajustar EXECUTE con `.cmd`, si el lunes hizo falta. Empezar `kronos-aislar-equipo` | Revisiones de PR el mismo día |
| **Mié 28** | Probar `deshabilitar-cuenta` y `aislar-equipo` en EP-WKS-01. Guía, partes 09, 10, 13 y 14 | Desplegar el cortacircuito (`git pull`). **Prueba de estrés y de ráfaga** con Nicolás | `kronos-aislar-equipo` → PR. **Avisos de Telegram en lenguaje claro** y nivel 0 sin aviso (D-50) → PR | Nicolás genera las alertas de la prueba de Patricio (1 h) |
| **Jue 29** | Generar los ataques E1 a E7 y capturar evidencia | Mirar VALIDATE y anotar las métricas | Desplegar la versión candidata (`git pull`) por la mañana. Mirar EXECUTE, NOTIFY y la consola | **Prueba integral, 2 a 3 h** (punto de encuentro 2) |
| **Vie 30** | Grabar el video de respaldo de la demo. Borrador de la presentación. Sus documentos de los 31 | Correcciones de la prueba. Sus documentos de los 31. Integrar el informe final, con resumen en inglés | Correcciones de la prueba. **Manual del encargado de TI.** Sus documentos de los 31 | Cada uno escribe sus secciones del informe |
| **Sáb 31** | Acta del replanteamiento. Revisión cruzada | Revisión cruzada | **Versión 1.0.0:** PR `develop` → `main`, etiqueta, notas, limpieza de ramas, subir los registros y archivar lo histórico | **Revisión final y primer ensayo cronometrado** (2 h) |
| **Dom 01** | Holgura | Holgura | Holgura | Cada uno trae su `KRO-LOG` al chat principal |

### 7.2 Quién espera a quién

| Espera | Qué | De quién | Para cuándo |
| :--- | :--- | :--- | :--- |
| Rodrigo | Resultado del `.cmd` sin extensión | Nicolás | Lun 26 |
| Patricio, Rodrigo | Servidor como clon de git (para desplegar con `git pull`) | Rodrigo | Lun 26 |
| Patricio | Aprobación del PR del cortacircuito | Nicolás | Mar 27 |
| Rodrigo | Aprobación de los PR de los scripts y los avisos | Patricio | El mismo día |
| Nicolás | Aprobación de los PR del README y la guía | Rodrigo | El mismo día |
| Nicolás | Scripts nuevos para probar | Rodrigo | Mar 27 y Mié 28 |
| Todos | Qué medida elige la IA en E3 y E4 | Patricio | Mar 27 |
| Patricio | Alertas generadas para la prueba de estrés | Nicolás | Mié 28 |
| Todos | Versión candidata desplegada | Rodrigo | Jue 29, por la mañana |
| Rodrigo | Aprobación del PR de versión `develop` → `main` | Nicolás **y** Patricio | Sáb 31 |

### 7.3 Reglas de la semana
- **Alcance congelado** (sección 5).
- **Regla de merge D-54 sin excepciones:** aprobación previa desde la cuenta personal, nunca mezcla el autor y nunca desde `soarai2026`. **Revisión el mismo día:** un PR que espera más de 12 horas se avisa por WhatsApp.
- **Servidor:** se avisa en el grupo de Telegram antes de desplegar, y despliega una sola persona a la vez. Desde el lunes, sólo con `git pull` y la etiqueta: no más copias desde Windows.
- **Avance diario por WhatsApp:** tres líneas (qué hice, qué sigue, qué me bloquea). Sirve además como evidencia de Scrum.
- **Redacción con el asistente de IA en cada chat, con revisión humana:** documentos, guía, README, manual e informe. Nadie entrega un texto que no leyó.
- **Laboratorio encendido** en las pruebas: el notebook enchufado y sin suspensión. Si una VM se apaga cuando vence una reversión, esta queda en `REVERSION_FALLIDA`.
- **No revertir todavía el HVCI** del PC de escritorio: EP-WKS-01 se necesita hasta la defensa.

### 7.4 Si el tiempo no alcanza

**Se corta en este orden:**
1. Inquilino por grupo.
2. Aislar en Linux.
3. Pruebas de integración en el CI.
4. E7.
5. Etiquetar más de 50 casos.

**No se negocia:**
- `main` con la v1.0.0 y un README completo;
- E1, E2, E3 y E4 funcionando;
- la prueba de estrés (E6);
- los 31 documentos sin la farmacia;
- el informe final;
- la presentación y el video de respaldo.

---

## 8. Documentos y entregables del cierre

| Entregable | Responsable | Base | Para |
| :--- | :--- | :--- | :--- |
| Acta del replanteamiento (D-57 a D-65) | Nicolás | Esta sección 2 | Sáb 31 |
| README completo, con resumen en inglés | Nicolás | Secciones 2 y 3 de este documento | Mar 27 |
| Guía de instalación, 15 partes | Los tres | README y registros que ya existen | Vie 30 |
| Manual del encargado de TI (nuevo; 6 a 8 páginas) | Rodrigo | Consola, avisos y niveles | Vie 30 |
| Los 31 documentos, sin farmacia ni marcas pendientes | Los tres (tabla de abajo) | Drive y `pendientes_entrega_2026-10-16.md` | Vie 30 |
| Informe final de Duoc, con apartados en inglés | Patricio integra; cada uno sus secciones | Guía de informe final (2.6) y guía de la Fase 3 | Vie 30 |
| Presentación, guion y video de respaldo de la demo | Nicolás, con secciones de cada uno | Escenarios de la sección 6 | Vie 30 (borrador) |
| Versión 1.0.0 y notas de la versión | Rodrigo | Esta semana | Sáb 31 |
| Documentos de la Fase 3 de Duoc (autoevaluación, diario y los que pidan) | Cada uno | **Subir las guías al proyecto** | Cuando las tengan |

### Guía de instalación (D-18): 15 partes y de dónde salen

| Parte | Tema | Quién | Base existente |
| :-: | :--- | :--- | :--- |
| 01 | Servidor y endurecimiento | Nicolás | Historial y registros |
| 02 | NetBird | Nicolás | Historial |
| 03 | Docker | Nicolás | Historial |
| 04 | Wazuh (compose, puertos y certificados) | Nicolás | `infra/wazuh/docker-compose.yml.example` |
| 05 | Reglas de sobre | Nicolás | `infra/wazuh/reglas/` |
| 06 | Ollama y modelo | Patricio | ✅ existe |
| 07 | Base SOAR-AUDIT y servicios | Rodrigo | `infra/docker/servicios/README.md` |
| 08 | Active Response y usuario de API | Nicolás | ✅ existe |
| 09 | Agente Linux | Nicolás | Registros del 15 y 21-10 |
| 10 | Agente Windows | Nicolás | Registro del 21-10 y `windows/README.md` |
| 11 | Telegram | Rodrigo | Registro del 21-10 |
| 12 | Respaldo, restauración y retención | Rodrigo | `respaldo/` y `retencion/` |
| 13 | Alta de una PyME (inquilino, exclusiones y redes) | Patricio y Nicolás | `validate.json` |
| 14 | Retiro de una PyME y desinstalación | Nicolás | Nuevo (corto) |
| 15 | Verificación de punta a punta | Patricio | Escenarios de la sección 6 |

### Los 31 documentos: quién actualiza cada uno

En todos se hace lo mismo:
- reemplazar la farmacia por la PyME simulada; las 20 marcas «PENDIENTE» se llenan con datos ficticios definidos por el equipo;
- resolver las «POR CONFIRMAR» que ya tienen respuesta (roles D-56, plazos D-45, retención D-46, verificación en dos pasos, `!` verificado, inquilino D-49 y demás);
- dejar las demás como limitación explícita.

| Nicolás | Patricio | Rodrigo |
| :--- | :--- | :--- |
| 1.1 FODA y PESTEL (reescribir para PyMEs) | 1.3 Carta Gantt (con el replanteamiento y el cierre) | 1.5 Minuta de kick-off |
| 1.2 Acta de constitución | 1.4 Scrum | 1.6 Plan de gestión |
| 2.1 Procesos AS-IS (la PyME sin especialista) | 1.7 EDT y RBS | 1.8 RACI |
| 2.7 Integraciones | 2.2 TO-BE | 1.9 Riesgos del proyecto |
| 3.2 Infraestructura, DRP y FinOps | 2.3 ERS | 2.5 Casos de uso |
| 5.1 Amenazas (STRIDE) | 2.4 Trazabilidad | 3.1 Arquitectura (4+1) |
| 5.2 Riesgos de seguridad | 2.6 Playbooks y runbooks | 4.2 Trazabilidad y HITL |
| 5.6 Respuesta a incidentes | 4.1 Motor de IA | 5.3 Políticas de seguridad |
| 6.2 Plan maestro de pruebas | 6.1 Calidad | 5.4 IAM |
| | 6.4 Pruebas deterministas | 5.5 Secretos |
| | 6.5 Carga, estrés y latencia | 6.3 Casos de prueba |

---

## 9. Lo que mirará la comisión: evidencias por competencia

Son los indicadores de calidad de la rúbrica de la Fase 2 (perfil de egreso de Ingeniería en Informática). Cada uno debe poder señalarse con un artefacto concreto.

| Indicador | Evidencia en Kronos | Estado |
| :--- | :--- | :-: |
| 1.1 Diseña pruebas de validación | Plan maestro (6.2), casos (6.3) y escenarios E1 a E7 | 🟡 |
| 1.2 Aplica pruebas de validación | 308 pruebas unitarias en el CI, 53 de integración, pruebas SQL, mediciones de la IA, prueba de estrés y prueba integral | 🟡 falta estrés e integral |
| 1.3 Desarrolla mejoras según los resultados | `FAMILIA_NO_COINCIDE` (mediciones), PR #36 (prueba del 20-10), recuperador de huérfanos y retención (revisión cruzada) | ✅ |
| 2.1 Planifica | Carta Gantt, Scrum, EDT y RACI; este plan | 🟡 actualizar |
| 2.2 Controla | KRO-LOG, actas, revisión cruzada y el replanteamiento por la retroalimentación del profesor | 🟡 subir al repositorio |
| 3.1 Diseña modelos de datos | Esquema de SOAR-AUDIT: multiinquilino, RLS y cadena de hash | ✅ |
| 3.2 Implementa modelos de datos | PostgreSQL desplegado, migraciones, respaldo y restauración probados, retención | ✅ |
| 4.1 Construye una solución de software | VALIDATE, EXECUTE, NOTIFY, CONSOLE y scripts de Active Response | 🟡 faltan 2 scripts |
| 4.2 Integra componentes | Wazuh ↔ VALIDATE ↔ Ollama ↔ PostgreSQL ↔ EXECUTE ↔ API de Wazuh ↔ agentes ↔ Telegram | ✅ |
| 4.3 Implanta la solución | Servidor en la nube, PyME simulada, v1.0.0 y guía de instalación | 🟡 v1.0 y guía |
| Inglés (indicador 8) | Resumen del informe y del README en inglés | ❌ |
| Ajustes justificados (indicador 1) | Acta del replanteamiento y su justificación en el informe | ❌ |

---

## 10. El mes restante (02-11 a la defensa)

| Semana | Objetivo |
| :--- | :--- |
| 02 al 08-11 | Prueba con un encargado de TI real (recomendada). Sólo corrección de errores, sin funciones nuevas. Informe en limpio, enviado al profesor guía para su revisión |
| 09 al 15-11 | **Estudio cruzado:** cada uno debe poder explicar los componentes de los otros dos. Banco de preguntas de la comisión y primer simulacro |
| 16 al 22-11 | Ensayo con el profesor guía; ajustes a la presentación |
| 23 al 29-11 | Dos o tres ensayos cronometrados. Revisar el servidor, los agentes y los respaldos; congelar todo |
| 30-11 en adelante | **Defensa ante la comisión** `[POR CONFIRMAR: fecha exacta]`. El contrato del servidor vence el 10-12 |

---

## 11. Riesgos de este plan

| Riesgo | Cómo se cubre |
| :--- | :--- |
| El servidor o la red fallan el día de la defensa | Video de respaldo de la demo y capturas; el servidor está contratado hasta el 10-12 |
| La IA elige otra medida en la demo | Patricio lo mide antes (martes). Si pasa, se muestra la falla segura, que también es parte del diseño |
| El laboratorio depende de los equipos de Nicolás (R-18) | Exportar EP-SRV-01 y EP-WKS-01 (OVA) a un disco y a un segundo integrante |
| No se alcanza todo en la semana | Orden de cortes de la sección 7.4 |
| El profesor espera algo distinto de la PyME simulada | Nicolás lo confirma con él el lunes, junto con la guía y la rúbrica de la Fase 3 |
| Se vuelven a mezclar PR sin revisión | Regla D-54 y revisión el mismo día; Rodrigo, como Scrum Master, lo vigila |
