# Evidencia · PB-F6-05, detener un servicio de apoyo del puesto · 11 y 12-11-2026

**Presentes:** Rodrigo Riveros (VM, consola y registros) y Nicolás Zamora (servidor y aprobación por Telegram).
**Equipo:** EP-WKS-01 (agente 002, Windows 11). **Servicio de prueba:** `Spooler` (cola de impresión).
**Regla:** 100120, severidad 12 (evento 7031 del Service Control Manager). **Nivel de la medida:** 3, con aprobación de una persona.
**Horas:** en UTC; en Chile son 3 horas menos.

---

## 1. Resultado

| Paso | Ticket | Hora | Evidencia | Resultado |
| :--- | :-: | :-: | :--- | :-: |
| Se termina el proceso de `Spooler` en la VM (`Stop-Process -Name spoolsv -Force`); Windows registra el evento 7031 | #207 | 12-11 20:42 | — | ✅ |
| La alerta llega con la regla 100120; VALIDATE propone PB-F6-05 y pide aprobación (nivel 3) | #207 | 20:42 | [Telegram](capturas/telegram-aprobacion-t207.png), [consola](capturas/consola-espera-aprobacion-t207.png) | ✅ |
| Aprobación por Telegram | #207 | 20:43 | [Telegram](capturas/telegram-aprobacion-t207.png) | ✅ |
| EXECUTE detiene el servicio; queda `Stopped` | #207 | 20:44:01 (EXECUTE) y 20:44:02 (equipo) | [registros](registros.txt) | ✅ |
| Reversión desde la consola; el servicio vuelve a `Running` | #203 | 20:58:55 (EXECUTE) y 20:58:58 (equipo) | [consola antes](capturas/consola-vigente-t203.png), [consola después](capturas/consola-revertido-t203.png), [registros](registros.txt) | ✅ |

El #203 es el mismo playbook, del 11-11. Ese día la alerta del 7031 abrió el ticket, se aprobó por Telegram y se ejecutó a las 20:51:12 (`aplicar Spooler OK`). Quedó vigente hasta esta prueba.

## 2. Acción por la API (11-11)

Antes del recorrido completo, `kronos-detener-servicio.cmd` se probó por la API de Wazuh con `probar-ar-api.sh`:

- `aplicar Spooler` a las 20:49:10: el servicio queda `Stopped`.
- `iniciar Spooler` a las 20:49:39: el servicio vuelve a `Running`.

Las líneas están en [registros.txt](registros.txt).

## 3. Lo que no salió como se esperaba

- **La reversión del #207 falló.** La VM se reinició por actualizaciones de Windows y arrancó a las 20:51:46. La reversión se pidió a las 20:52:53, cuando el agente todavía no se conectaba, así que la orden no llegó (`reversiones_fallidas: [207]`). Kronos no reintenta una reversión fallida (igual que el #188). Por eso la reversión se demostró con el #203.
- **La consola deja el #207 en «Reversión en curso»:** no lo saca de las medidas vigentes ni ofrece reintentarlo. En el equipo ya no queda nada pendiente: la reversión del #203 inició el servicio y borró la marca de Kronos.
- **Antes de la prueba,** el evento 7031 no llegaba al manager: sólo llegaban el arranque del agente y el escaneo de configuración. Se resolvió después del reinicio y de las actualizaciones de la VM.
- **En la VM, `Spooler` tiene configurados sólo dos reinicios automáticos por hora** (`sc.exe qfailure Spooler`). Una tercera prueba dentro de la misma hora no sirve, porque Windows ya no reinicia el servicio.

## 4. Para la defensa

- Pausar las actualizaciones de Windows en EP-WKS-01.
- Presionar «Revertir» sólo después de confirmar que el agente está `Active` (`probar-ar-api.sh estado`).
