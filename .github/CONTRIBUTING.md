# Cómo trabajamos en Kronos AI

Reglas del equipo para ramas, pull requests, revisiones, mezclas y despliegues. Las mantiene el
Scrum Master (D-56). Cualquier cambio a este archivo pasa por un PR como cualquier otro.

## Roles (D-56, 21-10-2026)

| Rol | Quién |
| :--- | :--- |
| Product Owner | Nicolás Zamora: visión del producto, alcance y prioridades; el servidor y el laboratorio |
| Scrum Master | Rodrigo Riveros: proceso, registros, revisión cruzada y despliegue |
| Equipo de desarrollo | Los tres. Patricio González, a cargo de la calidad de la decisión (IA y mediciones) |

## Dónde va cada cosa

El repositorio sigue las fases del proyecto de título (pedido de la institución, 26-10-2026):

| Carpeta | Qué va ahí |
| :--- | :--- |
| `Fase 1/` y `Fase 2/` | Una por fase, cada una con `Avances/`, `Documentación Individual/` y `Documentación Grupal/` |
| `Fase 2/Avances/` | **El proyecto:** código, infraestructura, pruebas, herramientas y documentación técnica (`docs/`). Es la raíz para todos los comandos: `cd "Fase 2/Avances"` |
| `Fase X/Documentación Grupal/` | Los documentos del equipo en PDF (en la Fase 2, los 31 documentos, el informe final y el manual) |
| `Fase X/Documentación Individual/` | Una carpeta por integrante con sus documentos en PDF |
| `.github/` | CI, plantilla de PR, esta guía y la política de seguridad |

Una fase nueva se agrega con las mismas tres carpetas. El código no se duplica entre fases: sigue en
`Fase 2/Avances` y su historia queda en git y en `Fase 2/Avances/CHANGELOG.md`.

## Flujo de una tarea

