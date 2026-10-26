# 13 · Alta de una PyME

| Campo | Valor |
| :--- | :--- |
| Parte | 13 de 15 |
| Responsable | Patricio González y Nicolás Zamora (revisa: Rodrigo Riveros) |
| Versión | 0.9, 26-10-2026 |
| Estado | Borrador para revisión: sale de `validacion/configuracion/validate.json`, de las partes 07 a 11 y del alta de la PyME simulada |
| Requisitos | Partes 01 a 12 |

Dar de alta una PyME es dejarla monitoreada y protegida: sus equipos con agente, su configuración de exclusiones,
su encargado de TI en Telegram y en la consola, y una verificación de punta a punta.

> **Límite de la versión 1.0: una PyME por servidor.** SOAR-VALIDATE asigna todas las alertas de Wazuh al
> inquilino de `KRONOS_INQUILINO`. Atender varias PyME con un mismo manager requiere asignar el inquilino por grupo
> de agentes de Wazuh (D-49), que queda como trabajo futuro. La base ya es multiinquilino (RLS y una cadena de hash
> por inquilino, probadas con dos y con 12 inquilinos).

---

## 1. Acuerdo con la PyME

Antes de instalar nada, por escrito:

- **Autorización** para instalar los agentes, monitorear los equipos y aplicar las medidas del catálogo.
- **Aviso a los trabajadores** de que sus equipos se monitorean, qué se observa y qué no (Ley 19.628, modificada por
  la Ley 21.719).
- **Aceptación de las medidas de contención**, con sus niveles: qué hace Kronos solo, qué avisa y qué aprueba el
  encargado de TI.
- **Quién es el encargado de TI** que recibe los avisos y aprueba el nivel 3 (D-59), y cómo se le avisa a una
  persona afectada (por correo, a mano, D-35).

## 2. Inventario

| Qué | Para qué |
| :--- | :--- |
| Equipos: nombre, sistema operativo, si es puesto o servidor | Agentes (partes 09 y 10) y medidas por arquetipo |
| IP propias: puerta de enlace, servidores, impresoras | Lista de exclusión: Kronos nunca las bloquea |
| Redes internas | Distinguir una IP interna (nivel 2) de una externa (nivel 1) |
| Cuentas críticas (respaldo, servicios) | Lista de exclusión: Kronos nunca las deshabilita |
| Servicios y programas críticos | Lista de exclusión |
| Destinos externos permitidos | Lista de exclusión |

## 3. Número y nombre de la PyME

Cada PyME es un **inquilino**, con un número entero. En la PyME simulada es el 1.

| Variable (`infra/docker/.env`) | Valor | Servicio |
| :--- | :--- | :--- |
| `KRONOS_INQUILINO` | El número de la PyME | VALIDATE |
| `KRONOS_INQUILINOS` | El mismo número | EXECUTE, NOTIFY y la consola |
| `KRONOS_NOMBRES_INQUILINOS` | `número:nombre`, por ejemplo `1:PyME de demostración` | NOTIFY (avisos) |

## 4. Lista de exclusión y redes internas

Van en `validacion/configuracion/validate.json`. Es configuración versionada: se cambia **por PR**, con la
aprobación de otro integrante, y se despliega con la nueva versión (parte 07, sección 8). Las categorías son
`equipo`, `cuenta`, `programa`, `servicio`, `ip` y `destino`. Por ejemplo:

```json
"redes_internas": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7"],
"exclusion": {
  "entradas": [
    {"categoria": "ip", "valor": "192.168.1.1", "comentario": "Puerta de enlace de la PyME"},
    {"categoria": "ip", "valor": "192.168.1.10", "comentario": "Servidor de archivos"},
    {"categoria": "cuenta", "valor": "svc_respaldo", "comentario": "Cuenta del respaldo nocturno"},
    {"categoria": "equipo", "valor": "SRV-CONTABLE", "comentario": "Servidor del sistema contable: sólo aviso"}
  ]
}
```

Lo que está en la lista nunca recibe una medida: el caso pasa a revisión manual con el motivo `ACTIVO_EXCLUIDO`.
En la PyME simulada, la única entrada es la puerta de enlace del laboratorio, `10.0.50.1`.

## 5. Encargado de TI

1. **Telegram:** entra al grupo de avisos con la verificación en dos pasos activada, y su cuenta se agrega a
   `KRONOS_TELEGRAM_EQUIPO` (parte 11). Recrear `notify`.
2. **Consola:** su PC entra a NetBird (parte 02) y crea su cuenta de la consola, con TOTP (parte 07, sección 6).
3. **Manual del encargado de TI** (`docs/informe/`): qué significa cada aviso y qué hacer.

## 6. Agentes y scripts

En cada equipo de la PyME: agente de Wazuh registrado desde el servidor y scripts `kronos-*` (partes 08 a 10).
Comprobar que todos aparecen `Active`:

```
[servidor] sudo docker exec single-node-wazuh.manager-1 /var/ossec/bin/agent_control -l
```

## 7. Verificación

Con todo instalado, la parte 15: al menos E1 (nivel 1) y un escenario de cada nivel que la PyME vaya a usar. El
acta del alta registra la fecha, los equipos, las exclusiones y el resultado de la verificación.

## 8. Lista de comprobación

- [ ] Autorización, aviso a los trabajadores y aceptación de las medidas, firmados.
- [ ] Inventario completo; exclusiones y redes internas en `validate.json`, por PR.
- [ ] Inquilino y nombre en `.env`; servicios recreados.
- [ ] Encargado de TI en Telegram (con verificación en dos pasos), en NetBird y con cuenta de consola.
- [ ] Agentes `Active` y scripts instalados.
- [ ] Verificación de la parte 15 hecha y registrada.
