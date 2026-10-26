# KRO-LOG-PG-2026-10-20 · Bloque A de Patricio (VALIDATE, pruebas, documentación)

Rama `feat/validate-mejoras-prueba-20-10` (desde `develop`, ddb81ef). Un solo PR; lo revisa Nicolás antes de mezclar. Estado: parche entregado, **sin desplegar**.

## Tarea 1 · Mejoras de VALIDATE (prueba del 20-10)
- **1a. Ámbito de la IP en el prompt del paso 2.** `RedesInternas.ambito()` dice si el origen es interna o externa; `decision/plantillas.py` agrega una nota (`NOTA_AMBITO`) sólo al paso 2. No se tocan los marcadores de la plantilla (la medición de inferencia sigue estable). El chequeo 3 sigue siendo la protección real; la nota sólo evita gastar decisiones de IA.
- **1b. Plazo de la IA 60 → 120 s.** `PLAZO_POR_OMISION = 120`, variable `KRONOS_PLAZO_SEGUNDOS` en `infra/docker/servicios.yml`. Además `ClienteOllama.precalentar()` carga el modelo al arrancar (`keep_alive=-1`).
- **1c. Exclusión de 10.0.50.1** (puerta de enlace NAT del laboratorio) en `validate.json` (versión 0.2).
- **1d. Agrupación.** Misma regla + IP de origen + equipo dentro de `agrupacion.ventana_minutos` (10) → un solo ticket y una sola decisión; las demás alertas quedan como evento `ALERTA_AGRUPADA` del ticket (sin migración: `auditoria.evento` no tiene CHECK). Esas alertas cuentan para el cortacircuito.

## Tarea 2 · Pruebas de integración fuera de la base real
- `tests/integracion/_base.py`: se niega a correr si el nombre de la base no termina en `_pruebas`.
- `tests/integracion/ejecutar.sh`: crea `kronos_pruebas`, copia el esquema, corre las pruebas en la red `kronos_interna` y la borra al terminar. Las contraseñas salen de `infra/docker/secrets/` y no aparecen en argumentos.
- Pruebas nuevas: agrupación (4 alertas → 1 ticket), cortacircuito con alertas agrupadas, agrupar en ticket de otro inquilino falla.
- Resultado local (PostgreSQL 16 desechable): 301 unitarias OK, ruff OK, R1 OK, 47 de integración OK (5 omitidas sin Ollama).
- Los tickets #1, #2 y #5 de la base real siguen ahí: limpiarlos es decisión del equipo.

## Tarea 3 · Documentación
- Doc 02 §8.1: siete estados (AWAITING_APPROVAL, D-38), nota con las decisiones (REJECTED, FAILED sin reintento, reversión como eventos REVERSION_*), motivos FAMILIA_NO_COINCIDE y APROBACION_VENCIDA en la Tabla 12, Figura 3 regenerada.
- `preguntas-abiertas.md`: quitadas las filas 6, 28, 38, 44 y 45. Total: 49 preguntas en 69 marcas.

## Pendientes y advertencias
- **Coordinar con Nicolás antes de desplegar en SOAR-CORE-01**: VALIDATE y EXECUTE están encendidos y actúan sobre EP-SRV-01. El PR se mezcla sólo con su aprobación.
- En el servidor, tras desplegar: `ollama ps` debe mostrar el modelo cargado «Forever»; en el log de VALIDATE buscar «cargando el modelo en memoria» y «agrupada».
- No se midió cómo responde el 7B con la nota de ámbito.
- Los grupos viven en memoria: se pierden al reiniciar; alertas sin IP de origen no se agrupan.
- Los documentos 09 §11, 17 §3 y 19 §3 y §4.1 aún llevan las marcas POR CONFIRMAR de las filas retiradas.
- La fila 3 (D-34) sigue en preguntas-abiertas; el doc 02 §8.1 ya la da por aceptada.
- Los documentos hablan de 60 s de latencia; el plazo ahora es 120 s.
