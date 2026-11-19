# Documentos de evidencia

Un archivo por cada documento que puede pedir la revisión del proyecto, ordenado por categoría. Sirve para
indicar dónde está cada uno sin buscarlo entre las carpetas de `Documentacion/`.

| Categoría | Documento | Archivo | Origen |
| :--- | :--- | :--- | :--- |
| Proyecto | Documento de inicio de proyecto | [`01-Proyecto/Documento de inicio de proyecto.docx`](01-Proyecto/Documento%20de%20inicio%20de%20proyecto.docx) | Copia de [`Gestion/Acta-Constitucion.docx`](../Gestion/Acta-Constitucion.docx) (1.2) |
| Metodología | Metodología declarada y justificada | [`02-Metodologia/Metodología declarada y justificada.docx`](02-Metodologia/Metodolog%C3%ADa%20declarada%20y%20justificada.docx) | Copia de [`Gestion/Scrum.docx`](../Gestion/Scrum.docx) (1.4) |
| Metodología ágil | Product Vision | [`03-Metodologia-agil/Product Vision.docx`](03-Metodologia-agil/Product%20Vision.docx) | Documento propio |
| Metodología ágil | Product Backlog | [`03-Metodologia-agil/Product Backlog.docx`](03-Metodologia-agil/Product%20Backlog.docx) | Documento propio, desde los issues del milestone «v1.0: cierre» y el historial de GitHub |
| Metodología ágil | Sprint Backlog | [`03-Metodologia-agil/Sprint Backlog.docx`](03-Metodologia-agil/Sprint%20Backlog.docx) | Documento propio, desde el CHANGELOG y el documento 1.4 |
| Metodología ágil | Definition of Done | [`03-Metodologia-agil/Definition of Done.docx`](03-Metodologia-agil/Definition%20of%20Done.docx) | Documento propio, desde la sección 8 del documento 1.4 y `CONTRIBUTING.md` |
| Metodología ágil | Retrospectivas | [`03-Metodologia-agil/Retrospectivas.docx`](03-Metodologia-agil/Retrospectivas.docx) | Documento propio, desde las actas y el registro de decisiones |
| Cascada | SRS (especificación de requisitos) | [`04-Cascada/SRS (especificación de requisitos).docx`](04-Cascada/SRS%20%28especificaci%C3%B3n%20de%20requisitos%29.docx) | Copia de [`Requerimientos/ERS.docx`](../Requerimientos/ERS.docx) (2.3) |
| Documentación técnica | README del repositorio | [`05-Documentacion-tecnica/README del repositorio.md`](05-Documentacion-tecnica/README%20del%20repositorio.md) | Copia de [`README.md`](../../README.md) de la raíz |
| Documentación técnica | Arquitectura | [`05-Documentacion-tecnica/Arquitectura.docx`](05-Documentacion-tecnica/Arquitectura.docx) | Copia de [`Arquitectura/SAD.docx`](../Arquitectura/SAD.docx) (3.1) |
| Documentación técnica | Modelo de datos | [`05-Documentacion-tecnica/Modelo de datos.docx`](05-Documentacion-tecnica/Modelo%20de%20datos.docx) | Documento propio, desde el esquema de SOAR-AUDIT y el documento 3.1 |
| Documentación técnica | Diagramas UML | [`05-Documentacion-tecnica/Diagramas UML.docx`](05-Documentacion-tecnica/Diagramas%20UML.docx) | Documento propio, con los diagramas de `Fase 2/Avances/docs/diagramas` |
| Documentación técnica | Requisitos no funcionales | [`05-Documentacion-tecnica/Requisitos no funcionales.docx`](05-Documentacion-tecnica/Requisitos%20no%20funcionales.docx) | Documento propio, desde la sección 4 del documento 2.3, con el estado al cierre |
| Documentación técnica | Docker | [`05-Documentacion-tecnica/Docker.docx`](05-Documentacion-tecnica/Docker.docx) | Documento propio, desde `Fase 2/Avances/infra` |
| Documentación técnica | Pruebas | [`05-Documentacion-tecnica/Pruebas.docx`](05-Documentacion-tecnica/Pruebas.docx) | Copia de [`Calidad/Pruebas Generales.docx`](../Calidad/Pruebas%20Generales.docx) (6.2) |
| Documentación técnica | Manual técnico | [`05-Documentacion-tecnica/Manual técnico.docx`](05-Documentacion-tecnica/Manual%20t%C3%A9cnico.docx) | Documento propio, desde la guía de instalación y los documentos 3.1 y 3.2 |
| Documentación técnica | Innovación | [`05-Documentacion-tecnica/Innovación.docx`](05-Documentacion-tecnica/Innovaci%C3%B3n.docx) | Documento propio |

## Copias y originales

- Las copias son iguales a su original al 12-11-2026. **El original manda**: si cambia, se vuelve a copiar.
- Los documentos propios se editan aquí, con el mismo formato y control de versiones que los 31 documentos.
- Para volver a copiar los originales, desde la raíz del repositorio (PowerShell):

```powershell
$E = 'Documentacion\Documentos-Evidencias'
Copy-Item 'Documentacion\Gestion\Acta-Constitucion.docx' "$E\01-Proyecto\Documento de inicio de proyecto.docx"
Copy-Item 'Documentacion\Gestion\Scrum.docx' "$E\02-Metodologia\Metodología declarada y justificada.docx"
Copy-Item 'Documentacion\Requerimientos\ERS.docx' "$E\04-Cascada\SRS (especificación de requisitos).docx"
Copy-Item 'README.md' "$E\05-Documentacion-tecnica\README del repositorio.md"
Copy-Item 'Documentacion\Arquitectura\SAD.docx' "$E\05-Documentacion-tecnica\Arquitectura.docx"
Copy-Item 'Documentacion\Calidad\Pruebas Generales.docx' "$E\05-Documentacion-tecnica\Pruebas.docx"
```

Índice de los 31 documentos: [`../README.md`](../README.md).
