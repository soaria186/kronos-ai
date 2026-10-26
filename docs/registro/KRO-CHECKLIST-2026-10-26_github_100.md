# KRO-CHECKLIST-2026-10-26 · GitHub al 100 %: lista de corrección

| Campo | Valor |
| :--- | :--- |
| Fecha | Lunes 26-10-2026 |
| Repositorio revisado | `soarai2026/kronos-ai`: todas las ramas y los 38 PR, clonado y probado hoy. `develop` está en `66d955e` (21-10); no hay cambios desde entonces |
| Complementa | `KRO-PLAN-2026-10-26_replanteamiento_pyme_y_cierre.md`, sección 4. Aquí está el detalle de cada corrección |
| Herramienta | `verificar_entrega.py` (adjunta): comprueba de forma automática 15 de estos puntos. **Hoy da 2 de 15** (sólo pasan las pruebas unitarias y R1) |

## Qué significa «100 %»
1. Todas las casillas de esta lista marcadas.
2. `python tools/verificar_entrega.py --pruebas` da **15 de 15**.
3. Los tres abren el repositorio como lo vería la comisión (sin sesión, si es público, o con la cuenta del profesor) y no encuentran nada que contradiga lo que van a decir en la defensa.

Cada punto dice **qué arreglar**, **cómo comprobarlo** y **quién y cuándo** (los días calzan con el plan de la semana).

---

## A. Portada: lo primero que ve la comisión

- [ ] **A1. `main` con el proyecto.**
  - Hoy: un solo commit del 06-10, con `README.md` de 3 líneas, `.gitignore` y `.pre-commit-config.yaml`. Todo el trabajo está en `develop` (129 commits y 38 PR).
  - Arreglo: PR `develop` → `main` llamado «Versión 1.0.0», con commit de merge (sin aplastar el historial).
  - Comprobar: `git ls-tree -r --name-only origin/main | wc -l` muestra más de 50 archivos, y la página del repositorio muestra el README nuevo.
  - **Rodrigo, sábado 31**, con la aprobación de Nicolás **y** de Patricio.
- [ ] **A2. Etiqueta y versión publicada.**
  - Hoy: no hay ninguna etiqueta. Los documentos citan `v0.4.0-laboratorio`, que no existe.
  - Arreglo: etiqueta `v1.0.0` en `main` y una versión publicada en GitHub con notas: qué hace, cómo instalarlo, evidencias y limitaciones conocidas.
  - Comprobar: `git tag -l` muestra `v1.0.0`, y la pestaña *Releases* tiene la versión.
  - **Rodrigo, sábado 31.**
- [ ] **A3. README completo.**
  - Hoy: 3 líneas en `develop`.
  - Secciones mínimas: problema (PyME sin especialista), solución, usuario (encargado de TI), cómo funciona (diagrama de flujo), componentes y tecnologías, estado de la v1.0 y limitaciones, instalación (enlace a la guía), pruebas (cómo correrlas y cuántas son), estructura del repositorio, equipo y roles, documentación (enlace a los 31) y **«English summary»**.
  - Comprobar: la herramienta exige al menos 60 líneas, 6 secciones y un título en inglés.
  - **Nicolás, martes 27.**
