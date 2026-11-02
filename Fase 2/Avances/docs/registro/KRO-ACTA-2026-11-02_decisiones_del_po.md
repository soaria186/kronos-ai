# KRO-ACTA-2026-11-02 · Decisiones del Product Owner

**Fecha:** 02-11-2026.
**Decide:** Nicolás Zamora, Product Owner (D-56).
**Origen:** las propuestas D-57 a D-65 del [plan del 26-10](KRO-PLAN-2026-10-26_replanteamiento_pyme_y_cierre.md)
(sección 2.6) que seguían sin aprobar, y tres decisiones nuevas de la semana de cierre. Quedan en el
[registro de decisiones](decisiones.md).

## Fechas

| Qué | Cuándo |
| :--- | :--- |
| Prueba integral, escenarios E1 a E7 en la PyME simulada | Martes 03-11-2026, 20:00 (hora de Chile) |
| Plazo para terminar todo, según el profesor guía (5 días) | Sábado 07-11-2026 |
| Versión 1.0.0 (D-64) | Hasta el sábado 07-11-2026 |
| Defensa | Primera semana de diciembre de 2026 |

## Decisiones

| # | Decisión | Justificación | Quién |
| :-: | :--- | :--- | :--- |
| D-57 | **Sin cliente real; validación en una PyME simulada** | Fecha: antes del 26-10-2026, en reunión con el profesor guía; el plan del 26-10 la registra. La validación se hace con escenarios reproducibles e inofensivos (E1 a E7), con evidencia y métricas | El profesor guía; la registra Nicolás |
| D-58 | **La PyME simulada no tiene nombre propio**: en todos los documentos se dice «la PyME simulada». Es un comercio ficticio de unos 15 trabajadores en Santiago, con un servidor Linux (EP-SRV-01) y puestos Windows (EP-WKS-01 representa uno), sin especialista en ciberseguridad. Tiene un encargado de TI que hace «de todo» y aprueba las medidas de nivel 3 | Sin nombre, no se confunde con una empresa real. El perfil es el de las PyMEs a las que apunta Kronos y calza con los dos equipos del laboratorio | Nicolás |
| D-59 | **El nivel 3 lo aprueba el encargado de TI de la PyME**, con el equipo Kronos como respaldo. Reemplaza a D-31 | Es el usuario principal del planteamiento del 26-10: Kronos hace el trabajo del especialista y el encargado de TI tiene la última palabra. No requiere código, sólo la configuración de Telegram | Nicolás |
| D-60 | **Alcance congelado de la v1.0**: bloquear la IP (Linux y Windows), deshabilitar la cuenta y aislar el equipo (Windows). Las demás medidas terminan en falla segura con aviso | Ya aprobada el 26-10, al integrar el catálogo 1.0 (#83) | Equipo (26-10) |
| D-61 | **Se anulan D-15, D-28, D-47 (en lo que toca a la farmacia) y D-48.** D-49 pasa a deseable y D-52, a limitación documentada | Dependían de un cliente real que ya no existe (D-57). En la v1.0 hay una PyME por servidor, y volver a aplicar las reglas después de un reinicio queda fuera del alcance congelado (D-60) | Nicolás |
| D-62 | **Documentación oficial: los 31 documentos más el informe final de Duoc**, en PDF en `Fase 2/Documentación Grupal`. Los 17 Word v0.1 se archivan | Una sola versión vigente de cada documento, en el lugar que pide la institución | Nicolás |
| D-63 | **Repositorio público. Todos los derechos reservados, Duoc UC**, en [`LICENSE`](../../../../LICENSE). No se usa licencia libre | Público, la comisión lo revisa sin invitaciones. Los derechos son de Duoc UC: el código y la documentación se publican sólo para su revisión académica | Nicolás |
| D-64 | **`main` pasa a ser la versión entregable, con la v1.0.0 hasta el 07-11** y no el sábado 31-10 | Los scripts de Windows se terminaron de probar el 02-11 (evidencia en `docs/evidencia/2026-11-02_ar-windows/`). Hasta la v1.0.0, el servidor queda en `v1.0.0-rc2` | Nicolás |
| D-65 | **Configuración de VALIDATE v1.0** | Ya aprobada el 26-10, al integrar `validate.json` 1.0 (#84) | Equipo (26-10) |
| D-66 | **CI en GitHub Actions.** Al mudar el repositorio a `soaria186`, GitHub tardó en habilitar Actions (el 02-11 mostró «Unable to enable Actions»); se habilitaron ese mismo día y **desde el PR #46 el CI corre en cada PR** | En el PR #46 el CI pasó 5 de 5: gitleaks, ruff, pruebas unitarias, R1 e integración. La verificación de la entrega corre sólo en los PR hacia `main` | Nicolás |
| D-67 | **E3 y E4, opción A**: en la prueba integral se muestran tal como salen. E3 termina en consulta; E4 pide aprobación y termina en falla segura («[NO SE APLICÓ]»). Los scripts de Windows se demuestran aparte, por la API | Mostrar el comportamiento real del sistema, incluida la falla segura, en vez de ajustar el prompt para la demostración | Nicolás |
| D-68 | **Laboratorio en la defensa**: Nicolás entrega EP-SRV-01 y EP-WKS-01 en OVA, listas, y Rodrigo las lleva en su notebook. Nunca se encienden dos copias de la misma VM a la vez | EP-SRV-01 está en el notebook de Nicolás y EP-WKS-01 en su PC de escritorio. Dos copias encendidas tendrían la misma llave del agente frente al manager | Nicolás |

## Consecuencias de las decisiones

- **D-58:** los documentos, el README y la guía dicen «la PyME simulada», sin nombre propio.
- **D-59 y D-61:** los documentos de Nicolás pasan a la versión 2.0 sin la farmacia, con el encargado de TI como
  quien aprueba y revierte (tarea T3).
- **D-63:** `LICENSE` en la raíz del repositorio, la sección «Licencia» del README y la comprobación de
  `tools/verificar_entrega.py`.
- **D-66:** cada PR se mezcla con los checks del CI en verde, como ya decían `CONTRIBUTING.md` y la plantilla
  de PR (D-54).
- **D-67:** la parte 15 de la guía registra E3 y E4 tal como salgan el 03-11 (tarea T5).
