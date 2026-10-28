# Evidencia de las pruebas

Salidas, extractos y capturas que respaldan lo que dicen el README del repositorio y los documentos de pruebas
(6.2 a 6.5). Lo que se muestra en la defensa tiene su respaldo aquí.

## Lo que hay

| Archivo | Prueba | Fecha |
| :--- | :--- | :--- |
| [`esquema-audit-pruebas-2026-10-08.txt`](esquema-audit-pruebas-2026-10-08.txt) | Esquema de SOAR-AUDIT en la base de pruebas: a) dos inquilinos en paralelo, b) un inquilino con 8 conexiones, c) `UPDATE`, `DELETE` y `TRUNCATE` rechazados en la bitácora y d) manipulación detectada por la cadena de hash | 08-10-2026 |
| [`esquema-audit-servidor-2026-10-08.txt`](esquema-audit-servidor-2026-10-08.txt) | Las mismas pruebas en SOAR-CORE-01 | 08-10-2026 |

## Lo que se agrega en la semana de cierre

| Qué | Quién | Cuándo |
| :--- | :--- | :--- |
| Tickets #19 y #20 del 20-10: el primer recorrido completo con alertas reales (fuerza bruta por SSH, bloqueo de la IP en EP-SRV-01) | Nicolás | Jue 29-10 |
| Reversión automática del 21-10: la regla se quitó a los 60 minutos y 3 segundos | Nicolás | Jue 29-10 |
| Prueba integral, escenarios E1 a E7 ([parte 15 de la guía](../../../../Instalacion/10-Operacion-y-Verificacion/15-verificacion-de-punta-a-punta.md)): capturas de Telegram y de la consola, extractos de registros y de la bitácora | Nicolás y Patricio | Jue 29-10 |
| Tabla de métricas de cada escenario: familia y medida esperadas y obtenidas, tiempos y falla segura | Patricio | Vie 30-10 |
| Prueba de estrés: 30 alertas en 10 minutos y apertura del cortacircuito (E6) | Patricio | Vie 30-10 |

## Cómo se guarda

- **Nombre:** `AAAA-MM-DD_<prueba>_<detalle>.<ext>`, por ejemplo `2026-10-29_E1_bitacora.txt` o
  `2026-10-29_E4_aprobacion-telegram.png`.
- **Texto antes que imagen:** los registros y las consultas a la bitácora van como `.txt`; las capturas, en PNG,
  recortadas a lo que muestran.
- **Sólo el extracto necesario:** una alerta completa de Wazuh puede traer datos personales.
- **Nada que no deba publicarse:** ni identificadores de Telegram (en las capturas se recortan o se tapan), ni el
  usuario del bot, ni usuarios del servidor, ni IP reales del servidor o de NetBird. Las IP de los ataques
  simulados son de documentación (`203.0.113.0/24`, `198.51.100.0/24`) o de la red del laboratorio.
- Por PR a `develop`, revisado por otro integrante (D-54).
