# Registro de trabajo — Rodrigo Riveros

| Campo | Valor |
| :--- | :--- |
| Código | KRO-LOG-RR-2026-10-08 (propuesto) |
| Fecha | Jueves 8 de octubre de 2026 (18:24 a 19:50, hora de Chile) |
| Integrante | Rodrigo Riveros — capa de persistencia y ejecución |
| Etapa | 1 — Infraestructura y detección |
| Estado de la jornada | SOAR-AUDIT cerrado: esquema en `develop`, desplegado y probado en SOAR-CORE-01, base vacía. Falta el respaldo |

> **Cómo leer los estados**
> - ✅ **Verificado:** hay evidencia (salida de terminal o pantalla de GitHub).
> - 🟡 **Informado por el asistente de código:** el resultado lo reportó la herramienta y no se reprodujo.
> - ⏳ **Pendiente.**
>
> Este documento no contiene secretos, contraseñas, llaves ni tokens. Las contraseñas del servidor se generan allí y no se escriben aquí.

---

## 1. Resumen

El esquema de SOAR-AUDIT quedó completo en una sola jornada:
1. Se probó desde cero en el PC, sobre un volumen recién creado.
2. Se integró a `develop` por el PR #2, con los tres checks de CI en verde.
3. Se desplegó en SOAR-CORE-01 y se probó ahí con las cuatro pruebas.
4. La base del servidor se recreó y quedó vacía, lista para datos reales.
5. La evidencia del servidor se subió a `develop` por el PR #3.

Queda pendiente el respaldo (`pg_dump` y restauración probada) y varias decisiones de equipo.

---

## 2. Qué se hizo

### 2.1 Verificación inicial de la rama

| Tarea | Estado | Evidencia |
| :--- | :---: | :--- |
| Rama `feat/e1-esquema-audit` limpia y al día con GitHub | ✅ | `git status`: `working tree clean` |
| Los tres commits de pruebas presentes | ✅ | `2354237`, `0beeee4`, `f521fa2` |
| Detectar la rama nueva de Patricio | ✅ | `git fetch` trajo `feat/e1-medicion-inferencia` |

### 2.2 Prueba del esquema desde cero, en el PC

| Tarea | Estado | Evidencia |
| :--- | :---: | :--- |
| Recrear el volumen (`docker compose down -v` y `up -d`) | ✅ | `kronos_pgdata` eliminado y creado de nuevo |
| `initdb` sobre una base nueva | ✅ | Extensión, esquema y roles se ejecutaron sin errores |
| Batería `tests/sql/ejecutar.sh` | ✅ | «Todas las pruebas pasaron», con los inquilinos 1, 2 y 3 (antes eran 7, 8 y 9, sobre datos previos) |
| Contenedor sin puertos publicados | ✅ | `docker compose ps` muestra sólo `5432/tcp` |
| Salida guardada en `docs/evidencia/esquema-audit-pruebas-2026-10-08.txt` | ✅ | Archivo de 160 líneas, sin contraseñas |

**Resultados de las pruebas** (como `kronos_worker`, no superusuario):

| Prueba | Resultado |
| :--- | :--- |
| a) Dos inquilinos en paralelo | Cada uno: 1000/1000 transacciones, `seq` 1..1000, cadena íntegra y 0 filas ajenas visibles. Cada uno recibe `42501` al verificar o escribir en la cadena del otro |
| b) Un inquilino, 8 conexiones × 100 filas | 800/800, `seq` 1..800, 799 cambios de conexión entre filas consecutivas, cadena íntegra |
| c) UPDATE, DELETE y TRUNCATE | Rechazados para `kronos_worker` (8/8) y para `kronos_admin` (16/16, incluso con `session_replication_role = replica`). La cadena sigue íntegra |
| d) Manipulación en una copia | Detectada en cada caso: contenido alterado (seq 400), enlace roto (seq 101) y fila borrada (seq 50) |

### 2.3 Revisiones del hash

Resultado 🟡 **informado por el asistente de código** (no se reprodujo la salida de cada comprobación):

