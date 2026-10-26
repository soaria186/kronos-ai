# Kronos AI: el proyecto (Fase 2)

Todo lo que se construyó en la Fase 2: el código de los servicios, la infraestructura, las pruebas, las
herramientas y la documentación técnica. **Esta carpeta es la raíz del proyecto:** los comandos de esta página,
de la guía de instalación y de los README de cada carpeta se corren desde aquí.

```bash
cd "Fase 2/Avances"
```

Qué es Kronos, para quién es y cómo funciona: [README principal](../../README.md).

## Qué hay en esta carpeta

```text
conectores/     lectura incremental de alerts.json de Wazuh
consola/        SOAR-CONSOLE: panel web
decision/       SOAR-CLASSIFY: prompts, inferencia en dos pasos, catálogo KRO-CAT-01 y mediciones
docs/           guía de instalación, diagramas, evidencias, registro de trabajo y archivo
ejecucion/      SOAR-EXECUTE: órdenes de Active Response y reversiones
infra/          Docker (base y servicios), Ollama y Wazuh (compose, reglas de sobre y scripts de los agentes)
notificacion/   SOAR-NOTIFY: avisos y aprobaciones por Telegram
persistencia/   acceso a SOAR-AUDIT
tests/          pruebas unitarias, de integración y SQL
tools/          regla R1 y verificación de la entrega
validacion/     SOAR-VALIDATE: preparación de la alerta, contrato JSON, chequeos y ciclo
```

Además: [`CHANGELOG.md`](CHANGELOG.md), con los cambios por sprint y por versión, y
[`decision/mediciones/experimentos/`](decision/mediciones/experimentos/), con el prompt v2 que no se integró.

## Componentes

| Componente | Qué hace | Tecnología | Código |
| :--- | :--- | :--- | :--- |
| SOAR-COLLECT | Agente en cada equipo de la PyME; aplica las medidas | Wazuh Agent 4.14.8 | [`infra/wazuh/active-response/`](infra/wazuh/active-response/) |
| SOAR-DETECT | Correlación y reglas de sobre | Wazuh Manager 4.14.8 | [`infra/wazuh/`](infra/wazuh/) |
| SOAR-CLASSIFY | Clasificación en dos pasos | Ollama 0.40.0 y qwen2.5:7b, sin GPU | [`decision/`](decision/), [`infra/ollama/`](infra/ollama/) |
| SOAR-VALIDATE | Lee las alertas, consulta el modelo, aplica los chequeos y registra la decisión | Python 3.12 | [`validacion/`](validacion/), [`conectores/`](conectores/) |
| SOAR-EXECUTE | Órdenes de Active Response y reversiones | Python 3.12, API de Wazuh | [`ejecucion/`](ejecucion/) |
| SOAR-NOTIFY | Avisos y aprobaciones | API de bots de Telegram | [`notificacion/`](notificacion/) |
| SOAR-CONSOLE | Panel web: aprobar, rechazar, revertir, cerrar el cortacircuito | FastAPI, HTML sin JavaScript, TOTP | [`consola/`](consola/) |
| SOAR-AUDIT | Tickets y bitácora multiinquilino, con RLS y cadena de hash | PostgreSQL 17.11 | [`persistencia/`](persistencia/), [`infra/docker/`](infra/docker/) |

Todo corre en **SOAR-CORE-01**, un Cloud VDS de Contabo (16 vCPU, 64 GB de RAM, sin GPU) con Docker, en Francia y en hora UTC. La API de Wazuh, el indexador, el dashboard y la consola sólo escuchan en la red privada NetBird del equipo.

## Familias de incidentes

| Familia | Qué la define | Reglas de sobre |
| :--- | :--- | :--- |
| F1 Abuso de credenciales | La autenticación o el uso de una credencial | 100101 a 100103: fuerza bruta por SSH, fallos de PAM o sudo, fallos de inicio de sesión en Windows |
| F2 Proceso sospechoso | Un programa que se ejecuta y actúa en el mismo equipo | 100104 a 100106: PowerShell codificado, ejecución sospechosa, ejecutable en carpeta temporal |
| F3 Movimiento lateral o acceso remoto | Un equipo accede a otro o lo controla a distancia | 100107 y 100108: RDP o NTLM de red, PsExec, WinRM |
| F4 Exfiltración o salida anómala | Datos o tráfico que salen de forma inusual | 100109: binario sospechoso con conexión de salida |
| F5 Alteración o persistencia | Un cambio que queda en el sistema | 100110 a 100113: archivo vigilado, cuenta nueva, tarea o cron, registro de auditoría borrado |
| F6 Disponibilidad | Un servicio que cae o se degrada sin alterar datos | 100114 y 100115: disco lleno, agente detenido |

## Seguridad por diseño

- **El modelo no actúa.** EXECUTE toma el comando de una tabla fija y valida cada argumento (IP, cuenta, servicio). Nunca actúa sobre el manager, la IP del propio equipo ni cuentas como `root` o `Administrator`.
- **Resistencia a la inyección.** En las mediciones, ninguno de los 10 ataques de inyección consiguió que qwen2.5:7b eligiera la familia que buscaba. Además, si la familia del modelo no coincide con la de la regla de sobre, el caso va a revisión manual (`FAMILIA_NO_COINCIDE`).
- **Falla segura.** Un modelo caído, una demora sobre el plazo o una respuesta fuera del esquema llevan a revisión manual, nunca a una acción.
- **Mínimo privilegio.** Cada pieza tiene una identidad propia con lo justo: el usuario de API `kronos-execute` sólo puede `active-response:command`; los servicios se conectan como `kronos_worker`; la consola, como `kronos_console`, sólo puede llamar a cuatro funciones de la base.
- **Bitácora inalterable.** `UPDATE`, `DELETE` y `TRUNCATE` se rechazan, incluso para el superusuario, y cada evento encadena el hash del anterior.
- **Freno ante inundaciones.** El cortacircuito detiene toda acción automática con 30 alertas en 10 minutos y sólo una persona lo vuelve a cerrar. Los contadores de tasa limitan las acciones por PyME, por equipo y por medida.
- **Datos personales acotados.** La alerta completa se guarda aparte, con tope de 64 KiB, y se purga a los 90 días; la bitácora conserva sólo su huella.
- **Sin secretos en el repositorio.** gitleaks revisa todo el historial en cada PR. Las claves viven como secretos de Docker en el servidor y en el gestor de contraseñas del equipo.

