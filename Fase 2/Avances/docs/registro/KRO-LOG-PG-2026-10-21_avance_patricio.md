# KRO-LOG-PG-2026-10-21 · Avance de Patricio (decisión e IA)

Respuesta a `KRO-TAREAS-2026-10-21_patricio.md`. Corte: 21-10-2026, 22:10 (hora de Chile).

## 1. Tareas hechas y no hechas

| # | Tarea | Estado |
| :-: | :--- | :--- |
| 1 | PR de `feat/validate-mejoras-prueba-20-10` hacia `develop` | **Hecha.** PR #36, mezclado. |
| 2 | Revisar el PR #35 de Rodrigo | **Mezclado.** Revisión preparada: aprobar con un cambio menor (el comentario de `repositorio.py` dice 60 s y ahora son 120 s). Falta confirmar que mi aprobación quedó en GitHub desde mi cuenta personal. |
| 3 | Desplegar VALIDATE | **Hecha en el servidor** (21-10, 22:09). **Falta la prueba de la ráfaga con Nicolás** (otro día). Falta confirmar el aviso en Telegram. |
| 4 | Modo observación por inquilino (D-48) | No hecha |
| 5 | Inquilino por grupo de Wazuh (D-49) | No hecha. Espera el número de grupo e inquilino de Nicolás. |
| 6 | Cortacircuito por alertas recibidas | No hecha. El #36 ya cuenta las alertas agrupadas, pero sigue contando las que VALIDATE procesa, no las que llegan. |
| 7 | Catálogo y prompt de un solo paso; medir acierto del paso 2 con 7B | No hecha |
| 8 | Eventos de Windows para EP-WKS-01 | No hecha. Hay que decírselos a Nicolás. |
| 9 | `validate.json` de la farmacia | No hecha. Depende de los datos de Nicolás. |
| 10 | Documentos | **Parcial:** documento 02 §8.1 con los siete estados, motivos nuevos y Figura 3 (PR #36 y #38). Faltan D-44 a D-56, 60 s → 120 s, marcas POR CONFIRMAR de 09 §11, 17 §3 y 19 §3/§4.1, fila 3 (D-34), tickets #1, #2 y #5 como evidencia, y la fila de `DECISION_NO_REGISTRADA` en la Tabla 12. |

## 2. PR y su estado

| PR | Contenido | Estado |
| :-: | :--- | :--- |
| #36 | VALIDATE: nota de ámbito de IP, plazo 120 s con precalentamiento, exclusión de 10.0.50.1, agrupación de alertas; pruebas en `kronos_pruebas`; doc 02 §8.1 | Mezclado |
| #38 | Doc 02: estados del ticket y del cortacircuito al día con #35 y #36 | Mezclado |
| #35 (Rodrigo) | Recuperador de tickets huérfanos | Mezclado. **Aún no desplegado.** |

## 3. Resultados de las pruebas
- Antes del PR #36, en un sandbox con PostgreSQL 16 desechable: 301 pruebas unitarias OK, ruff OK, R1 OK, 47 de integración OK (5 omitidas sin Ollama).
- No se corrieron en el servidor ni con el modelo real.
- En el servidor tras el despliegue: log «cargando el modelo en memoria» y «en marcha para el inquilino 1»; `ollama ps` muestra qwen2.5:7b «Forever».
- **No medido:** el acierto del 7B con la nota de ámbito de IP; la ráfaga de alertas con agrupación.

## 4. Hallazgos
1. **Permisos al copiar desde Windows.** `scp` dejó `validacion/configuracion` en `drwx------`; el `COPY` del Dockerfile lo llevó a la imagen y VALIDATE no pudo leer `validate.json` (unos 3 minutos sin clasificar, de 22:05 a 22:09). Un `chmod` en el disco no bastó porque Docker reutilizó la capa en caché; se resolvió cambiando el contenido de `validacion/README.md`. Para el despliegue del #35: `chmod -R a+rX` tras copiar y comprobar con `docker run --rm --entrypoint ls <imagen> -ld /app/<carpeta>`.
2. **`/opt/kronos/audit` no es un clon de git** (D-55, de Rodrigo). El código se despliega copiándolo a mano: sólo `validacion`, `decision`, `persistencia` y `servicios.yml`. Respaldo en `/opt/kronos/audit.bak-2026-10-21`.
3. **El usuario de Patricio en el servidor está en `sudo`, no en `docker`.** Los comandos de Docker van con `sudo`.
4. **La tabla `alertas_guardadas` (PR #34) ya existía** en la base del servidor. La migración `2026-10-21_motivo_decision_no_registrada.sql` del #35 aún no se ha aplicado (es de Rodrigo).
5. **El cortacircuito mide la velocidad de procesamiento, no la de llegada** (hallazgo de Rodrigo en el #28).
6. Los grupos de agrupación viven en memoria y se pierden al reiniciar VALIDATE. Las alertas sin IP de origen no se agrupan.
7. Los documentos todavía hablan de 60 s de latencia; el plazo ahora es 120 s.

## 5. Lo que necesito de los otros
- **Nicolás:** estar conectado para la prueba de la ráfaga; aprobar los PR de las tareas 4 y 6; el grupo de Wazuh e inquilino de la farmacia (tarea 5); las redes y la puerta de enlace de la farmacia (tarea 9); decir si el Ollama del servidor se puede usar para la medición de la tarea 7.
- **Rodrigo:** desplegar el #35 (aplicar su migración, copiar `ejecucion` y `notificacion`); sumar el inquilino 2 en `KRONOS_INQUILINOS` de EXECUTE y NOTIFY cuando exista (tarea 5); dejar `/opt/kronos/audit` como clon con etiquetas (D-55).
- **De mi parte, para ellos:** avisar en Telegram que VALIDATE quedó desplegado y la lista de eventos de Windows (tarea 8).