| Revisión | Resultado |
| :--- | :--- |
| El hash no depende de la zona horaria de la sesión | `fn_verificar_cadena` devolvió `NULL` desde sesiones en `Etc/UTC`, `America/Santiago`, `Asia/Kathmandu` y `Pacific/Chatham`. También con una fila insertada desde Santiago y verificada en UTC. La función convierte la fecha con `AT TIME ZONE 'UTC'` |
| Columnas que entran al hash | `tenant_id`, `seq`, `ticket_id`, `evento`, `actor`, `detalle`, `creado_en` (en UTC) y el hash anterior |
| Sensibilidad | Con `tenant_id + 1` o `seq + 1` el hash cambia. Con otro `id` no cambia, por diseño: la cadena se define por `(tenant_id, seq)` |
| La función en la base coincide con el archivo | Sí, según el asistente de código |

**Decisión de Rodrigo:** no agregar la prueba de regresión «e» que cubriría estas dos propiedades. Queda anotado como una protección que no existe: un cambio futuro al trigger podría romper el hash sin que ninguna prueba lo detecte.

### 2.4 Integración a `develop` (PR #2)

| Tarea | Estado | Evidencia |
| :--- | :---: | :--- |
| Commit de la evidencia (`31b890e`) | ✅ | gitleaks `Passed`; push sin `--force` |
| Crear el PR | ✅ | El primer intento falló con un error de GraphQL de GitHub; el reintento funcionó: PR #2 |
| Checks de CI | ✅ | R1, gitleaks y ruff: 3 de 3 en verde |
| Merge a `develop` | ✅ | `develop` pasó de `ae85df7` a `05a4e2b`: 15 archivos y 1032 líneas |
| Ramas borradas, local y remota | ✅ | `feat/e1-esquema-audit` eliminada |
| Sin secretos en el repositorio | ✅ | Sólo `03_roles.sql.example` y `generar_secretos.sh`; `03_roles.sql` y `secrets/` ignorados |

### 2.5 Despliegue en SOAR-CORE-01

| Tarea | Estado | Evidencia |
| :--- | :---: | :--- |
| Empaquetar sólo lo versionado con `git archive` | ✅ | Paquete `kronos-audit.tar.gz`, sin secretos |
| Copiar al servidor por `scp` | ✅ | Tras activar NetBird en el PC (ver sección 4) |
| Desplegar en `/opt/kronos/audit` | ✅ | `docker-compose.yml`, `generar_secretos.sh` e `initdb` presentes |
| El compose no publica puertos | ✅ | `grep ports` sin resultados; `ss -tlnp \| grep 5432` sin resultados |
| Secretos generados en el servidor | ✅ | `generar_secretos.sh` creó `secrets/postgres_password` e `initdb/03_roles.sql` |
| Permisos para el usuario `postgres` de la imagen (uid 999) | ✅ | `03_roles.sql`: `640`, dueño 999. `postgres_password`: `400`, dueño 999 |
| `initdb` completo en el servidor | ✅ | Se ejecutaron los tres scripts; «init process complete»; contenedor `healthy` |
| Batería de pruebas en el servidor | ✅ | «Todas las pruebas pasaron», inquilinos 1, 2 y 3 |
| Base recreada y vacía | ✅ | `docker compose down -v` y `up -d`; `select count(*) from auditoria` → `0` |
| Política de reinicio | ✅ | `restart: unless-stopped` en el compose |

### 2.6 Evidencia del servidor (PR #3)

| Tarea | Estado | Evidencia |
| :--- | :---: | :--- |
| Traer la salida al PC por `scp` | ✅ | `esquema-audit-servidor-2026-10-08.txt`, 9953 bytes |
| Buscar secretos en el archivo | ✅ | Sin coincidencias para `passw` ni `secret` |
| Commit (`2b06744`) | ✅ | gitleaks `Passed` |
| PR #3, checks y merge | ✅ | R1, gitleaks y ruff en verde; `develop` pasó de `05a4e2b` a `532ec58` |

---

## 3. Decisiones tomadas hoy

| Decisión | Detalle |
| :--- | :--- |
| Omitir la prueba de regresión «e» (hash independiente de la zona) | Decisión de Rodrigo. La propiedad queda verificada una vez, y sin protección contra cambios futuros |
| Fusionar los PR #2 y #3 sin revisión de otro integrante | Decisión de Rodrigo, que se aparta de la regla del traspaso. Los checks automáticos pasaron |
| Mantener Docker Desktop en el PC | Se usa para probar el respaldo, las migraciones y los servicios siguientes antes de llevarlos al servidor |
| La batería de pruebas se corre sólo una vez en el servidor | Deja filas inmutables; la base se recrea después de probar |
| Los secretos del servidor se generan allí | No viajan por el repositorio ni por el paquete |