## Medidas con actuador en la versión 1.0

Las demás medidas del catálogo siguen ahí: si la IA elige una, Kronos no toca el equipo y el ticket termina en falla
segura con aviso. Qué acciones tienen script en cada sistema operativo lo dice `actuadores_v1` en
[`decision/catalogo/kro-cat-01.json`](decision/catalogo/kro-cat-01.json).

| Medida | Nivel | Linux | Windows |
| :--- | :-: | :--- | :--- |
| Bloquear la IP externa que intenta entrar | 1 | `iptables` | Firewall de Windows |
| Bloquear la IP de otro equipo de la organización | 2 | `iptables` | Firewall de Windows |
| Deshabilitar la cuenta local | 2 | — | `net user` |
| Aislar un puesto de trabajo | 3 | — | Firewall de Windows, salvo el canal con el manager |

## Limitaciones conocidas

- Un solo servidor, sin alta disponibilidad. La continuidad se apoya en el respaldo diario cifrado y la restauración probada.
- Kronos sólo contiene donde hay agente.
- En Linux, una regla de bloqueo no sobrevive al reinicio del equipo y nadie la vuelve a aplicar (D-52).
- Si el agente está apagado cuando vence una reversión, ésta falla y no se reintenta. Queda el aviso para hacerla a mano (D-51).
- La confianza que declara el modelo no separa aciertos de errores. El control fuerte es la coincidencia con la regla de sobre.
- PB-F6-04 y PB-F6-05 (nivel 3) no se alcanzan: las reglas F6 tienen severidad 7, que permite como máximo el nivel 1.
- F4 (exfiltración) tiene una sola regla de sobre.
- La meta es decidir en 60 segundos. En la prueba real del 20-10 tomó 11 s; con el modelo cargado, cada alerta toma unos 20 s. VALIDATE espera hasta 120 s antes de abstenerse.

## Instalación

Se necesita un servidor Linux con Docker y NetBird, y el agente de Wazuh 4.14.8 en cada equipo de la PyME. La **guía de instalación paso a paso, en 15 partes**, está en [`docs/instalacion/`](docs/instalacion/): servidor, NetBird, Docker, Wazuh y reglas, Ollama, base y servicios, Active Response, agentes, Telegram, respaldo, alta y retiro de una PyME, y verificación de punta a punta.

Para trabajar en el código basta con Python 3.12:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r persistencia/requirements.txt -r consola/requirements.txt httpx
python -m unittest discover -s tests/unit
```

## Pruebas

| Tipo | Cantidad | Cómo se corren |
| :--- | :--- | :--- |
| Unitarias | 319 | `python -m unittest discover -s tests/unit`. Las 13 de la consola necesitan sus dependencias (arriba) |
| Integración | 65, de las que 5 usan el modelo | `bash tests/integracion/ejecutar.sh`: crea una base aparte (`kronos_pruebas`), corre las pruebas y la borra. Nunca escriben en la base real. Sin Docker, `tests/integracion/preparar_base.sh` prepara la base en un PostgreSQL local, como en el CI |
| SQL de SOAR-AUDIT | 4 | `bash tests/sql/ejecutar.sh`: dos inquilinos en paralelo, concurrencia, inmutabilidad y manipulación detectada |
| Mediciones de la IA | 20 originales, 24 de frontera, 10 de inyección, 18 en formato real y 150 etiquetados | [`decision/mediciones/`](decision/mediciones/) |
| Escenarios de demostración | E1 a E7 | [`docs/evidencia/`](docs/evidencia/) |

En cada pull request y en cada cambio a `develop` y `main`, GitHub Actions corre gitleaks 8.30.1 sobre todo el historial, ruff 0.16.10, la regla R1 (`decision/` no importa la capa de efectos), las pruebas unitarias (con las de la consola) y las de integración, contra un PostgreSQL 17.11 de servicio. En los PR hacia `main` corre además `tools/verificar_entrega.py --antes-de-publicar`, que revisa que el repositorio esté listo para una entrega.

## Documentación técnica

| Qué | Dónde |
| :--- | :--- |
| Guía de instalación, en 15 partes | [`docs/instalacion/`](docs/instalacion/) |
| Diagramas (Mermaid e imagen) | [`docs/diagramas/`](docs/diagramas/) |
| Evidencias de las pruebas | [`docs/evidencia/`](docs/evidencia/) |
| Registro de trabajo: registros, actas, revisiones, planes y decisiones | [`docs/registro/`](docs/registro/) |
| Lo que ya no está vigente (17 documentos v0.1 del 14-10) | [`docs/archivo/`](docs/archivo/) |
| Los 31 documentos, el informe final y el manual del encargado de TI | [`../Documentación Grupal/`](../Documentaci%C3%B3n%20Grupal/) |
| Cómo trabaja el equipo | [`../../.github/CONTRIBUTING.md`](../../.github/CONTRIBUTING.md) |
