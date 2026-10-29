# Registro de cambios

Cambios de Kronos AI por sprint y por versión, con el pull request de cada uno. Las versiones siguen el [versionado semántico](https://semver.org/lang/es/); `main` recibe sólo versiones publicadas y `develop` integra el trabajo del sprint (ver [CONTRIBUTING.md](../../.github/CONTRIBUTING.md)).

## Sin publicar: semana de cierre (26-10 al 01-11-2026)

Milestone [«v1.0: cierre»](https://github.com/soaria186/kronos-ai/milestone/1). Esta sección pasa a ser la versión 1.0.0 al publicarla.

### Cambiado

- **Repositorio ordenado por fases**, a pedido de la institución: `Fase 1/` y `Fase 2/`, cada una con `Avances/`, `Documentación Individual/` y `Documentación Grupal/`. El proyecto completo pasó a `Fase 2/Avances/` y los documentos formales a `Fase 2/Documentación Grupal/`. Quedan sólo las ramas `develop` y `main`; los PR #75 a #84 y las ramas de experimentos se integraron en el mismo cambio (26-10).
- Kronos se presenta como solución para **PyMEs sin especialista en ciberseguridad**, con el encargado de TI como usuario principal. Se valida en una PyME simulada, por retroalimentación del profesor guía (decisiones D-57 a D-65 del arranque del 26-10).
- **Documentación oficial e instalación en la raíz del repositorio** (27-10): los 31 documentos oficiales, en su versión corregida, pasan a `Documentacion/`, por área, y se retiran los 17 documentos v0.1 en Word de `docs/archivo/` (siguen en el historial de git). La guía de instalación pasa de `docs/instalacion/` a `Instalacion/`, con una carpeta por componente y las mismas 15 partes. Se agregan `Fase 3/` y `Paso a Paso/`, reservadas.

### Agregado

- Avisos de Telegram en lenguaje claro: la PyME, el equipo, qué pasó y qué hacer, sin códigos internos. Una medida de nivel 0 sin comando ya no avisa (D-50) (#78).
- CI: pruebas de la consola, pruebas de integración con PostgreSQL 17.11 y verificación de la entrega en los PR hacia `main` (#77). Desde la reestructuración, el CI corre también en cada cambio a `develop` y `main`.
- Catálogo KRO-CAT-01 1.0, con las acciones que tienen script en cada sistema operativo (D-60) (#83).
- `validate.json` 1.0, aprobada (D-65) (#84).

### Corregido

- Coherencia entre el código, la configuración y la documentación: `.env.example` con todas las variables, la imagen de servicios se construye una sola vez y los textos que seguían «pendientes» de cosas ya resueltas (#76).

### Documentación

- README completo con resumen en inglés, registro de cambios, política de seguridad y plantilla de pull request (#75).
- Diagramas al día con el estado real y la numeración de los 31 documentos (#79).
- Guía de instalación completa, en 15 partes (#80).
- Estructura de `docs/`: índice de los 31 documentos, registro de trabajo del 15 al 26-10, registro de decisiones y archivo de los documentos v0.1 (#81).
- Las ramas de experimentos del 14-10 quedan en el registro de mediciones, y el prompt v2 como parche en `decision/mediciones/experimentos/` (#82).

## Sprint 3: respuesta y niveles (20-10 al 02-11-2026)

### Agregado

- Script de Active Response `kronos-bloquear-ip` para Linux y parte 08 de la guía de instalación (#31).
- `kronos-bloquear-ip` para Windows: lanzador `.cmd` y script de PowerShell (#32).
- Tope de 64 KiB y retención de 90 días de las alertas guardadas, con purga diaria; la bitácora conserva sólo su huella (#34).
- Recuperador de tickets huérfanos: un ticket sin decisión a los 10 minutos pasa a revisión manual con aviso (#35).
- SOAR-VALIDATE: nota de ámbito de la IP en el paso 2, plazo de 120 s con precarga del modelo, exclusión de la puerta de enlace del laboratorio y agrupación de las alertas de un mismo ataque (#36).

### Documentación

- EP-WKS-01 en el PC de escritorio y estado del laboratorio (#33).
- Regla de merge D-54, roles Scrum y excepciones R-04 en `CONTRIBUTING.md` (#37).
- Documento 02: estados del ticket y del cortacircuito (#38).

### Hitos verificados

- **20-10:** primer ticket de punta a punta con alertas reales: fuerza bruta por SSH, bloqueo automático de la IP en EP-SRV-01 (ticket 20).
- **21-10:** reversión automática del nivel 1, a los 60 minutos y 3 segundos. SOAR-NOTIFY en el grupo de Telegram de los tres integrantes, con verificación en dos pasos. Agente de Windows (EP-WKS-01) activo.

## Sprint 2: núcleo de decisión (06 al 19-10-2026)

### Agregado

- **CI:** gitleaks, ruff y la regla R1 (#1); pruebas unitarias en cada PR (#18).
- **SOAR-AUDIT:** esquema multiinquilino con RLS y cadena de hash por inquilino (#2); motivos nuevos y una alerta por ticket (#16); capa de acceso para VALIDATE (#17); respaldo diario cifrado con age y prueba de restauración (#19); rol `kronos_console` y esquema `consola` (#23).
- **Detección:** compose de Wazuh sin secretos (#7) y las 15 reglas de sobre, de F1 a F6 (#8).
- **SOAR-CLASSIFY:** prompts en dos pasos y medición de la inferencia (#4); casos de frontera (#5); mediciones del 14-10 y elección de qwen2.5:7b (#12); Ollama con versión fija y parte 06 de la guía (#13); alertas en formato real (#14); 150 casos etiquetados (#15); plazos de reversión del nivel 1 en KRO-CAT-01 0.2 (#27).
- **SOAR-VALIDATE:** contrato JSON, chequeos, KRO-CAT-01 0.1 y casos de inyección (#6); mapa de severidad, exclusiones y contadores (#10); lectura de `alerts.json` y coincidencia con la regla de sobre (#11); alerta completa en el ticket (#25); ciclo y servicio `python -m validacion` (#28); despliegue en `servicios.yml` (#29 y #30).
- **SOAR-EXECUTE** (#20), **SOAR-NOTIFY** (#21) y su despliegue con Docker (#22).
- **SOAR-CONSOLE:** panel web con contraseña y TOTP (#24).

### Corregido

- Tres pruebas que fallaban sólo en Windows (#26).

### Documentación y evidencia

- Pruebas del esquema de SOAR-AUDIT en el servidor (#3).
- 17 documentos v0.1 preparados para la entrega del 16-10 (#9). El 15-10 los reemplazó la lista de 31 documentos, que se entregó el 16-10 y los usó como fuente.

### Hitos verificados

- **08-10:** SOAR-AUDIT desplegado y probado en el servidor: dos inquilinos en paralelo, concurrencia, inmutabilidad y manipulación detectada.
- **14-10:** mediciones de la IA en el servidor: con qwen2.5:7b, ninguno de los 10 ataques de inyección consiguió la familia que buscaba.
- **15-10:** restauración del respaldo: 2822 de 2822 eventos, 12 inquilinos y 0 cadenas rotas.

## Sprint 1: migración de infraestructura (25-09 al 05-10-2026)

- Replanteamiento del proyecto como servicio en la nube (25-09).
- Servidor SOAR-CORE-01 (Contabo, Francia, en hora UTC), red privada NetBird, Docker y Wazuh 4.14.8.
- Este sprint no tiene pull requests: el repositorio actual se creó el 06-10. La configuración de Wazuh entró en el sprint 2 (#7 y #8), y la instalación queda en la guía (`docs/instalacion/`, partes 01 a 05).
