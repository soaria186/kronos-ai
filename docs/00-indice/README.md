# Kronos AI — Índice de la documentación

Entrega del **16-10-2026**. Documentos de ingeniería de software del proyecto de título (Capstone, Ingeniería en Informática, DUOC UC).
Cada documento se identifica por su número y su nombre. El documento 00 contiene además la matriz de trazabilidad y las diferencias entre fuentes.

Leyenda: ✅ verificado · 🟡 informado · ⏳ pendiente · ❓ por confirmar. «Propuesta» marca lo que el equipo aún no decide.

## Documentos de esta entrega

| N.° | Documento | Archivo | Responsable | Prioridad | Estado | Páginas | [POR CONFIRMAR] |
| :---: | :--- | :--- | :--- | :---: | :--- | :---: | :---: |
| 00 | Índice documental y matriz de trazabilidad | [00_indice.docx](../entregables/00_indice.docx) | Equipo | P1 | Borrador 0.1, en revisión | 9 | 2 |
| 01 | Visión de la solución | [01_vision.docx](../entregables/01_vision.docx) | Equipo | P1 | Borrador 0.1, en revisión | 9 | 1 |
| 02 | Especificación de requerimientos | [02_requerimientos.docx](../entregables/02_requerimientos.docx) | Patricio | P1 | Borrador 0.1, en revisión | 16 | 8 |
| 03 | Justificación metodológica | [03_metodologia.docx](../entregables/03_metodologia.docx) | Patricio | P2 | Borrador 0.1, en revisión | 9 | 2 |
| 04 | Estimación y planificación | [04_planificacion.docx](../entregables/04_planificacion.docx) | Patricio | P2 | Borrador 0.1, en revisión | 8 | 5 |
| 05 | Plan de administración de la configuración | [05_configuracion.docx](../entregables/05_configuracion.docx) | Rodrigo | P2 | Borrador 0.1, en revisión | 8 | 5 |
| 06 | Plan de calidad | [06_calidad.docx](../entregables/06_calidad.docx) | Patricio | P2 | Borrador 0.1, en revisión | 8 | 2 |
| 07 | Plan de métricas y medición | [07_metricas.docx](../entregables/07_metricas.docx) | Patricio | P3 | Borrador 0.1, en revisión | 7 | 6 |
| 08 | Seguimiento y control | [08_seguimiento.docx](../entregables/08_seguimiento.docx) | Equipo | P3 | Borrador 0.1, en revisión | 9 | 2 |
| 09 | Documento de arquitectura | [09_arquitectura.docx](../entregables/09_arquitectura.docx) | Nicolás y Rodrigo | P1 | Borrador 0.1, en revisión | 16 | 7 |
| 11 | Especificación de prompts | [11_prompts.docx](../entregables/11_prompts.docx) | Patricio | P2 | Borrador 0.1, en revisión | 10 | 5 |
| 13 | Estándares de codificación | [13_estandares.docx](../entregables/13_estandares.docx) | Rodrigo | P1 | Borrador 0.1, en revisión | 9 | 2 |
| 14 | Proceso de integración continua | [14_integracion-continua.docx](../entregables/14_integracion-continua.docx) | Rodrigo | P1 | Borrador 0.1, en revisión | 9 | 3 |
| 15 | Plan de pruebas de software | [15_plan-pruebas.docx](../entregables/15_plan-pruebas.docx) | Nicolás y Patricio | P2 | Borrador 0.1, en revisión | 10 | 3 |
| 17 | Seguridad de la plataforma | [17_seguridad.docx](../entregables/17_seguridad.docx) | Rodrigo | P1 | Borrador 0.1, en revisión | 10 | 6 |
| 19 | Política de respaldo y retención | [19_respaldo-retencion.docx](../entregables/19_respaldo-retencion.docx) | Rodrigo | P2 | Borrador 0.1, en revisión | 8 | 7 |
| 20 | Procedimiento de gestión de secretos | [20_secretos.docx](../entregables/20_secretos.docx) | Rodrigo | P2 | Borrador 0.1, en revisión | 8 | 5 |

Todos los documentos citan la bibliografía con una marca de año y edición por confirmar; esa marca se cuenta en cada uno.

## Documentos pendientes

| N.° | Documento | Responsable | Qué le falta |
| :---: | :--- | :--- | :--- |
| 10 | Documento de diseño | Rodrigo y Patricio | Cómo escribe SOAR-CONSOLE (R-13); conexión de los servicios a la base y entrega de contraseñas; cómo se llevan los plazos de 2 días; estado del ticket mientras espera aprobación; ancla externa (R-14) |
| 12 | Catálogo de playbooks, versión de trabajo | Patricio | Plazos de reversión del nivel 1; restauración de cuarentenas y tareas; tres acciones adicionales; consultas de nivel 0; carpeta de cuarentena; playbooks de varios pasos. La versión 0.1 ya existe como datos en `decision/catalogo/kro-cat-01.json` |
| 16 | Casos de prueba y plan de aceptación en el laboratorio | Nicolás | Laboratorio funcionando; SOAR-EXECUTE; nombres de los escenarios CU-C01 a CU-C10 y CU-S01 a CU-S12; quién da el visto bueno a la puerta de salida |
| 18 | Cierre de brechas BR-01 y BR-05 | Rodrigo y Nicolás | Política de retención aprobada; forma de expirar una cadena inmutable (R-09); acuerdo de tratamiento con el proveedor (DPA); destino de los datos tras el 10-12-2026 (R-15) |
| 21 | Guía de instalación (`docs/instalacion/`, 15 partes) | Cada uno su parte | Se escribe al instalar cada componente (D-18); las partes 13 (alta de un cliente) y 14 (retiro) dependen de la farmacia |
| 22 | Cierre del proyecto | Equipo | Se completa en S6 (sólo esqueleto) |

## Archivos de apoyo

| Archivo | Contenido |
| :--- | :--- |
| [preguntas-abiertas.md](preguntas-abiertas.md) | Cada `[POR CONFIRMAR]`, con documento, sección y a quién preguntar |
| [pendientes-farmacia.md](pendientes-farmacia.md) | Lo que se completa después de instalar en la farmacia (D-28) |
| [../diagramas/](../diagramas/) | Diagramas: fuente Mermaid (`.mmd`) e imagen (`.png`) |
| [../registro/](../registro/) | Registros de trabajo `KRO-LOG-<iniciales>-<fecha>` |
| [../evidencia/](../evidencia/) | Salida de las pruebas del esquema de SOAR-AUDIT |

## Cómo se mantienen

- Cada documento lo revisa un integrante distinto del autor, por PR a `develop`.
- Al responder una pregunta abierta, se corrige cada documento que la cita y se quita de `preguntas-abiertas.md`.
- Los diagramas se editan en el `.mmd` y se vuelven a renderizar a `.png` (ver `docs/diagramas/README.md`).