- [ ] **A4. `CHANGELOG.md`.**
  - Historia por sprint y versión, con los PR de cada uno: S1 infraestructura; S2 núcleo de decisión (#1 a #30); S3 respuesta y niveles (#31 a #38 y esta semana); v1.0.0.
  - **Rodrigo, sábado 31.**
- [ ] **A5. Licencia (D-63).**
  - Si el repositorio queda público: una licencia abierta (por ejemplo MIT). Si queda privado: «Todos los derechos reservados» o la que indique Duoc.
  - **Nicolás, al decidir D-63.**
- [ ] **A6. Ficha del repositorio («About»).**
  - Descripción en una línea y temas (`soar`, `wazuh`, `ollama`, `llm`, `cybersecurity`, `pyme`, `postgresql`, `fastapi`). Hoy está vacía.
  - Se edita desde la cuenta dueña, `soarai2026`.
  - **Nicolás, sábado 31.**
- [ ] **A7. Acceso de la comisión (D-63).**
  - El repositorio es privado y su dueño es una cuenta personal compartida (`soarai2026`).
  - **Opción 1:** invitar al profesor guía como colaborador de lectura.
  - **Opción 2, recomendada:** hacerlo público al publicar la v1.0, después de la sección F. Así se pueden activar gratis las **reglas de protección** de `main` y `develop` (una aprobación obligatoria, checks en verde, sin `force push`). Hoy GitHub no las permite porque el repositorio es privado y la cuenta es gratuita.
  - **Nicolás y Rodrigo.**

## B. Ramas, versiones e historial

- [ ] **B1. Borrar las 37 ramas ya mezcladas.**
  - Todas menos `main`, `develop` y las 4 de experimentos.
  - Activar *Settings → General → Automatically delete head branches*, para que no se vuelvan a acumular.
  - Comprobar: la herramienta da «sin ramas ya mezcladas».
  - **Rodrigo, sábado 31.**
- [ ] **B2. Las 4 ramas de experimentos.**
  - Ramas: `feat/e1-mediciones-servidor`, `feat/e2-mediciones-prompt-v1`, `feat/e2-mediciones-prompt-v2` y `feat/e2-prompt-confianza`.
  - Arreglo: etiqueta de archivo (por ejemplo `archivo/prompt-v2`), una línea en `decision/mediciones/resultados/README.md` con qué se probó y por qué no se integró, y después borrar las ramas.
  - **Patricio y Rodrigo, sábado 31.**
- [ ] **B3. Una sola forma de mezclar.**
  - Dejar habilitado sólo el commit de merge (desactivar *squash* y *rebase*), como dice el modelo de ramas.
  - **Rodrigo.**
- [ ] **B4. El modelo de ramas documentado no se cumplió.**
  - Problema: el diagrama `05_ramas` y `14_flujo_ci` (documento 05) dicen que cada etapa cerrada pasa a `main` con su etiqueta, y eso nunca se hizo.
  - Arreglo: corregir el texto y los diagramas («`main` recibe versiones: v1.0.0»).
  - Opcional: etiquetas retroactivas, rotuladas en su mensaje como creadas el 31-10 sobre el estado de esa fecha. Por ejemplo `v0.2.0` en el merge del #30 (fin del S2) y `v0.3.0` en `66d955e` (21-10).
  - **Rodrigo.**
- [ ] **B5. Dos commits de Rodrigo con coautoría de herramientas de IA** (`f825322` y `4bab070`).
  - Choca con tu preferencia, pero cambiarlos exige reescribir el historial de `develop` (`force push`), con riesgo para todos los clones. **No lo recomiendo.**
  - Lo coherente es declarar el uso de asistentes de IA en el informe, como lo pida Duoc.
  - **Rodrigo decide.**

## C. Documentación del repositorio

- [ ] **C1. Una sola estructura de `docs/`,** explicada en `docs/README.md` (hoy tiene 1 línea):

  | Carpeta | Contenido |
  | :--- | :--- |
  | `docs/entregables/` | Los 31 documentos en PDF, con un índice |
  | `docs/informe/` | Informe final de Duoc y manual del encargado de TI |
  | `docs/instalacion/` | Guía en 15 partes |
  | `docs/diagramas/` | Fuentes `.mmd` e imágenes |
  | `docs/evidencia/` | Pruebas del 08, 20 y 21-10 y la prueba integral del jueves |
  | `docs/registro/` | Registros de trabajo, actas, revisiones y planes |
  | `docs/archivo/` | Lo histórico, con un README que diga que no está vigente |

  **Rodrigo, sábado 31.**
- [ ] **C2. Los 31 documentos en PDF** en `docs/entregables/`, con su índice (número, nombre, responsable y versión).
  - Hoy hay 17 Word v0.1 que el propio equipo descartó, y el índice `docs/00-indice/README.md` apunta a ellos.
  - **Cada uno envía sus PDF el viernes 30 en la noche; Rodrigo los sube.**
- [ ] **C3. Archivar a `docs/archivo/`** los 17 Word v0.1, el contexto maestro v2.1, `docs/00-indice/README.md`, `preguntas-abiertas.md` y `pendientes-farmacia.md`.
  - **Rodrigo, sábado 31.**
- [ ] **C4. Guía de instalación en 15 partes** (tabla de la sección 8 del plan), cada una con su cabecera: responsable, revisor, versión y estado.
  - Hoy hay 2 (06 y 08).
  - Comprobar: la herramienta exige las partes 01 a 15.
  - **Los tres, hasta el viernes 30.**
- [ ] **C5. README de una línea (6).** Cada uno, con qué hay en la carpeta, cómo se usa y el enlace a la guía:
  - `conectores/` (Patricio): **corregir el texto**. Dice «SIEM, EDR, ticketing», pero sólo contiene el lector de `alerts.json`, y el diseño excluye a propósito EDR y ticketing.
  - `decision/` y `validacion/`: Patricio.
  - `docs/`, `infra/` y `tools/`: Rodrigo.
  - Comprobar: la herramienta da «ningún README de una línea».
- [ ] **C6. Registros de trabajo** en `docs/registro/`.
  - Hoy hay 1. Faltan los 14 del proyecto, más el plan, las tareas y el acta del 26-10.
  - **Antes de subirlos, quitar los identificadores de Telegram** (el id del grupo y los de cada integrante, que aparecen en `KRO-LOG-RR-2026-10-21`) y cualquier IP real.
  - **Rodrigo, sábado 31.**
- [ ] **C7. Evidencias** en `docs/evidencia/`: tickets #19 y #20 del 20-10, la reversión del 21-10, la prueba de estrés y la tabla de métricas y las capturas de la prueba integral, sin datos sensibles.
  - **Nicolás y Patricio, jueves 29 y viernes 30.**
- [ ] **C8. Diagramas desactualizados** (17 de 19 son del 14-10). Corregir el `.mmd` y volver a generar la imagen:

  | Diagrama | Qué está mal | Quién |
  | :--- | :--- | :--- |
  | `09_despliegue` | Dice que VALIDATE, EXECUTE, NOTIFY y CONSOLE están «pendientes» y la consola «(pendiente)» | Rodrigo (3.1) |
  | `15_ambientes` | «72 pruebas» (hoy 308), sistema «pendiente», «puerta para la farmacia» | Nicolás (6.2) |
  | `19_respaldo` | Temporizador «pendiente» y `restaurar_prueba.sh` «pendiente»; el script real es `probar_restauracion.sh` y la restauración está probada | Rodrigo (5.3) |
  | `02_casos_uso` y `02_tratamiento_niveles` | «Propuesta D-34», que ya está aceptada | Patricio (2.2 y 2.5) |
  | `14_flujo_ci` | «Tres checks»: son cuatro, con las pruebas unitarias | Rodrigo (6.1) |
  | `05_ramas` | Modelo que no se cumplió (B4) | Rodrigo |
  | `04_cronograma` | Plan del 25-09, sin el replanteamiento ni el cierre | Patricio (1.3) |
  | `diagramas/README.md` | Asocia cada figura con la numeración de los 17 Word; debe usar la de los 31 | Rodrigo |

- [ ] **C9. Textos que dicen «pendiente» de algo ya resuelto:**

  | Archivo | Qué dice | Qué debe decir | Quién |
  | :--- | :--- | :--- | :--- |
  | `docs/instalacion/08-active-response.md` (cabecera y lista final) | Reversión automática «pendiente» | Confirmada el 21-10: 60 min y 3 s | Nicolás |
  | `docs/instalacion/06-ollama.md` | Revisor «POR CONFIRMAR»; pendientes de Ollama y `kronos_inferencia` | Revisor real y estado actual (ver D5) | Patricio |
  | `ejecucion/README.md` | «Lo que falta en Wazuh (a cargo de Nicolás)» y «Por verificar: prefijo `!`» | Usuario de API creado; `!` verificado el 20-10; no hace falta `<command>` en el manager | Rodrigo |
  | `infra/wazuh/active-response/windows/README.md` | «Pendiente de verificar en EP-WKS-01» | Resultado de la prueba del lunes | Rodrigo, con el dato de Nicolás |
  | `notificacion/README.md` | Verificación en dos pasos «pendiente» | Activada en las tres cuentas (21-10) | Rodrigo |
  | `infra/docker/retencion/README.md` y `persistencia/README.md` | 90 días «(propuesta)» | Confirmado (D-46 del acta del 21-10) | Rodrigo |
  | `consola/README.md` | «Pendiente: vista del encargado del cliente» | Trabajo futuro (PyME) | Rodrigo |
  | `CONTRIBUTING.md` | Product Owner: «contacto con la farmacia» | «Visión del producto, alcance y prioridades» | Rodrigo |
  | `infra/docker/servicios/README.md` | «Mientras Ollama siga siendo el contenedor creado a mano…» | Estado real después de D5 | Nicolás y Patricio |

  Comprobar: la herramienta da «sin marcas de pendiente o por confirmar».

## D. Coherencia entre código, configuración y servidor

- [ ] **D1. Catálogo KRO-CAT-01 a la versión 1.0.**
  - Hoy: `0.2`, en estado `version_de_trabajo`, y en `puntos_abiertos` siguen preguntas ya decididas (60 min, D-45; un solo paso, D-44).
  - Arreglo:
    - estado `aprobado`, versión `1.0`;
    - puntos abiertos que reflejen la v1.0;
    - anotar qué medidas tienen actuador en la v1.0;
    - nota sobre PB-F6-04 y PB-F6-05, que la severidad de las reglas F6 (7) deja fuera de alcance.
  - **Patricio, jueves 29** (aprueba Nicolás).
- [ ] **D2. `validate.json` a la versión 1.0.**
  - Hoy: `0.2`, en estado `propuesta`, con la nota «Ninguno está decidido».
  - **Requiere una decisión de los tres** (agregar al arranque del lunes como D-65): aprobar el mapa de severidad, las exclusiones, los contadores, la agrupación y el disparo del cortacircuito.
  - Después: estado `aprobado` y la nota corregida.
  - **Patricio** (aprueba Nicolás).
- [ ] **D3. `infra/docker/servicios/.env.example`:**
  - agregar `KRONOS_PLAZO_SEGUNDOS`, que usa `servicios.yml` y no está en el ejemplo;
  - documentar `KRONOS_WAZUH_NOMBRE_SERVIDOR=localhost`: el certificado de la API de Wazuh dice CN `wazuh.com` y SAN `localhost` (comprobado el 20-10);
  - cambiar la IP de NetBird del servidor (la real) por un ejemplo.
  - **Rodrigo, miércoles 28.**
- [ ] **D4. La imagen de servicios se construye dos veces** (`validate` y `execute` tienen `build:`). Dejar `build` en uno y `pull_policy: never` en el otro, como en `notify`.
  - **Rodrigo.**
- [ ] **D5. Ollama del servidor distinto del repositorio.**
  - Problema: el repositorio dice Ollama 0.40.0 con `infra/ollama/docker-compose.yml`, pero según `06-ollama.md` y el README de servicios, el contenedor del servidor se creó a mano con una imagen sin versión fijada.
  - Comprobar en el servidor:
    ```
    sudo docker inspect ollama --format '{{.Config.Image}}'
    sudo docker exec ollama ollama --version
    ```
  - Después, una de dos: pasarlo al compose (borrando antes la red `kronos_inferencia` creada a mano) o documentar la versión real.
  - **Nicolás y Patricio, miércoles 28.**
- [ ] **D6. El servidor corre desde un clon de git en la etiqueta (D-55).**
  - Comprobar: `git -C <ruta de despliegue> describe --tags` muestra `v1.0.0-rc1` el jueves y `v1.0.0` después del sábado.
  - **Rodrigo.**
- [ ] **D7. Latencia.** Los documentos comprometen «60 s como máximo» y el código espera hasta 120 s. Explicar que la meta es 60 s (11 s en la prueba real del 20-10) y el plazo 120 s antes de abstenerse.
  - **Patricio, en 2.3, 4.1 y 6.5.**
- [ ] **D8. Códigos D-44 a D-46 repetidos** entre el contexto maestro del 15-10 y el acta del 21-10. Valen los del acta; las antiguas se citan por su texto.
  - **Cada uno en sus documentos.**
- [ ] **D9. Avisos de Telegram en lenguaje claro**, sin «PB-…», «D-35» ni «Inquilino 1». Es código, pero es lo que la comisión verá en la demo.
  - **Rodrigo, miércoles 28.**

## E. Proceso visible en GitHub (Scrum)

- [ ] **E1. Milestone «v1.0: cierre» con las tareas de esta semana como issues**, y cada PR que lo cierre con «Cierra #NN». Hoy hay 0 issues y 0 milestones: el backlog sólo existe en el proyecto del asistente de IA.
  - **Rodrigo, lunes 26** (o yo, si me lo piden).
- [ ] **E2. Plantilla de PR** (`.github/pull_request_template.md`) con: qué cambia, por qué, cómo se probó, checks y quién aprueba según D-54.
  - **Rodrigo.**
- [ ] **E3. Revisores automáticos** (`.github/CODEOWNERS`): cada carpeta pide la revisión de quien corresponde según la regla cruzada. Funciona si las cuentas personales tienen permiso de escritura.
  - **Rodrigo, opcional.**
- [ ] **E4. Cero excepciones desde ahora.** Hoy 26 de 38 PR no tienen aprobación registrada. Agregar el #36 (mezclado por su autor) a las excepciones de `CONTRIBUTING.md`.
  - Comprobar: cada PR desde el #39 tiene una aprobación de un integrante distinto del autor, y lo mezcló alguien que no es el autor, desde una cuenta personal.
  - **Rodrigo vigila.**

## F. Seguridad antes de abrirlo

- [x] **F1. Secretos en el historial:** gitleaks 8.30.1 sobre todas las ramas da **0 hallazgos** (comprobado hoy, 95 commits). Los 17 Word tampoco tienen IP reales ni claves. Repetir antes de publicar la versión.
- [ ] **F2.** IP de NetBird en `.env.example` (D3).
- [ ] **F3.** Registros y evidencias sin identificadores de Telegram, usuarios del servidor ni IP reales (C6 y C7).
- [ ] **F4. `SECURITY.md`** (cómo reportar un problema de seguridad). Opcional, si el repositorio queda público.
  - **Rodrigo.**

## G. CI y pruebas

- [ ] **G1. Que el CI corra las 13 pruebas de la consola.** Hoy se omiten porque el CI no instala sus dependencias. Hoy las corrí con ellas instaladas y pasan.
  - **Rodrigo, opcional.**
- [ ] **G2. `tools/verificar_entrega.py`** en el repositorio (PR de Rodrigo). Opcional: un job del CI que lo corra en los PR hacia `main`.
- [ ] **G3. Pruebas de integración en el CI**, con un servicio de PostgreSQL. Opcional.
- [ ] **G4. Cifras de pruebas en el README:**
  - 308 unitarias (verificadas hoy);
  - 53 de integración (registro de Rodrigo; repetir antes de publicar);
  - pruebas SQL a, b, c y d.

---

## Decisiones que necesita esta lista
- **D-63:** repositorio público o privado, y licencia. Recomiendo **público**, porque habilita las reglas de protección gratis.
- **D-65 (nueva):** aprobar la configuración de VALIDATE v1.0.
- **B5:** qué hacer con los dos commits con coautoría (recomiendo dejarlos).

## Orden de trabajo (calza con el plan)

| Día | Puntos |
| :--- | :--- |
| Lun 26 | E1 (milestone e issues); D-63 y D-65 en el arranque |
| Mar 27 | A3 (README) |
| Mié 28 | D3, D4, D5, D9 |
| Jue 29 | D1, D6 (`v1.0.0-rc1`), C7 (evidencia de la prueba integral) |
| Vie 30 | C2 (PDF), C4 (guía), C5, C8, C9, D2, D7 |
| Sáb 31 | C1, C3, C6, B1 a B4, E2, E4, A4, A5, A6, A1, A2, A7, F1 a F3. Al final, la herramienta debe dar **15 de 15** |
