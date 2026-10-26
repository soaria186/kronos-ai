# Notificación (SOAR-NOTIFY)

Avisa por Telegram al grupo de la PyME (el encargado de TI y el equipo Kronos, que lo
respalda) y recibe sus respuestas a las solicitudes de nivel 3 (RF-13, RF-16, CU-02).
Quién puede aprobar lo fija `KRONOS_TELEGRAM_EQUIPO` (D-59; antes D-31, sólo el equipo). El
aviso a la persona afectada es por correo y manual (D-35), así que NOTIFY no envía correos.

| Módulo | Qué hace |
| :--- | :--- |
| `mensajes.py` | Textos de los avisos (texto plano, títulos recortados y sin saltos de línea) y formato de los botones |
| `telegram.py` | Cliente de la API de bots. Sólo conexiones salientes; el token nunca aparece en un error |
| `avisos.py` | Por inquilino: genera los recordatorios diarios del nivel 2 y envía los avisos pendientes de la bitácora |
| `respuestas.py` | Botones «Aprobar» y «Rechazar» del nivel 3; el rechazo pide el motivo como respuesta al mensaje del bot |
| `__main__.py` | Servicio: `python -m notificacion` |

## Qué se avisa

Los avisos los lee el encargado de TI de la PyME, que no es especialista en seguridad. Cada uno
dice, en palabras simples, qué pasó (el título de la alerta, con la familia en palabras), en qué
PyME y equipo, qué hizo Kronos (la medida con su nombre del catálogo y su efecto) y **qué tiene
que hacer la persona**. No llevan códigos internos (`PB-…`, `D-…`) ni la palabra «inquilino».
Ejemplo:

```text
[APROBACIÓN] Kronos necesita una decisión
PyME de demostración · ticket #24 · equipo EP-WKS-01
Qué pasó: registro de auditoría borrado (cambio en el sistema)
Kronos propone: aislar un equipo de trabajo.
Efecto: sin internet ni red.
Qué hacer: aprobar o rechazar con los botones o en la consola. Si nadie responde en 2 días, no se ejecuta y queda en revisión manual.
[Aprobar] [Rechazar]
```

| Evento | Aviso |
| :--- | :--- |
| `DECISION` aprobada de nivel 3 | `[APROBACIÓN]`: la medida propuesta, su efecto y los botones. Plazo de 2 días (D-32) |
| `EJECUCION_OK` de nivel 2 | `[MEDIDA APLICADA]`: la medida, su objetivo y su efecto; avisar por correo a la persona afectada y revisarla en la consola |
| `RECORDATORIO_REVISION` | `[RECORDATORIO]`: nivel 2 sin revisar tras 2 días; uno por día (D-33) |
| `APROBACION_VENCIDA` | `[VENCIDA]`: nivel 3 sin respuesta; quedó en revisión manual sin ejecutarse (D-34) |
| `TICKET_SIN_DECISION` | `[SIN DECISIÓN]`: VALIDATE no registró la decisión en 10 minutos; revisión manual sin ejecutar nada |
| `EJECUCION_FALLIDA` | `[NO SE APLICÓ]`: por qué, en palabras (equipo apagado, medida no disponible, objetivo inválido) y qué revisar |
| `REVERSION_FALLIDA` | `[NO SE REVIRTIÓ]`: la medida sigue aplicada; quitarla a mano o volver a pedir la reversión (D-51) |
| `CORTACIRCUITO_ABIERTO` | `[DETENIDO]`: Kronos dejó de actuar solo; cómo volver a habilitarlo |

**No se avisa** la falla de una consulta de nivel 0 cuya acción no tiene comando
(`ACCION_NO_IMPLEMENTADA`, D-50): queda en la consola, pero no llena el grupo.

Cada aviso enviado deja `AVISO_ENVIADO` en la bitácora, con el mensaje de Telegram.
Si Telegram falla, el aviso se reintenta en el ciclo siguiente: puede llegar repetido,
pero no se pierde. Un solo proceso de NOTIFY a la vez.

## Seguridad de las respuestas

- Sin puertos de entrada: las respuestas se leen con `getUpdates` (consulta larga).
- Sólo cuentan el chat del equipo y las cuentas de `KRONOS_TELEGRAM_EQUIPO`. Un botón
  de otra cuenta se rechaza y queda en el registro del servicio.
- Quien aprueba o rechaza queda como actor del evento (`telegram:<nombre>`).
- Un ticket que ya no espera aprobación (otro integrante respondió o venció) no cambia.
- Pendiente del equipo: verificación en dos pasos en las cuentas de Telegram (pregunta
  abierta #39).

## Servicio

| Variable | Qué es |
| :--- | :--- |
| `KRONOS_DSN`, `KRONOS_DB_CLAVE_ARCHIVO`, `KRONOS_INQUILINOS` | Como en SOAR-EXECUTE |
| `KRONOS_TELEGRAM_TOKEN_ARCHIVO` | Archivo con el token del bot (secreto; al gestor) |
| `KRONOS_TELEGRAM_CHAT` | Identificador del grupo del equipo |
| `KRONOS_TELEGRAM_EQUIPO` | Cuentas que pueden aprobar: `id:nombre,id:nombre` |
| `KRONOS_NOMBRES_INQUILINOS` | Opcional: nombre de cada PyME en los avisos, `inquilino:nombre,…`. Sin él, «PyME 1» |
| `KRONOS_ESPERA_SEGUNDOS` | Espera de la consulta larga (20 por omisión) |
