# Cómo trabajamos en Kronos AI

Reglas del equipo para ramas, pull requests, revisiones, mezclas y despliegues. Las mantiene el
Scrum Master (D-56). Cualquier cambio a este archivo pasa por un PR como cualquier otro.

## Roles (D-56, 21-10-2026)

| Rol | Quién |
| :--- | :--- |
| Product Owner | Nicolás Zamora: contacto con la farmacia y el servidor, alcance y prioridades |
| Scrum Master | Rodrigo Riveros: proceso, registros, revisión cruzada y despliegue |
| Equipo de desarrollo | Los tres. Patricio González, a cargo de la calidad de la decisión (IA y mediciones) |

## Flujo de una tarea

1. Rama desde `develop`, con nombre `tipo/etapa-tema` (por ejemplo `feat/e3-tickets-huerfanos`).
2. Push diario a la rama, aunque el trabajo esté a medias.
3. Commits en español: `tipo(ámbito): descripción` (`feat`, `fix`, `docs`, `test`, `ci`, `refactor`).
4. Al terminar, PR hacia `develop` con: qué cambia, por qué, cómo se probó y qué falta para desplegar.
5. Los cuatro checks del CI en verde: gitleaks, ruff, R1 y pruebas unitarias.
6. Revisión cruzada y mezcla según la regla de abajo.

## Regla de merge (D-54)

1. **Siempre hay una aprobación previa** («Approve» en GitHub), hecha desde la **cuenta
   personal** de un integrante.
2. **Nunca mezcla el autor** del PR.
3. **Nadie mezcla desde la cuenta compartida `soarai2026`.**
4. Se mezcla sólo con los checks del CI en verde y sin cambios pedidos pendientes.

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

El acta del punto de encuentro 1 fija la excepción para los PR #7 al #34. Los #1 al #6 ya
estaban anotados como excepción en el contexto maestro.

## Despliegue en SOAR-CORE-01 (D-55)

- **Nadie despliega sin avisar antes en el grupo de Telegram** «Kronos — avisos», y sin
  confirmar que no hay una prueba en curso.
- Sólo se despliega lo que está mezclado en `develop`.
- Antes de tocar la base: respaldo (`sudo systemctl start kronos-respaldo-postgres.service`).
- Al terminar: registro de qué se desplegó y a qué hora (UTC), en el `KRO-LOG` del día.
- `/opt/kronos/audit` pasará a ser un `git clone` con etiquetas de versión (D-55, a cargo del
  Scrum Master). Hasta entonces se actualiza copiando `develop` y comparando antes con `diff`.

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
se necesita de los demás.
