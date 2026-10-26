# Decisión (SOAR-CLASSIFY)

Clasificación de una alerta en dos pasos con el modelo local: primero la familia (F1 a F6) y después la medida
dentro de esa familia. El modelo **sólo propone un identificador del catálogo**; el nivel lo fija el catálogo y la
propuesta la revisa SOAR-VALIDATE (`validacion/`) antes de que nada se ejecute.

**Regla R1:** este paquete no importa `ejecucion`, `persistencia` ni `conectores`. Lo comprueba
`tools/check_r1.py` en el CI.

| Archivo | Qué hace |
| :--- | :--- |
| `prompts/paso1_familia.txt` | Paso 1: las seis familias por comportamiento observable y reglas de desempate en orden fijo |
| `prompts/paso2_plantilla.txt` | Paso 2: la medida entre los candidatos de la familia. El bloque de candidatos se genera desde el catálogo |
| `catalogo/kro-cat-01.json` | Catálogo KRO-CAT-01: 25 medidas con familia, acción, nivel, reversión y efecto en la persona. Son datos versionados: no se cambian en caliente (R2) |
| `catalogo/generar_prompt.py` | Regenera el bloque de candidatos del paso 2 desde el catálogo. Una prueba falla si no coinciden |
| `inferencia.py` | Los dos pasos con un plazo total y falla segura: `MOTOR_INFERENCIA_NO_DISPONIBLE`, `TIEMPO_EXCEDIDO` o `ESQUEMA_INVALIDO` |
| `ollama.py` | Cliente de Ollama: temperatura 0, contexto de 4096, esquema JSON en `format` y el modelo siempre cargado (`keep_alive` -1) |
| `plantillas.py` | Carga de los prompts y del catálogo |
| `mediciones/` | Herramienta de medición, conjuntos de casos y resultados |

## Modelo y resultados

`qwen2.5:7b` en Ollama 0.40.0, en el propio servidor y sin GPU (instalación: parte 06 de la guía). Resumen de
las mediciones (detalle en `mediciones/resultados/README.md`):

- Paso 1: 19 de 20 casos originales y 18 de 18 alertas en formato real coinciden con su regla de sobre.
- Inyección: ninguno de los 10 ataques consiguió que el 7B eligiera la familia que buscaba; con el 3B, 4 de 10.
  Por eso se eligió el 7B.
- Unos 20 s por alerta con el modelo cargado y más de 60 s en frío; por eso el modelo queda siempre en memoria.
- La confianza que declara el modelo no separa aciertos de errores. El control fuerte es la coincidencia con la
  regla de sobre (`FAMILIA_NO_COINCIDE`, en `validacion/chequeos.py`).

Para repetir una medición: `python decision/mediciones/medir_inferencia.py qwen2.5:7b --condiciones tibio`, con
el túnel hacia el Ollama del servidor (parte 06 de la guía). No se ajusta un prompt con los mismos casos con que
se mide.
