# Notificación (SOAR-NOTIFY)

Avisa al equipo por Telegram y recibe sus respuestas a las solicitudes de nivel 3
(D-31, RF-13, RF-16, CU-02). Sólo el equipo recibe avisos; el aviso a la persona
afectada es por correo y manual (D-35), así que NOTIFY no envía correos.

| Módulo | Qué hace |
| :--- | :--- |
| `mensajes.py` | Textos de los avisos (texto plano, títulos recortados y sin saltos de línea) y formato de los botones |
| `telegram.py` | Cliente de la API de bots. Sólo conexiones salientes; el token nunca aparece en un error |
| `avisos.py` | Por inquilino: genera los recordatorios diarios del nivel 2 y envía los avisos pendientes de la bitácora |
| `respuestas.py` | Botones «Aprobar» y «Rechazar» del nivel 3; el rechazo pide el motivo como respuesta al mensaje del bot |
| `__main__.py` | Servicio: `python -m notificacion` |

## Qué se avisa

| Evento | Aviso |
| :--- | :--- |
| `DECISION` aprobada de nivel 3 | Solicitud de aprobación, con botones. Plazo de 2 días (D-32) |
| `EJECUCION_OK` de nivel 2 | Medida aplicada; recordar el correo a la persona afectada |
| `RECORDATORIO_REVISION` | Nivel 2 sin revisar tras 2 días; uno por día (D-33) |
| `APROBACION_VENCIDA` | Nivel 3 sin respuesta: quedó en revisión manual (D-34) |
| `EJECUCION_FALLIDA` / `REVERSION_FALLIDA` | Falló una medida o su reversión |
| `CORTACIRCUITO_ABIERTO` | Ejecución automática detenida |

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
| `KRONOS_ESPERA_SEGUNDOS` | Espera de la consulta larga (20 por omisión) |
