# 03 · Docker

| Campo | Valor |
| :--- | :--- |
| Parte | 03 de 15 |
| Responsable | Nicolás Zamora (revisa: Rodrigo Riveros) |
| Versión | 1.0, 12-11-2026 |
| Estado | Vigente: comparada con SOAR-CORE-01 el 12-11-2026 (Docker 29.9.1 y Compose v5.6.0 del repositorio oficial). La prueba de reinicio de la sección 4 no se ha hecho en ese servidor |
| Requisitos | Parte 01 |

Todo Kronos corre en contenedores: Wazuh, Ollama, PostgreSQL y los cuatro servicios. Se usa Docker Engine con
el complemento Compose, del repositorio oficial de Docker.

---

## 1. Instalar Docker Engine y Compose

```
[servidor] sudo apt-get update
[servidor] sudo apt-get install -y ca-certificates curl
[servidor] sudo install -m 0755 -d /etc/apt/keyrings
[servidor] sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
[servidor] sudo chmod a+r /etc/apt/keyrings/docker.asc
[servidor] echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
[servidor] sudo apt-get update
[servidor] sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## 2. Comprobar

```
[servidor] sudo docker run --rm hello-world
[servidor] sudo docker compose version
[servidor] systemctl is-enabled docker
```

**Debe mostrar:** `Hello from Docker!`, la versión de Compose (`v2.x` o posterior) y `enabled`: Docker arranca
solo con el servidor.

No se agrega a nadie al grupo `docker` (equivale a `root`): todo con `sudo docker`.

## 3. Qué escucha en internet

Docker publica los puertos de los contenedores por fuera de `ufw` (parte 01, sección 5). La regla de Kronos es
que cada puerto se publique en una dirección concreta:

| Dónde escucha | Puertos |
| :--- | :--- |
| Todas las interfaces | Sólo 1514 (agentes) |
| IP de NetBird | 443 (consola), 55000, 9200 y 5601 (Wazuh) |
| `127.0.0.1` | 11434 (Ollama) |
| Ninguna (red interna de Docker) | 5432 (PostgreSQL) |

Al terminar las partes 04 a 07:

```
[servidor] sudo ss -tlnp | grep -v -E '127\.0\.0\.|::1'
```

**Debe mostrar:** en `0.0.0.0` y `[::]` sólo el 22 y el 1514; el resto, en la IP de NetBird (443, 55000, 9200 y
5601, más el 53 del DNS de NetBird). El 22 aparece en todas las interfaces porque `sshd` escucha en todas, pero
`ufw` sólo lo deja entrar por `wt0` (parte 01, sección 5).

## 4. Prueba de reinicio

Coordinarla con el equipo en el grupo de Telegram: mientras el servidor reinicia no hay detección ni respuesta.

```
[servidor] sudo reboot
[servidor] sudo docker ps --format '{{.Names}}\t{{.Status}}'
```

**Debe mostrar:** todos los contenedores `Up` sin haberlos levantado a mano. Después, dejar el modelo cargado
otra vez (parte 06, paso 5).

La política de reinicio de cada contenedor se ve sin reiniciar:

```
[servidor] sudo docker ps --format '{{.Names}}' | xargs -n1 sudo docker inspect -f '{{.Name}} {{.HostConfig.RestartPolicy.Name}}'
```

**Debe mostrar:** `always` en los tres de Wazuh y `unless-stopped` en `ollama` y en los cinco de Kronos
(`kronos-db-1`, `kronos-validate-1`, `kronos-execute-1`, `kronos-notify-1` y `kronos-consola-1`).

> **Estado en SOAR-CORE-01.** Las políticas están comprobadas (12-11-2026), pero el servidor no se ha
> reiniciado desde el 20-10-2026: la prueba completa queda pendiente antes de instalar en una PyME real
> (riesgo R-02 y caso CP-46).

## 5. Lista de comprobación

- [ ] Docker y Compose instalados desde el repositorio oficial; Docker habilitado al arranque.
- [ ] Nadie en el grupo `docker`.
- [ ] Desde internet sólo el 1514; el 22 sólo por NetBird.
- [ ] Los contenedores vuelven solos después de un reinicio.
