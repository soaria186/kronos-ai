# Diagramas

Fuente Mermaid (`.mmd`) e imagen (`.png`) de cada figura. La fuente es la que vale: la imagen se genera desde
ella y nunca se edita a mano.

El prefijo del archivo es el número del documento donde nació la figura, en los 17 documentos v0.1 del 14-10
(hoy en `docs/archivo/documentos-v0.1/`). La última columna dice en cuál de los 31 documentos del proyecto se
usa.

| Archivo | Figura | Documentos (de los 31) |
| :--- | :--- | :--- |
| `02_casos_uso` | Casos de uso: encargado de TI, equipo Kronos, agente y temporizador | 2.5 Casos de uso |
| `02_tratamiento_niveles` | Tratamiento de una decisión según su nivel | 2.2 Procesos TO-BE, 4.2 Trazabilidad y HITL |
| `02_estados_ticket` | Estados del ticket | 2.3 ERS, 3.1 Arquitectura |
| `02_estados_cortacircuito` | Estados del cortacircuito | 4.1 Motor de IA, 6.5 Carga y estrés |
| `03_ciclo_trabajo` | Ciclo de trabajo de un sprint | 1.4 Metodología Scrum |
| `04_cronograma` | Sprints, cierre y defensa | 1.3 Carta Gantt |
| `05_ramas` | Modelo de ramas y versiones | 6.1 Plan de calidad |
| `06_no_conformidades` | Tratamiento de una no conformidad | 6.1 Plan de calidad |
| `09_contexto` | Contexto de Kronos AI | 3.1 Arquitectura |
| `09_componentes` | Componentes | 3.1 Arquitectura |
| `09_dependencias_r1` | Regla de dependencias R1 | 3.1 Arquitectura, 6.1 Plan de calidad |
| `09_despliegue` | Despliegue en SOAR-CORE-01 | 3.1 Arquitectura, 3.2 Infraestructura |
| `09_flujo_alerta` | Flujo de una alerta | 2.2 Procesos TO-BE, 3.1 Arquitectura |
| `11_dos_pasos` | Clasificación en dos pasos | 4.1 Motor de IA |
| `14_flujo_ci` | Flujo de un cambio hasta `develop` y `main` | 6.1 Plan de calidad |
| `15_ambientes` | Niveles y ambientes de prueba | 6.2 Plan maestro de pruebas |
| `17_zonas_confianza` | Zonas de confianza | 5.1 Modelado de amenazas |
| `19_respaldo` | Respaldo, copia fuera del servidor, restauración y purga | 3.2 Infraestructura y DRP |
| `20_ciclo_secretos` | Ciclo de vida de un secreto | 5.5 Mínimo privilegio y secretos |

## Cómo regenerar las imágenes

`mermaid.json` fija el tema y los colores. Desde esta carpeta, con Docker:

```bash
docker run --rm -v "$PWD:/data" minlag/mermaid-cli:11.4.2 -i /data/09_flujo_alerta.mmd -o /data/09_flujo_alerta.png -s 2 -w 2400 -b white -c /data/mermaid.json
```

o con mermaid-cli instalado (`npm install -g @mermaid-js/mermaid-cli`):

```bash
mmdc -i 09_flujo_alerta.mmd -o 09_flujo_alerta.png -s 2 -w 2400 -b white -c mermaid.json
```

El cronograma (`04_cronograma`) se genera con `-w 800`. Después de cambiar una imagen hay que volver a insertarla
en el documento que la usa.
