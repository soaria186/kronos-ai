# Diagramas

Fuente Mermaid (`.mmd`) e imagen (`.png`) de cada figura de los documentos de `docs/entregables/`.
El prefijo del archivo es el número del documento que contiene la figura.

| Archivo | Figura | Documento |
| :--- | :--- | :--- |
| `02_casos_uso` | Casos de uso del sistema y sus actores | 02 |
| `02_tratamiento_niveles` | Tratamiento de una decisión según su nivel | 02 |
| `02_estados_ticket` | Estados del ticket | 02 |
| `02_estados_cortacircuito` | Estados del cortacircuito | 02 |
| `03_ciclo_trabajo` | Ciclo de trabajo de un sprint | 03 |
| `04_cronograma` | Calendario de los sprints | 04 |
| `05_ramas` | Modelo de ramas del repositorio | 05 |
| `06_no_conformidades` | Tratamiento de una no conformidad | 06 |
| `09_contexto` | Contexto de Kronos AI | 09 |
| `09_componentes` | Componentes | 09 |
| `09_dependencias_r1` | Regla de dependencias R1 | 09 |
| `09_despliegue` | Despliegue en SOAR-CORE-01 | 09 |
| `09_flujo_alerta` | Flujo de una alerta | 09 |
| `11_dos_pasos` | Clasificación en dos pasos | 11 |
| `14_flujo_ci` | Flujo de un cambio hasta `develop` y `main` | 14 |
| `15_ambientes` | Niveles y ambientes de prueba | 15 |
| `17_zonas_confianza` | Zonas de confianza | 17 |
| `19_respaldo` | Flujo del respaldo | 19 |
| `20_ciclo_secretos` | Ciclo de vida de un secreto | 20 |

## Cómo regenerar las imágenes

Con Docker, desde esta carpeta (`mermaid.json` fija el tema y los colores):

```bash
docker run --rm -v "$PWD:/data" minlag/mermaid-cli:11.4.2 -i /data/09_flujo_alerta.mmd -o /data/09_flujo_alerta.png -s 2 -w 2400 -b white -c /data/mermaid.json
```

El cronograma (`04_cronograma`) se genera con `-w 800`. Después de cambiar una imagen hay que volver a insertarla en el documento Word que la usa.
