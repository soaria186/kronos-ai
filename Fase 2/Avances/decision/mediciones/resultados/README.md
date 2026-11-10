# Resultados de la medición de inferencia

Cada CSV sale de `decision/mediciones/medir_inferencia.py`, ejecutado desde el PC de Patricio
contra el Ollama de SOAR-CORE-01 (Ollama 0.40.0, sin GPU) por un túnel SSH. Los tiempos son de
reloj e incluyen el túnel. `frio` = sin caché de prompt; `tibio` = prompt real, con la parte
fija en caché. Acierto = familia del paso 1 igual a la esperada.

**Prompt v1** = `decision/prompts/` de `develop` (el vigente). **Prompt KRO-CAT-01** = el paso 2 con los candidatos y condiciones de uso generados desde `decision/catalogo/kro-cat-01.json` (el v1 usaba un catálogo provisional con los mismos identificadores y otro significado). **Prompt v2** = reglas 4 y 6 y
escala de confianza reescritas en la rama `feat/e2-prompt-confianza`, guardada en
[`../experimentos/prompt-v2.patch`](../experimentos/prompt-v2.patch); no se integró (ver conclusiones).

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
| `inferencia_casos_formato_wazuh_qwen2.5_7b_20261014-215235.csv` | 14-10 | 7B | 18 en formato real | v1 | tibio | 18/18 | 15,6 s | 22,9 s |
| `inferencia_casos_qwen2.5_7b_20261015-204009.csv` | 15-10 | 7B | 150 (`casos_150`) | KRO-CAT-01 | tibio | 150/150 | 13,6 s | 25,6 s |

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

## Alertas en formato real (14-10)

`casos_formato_wazuh.json` sale de `alertas_formato_wazuh.json` (18 alertas con la forma de
`alerts.json`, una o dos por cada una de las 15 reglas de sobre) pasado por
`validacion.alerta.preparar()`: el modelo ve el texto de producción, sin la etiqueta
`kronos_fX` y con la descripción de la regla de sobre en lugar de la nativa. Aquí el acierto
es la **coincidencia con la regla de sobre**: las alertas que coinciden se pueden
automatizar; las demás irían a revisión humana por `FAMILIA_NO_COINCIDE`.

6. **18 de 18 coinciden.** El chequeo de coincidencia no frena las alertas típicas de cada
   regla, y quitar la descripción nativa no le quita al modelo el contexto que necesita.
   Mediana de 15,6 s: las alertas reales son más cortas que los casos de prueba.
7. **Límite de esta medición:** la descripción de la regla de sobre ya sugiere la familia
   («fuerza bruta…», «archivo vigilado modificado…») y las 18 alertas son casos típicos, así
   que el 100 % no mide la capacidad del modelo por sí solo; eso lo miden los casos de
   frontera y de inyección. En la familia, la regla de sobre decide y el modelo es un segundo
   voto que detecta los casos raros; su aporte principal es el paso 2, elegir el playbook
   dentro de la familia, que ninguna regla de Wazuh hace.

## Paso 2 con el catálogo real, 150 casos (15-10)

`casos_150/casos.json` con el prompt generado desde KRO-CAT-01 (5 candidatos en F1, F5 y F6;
3 en F2 y F4; 4 en F3). El paso 1 no cambió. Los casos no traen `playbook_esperado`, así que
**esta medición no dice si el paso 2 acierta**: solo qué elige, con qué confianza y cuánto
tarda.

8. **Tiempo:** mediana 13,6 s, p90 15,1 s, JSON válido 150 de 150. Más candidatos no alargaron
   el paso 2; las alertas reales son más cortas que los casos de prueba.
9. **Qué elige:** consulta de solo lectura (nivel 0) 57 casos; nivel 1, 71; nivel 2, 5;
   nivel 3, 17 (todos PB-F5-03, esperan aprobación). Nunca eligió 13 de los 25 playbooks.
10. **Confianza:** la menor de los dos pasos fue 0,8 en 82 casos, 0,7 en 59, 0,6 en uno y 0,0
    en ocho (F5-01 uno y F5-03 siete, que el chequeo rechaza). Pasan el umbral 141 de 150; 75
    de ellos serían medidas automáticas (nivel 1 o 2).
