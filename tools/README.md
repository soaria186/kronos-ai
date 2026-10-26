# Herramientas

Scripts de apoyo al desarrollo. Sólo usan la biblioteca estándar de Python y git, y no modifican nada.

| Script | Qué hace | Dónde corre |
| :--- | :--- | :--- |
| `check_r1.py` | Regla R1: el código de `decision/` no importa `ejecucion`, `persistencia` ni `conectores`. Revisa `import`, `from … import`, imports relativos e imports dinámicos con nombre literal | Check «R1» del CI, en cada PR |
| `verificar_entrega.py` | Revisa que el repositorio esté listo para una entrega: `main` y la etiqueta v1.x, README, CHANGELOG, guía en 15 partes, sin farmacia ni marcas de pendiente, `.env.example` completo, catálogo y `validate.json` aprobados, sin ramas ya mezcladas y, con `--pruebas`, las pruebas unitarias y R1 | Job del CI en los PR hacia `main` (con `--antes-de-publicar`) |

```bash
python tools/check_r1.py
git fetch --all --tags --prune
python tools/verificar_entrega.py --pruebas
```

`verificar_entrega.py` termina con código 1 si falla alguna comprobación obligatoria y lista cuál y por qué.
Las marcadas «aviso» (licencia, una sola construcción de la imagen, IP de NetBird) no detienen la entrega.
