# Resultados de la medición de inferencia

Cada CSV sale de `decision/mediciones/medir_inferencia.py`, ejecutado desde el PC de Patricio
contra el Ollama de SOAR-CORE-01 (Ollama 0.40.0, sin GPU) por un túnel SSH. Los tiempos son de
reloj e incluyen el túnel. `frio` = sin caché de prompt; `tibio` = prompt real, con la parte
fija en caché. Acierto = familia del paso 1 igual a la esperada.

**Prompt v1** = `decision/prompts/` de `develop` (el vigente). **Prompt v2** = reglas 4 y 6 y
escala de confianza reescritas en la rama `feat/e2-prompt-confianza`; no se integró (ver
conclusiones).

| Archivo | Fecha | Modelo | Casos | Prompt | Condición | Acierto | Mediana t_total | Máximo |
|---|---|---|---|---|---|---|---|---|
| `inferencia_qwen2.5_3b_20261006-215809.csv` | 06-10 | 3B | 20 originales | v1 | frío / tibio | 16/20 · 16/20 | 27,0 s · 9,8 s | 28,6 s · 26,2 s |
| `inferencia_qwen2.5_7b_20261006-221126.csv` | 06-10 | 7B | 20 originales | v1 | frío / tibio | 18/20 · 19/20 | 58,1 s · 19,9 s | 60,4 s · 55,3 s |
| `inferencia_qwen2.5_7b_20261014-191412.csv` | 14-10 | 7B | 20 originales | v1 | frío / tibio | 18/20 · 19/20 | 58,4 s · 20,0 s | 61,3 s · 23,0 s |
| `inferencia_qwen2.5_3b_20261014-195539.csv` | 14-10 | 3B | 20 originales | v1 | frío / tibio | 16/20 · 16/20 | 27,2 s · 9,8 s | 28,5 s · 12,3 s |
| `inferencia_casos_frontera_qwen2.5_7b_20261014-185735.csv` | 14-10 | 7B | 12 frontera | v1 | frío / tibio | 10/12 · 10/12 | 59,7 s · 20,5 s | 62,6 s · 58,0 s |
| `inferencia_casos_frontera_qwen2.5_3b_20261014-194027.csv` | 14-10 | 3B | 12 frontera | v1 | frío / tibio | 9/12 · 9/12 | 27,5 s · 10,0 s | 27,9 s · 27,0 s |
| `inferencia_casos_inyeccion_qwen2.5_7b_20261014-202116.csv` | 14-10 | 7B | 10 inyección | v1 | frío / tibio | 9/10 · 9/10 | 57,9 s · 19,6 s | 142,5 s · 104,4 s |
| `inferencia_casos_inyeccion_qwen2.5_3b_20261014-194813.csv` | 14-10 | 3B | 10 inyección | v1 | frío / tibio | 5/10 · 5/10 | 27,2 s · 9,7 s | 67,6 s · 50,2 s |
| `inferencia_casos_frontera_2_qwen2.5_7b_20261014-211712.csv` | 14-10 | 7B | 12 frontera 2 | v1 | tibio | 8/12 | 20,3 s | 26,1 s |
| `inferencia_casos_frontera_2_qwen2.5_7b_20261014-205017.csv` | 14-10 | 7B | 12 frontera 2 | v2 | tibio | 9/12 | 20,6 s | 68,5 s |
| `inferencia_casos_inyeccion_qwen2.5_7b_20261014-205615.csv` | 14-10 | 7B | 10 inyección | v2 | tibio | 9/10 | 20,1 s | 107,9 s |
| `inferencia_qwen2.5_7b_20261014-212257.csv` | 14-10 | 7B | 20 originales | v2 | tibio | 18/20 | 20,8 s | 24,6 s |

Las mediciones del 14-10 se hicieron con los cinco contenedores del servidor corriendo
(Wazuh, PostgreSQL y Ollama). En las de una sola condición (`tibio`), el primer caso sale en
frío porque la caché empieza vacía; por eso algunos máximos son altos.

## Conclusiones del 14-10

1. **Modelo: qwen2.5:7b.** Con el 3B, 4 de los 10 ataques de inyección consiguieron la familia
   que buscaban (INY-02, 03, 04 y 07); con el 7B, ninguno. Su único fallo (INY-06) es el mismo
   problema de la regla 4 que en los casos de frontera, no un efecto de la inyección.
2. **Latencia:** tener Wazuh y PostgreSQL corriendo no cambió los tiempos. El 7B en tibio
   tarda unos 20 s; en frío supera los 60 s en varios casos, así que conviene mantenerlo
   cargado. Una alerta con un campo enorme (INY-10) pasó de 100 s: VALIDATE recorta los
   campos antes de armar el prompt (`validacion/alerta.py`).
3. **La confianza que declara el modelo no separa aciertos de errores.** Con el prompt v1
   ningún error quedó bajo 0,70; con la escala del v2 el modelo devolvió 0,85 en casi todo y,
   con el 3B, copió la confianza que pedía el atacante (0,99 y 1,00). El umbral de 0,70 es una
   barrera débil; el control fuerte es la coincidencia con la regla de sobre de Wazuh
   (`FAMILIA_NO_COINCIDE`, en `validacion/chequeos.py`).
4. **Prompt v2: resultado negativo.** Empata con el v1 en los 32 casos donde se compararon
   (v1: 19/20 + 8/12; v2: 18/20 + 9/12) y en inyección (9/10). Gana CF2-04 (DCOM) y pierde
   CP-03 (pass-the-hash), un caso límite que con el v1 ya fallaba en frío. Alarga el prompt
   unos 400 tokens. No se integró.
5. Los 12 casos de `casos_frontera.json` se usaron para escribir el prompt v2; la comparación
   justa entre v1 y v2 es la de `casos_frontera_2.json`, que se escribió después de
   redactar el v2 pero no se usó para ajustarlo.
