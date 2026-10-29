# 04 · Wazuh

Detección y respuesta en los equipos: Wazuh 4.14.8 (manager, indexer y dashboard) en Docker, las 15 reglas de
sobre que etiquetan cada alerta con su familia, y Active Response, el canal por el que Kronos aplica y revierte
las medidas en los agentes.

| Parte | Tema | Requisitos | Estado |
| :-: | :--- | :--- | :--- |
| [04](04-wazuh.md) | Wazuh 4.14.8: compose, puertos y certificados | Partes 01 a 03 | Borrador |
| [05](05-reglas-de-sobre.md) | Reglas de sobre | Parte 04 | Borrador |
| [08](08-active-response.md) | Active Response: script `kronos-bloquear-ip` y usuario de API `kronos-execute` | Parte 04; se hace después de la parte 07 | Vigente |

**En el repositorio:** [`Fase 2/Avances/infra/wazuh`](../../Fase%202/Avances/infra/wazuh/), con el compose de
ejemplo, las reglas de sobre (`reglas/`) y los scripts de Active Response para Linux y Windows
(`active-response/`).

**Anterior:** [03 · Docker](../03-Docker/) · **Siguiente:** [05 · IA (Ollama)](../05-IA-Ollama/). Índice de la
guía: [`Instalacion`](../README.md).
