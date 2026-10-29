# 06 · PostgreSQL y servicios

La base SOAR-AUDIT en PostgreSQL 17.11, sin puertos publicados, con su bitácora de sólo inserción y cadena de
hash por inquilino, y los servicios de Kronos que la usan: SOAR-VALIDATE, SOAR-EXECUTE, SOAR-NOTIFY y
SOAR-CONSOLE.

| Parte | Tema | Requisitos | Estado |
| :-: | :--- | :--- | :--- |
| [07](07-base-y-servicios.md) | Base SOAR-AUDIT y servicios | Partes 01 a 04 y 06 | Borrador |

**En el repositorio:** [`Fase 2/Avances/infra/docker`](../../Fase%202/Avances/infra/docker/) (compose de la base y
de los servicios, scripts de inicialización y migraciones) y el código de cada servicio en
[`persistencia`](../../Fase%202/Avances/persistencia/), [`validacion`](../../Fase%202/Avances/validacion/),
[`ejecucion`](../../Fase%202/Avances/ejecucion/), [`notificacion`](../../Fase%202/Avances/notificacion/) y
[`consola`](../../Fase%202/Avances/consola/).

**Anterior:** [05 · IA (Ollama)](../05-IA-Ollama/) · **Siguiente:** Active Response, la
[parte 08](../04-Wazuh/08-active-response.md), y después [07 · Agentes](../07-Agentes/). Índice de la guía:
[`Instalacion`](../README.md).
