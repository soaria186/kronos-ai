# Documentación

Todo lo que no es código. Cada carpeta tiene su README con lo que contiene y cómo se mantiene.

| Carpeta | Contenido | Quién la mantiene |
| :--- | :--- | :--- |
| [`entregables/`](entregables/) | Los 31 documentos del proyecto, en PDF, con su índice | Cada responsable su documento; Rodrigo los sube |
| [`informe/`](informe/) | Informe final de Duoc y manual del encargado de TI | Patricio (informe) y Rodrigo (manual) |
| [`instalacion/`](instalacion/) | Guía de instalación en 15 partes (D-18) | Cada responsable su parte; la revisa otro integrante |
| [`diagramas/`](diagramas/) | Fuente Mermaid (`.mmd`) e imagen de cada figura | Quien cambia una figura vuelve a generar su imagen |
| [`evidencia/`](evidencia/) | Salidas, extractos y capturas de las pruebas | Quien hace la prueba |
| [`registro/`](registro/) | Registros de trabajo, estados, actas, revisiones, planes y el [registro de decisiones](registro/decisiones.md) | Cada integrante sus registros |
| [`archivo/`](archivo/) | Lo que ya no está vigente: los 17 documentos v0.1 del 14-10 y su índice | No se modifica |

## Reglas para toda la carpeta

- **Nada que no deba publicarse:** ni secretos, ni identificadores de Telegram, ni usuarios del servidor, ni IP
  reales. Las IP de ejemplo son de los rangos de documentación (`192.0.2.0/24`, `198.51.100.0/24` y
  `203.0.113.0/24`) o de la red del laboratorio.
- **Todo cambio por PR a `develop`,** con la aprobación de un integrante distinto del autor (D-54, en
  [`CONTRIBUTING.md`](../CONTRIBUTING.md)).
- **Fechas** `DD-MM-AAAA` en el texto y `AAAA-MM-DD` en los nombres de archivo; las horas del servidor, en UTC.
- **Decisiones:** se citan por su código `D-NN`, definido en [`registro/decisiones.md`](registro/decisiones.md).
- **Lo vigente no remite al archivo,** salvo para explicar de dónde viene algo.
