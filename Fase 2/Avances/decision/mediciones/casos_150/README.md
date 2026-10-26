# Conjunto de 150 casos etiquetados

Conjunto de prueba para medir la clasificación de Kronos al cierre (etapa 5). Se construye
y se etiqueta **antes** de medir, y queda versionado, para demostrar que las respuestas no
se ajustaron después de ver los resultados.

## Archivos

- `alertas.json`: 150 alertas ficticias con la forma de `alerts.json` de Wazuh 4.14, cada
  una con la regla de sobre que la etiquetaría (100101 a 100115). Datos ficticios: IP sólo
  de 192.0.2.0/24, dominios `.example`, equipos y cuentas inventados.
- `generar.py`: pasa cada alerta por `validacion.alerta.preparar()` y escribe `casos.json`
  con el texto que verá el modelo (sin la etiqueta `kronos_fX`, con los campos recortados).
  Regenerar con `python -m decision.mediciones.casos_150.generar`.
- `casos.json`: los 150 casos para `medir_inferencia.py`.

## Etiquetas de cada caso

| Campo | Estado |
| :--- | :--- |
| `familia_esperada` | Puesta (F1 a F6) |
| `regla` | Puesta (regla de sobre que dispara) |
| `frontera` | En los casos ambiguos, las dos familias en juego |
| `playbook_esperado` | **Vacío**: se completa al cerrar KRO-CAT-01 |

## Qué se puede medir ya (sin el playbook)

- precisión del paso 1 (familia) sobre 150 casos;
- cuántas alertas coinciden con su regla de sobre y cuántas irían a revisión humana por
  `FAMILIA_NO_COINCIDE`.

## Qué falta

- **El playbook esperado** de cada caso. Con el catálogo cerrado (KRO-CAT-01 1.0) ya se
  puede etiquetar (#68); recién entonces se mide el paso 2 y la precisión de punta a punta.
- **Límite declarado:** en esta versión `familia_esperada` coincide con la familia de la
  regla de sobre en los 150 casos, así que la línea base sin IA acierta la familia por
  construcción. Es coherente con lo medido el 14-10: en la familia la regla ya acierta, y el
  aporte de la IA está en el paso 2 (el playbook). El campo `frontera` marca los casos en
  que el modelo tiende a discrepar, no la regla.

## Distribución

150 casos: F1 26, F2 26, F3 24, F4 16, F5 30, F6 28 (F4 y F6 tienen menos reglas de sobre).
11 casos ambiguos marcados con `frontera`. Las 15 reglas de sobre están cubiertas.
