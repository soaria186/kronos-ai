# Experimentos que no se integraron

| Archivo | Qué es |
| :--- | :--- |
| `prompt-v2.patch` | Prompt v2 de Patricio (14-10-2026): reglas 4 y 6 y escala de confianza reescritas, con sus mediciones. Resultado negativo: empata con el prompt v1 y lo alarga unos 400 tokens. Detalle en [`../resultados/README.md`](../resultados/README.md), conclusión 4 |

El parche reemplaza a las ramas `feat/e2-mediciones-prompt-v2` y `feat/e2-prompt-confianza`. Para aplicarlo en
una rama aparte, desde la carpeta del proyecto (`Fase 2/Avances`):

```bash
git switch -c prueba-prompt-v2
git am --directory="Fase 2/Avances" decision/mediciones/experimentos/prompt-v2.patch
```
