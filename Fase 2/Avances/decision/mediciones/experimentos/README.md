# Experimentos que no se integraron

| Archivo | Qué es |
| :--- | :--- |
| `prompt-v2.patch` | Prompt v2 de Patricio (14-10-2026): reglas 4 y 6 y escala de confianza reescritas, con sus mediciones. Resultado negativo: empata con el prompt v1 y lo alarga unos 400 tokens. Detalle en [`../resultados/README.md`](../resultados/README.md), conclusión 4 |
| `prompt-v3.patch`, `prompt-v4-1b.patch`, `prompt-v4-2.patch` | Prompts del paso 2 probados el 05-11-2026 para E4 y las medidas sin su dato. Resultado negativo: ninguno iguala a quitar esas medidas del esquema (#68). El v4-2 acierta E4 sólo porque trae el caso escrito. Detalle en [`../resultados/README.md`](../resultados/README.md), conclusiones 18 a 20. Se aplican con `git apply` desde la raíz del repositorio |

El parche reemplaza a las ramas `feat/e2-mediciones-prompt-v2` y `feat/e2-prompt-confianza`. Para aplicarlo en
una rama aparte, desde la carpeta del proyecto (`Fase 2/Avances`):

```bash
git switch -c prueba-prompt-v2
git am --directory="Fase 2/Avances" decision/mediciones/experimentos/prompt-v2.patch
```
