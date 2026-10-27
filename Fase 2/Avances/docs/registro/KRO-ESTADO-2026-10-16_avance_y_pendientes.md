# Kronos AI — Avance y pendientes al 16-10-2026 (13:00, hora de Chile)

**Sprint actual:** S2, núcleo de decisión (06 al 19-10).
**Meta del sprint:** un ticket de nivel 0 o 1 se resuelve solo, de punta a punta.
**Avance estimado hacia la farmacia:** cerca del 62 %. Es una estimación ponderada por bloques, no una medición.

---

## 1. Lo que se hizo

### Equipo (mañana del 16-10)
- Cuentas de la consola SOAR-CONSOLE creadas para los tres (Nicolás, Patricio y Rodrigo), en el servidor y con TOTP.
- Presentación de avance al profesor.
- Documentos de la Fase 2 (2.1, 2.2 ×3, 2.3, 2.4 y 2.6) rellenados.

### Patricio
| PR | Qué hace | Estado |
| :--- | :--- | :--- |
| #25 | VALIDATE guarda la alerta completa en `detalle["alerta"]` del evento `ALERTA_RECIBIDA` (lo que EXECUTE necesita) | En `develop` |
| #26 | Omite en Windows 3 pruebas que fallan solo ahí (`skipIf`) | En `develop` |
| #27 | Plazos de reversión del nivel 1 en KRO-CAT-01 0.2 (60 min) | En `develop`, **como propuesta** |
| #28 | Ciclo de VALIDATE y servicio `python -m validacion` | En `develop` |
| #29 | Servicio `validate` en `infra/docker/servicios.yml` | En `develop` y **desplegado** |
| #30 | README: permisos de `kronos_worker_password` | **Abierto** |

**Despliegue de VALIDATE en SOAR-CORE-01:**
- Lee `alerts.json` en solo lectura (volumen `single-node_wazuh_logs`, `:ro`, `group_add` del GID 999).
- Solo monta el secreto `kronos_worker_password`, no la carpeta de secretos.
- Guarda la posición de lectura en el volumen `validate_estado` (`/estado/posicion.json`).
- Llega a Ollama por `http://ollama:11434` a través de la red interna `kronos_inferencia`, sin internet.
- Registro: `en marcha para el inquilino 1`; el contenedor ve a Ollama.
- Ollama no se recreó ni se tocaron sus modelos. Se creó a mano la red `kronos_inferencia` (`--internal`) y se conectó el contenedor `ollama` con el alias `ollama`.
- Problema resuelto: `kronos_worker_password` estaba `root:root 600` y el contenedor (uid 10001) no podía leerlo. Se dejó en `root:10001 640`.
- EXECUTE y NOTIFY siguen **apagados**, así que nada se ejecuta aunque VALIDATE apruebe.

**Verificado:**
- Prueba de integración del #25 (3/3).
- Prueba del ciclo del #28 (5/5, con la base y Ollama reales).
- VALIDATE corriendo como servicio en el servidor.

**No verificado:**
- Una alerta real recorriendo el servicio.
- Que `jsonb` rechace `\u0000` sin la sustitución.
- Si el paso 2 acierta el playbook (faltan los playbooks esperados de los 150 casos).

**Otros:** presentación v2 (diapositivas 6, 7 y 8) y el diario de reflexión de la Fase 2 (preguntas 5 y 6 por confirmar con el grupo).

---

## 2. Lo que falta para cerrar el Sprint 2

1. **Prueba real de punta a punta con VALIDATE (Patricio y Nicolás).**
   - Ataque simulado de SSH contra EP-SRV-01 (unos 10 intentos con un usuario inexistente) para disparar la regla 100101.
   - Esperado: una línea `lote de N alertas` en el registro de `validate` y el ticket con su decisión en la consola.
2. **Encender EXECUTE y NOTIFY.** Hoy sus secretos están vacíos (`telegram_token`, `wazuh_api_ca.pem` y `wazuh_api_password` miden 0 bytes). Faltan:
   - el usuario de la API de Wazuh `kronos-execute`, solo con `active-response:command` (Nicolás);
   - los comandos `kronos-*` en el manager, sin bloques `<active-response>` (Nicolás);
   - los scripts `kronos-*` en los agentes del laboratorio (Nicolás);
   - el bot de Telegram (token directo al gestor, nunca al chat).

---