11. **F3 no discrimina:** los 24 casos de F3 eligieron PB-F3-01 (bloquear una IP *externa*) con
    confianza 0,7 exacta, el tope que fija la regla de desempate del paso 1, y 0,7 pasa el
    umbral. 16 de ellos son la regla 100108 (ejecución remota entre equipos, tipo PsExec), que
    por las condiciones de uso pediría bloquear un equipo interno o aislarlo. Hoy esos 24
    casos terminarían en un bloqueo automático de IP. Las alertas no dicen si una IP es
    externa, así que el prompt no puede distinguirlo; falta decidir si se resuelve con un
    chequeo determinista sobre la IP o con otras condiciones de uso.

    **Resolución:** VALIDATE comprueba el ámbito de la IP (`ambito_ip` en el catálogo y
    `redes_internas` en `validate.json`): PB-F1-02 y PB-F3-01 exigen una IP externa; PB-F1-03 y
    PB-F3-02, una interna. Con IP interna, F3-01 se rechaza y el caso va a revisión humana. Las
    IP de `casos_150` son del rango de documentación 192.0.2.0/24, que cuenta como externa, así
    que esta medición no cambia; el efecto real depende de las IP de cada cliente.

## E3 y E4 con las alertas reales de la prueba integral (D-67)

`escenarios_e3_e4_reales_qwen2.5_7b_20261104.csv`, del 04-11. Lo generó `tools/medir_escenarios.py --alertas` desde el PC de
Patricio contra el Ollama de SOAR-CORE-01 (0.40.0, qwen2.5:7b), con 5 repeticiones. Usó las alertas reales de los tickets #35 (E3, regla 100103, cuenta bloqueada en EP-WKS-01) y #36 (E4, regla 100113, registro de auditoría borrado en EP-WKS-01), tal como quedaron en `alertas_guardadas` el 03-11. El archivo de alertas no está en el repositorio porque trae datos del laboratorio. **No se cambió el prompt.**

| Escenario | Esperada | Eligió | Nivel | Confianza (paso 1 / paso 2) | VALIDATE | Coincide |
| :-: | :--- | :--- | :-: | :-: | :--- | :-: |
| E3 | PB-F1-05 (deshabilitar la cuenta) | PB-F1-05 las 5 veces | 2 | 0,8 / 0,8 | aprobada | 5/5 |
| E4 | PB-F5-04 (aislar un equipo de trabajo) | PB-F5-03 (cuarentena de un archivo) las 5 veces | 3 | 0,8 / 0,8 | aprobada | 0/5 |

Tiempo: la primera repetición de cada escenario tardó unos 50 s, porque el prompt de esa alerta todavía no estaba en caché; las demás, entre 8,2 y 8,7 s.

12. **E3 acierta y es estable:** con la alerta real elige deshabilitar la cuenta, de nivel 2 y automática, igual que en la prueba integral del 03-11.
13. **E4 es estable, pero elige otra medida:** las 5 veces eligió PB-F5-03, aunque la condición de uso de PB-F5-04 nombra el caso («registros de auditoría borrados, en un EQUIPO DE TRABAJO»). Es el mismo sesgo de la conclusión 9, donde todos los casos de nivel 3 de `casos_150` fueron PB-F5-03. Es una falla segura: las dos medidas son de nivel 3 y esperan la aprobación del encargado de TI. La alerta no trae un archivo, así que, aprobada, la cuarentena termina en `ARGUMENTO_FALTANTE` sin tocar el equipo. El resultado es que el equipo no se aísla aunque el encargado de TI apruebe. Queda para decidir entre los tres, sin cambiar el prompt antes de la v1.0 (D-67): dejarlo como limitación documentada o, después de la v1.0, un chequeo determinista que lleve la regla 100113 en un equipo de trabajo a PB-F5-04.

## Ramas de experimentos archivadas

Las cuatro ramas de las mediciones del 14-10 se integraron aquí para poder borrarlas sin perder nada. Sus datos
(casos y CSV) ya estaban en el proyecto desde el #12; lo único que no se integró es el prompt v2, que queda con
sus 6 commits en [`../experimentos/prompt-v2.patch`](../experimentos/prompt-v2.patch).

| Rama | Qué se probó | Por qué no se integró |
| :--- | :--- | :--- |
| `feat/e1-mediciones-servidor` | Casos de frontera y de inyección en el servidor, con todos los servicios corriendo | Sus datos entraron con el #12 |
| `feat/e2-mediciones-prompt-v1` | Prompt v1 con el segundo conjunto de frontera | Sus datos entraron con el #12 |
| `feat/e2-mediciones-prompt-v2` | Prompt v2 con el 7B: 20 casos originales, frontera 2 e inyección | Resultado negativo (conclusión 4). Es el parche |
| `feat/e2-prompt-confianza` | Prompt v2: reglas 4 y 6 y escala de confianza reescritas | Resultado negativo (conclusión 4). Sus commits están en el parche |

