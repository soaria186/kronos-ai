# Validación (SOAR-VALIDATE)

Servicio que lee las alertas de Wazuh, pide la clasificación a SOAR-CLASSIFY, revisa la propuesta con chequeos
deterministas y registra la decisión en SOAR-AUDIT **antes** de que nadie actúe (R3): `python -m validacion`.

| Módulo | Qué hace |
| :--- | :--- |
| `__main__.py` | Servicio y variables de entorno |
| `ciclo.py` | Una alerta: agrupación, registro, cortacircuito, clasificación, chequeos y decisión |
| `alerta.py` | Prepara la alerta: familia candidata (`kronos_fX`), severidad, el texto que ve el modelo sin la etiqueta de familia y los objetivos para la lista de exclusión |
| `contrato.py` | Contrato JSON de las respuestas del modelo. Lo que no lo cumple se rechaza entero, sin repararlo |
| `chequeos.py` | Los chequeos 2 a 6, en orden. El primero que falla da el motivo |
| `catalogo.py` | Carga y valida KRO-CAT-01 |
| `configuracion.py` | Carga y valida `configuracion/validate.json`: mapa de severidad, lista de exclusión, contadores, agrupación y disparo del cortacircuito |
| `servicio.py` | Crea el ticket y guarda la alerta completa que después usa SOAR-EXECUTE |
| `posicion.py` | Dónde quedó la lectura de `alerts.json`, para retomar tras un reinicio |

## Chequeos, en orden

| # | Qué se comprueba | Motivo si falla |
| :-: | :--- | :--- |
| 1 | La respuesta del modelo cumple el esquema JSON | `ESQUEMA_INVALIDO` |
| 2 | Confianza ≥ 0,70, y la familia del modelo coincide con la de la regla de sobre | `CONFIANZA_BAJA`, `FAMILIA_NO_COINCIDE` |
| 3 | La medida existe en el catálogo, es de esa familia y, si es para una IP externa o interna, la IP de la alerta es de ese ámbito | `PLAYBOOK_FUERA_DE_CATALOGO` |
| 4 | El objetivo no está en la lista de exclusión | `ACTIVO_EXCLUIDO` |
| 5 | El cortacircuito está cerrado y ningún contador de tasa llegó a su tope | `CORTACIRCUITO_ABIERTO`, `LIMITE_DE_TASA` |
| 6 | El nivel de la medida está permitido para la severidad de la alerta | `NIVEL_NO_PERMITIDO_POR_SEVERIDAD` |

Si falla un chequeo, el ticket queda en `MANUAL_TRIAGE` con su motivo y nada se ejecuta. Lo mismo si el modelo
no responde o se pasa del plazo (falla segura). Las alertas de un mismo ataque (misma regla, misma IP de origen y
mismo equipo, dentro de 10 minutos) se resuelven con una sola decisión y quedan como `ALERTA_AGRUPADA`. Nunca se
actúa sobre el manager (agente 000).

Despliegue: `infra/docker/servicios/README.md` y la parte 07 de la guía de instalación. Alta de una PyME
(inquilino, exclusiones y redes internas): parte 13. Pruebas: `tests/unit/test_chequeos.py`,
`test_contrato.py`, `test_ciclo.py`, `test_alerta.py` y `test_configuracion.py`, entre otras.