## 3. Pendientes por persona

### Nicolás
- [ ] Hacer la prueba real de SSH con Patricio.
- [ ] Revisar la red `kronos_inferencia`, que Patricio creó a mano. Antes de pasar Ollama al compose de `infra/ollama` hay que borrarla.
- [ ] Usuario de API `kronos-execute` y comandos `kronos-*` en el manager.
- [ ] Verificar en el laboratorio que la 4.14.8 acepte el prefijo `!` y entregue `arguments`.
- [ ] Scripts `kronos-*` en EP-SRV-01.
- [ ] EP-WKS-01: renombrar, instantánea `base-limpia` e instalar el agente.
- [ ] Regenerar la llave del agente 001.
- [ ] Confirmar el `agent.id` de la alerta de agente caído (regla 100115).
- [ ] PR con las observaciones a las reglas (92652 en la 100107; nivel de la 100115).
- [ ] Autorizar la llave SSH propia de Rodrigo en el servidor (hoy entró con la cuenta de Nicolás).
- [ ] Copia del respaldo fuera del servidor y reiniciar el notebook para reactivar HVCI.
- [ ] Presentación: usar la v2 de Patricio, cambiar 269 por **270** pruebas en la diapositiva 13 y marcar VALIDATE como **desplegado** en la diapositiva 4.

### Patricio
- [ ] Prueba real con Nicolás.
- [ ] Documento 02 §8.1 con los estados nuevos.
- [ ] Quitar de `preguntas-abiertas.md` las filas #6, #28, #38, #44 y #45.
- [ ] Si el equipo lo pide, responder las preguntas de los documentos marcadas «preguntar a Patricio».
- [ ] Etiquetar el playbook de los 150 casos (bloqueado hasta que el equipo decida si los playbooks serán de uno o de varios pasos).

### Rodrigo
- [ ] Revisar los PR #29 y #30, incluido el cambio en `infra/ollama/docker-compose.yml`: `kronos_inferencia` pasa a ser interna y Ollama suma la red `salida`.
- [ ] Recuperador de tickets sin decisión.
- [ ] Tope y retención de las alertas guardadas (datos personales, R-09).
- [ ] Comandos de respuesta activa para los 9 playbooks sin comando.
- [ ] Job de CI con FastAPI para las 13 pruebas de consola omitidas.
- [ ] Vista de solo lectura para el encargado del cliente.
- [ ] Parte 07 de la guía de instalación.
- [ ] Pasar sus secretos al gestor y bajar su rol de NetBird a User.
- [ ] Decidir si habrá códigos de recuperación del TOTP.

### Los tres
- [ ] Confirmar o ajustar los 60 minutos de reversión del nivel 1 (#27).
- [ ] Revisar las 25 condiciones de uso del catálogo.
- [ ] Decidir si los playbooks serán de varios pasos (Patricio recomienda un solo paso por ahora).
- [ ] Definir cómo se asigna el inquilino a cada alerta y las redes internas de cada cliente (`validate.json`).
- [ ] Crear el bot de Telegram y activar la verificación en dos pasos en las tres cuentas.
- [ ] Definir el gestor de contraseñas y la custodia de la cuenta `soaria186`.
- [ ] Revisar después del hecho los PR **#25 al #29**, o anotarlos como excepción junto con los #7 al #16, que se integraron sin revisión registrada. Desde ahora, cada PR lo aprueba otro integrante antes de integrarlo.

---

## 4. Orden de avance

1. **Ahora:** prueba real de VALIDATE (Patricio y Nicolás) · revisión de #29 y #30 (Rodrigo) · usuario de API y comandos en el manager (Nicolás).
2. **Después:** scripts en los agentes y EP-WKS-01 (Nicolás) · bot de Telegram → encender EXECUTE y NOTIFY.
3. **Reunión corta de los tres:** plazos del nivel 1, playbooks de uno o varios pasos, inquilino y redes internas.
4. **Prueba integral en el laboratorio:** alerta → VALIDATE → EXECUTE → NOTIFY → consola, con un caso de cada nivel (1, 2 y 3) y una reversión.
5. **Preparación de la farmacia:** lista de exclusión, inquilino y fecha → instalación de los agentes.

**Fechas clave:** cierre del S2 el **19-10** · punto de no retorno el **07-11**: si no hay un ticket ejecutado solo contra un equipo real, se activa la contingencia.
