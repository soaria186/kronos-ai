# Guía de instalación de Kronos AI

Paso a paso para instalar Kronos desde cero: el servidor en la nube, los servicios y los agentes de una PyME.
Son 15 partes (decisión D-18), en el orden en que se instalan. Cada parte dice quién la escribió, quién la revisa
y en qué estado está.

| Parte | Tema | Responsable | Revisa | Estado |
| :-: | :--- | :--- | :--- | :--- |
| [01](01-servidor.md) | Servidor SOAR-CORE-01 y endurecimiento | Nicolás | Rodrigo | Borrador |
| [02](02-netbird.md) | Red privada NetBird | Nicolás | Rodrigo | Borrador |
| [03](03-docker.md) | Docker | Nicolás | Rodrigo | Borrador |
| [04](04-wazuh.md) | Wazuh 4.14.8: compose, puertos y certificados | Nicolás | Rodrigo | Borrador |
| [05](05-reglas-de-sobre.md) | Reglas de sobre | Nicolás | Patricio | Borrador |
| [06](06-ollama.md) | Ollama y el modelo | Patricio | Nicolás | Vigente |
| [07](07-base-y-servicios.md) | Base SOAR-AUDIT y servicios | Rodrigo | Patricio | Borrador |
| [08](08-active-response.md) | Active Response y usuario de API | Nicolás | Rodrigo | Vigente |
| [09](09-agente-linux.md) | Agente Linux | Nicolás | Rodrigo | Borrador |
| [10](10-agente-windows.md) | Agente Windows | Nicolás | Rodrigo | Borrador |
| [11](11-telegram.md) | Telegram | Rodrigo | Patricio | Borrador |
| [12](12-respaldo-y-retencion.md) | Respaldo, restauración y retención | Rodrigo | Patricio | Borrador |
| [13](13-alta-de-una-pyme.md) | Alta de una PyME | Patricio y Nicolás | Rodrigo | Borrador |
| [14](14-retiro-y-desinstalacion.md) | Retiro de una PyME y desinstalación | Nicolás | Rodrigo | Borrador |
| [15](15-verificacion-de-punta-a-punta.md) | Verificación de punta a punta (escenarios E1 a E7) | Patricio | Nicolás | Borrador |

**Estados.** *Borrador*: escrito desde la configuración del repositorio y los registros del proyecto; su
responsable lo compara con lo que se hizo de verdad, lo corrige y lo pasa a *vigente*. *Vigente*: seguido y
comprobado en SOAR-CORE-01 o en la PyME simulada.

## Convenciones

- Cada comando dice dónde se ejecuta: **[PC]** (el computador del integrante), **[servidor]** (SOAR-CORE-01),
  **[agente Linux]**, **[agente Windows]** o **[manager]** (dentro del contenedor del manager de Wazuh). El
  rótulo no se copia.
- Después de los comandos importantes, **Debe mostrar:** dice qué se espera. Si sale otra cosa, no se sigue.
- **Nunca** van en esta guía contraseñas, tokens, llaves, IP reales, identificadores de Telegram ni usuarios del
  servidor. Donde hacen falta se escribe `XXXX` o `<qué va>`, y el valor real sale del gestor de contraseñas.
- Las contraseñas se cargan con `read -rs` y nunca se escriben en el comando. Antes de un comando con `!` en
  Bash: `set +H`.
- IP de ejemplo, sólo de los rangos de documentación (`203.0.113.0/24`, `198.51.100.0/24`, `192.0.2.0/24`) o de
  la red del laboratorio. Nunca se bloquea la puerta de enlace ni la IP desde la que se está conectado por SSH.
- Antes de tocar el servidor, se avisa en el grupo de Telegram y se despliega de a uno (`CONTRIBUTING.md`).

## Lo que queda instalado

```text
Equipos de la PyME ──1514/TCP──▶ SOAR-CORE-01 (Contabo, Docker)
  agente de Wazuh                 ├─ Wazuh 4.14.8 (manager, indexer, dashboard) + 15 reglas de sobre
  scripts kronos-*                ├─ Ollama 0.40.0 + qwen2.5:7b (sólo 127.0.0.1 y red interna)
                                  ├─ PostgreSQL 17.11: SOAR-AUDIT (sin puertos)
                                  ├─ SOAR-VALIDATE, SOAR-EXECUTE, SOAR-NOTIFY y SOAR-CONSOLE
                                  └─ respaldo cifrado (04:15 UTC) y purga de alertas (04:45 UTC)
Equipo y encargado de TI ──NetBird──▶ consola (443), API de Wazuh (55000), indexer (9200), dashboard (5601)
SOAR-NOTIFY ──HTTPS saliente──▶ Telegram
```

Arquitectura completa: [`docs/diagramas/`](../diagramas/) (`09_despliegue`, `09_componentes` y `09_flujo_alerta`).
