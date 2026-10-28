# Guía de instalación de Kronos AI

Cómo instalar Kronos desde cero: el servidor en la nube, los servicios y los agentes de una PyME. Hay una
carpeta por cada componente que se instala, y dentro de ella las partes de la guía que le corresponden. Cada
parte dice quién la escribió, quién la revisa y en qué estado está.

## Componentes

| Carpeta | Qué se instala | Partes |
| :--- | :--- | :--- |
| [`01-Servidor`](01-Servidor/) | Servidor SOAR-CORE-01 (Ubuntu 24.04 en Contabo) y su endurecimiento | 01 |
| [`02-NetBird`](02-NetBird/) | Red privada del equipo y del encargado de TI | 02 |
| [`03-Docker`](03-Docker/) | Motor de contenedores | 03 |
| [`04-Wazuh`](04-Wazuh/) | Wazuh 4.14.8 (manager, indexer y dashboard), reglas de sobre y Active Response | 04, 05 y 08 |
| [`05-IA-Ollama`](05-IA-Ollama/) | Ollama y el modelo qwen2.5:7b (SOAR-CLASSIFY) | 06 |
| [`06-PostgreSQL-y-Servicios`](06-PostgreSQL-y-Servicios/) | PostgreSQL 17.11 (SOAR-AUDIT) y los servicios VALIDATE, EXECUTE, NOTIFY y CONSOLE | 07 |
| [`07-Agentes`](07-Agentes/) | Agente de Wazuh en los equipos Linux y Windows de la PyME | 09 y 10 |
| [`08-Telegram`](08-Telegram/) | Bot y grupo de avisos de SOAR-NOTIFY | 11 |
| [`09-Respaldo-y-Retencion`](09-Respaldo-y-Retencion/) | Respaldo cifrado de la base, restauración y purga de alertas | 12 |
| [`10-Operacion-y-Verificacion`](10-Operacion-y-Verificacion/) | Alta y retiro de una PyME, y verificación de punta a punta | 13, 14 y 15 |

## Orden de instalación

Las partes se siguen por su número, que es el orden en que se instala. Algunas carpetas reúnen partes que no
son consecutivas: la de Wazuh tiene las partes 04, 05 y 08, y la parte 08 se hace después de la 07.

| Parte | Tema | Carpeta | Responsable | Revisa | Estado |
| :-: | :--- | :--- | :--- | :--- | :--- |
| [01](01-Servidor/01-servidor.md) | Servidor SOAR-CORE-01 y endurecimiento | `01-Servidor` | Nicolás | Rodrigo | Borrador |
| [02](02-NetBird/02-netbird.md) | Red privada NetBird | `02-NetBird` | Nicolás | Rodrigo | Borrador |
| [03](03-Docker/03-docker.md) | Docker | `03-Docker` | Nicolás | Rodrigo | Borrador |
| [04](04-Wazuh/04-wazuh.md) | Wazuh 4.14.8: compose, puertos y certificados | `04-Wazuh` | Nicolás | Rodrigo | Borrador |
| [05](04-Wazuh/05-reglas-de-sobre.md) | Reglas de sobre | `04-Wazuh` | Nicolás | Patricio | Borrador |
| [06](05-IA-Ollama/06-ollama.md) | Ollama y el modelo | `05-IA-Ollama` | Patricio | Nicolás | Vigente |
| [07](06-PostgreSQL-y-Servicios/07-base-y-servicios.md) | Base SOAR-AUDIT y servicios | `06-PostgreSQL-y-Servicios` | Rodrigo | Patricio | Borrador |
| [08](04-Wazuh/08-active-response.md) | Active Response y usuario de API | `04-Wazuh` | Nicolás | Rodrigo | Vigente |
| [09](07-Agentes/09-agente-linux.md) | Agente Linux | `07-Agentes` | Nicolás | Rodrigo | Borrador |
| [10](07-Agentes/10-agente-windows.md) | Agente Windows | `07-Agentes` | Nicolás | Rodrigo | Borrador |
| [11](08-Telegram/11-telegram.md) | Telegram | `08-Telegram` | Rodrigo | Patricio | Borrador |
| [12](09-Respaldo-y-Retencion/12-respaldo-y-retencion.md) | Respaldo, restauración y retención | `09-Respaldo-y-Retencion` | Rodrigo | Patricio | Borrador |
| [13](10-Operacion-y-Verificacion/13-alta-de-una-pyme.md) | Alta de una PyME | `10-Operacion-y-Verificacion` | Patricio y Nicolás | Rodrigo | Borrador |
| [14](10-Operacion-y-Verificacion/14-retiro-y-desinstalacion.md) | Retiro de una PyME y desinstalación | `10-Operacion-y-Verificacion` | Nicolás | Rodrigo | Borrador |
| [15](10-Operacion-y-Verificacion/15-verificacion-de-punta-a-punta.md) | Verificación de punta a punta (escenarios E1 a E7) | `10-Operacion-y-Verificacion` | Patricio | Nicolás | Borrador |

**Estados.** *Borrador*: escrito desde la configuración del repositorio y los registros del proyecto; su
responsable lo compara con lo que se hizo de verdad, lo corrige y lo pasa a *vigente*. *Vigente*: seguido y
comprobado en SOAR-CORE-01 o en la PyME simulada.

## Convenciones

- Las rutas de archivos que nombra la guía (`infra/…`, `persistencia/…`, `tools/…`) son relativas a la carpeta
  del proyecto, [`Fase 2/Avances`](../Fase%202/Avances/), y los comandos se corren desde ahí.
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
- Antes de tocar el servidor, se avisa en el grupo de Telegram y se despliega de a uno
  ([`CONTRIBUTING.md`](../.github/CONTRIBUTING.md)).

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

Arquitectura completa: [`Fase 2/Avances/docs/diagramas`](../Fase%202/Avances/docs/diagramas/) (`09_despliegue`,
`09_componentes` y `09_flujo_alerta`). Documentos de arquitectura e infraestructura:
[`Documentacion/Arquitectura`](../Documentacion/Arquitectura/).
