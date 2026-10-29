# 02 · Red privada NetBird

| Campo | Valor |
| :--- | :--- |
| Parte | 02 de 15 |
| Responsable | Nicolás Zamora (revisa: Rodrigo Riveros) |
| Versión | 0.9, 26-10-2026 |
| Estado | Borrador para revisión: escrito desde la configuración del repositorio y los registros del proyecto. Nicolás lo compara con lo que hizo (por ejemplo, si el servidor entró con una clave de configuración o con inicio de sesión) y lo corrige |
| Requisitos | Parte 01 |

NetBird es la red privada del equipo (WireGuard en malla). El servidor y los PC de los integrantes, y los del
encargado de TI que use la consola, quedan en la misma red, con una IP del rango `100.64.0.0/10`. Por esa red, y
sólo por ella, se llega a:

| Puerto | Qué es | Parte |
| :--- | :--- | :--- |
| 443 | SOAR-CONSOLE | 07 |
| 55000 | API de Wazuh | 04 y 08 |
| 9200 | Indexador de Wazuh | 04 |
| 5601 | Dashboard de Wazuh (uso interno del equipo) | 04 |

Los **agentes de las PyME no usan NetBird**: envían sus eventos por internet al 1514 (parte 01, sección 5).

---

## 1. Instalar NetBird en el servidor

```
[servidor] curl -fsSL https://pkgs.netbird.io/install.sh | sudo sh
```

Unir el servidor a la red con una **clave de configuración** (*setup key*) creada en el panel de NetBird. Es un
secreto: se carga sin que quede en pantalla ni en el historial.

```
[servidor] read -rs NB_CLAVE; echo
[servidor] sudo netbird up --setup-key "$NB_CLAVE"; unset NB_CLAVE
[servidor] netbird status
```

**Debe mostrar:** `Management: Connected`, `Signal: Connected` y `NetBird IP: 100.x.y.z/16`. Esa es la **IP de
NetBird del servidor**: va a `NETBIRD_IP` (parte 04) y a `KRONOS_CONSOLA_IP` (parte 07). No se publica en el
repositorio.

## 2. Instalar NetBird en cada PC

Con el instalador de <https://netbird.io> para el sistema del PC, e inicio de sesión con la cuenta del equipo.

```
[PC] netbird status
[PC] ping XXXX
```

**Debe mostrar:** `Connected` y respuesta del servidor en su IP de NetBird.

## 3. Quién llega a qué

En el panel de NetBird:

- Los PC del equipo van al grupo `admins`, y una política permite a ese grupo llegar al servidor.
- Cada integrante tiene rol **User**; el rol de administrador de la red queda en una sola cuenta (R-06).
- Un equipo que deja el proyecto, o el PC del encargado de TI cuando la PyME se retira, se borra de la red
  (parte 14).

## 4. Comprobación

```
[PC] ssh soar-core-01 'netbird status | grep -E "Management|NetBird IP"'
[servidor] sudo ss -tlnp | grep -E ':(443|5601|9200|55000) '
```

**Debe mostrar:** la IP de NetBird del servidor y, una vez hechas las partes 04 y 07, los cuatro puertos
escuchando **sólo** en esa IP, nunca en `0.0.0.0`.

## 5. Lista de comprobación

- [ ] Servidor en NetBird, con su IP anotada en el gestor de contraseñas (no en el repositorio).
- [ ] PC de cada integrante en el grupo `admins`, con rol User.
- [ ] 443, 55000, 9200 y 5601 sólo en la IP de NetBird.