Para revisar el prompt v2 sin tocar el proyecto: `git apply --stat ../experimentos/prompt-v2.patch` muestra qué
cambia, y `git am` en una rama aparte lo aplica con sus autores y fechas.

## Paso 2 sólo con medidas aplicables (propuesta del 04-11)

Desde E4 con la alerta real (#67), el modelo elegía la cuarentena (PB-F5-03) para un registro de auditoría borrado,
y esa alerta no trae archivo: EXECUTE la terminaba en `ARGUMENTO_FALTANTE`. La propuesta es que VALIDATE quite del
**esquema de la respuesta** del paso 2 las medidas cuyo dato no viene en la alerta (`ejecucion.ordenes.falta_argumento`).
El texto del prompt no cambia. Con temperature = 0, si el modelo iba a elegir una medida posible, elige la misma.

Medido el 04-11 desde el PC de Patricio contra el Ollama de SOAR-CORE-01 (qwen2.5:7b). Se usaron los 71 casos de
`casos_150` en los que cambia el esquema (`tools/medir_sin_datos.py`), una vez en `develop` y otra con el cambio:
`sin_datos_antes_qwen2.5_7b_20261104.csv` y `sin_datos_despues_qwen2.5_7b_20261104.csv`.

| | Antes | Después |
| :--- | :-: | :-: |
| Medida elegida sin su dato (`ARGUMENTO_FALTANTE`) | 32 de 71 | **0 de 71** |
| Casos con otra respuesta | — | 32, justo los que antes eran imposibles |

| Antes → después | Casos | Qué cambia |
| :--- | :-: | :--- |
| PB-F5-03 → PB-F5-05 | 10 | De una cuarentena sin archivo a aislar un servidor (nivel 3). 8 son la regla 100111, cuenta nueva o usuario en sudo |
| PB-F3-01 → PB-F3-03 / PB-F3-04 | 8 / 4 | Movimiento lateral sin IP de origen: de bloquear la IP a aislar el equipo (nivel 3) |
| PB-F5-01 → PB-F5-02 | 5 | Persistencia sin archivo: de la cuarentena a revertir la tarea (nivel 1) |
| PB-F4-01 → PB-F4-02 | 3 | Salida sin IP de destino: de bloquear el destino a aislar el equipo (nivel 3) |
| PB-F2-03 → PB-F2-01 | 1 | Proceso sin PID: de terminarlo a reunir contexto (nivel 0) |
| PB-F5-01 → PB-F5-05 | 1 | Persistencia sin archivo: a aislar un servidor (nivel 3) |

Con las alertas reales, E3 sigue en PB-F1-05 (5/5). E4 pasa de PB-F5-03, que fallaba, a **PB-F5-05**, aislar un
servidor (5/5, nivel 3, con script en Windows). Los tiempos no cambian: unos 50 s la primera vez y 8 s las demás.

14. **Ninguna medida imposible, sin efectos laterales:** los 39 casos con una medida posible no cambiaron. Una primera
    versión quitaba las medidas también del texto del prompt. Esa versión acertaba E4 (PB-F5-04), pero 8 casos de F2
    bajaban de la cuarentena, que sí era posible, a una consulta de nivel 0. Por eso se descartó.
15. **Lo que sube de nivel pide aprobación:** 16 casos pasan de una medida de nivel 1 que fallaba (no hacía nada) a
    aislar el equipo, que es de nivel 3 y espera la aprobación del encargado de TI. En F3 coincide con lo que la
    conclusión 11 decía que correspondía.
16. **Puesto o servidor:** el modelo no distingue el tipo de equipo. E4 ocurre en un puesto (EP-WKS-01) y elige
    PB-F5-05 (servidor) en vez de PB-F5-04 (puesto). Las dos medidas ejecutan lo mismo (`aislar_equipo` sobre el equipo de la alerta),
    así que el efecto es el correcto. Lo que queda mal es el nombre de la medida en el ticket y en el aviso. Los
    arquetipos del catálogo (`puesto` y `servidor`) permitirían filtrar también por tipo de equipo, con un mapa de
    equipos por PyME. Queda como mejora.
17. **Vacío del catálogo:** para una cuenta nueva o un usuario agregado a sudo (regla 100111), F5 no tiene una medida
    proporcionada. Hoy se propone aislar el servidor, con aprobación.
