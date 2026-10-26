# 11 · Telegram

| Campo | Valor |
| :--- | :--- |
| Parte | 11 de 15 |
| Responsable | Rodrigo Riveros (revisa: Patricio González) |
| Versión | 0.9, 26-10-2026 |
| Estado | Borrador para revisión: sale de la puesta en marcha de SOAR-NOTIFY del 21-10-2026 y de `infra/docker/servicios/README.md` |
| Requisitos | Parte 07 |

SOAR-NOTIFY avisa por Telegram al grupo de la PyME (el encargado de TI y el equipo Kronos) y recibe ahí la
aprobación o el rechazo de las medidas de nivel 3, con botones. Sólo hace conexiones salientes a
`api.telegram.org`: no abre puertos.

---

## 1. El bot

1. En Telegram, hablar con **@BotFather**: `/newbot`, un nombre («Kronos AI») y un usuario para el bot.
2. BotFather entrega el **token**: es un secreto. Va al gestor de contraseñas del equipo y al servidor, nunca a un
   chat ni al repositorio.

## 2. El token al servidor, sin pasar por la pantalla

Con el token copiado en el portapapeles del PC:

```
[PC]       Get-Clipboard | ssh soar-core-01 'umask 077; cat > ~/token.tmp'
[servidor] sudo install -o root -g 10001 -m 640 ~/token.tmp /opt/kronos/audit/infra/docker/secrets/telegram_token
[servidor] shred -u ~/token.tmp
[servidor] sudo wc -c /opt/kronos/audit/infra/docker/secrets/telegram_token
```

**Debe mostrar:** entre 46 y 48 bytes: el token y, a veces, un salto de línea, que NOTIFY descarta. Después,
vaciar el portapapeles del PC.

## 3. El grupo

1. Crear un grupo («Kronos — avisos») con el encargado de TI, los integrantes del equipo y el bot.
2. Que quede como **grupo**, no supergrupo: al convertirse, su identificador cambia y los avisos dejan de llegar.
3. **Verificación en dos pasos** activada en todas las cuentas del grupo: quien entra a una de ellas puede
   aprobar medidas (en el proyecto, activada el 21-10-2026).
4. Cuando todos están dentro, revocar el enlace de invitación.

## 4. Identificadores

**Sólo antes de levantar NOTIFY:** escribir algo en el grupo y abrir en el navegador
`https://api.telegram.org/bot<token>/getUpdates`. Con NOTIFY en marcha, abrir esa dirección le quita las
respuestas a los botones.

- `chat.id` (un número negativo) va a `KRONOS_TELEGRAM_CHAT`.
- El `from.id` de cada persona que puede aprobar va a `KRONOS_TELEGRAM_EQUIPO`, con su nombre:
  `id:nombre,id:nombre`. Son el encargado de TI y el equipo Kronos (D-59).

Estos identificadores no van al repositorio ni a los registros de trabajo.

## 5. Configuración de NOTIFY

En `infra/docker/.env` (parte 07, sección 4):

| Variable | Valor |
| :--- | :--- |
| `KRONOS_TELEGRAM_CHAT` | El identificador del grupo |
| `KRONOS_TELEGRAM_EQUIPO` | Las cuentas que pueden aprobar |
| `KRONOS_NOMBRES_INQUILINOS` | El nombre de la PyME en los avisos, por ejemplo `1:PyME de demostración`. Sin él, los avisos dicen «PyME 1» |

```
[servidor] cd /opt/kronos/audit/infra/docker
[servidor] sudo docker compose -f docker-compose.yml -f servicios.yml up -d notify
[servidor] sudo docker compose -f docker-compose.yml -f servicios.yml logs --tail 5 notify
```

**Debe mostrar:** `en marcha para los inquilinos [1]; equipo de N cuentas`, con N igual al número de personas
de `KRONOS_TELEGRAM_EQUIPO`.

## 6. Comprobar los botones

En la prueba integral (parte 15, escenario E4) llega un aviso «[APROBACIÓN] Kronos necesita una decisión» con
los botones **Aprobar** y **Rechazar**:

- **Aprobar** cambia el ticket a `PENDING`; EXECUTE lo ejecuta y el grupo recibe «Ticket #N aprobado por …».
- **Rechazar** pide el motivo como respuesta al mensaje del bot; el ticket queda en `REJECTED` con ese motivo.
- Un botón de una cuenta que no está en `KRONOS_TELEGRAM_EQUIPO` se rechaza («No autorizado») y queda en el
  registro de NOTIFY.

## 7. Si se filtra el token

1. En @BotFather, `/revoke` para el bot: el token anterior deja de servir.
2. Cargar el nuevo como en la sección 2 y recrear `notify`.
3. Dejar constancia en el registro del día, sin el token.

## 8. Lista de comprobación

- [ ] Token en el gestor y en `secrets/telegram_token` (`root:10001`, 640), nunca en un chat.
- [ ] Grupo (no supergrupo) con el encargado de TI, el equipo y el bot; enlace de invitación revocado.
- [ ] Verificación en dos pasos en todas las cuentas.
- [ ] NOTIFY en marcha con el número correcto de cuentas.
- [ ] Botones probados en E4.