1. Rama desde `develop`, con nombre `tipo/etapa-tema` (por ejemplo `feat/e3-tickets-huerfanos`). Si la tarea
   está en el [milestone](https://github.com/soarai2026/kronos-ai/milestones), el PR la nombra («Parte de #NN»).
2. Push diario a la rama, aunque el trabajo esté a medias.
3. Commits en español: `tipo(ámbito): descripción` (`feat`, `fix`, `docs`, `test`, `ci`, `refactor`).
4. Al terminar, PR hacia `develop` con la plantilla (`.github/pull_request_template.md`): qué cambia, por qué,
   cómo se probó, qué falta para desplegar y quién aprueba.
5. Los checks del CI en verde: gitleaks, ruff, R1, pruebas unitarias y pruebas de integración. Los comandos
   para correrlos antes, desde `Fase 2/Avances`, están en su README.
6. Revisión cruzada y mezcla según la regla de abajo.

## Regla de merge (D-54)

1. **Siempre hay una aprobación previa** («Approve» en GitHub), hecha desde la **cuenta
   personal** de un integrante.
2. **Nunca mezcla el autor** del PR.
3. **Nadie mezcla desde la cuenta compartida `soarai2026`.**
4. Se mezcla sólo con los checks del CI en verde y sin cambios pedidos pendientes.
5. **Siempre con commit de merge** («Create a merge commit»): sin aplastar ni rebasar, para que el historial
   muestre cada tarea y quién la hizo.

Quién revisa a quién:

| Autor | Revisa y aprueba |
| :--- | :--- |
| Nicolás | Rodrigo |
| Patricio | Nicolás |
| Rodrigo | Patricio |

Un PR que se abre desde la cuenta `soarai2026` (por ejemplo, desde un chat del asistente de IA) se atribuye
al integrante que lo pidió, y ese integrante cuenta como autor: no lo aprueba ni lo mezcla.

### Excepciones registradas (R-04)

Antes de esta regla, varios PR se mezclaron sin aprobación registrada en GitHub. Quedan como
excepción y no se repiten:

| PR | Situación |
| :--- | :--- |
| #1 a #16 | Mezclados sin aprobación registrada |
| #17 a #24 | Aprobados por Nicolás y mezclados por él |
| #25 a #30 | Mezclados sin aprobación registrada. Revisión de Rodrigo después del hecho (`KRO-REV-RR-2026-10-21`) |
| #31 a #34 | Mezclados el 21-10 desde `soarai2026` sin aprobación. #31 y #33, con revisión de Rodrigo después del hecho |
| #36 | Mezclado el 21-10 por su propio autor, ya vigente la regla. Tenía la aprobación de Nicolás |
| #75 a #84 | Integrados el 26-10 sin aprobación previa, junto con la reestructuración por fases que pidió la institución. Los tres lo autorizaron el mismo día |

El acta del punto de encuentro 1 fija la excepción para los PR #7 al #34. Los #1 al #6 ya
estaban anotados como excepción en el contexto maestro. **Desde la reestructuración del 26-10 no
hay excepciones:** cada PR tiene la aprobación de un integrante distinto del autor y lo mezcla
alguien que no es el autor, desde su cuenta personal.

## Despliegue en SOAR-CORE-01 (D-55)

- **Nadie despliega sin avisar antes en el grupo de Telegram** «Kronos — avisos», y sin
  confirmar que no hay una prueba en curso.
- Sólo se despliega lo que está mezclado en `develop`.
- Antes de tocar la base: respaldo (`sudo systemctl start kronos-respaldo-postgres.service`).
- Al terminar: registro de qué se desplegó y a qué hora (UTC), en el `KRO-LOG` del día.
- El servidor corre un clon de git en una etiqueta de versión (D-55, a cargo del Scrum Master), en
  `/opt/kronos/kronos-ai`; `/opt/kronos/audit` es un enlace a su carpeta `Fase 2/Avances`. Desplegar
  es `git fetch --tags`, `git checkout <etiqueta>` y recrear los servicios que cambiaron.
  `git describe --tags` dice qué versión corre (guía, parte 07).
- No se copian archivos desde Windows: el 21-10 eso rompió los permisos de una carpeta dentro de la
  imagen. `.env`, `secrets/`, `initdb/03_roles.sql` e `initdb/05_clave_consola.sql` viven sólo en el
  servidor, fuera de git.

## Seguridad

- Nunca secretos en el repositorio, en los documentos ni en los chats. Las contraseñas y llaves
  se cargan con `read -rs` (o desde el portapapeles por `ssh`) y se guardan en el gestor de
  contraseñas del equipo.
- No abrir `getUpdates` del bot de Telegram en el navegador: le quita las respuestas a SOAR-NOTIFY.
- No convertir el grupo de Telegram en supergrupo: cambia su id.
- No tocar la configuración de Wazuh del servidor sin avisar a Nicolás.

## Registros

Cada jornada relevante deja un `KRO-LOG-<iniciales>-<AAAA-MM-DD>_<tema>.md` con las tareas
hechas y pendientes, los PR y revisiones, los despliegues (con hora UTC), los hallazgos y lo que
se necesita de los demás. Los registros, actas, revisiones y planes van a
`Fase 2/Avances/docs/registro/`, sin
secretos, identificadores de Telegram, IP reales ni usuarios del servidor.

## Ramas y versiones

- `develop` integra las tareas; cada una llega por PR desde su rama.
- `main` recibe sólo versiones publicadas, por un PR desde `develop` mezclado con commit de merge y
  con su etiqueta (`v1.0.0`). Lo prepara el Scrum Master y lo aprueban los otros dos integrantes.
- Sólo hay dos ramas permanentes, `develop` y `main`. Una rama de tarea se borra al mezclar su PR.
- Un experimento que no se integra se guarda como parche en `Fase 2/Avances/decision/mediciones/experimentos/`,
  con una línea en el registro de mediciones que dice qué se probó, y su rama se borra.
