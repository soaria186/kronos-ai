# Fase 1: avances

El repositorio actual se creó el 06-10-2026, ya en la Fase 2, así que la Fase 1 no tiene código aquí. Esta
página resume lo que se hizo; los documentos de la fase van en
[`Documentación Grupal`](../Documentaci%C3%B3n%20Grupal/) y
[`Documentación Individual`](../Documentaci%C3%B3n%20Individual/).

## Hitos

| Fecha | Hito |
| :--- | :--- |
| 10-08-2026 | Kick-off con los tres integrantes y el profesor guía |
| 21-08-2026 | Primera presentación del proyecto |
| 31-08 al 03-09-2026 | Guía de definición del proyecto, autoevaluaciones, diarios de reflexión y Formativa Fase 1 |
| 03-09-2026 | Presentación de la Fase 1 |
| Agosto y septiembre | Etapas 1 a 4 del laboratorio local |

## Qué se definió

- **El problema:** los centros de operaciones de seguridad reciben más alertas de las que pueden analizar, y
  las plataformas SOAR comerciales tienen licencias que una PyME no puede pagar.
- **La tesis, que sigue vigente:** una IA que **sólo clasifica** y un código determinista que **ejecuta**, con
  restricciones verificables y una bitácora encadenada.
- **Objetivo general:** implementar un sistema SOAR automatizado con IA y ejecución determinista, que garantice
  trazabilidad y control humano.
- **Objetivos específicos:** infraestructura con Wazuh; catálogo de 25 playbooks en 4 niveles de autonomía;
  modelo local con clasificación en dos pasos; orquestación con limitador de tasa y cortacircuito; persistencia
  inmutable.
- **Evidencias comprometidas:** cadena de hash verificable, 10 casos de inyección bloqueados y una prueba de
  estrés de 30 alertas en 10 minutos que abra el cortacircuito.

## El laboratorio de la Fase 1

El primer diseño corría en un laboratorio local con VirtualBox, con un dominio, un proxy con inspección TLS y
cuatro máquinas virtuales. La orquestación era n8n, la red privada Tailscale y la interfaz, el dashboard de
Wazuh. Los componentes tenían nombres mitológicos (ARGOS, NEMESIS, PITIA, TEMIS, HEFESTO, MNEMOSINE, AGORA e
IRIS).

## Qué cambió al pasar a la Fase 2

El 25-09-2026 el proyecto se replanteó como servicio en la nube, y cada componente pasó a tener un nombre
`SOAR-*`:

| Fase 1 | Fase 2 |
| :--- | :--- |
| Laboratorio local (VirtualBox) | Servidor en la nube (SOAR-CORE-01, Contabo) |
| Dominio, proxy y cuatro máquinas virtuales en el cliente | Sólo un agente de Wazuh por equipo |
| Contención deshabilitando la cuenta en Active Directory | Medidas locales por Active Response |
| n8n | Python (FastAPI) |
| Tailscale | NetBird |
| Dashboard de Wazuh | SOAR-CONSOLE y Telegram |
| Un cliente | Multiinquilino |
| ARGOS, NEMESIS, PITIA, TEMIS, HEFESTO, MNEMOSINE, AGORA e IRIS | SOAR-COLLECT, -DETECT, -CLASSIFY, -VALIDATE, -EXECUTE, -AUDIT, -CONSOLE y -NOTIFY |

El resultado está en [`../../Fase 2/Avances`](../../Fase%202/Avances/).
