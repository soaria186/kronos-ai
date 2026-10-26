# Conectores

Lectura de las alertas de Wazuh para SOAR-VALIDATE. Es el único punto por donde entran datos de afuera a la
decisión.

| Módulo | Qué hace |
| :--- | :--- |
| `alertas_wazuh.py` | Lee `alerts.json` del manager de Wazuh de forma incremental y en sólo lectura. Sólo procesa líneas completas, guarda la posición (inodo y desplazamiento) para retomar tras un reinicio y sigue la rotación diaria de las 00:00 UTC sin perder alertas |

El archivo llega al contenedor de VALIDATE como el volumen de logs del manager, montado con `:ro`, y el
contenedor lo lee a través del grupo `wazuh`. Montaje y permisos: `infra/docker/servicios/README.md`
(sección SOAR-VALIDATE) y la parte 07 de la guía de instalación.

**Lo que Kronos no integra, a propósito.** No hay conectores con EDR, firewalls perimetrales, Active Directory
ni sistemas de tickets. Kronos actúa sólo por Active Response de Wazuh en los equipos que tienen agente, así que
la PyME no tiene que instalar, licenciar ni abrir nada más. El detalle está en el documento 2.7, Matriz de
integraciones.

Pruebas: `tests/unit/test_alertas_wazuh.py` (lectura incremental, líneas incompletas y rotación).
