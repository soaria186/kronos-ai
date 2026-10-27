# KRO-ACTA-2026-10-21 · Punto de encuentro 1

**Fecha:** 21-10-2026, 18:27 a 18:41 (hora de Chile).
**Asistentes:** Nicolás Zamora, Patricio González y Rodrigo Riveros.

## Decisiones

| # | Tema | Decisión |
| :-: | :--- | :--- |
| D-44 | Playbooks | **De un solo paso** |
| D-45 | Reversión del nivel 1 | **60 minutos**, confirmados |
| D-46 | Retención de las alertas guardadas | **90 días**. La bitácora se mantiene 2 años |
| D-47 | Medidas en la farmacia | **Las 25 del catálogo** KRO-CAT-01. Se agregarán más en el futuro |
| D-48 | Inicio en la farmacia | **Modo observación durante 1 semana** |
| D-49 | Inquilino de cada alerta | **Por grupo de agentes de Wazuh** |
| D-50 | Nivel 0 sin comando (por ejemplo, 100115 → PB-F6-01) | **Se desactiva y no se avisa** |
| D-51 | Reversión con el agente apagado | **Aviso manual**, sin reintento automático |
| D-52 | Reglas que se pierden al reiniciar el equipo | **Se corrige**: deben volver a aplicarse |
| D-53 | Tickets de prueba #1, #2 y #5 | **Se dejan como evidencia** |
| D-54 | Regla de merge | Nadie mezcla desde `soaria186`; nunca mezcla el autor; siempre hay una aprobación previa desde la cuenta personal. Los PR #7 al #34 quedan como excepción R-04 |
| D-55 | Despliegue en SOAR-CORE-01 | **Rodrigo** pasa `/opt/kronos/audit` a un `git clone` con etiquetas de versión. Nadie despliega sin avisar en el grupo de Telegram |
| D-56 | Roles de Scrum | **Product Owner: Nicolás. Scrum Master: Rodrigo. Equipo de desarrollo: los tres**, con Patricio a cargo de la calidad de la decisión (IA y mediciones) |

**Fundamento de D-56:**
- **Nicolás** es el contacto con la farmacia y con el servidor, decide el alcance (SaaS con foco en la farmacia y el orden de las etapas) y prioriza el trabajo.
- **Rodrigo** ya cumple ese rol en la práctica: lleva los registros, la revisión cruzada, el despliegue y el proceso.

## Consecuencias de las decisiones

- **D-47 con D-50:** las medidas sin comando se mantienen en el catálogo. Mientras no tengan su comando:
  - las de **nivel 0** no se ejecutan ni se avisan (D-50);
  - las de **nivel 1 a 3** terminan en `FAILED` con `ACCION_NO_IMPLEMENTADA`.
  - Durante la semana de observación (D-48) nada se ejecuta solo, así que no afecta a la farmacia. Antes de salir del modo observación hay que tener los comandos.
- **D-48:** hay que definir cómo se implementa el modo observación (por ejemplo, un ajuste por inquilino en VALIDATE que lleve todo nivel mayor que 0 a aprobación).
- **D-51:** EXECUTE debe avisar por Telegram cada `REVERSION_FALLIDA`, con el comando para revertir a mano.
- **D-52:** EXECUTE vuelve a aplicar las medidas vigentes de un agente cuando este se reconecta. Lo alternativo son reglas persistentes en los scripts.

## Pendiente de definir

- Parte 3 de la agenda: revisiones de hoy (#35 y PR de VALIDATE), orden de despliegue, fecha del punto de encuentro 2 y corrección del cortacircuito.