---

## 4. Incidencias resueltas

| # | Síntoma | Causa y solución |
| :---: | :--- | :--- |
| 1 | `scp`: `Connection timed out` hacia `[IP de NetBird omitida]` | NetBird estaba apagado en el PC. Se activó, y la conexión funcionó |
| 2 | `gh pr create` falló con `GraphQL: Something went wrong` | Error pasajero de GitHub. Se repitió el comando un minuto después |
| 3 | `gh pr checks` y `gh pr merge` respondieron «no pull requests found» | Se ejecutaron estando en `develop`, o con el marcador `NUMERO` sin reemplazar. No tuvieron efecto. **Los comandos de PR llevan el número y el merge va aparte, con los checks a la vista** |
| 4 | Riesgo de que PostgreSQL no pudiera leer `03_roles.sql` (permisos 600) | La imagen corre como `uid 999`. Se dejó `03_roles.sql` en 640 con dueño 999, y `postgres_password` en 400 |
| 5 | PowerShell arrancaba en `C:\WINDOWS\System32` | Se había abierto como administrador. Para este trabajo se usa PowerShell normal |
| 6 | `ls infra\docker` en `develop` sólo mostraba `initdb` y `secrets` | Era lo esperado antes del merge, porque el esquema aún no estaba en `develop` |

---

## 5. Estado actual de SOAR-AUDIT

| Aspecto | Estado |
| :--- | :--- |
| Esquema en `develop` | ✅ |
| Probado en el PC y en el servidor | ✅ |
| PostgreSQL 17.11 corriendo en SOAR-CORE-01, sin puertos publicados | ✅ |
| Base vacía, sin inquilinos de prueba | ✅ |
| Respaldo | ❌ No existe |
| Alguien que se conecte a la base | ❌ SOAR-VALIDATE y SOAR-CONSOLE aún no existen |
| `systemctl is-enabled docker` | ⏳ No comprobado: sin eso, la política de reinicio no sirve |

---

## 6. Pendientes

**Respaldo (siguiente tarea)**
- [ ] Rama `feat/e2-respaldo`: `respaldo.sh`, `restaurar_prueba.sh` y el temporizador de systemd.
- [ ] Comprobar si la restauración altera la cadena de hash. Si el trigger se dispara al restaurar, usar `--disable-triggers` y documentar por qué.
- [ ] Decidir la **copia fuera del servidor**, cifrada y sin pasar por PC personales.
- [ ] Decidir la retención: respaldos diarios y semanales.

**Operación**
- [ ] `systemctl is-enabled docker` en el servidor.
- [ ] Guardar en el gestor de contraseñas los secretos del servidor (no se pueden recuperar de otro lado). Pedir el procedimiento sin mostrarlos en pantalla.
- [ ] Comparar la huella SHA256 de `02_esquema.sql` entre el PC y el servidor (opcional).

**Diseño**
- [ ] Decidir cómo se conectan SOAR-VALIDATE y SOAR-CONSOLE a la base, que no publica puertos: contenedores en la red `kronos_interna` o un socket compartido.
- [ ] Un mecanismo para entregar las contraseñas de `kronos_worker` y `kronos_frontend` a cada componente sin pasarlas por el chat ni por el repositorio.
- [ ] Evaluar correr `tests/sql` en el CI con un contenedor de PostgreSQL.

**Proceso y documentos**
- [ ] Revisar `feat/e1-test-r1`: si tiene PR abierto y si pasa en el CI.
- [ ] Revertir el rol de NetBird de Rodrigo a *User*, o acordar un respaldo con Nicolás.
- [ ] Documentos: Proceso de Integración Continua, Estándares de Codificación y borrador del Documento de Seguridad de la Plataforma.
- [ ] Subir los registros de trabajo a `docs/registro/` del repositorio.

---

## 7. Límites y notas
- Las revisiones del hash (sección 2.3) son del asistente de código. La salida de las cuatro pruebas del servidor, en cambio, está verificada con la terminal.
- El grupo `systemd-journal` que aparece como dueño del archivo de contraseña en el servidor es sólo el nombre que el sistema da al grupo 999. No cambia nada.
- Los datos de cada cliente real vivirán en este servidor. Siguen abiertas la brecha de retención de registros (BR-01) y el acuerdo de tratamiento de datos con el proveedor (BR-05).
