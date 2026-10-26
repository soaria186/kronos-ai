# 03 · Docker

| Campo | Valor |
| :--- | :--- |
| Parte | 03 de 15 |
| Responsable | Nicolás Zamora (revisa: Rodrigo Riveros) |
| Versión | 0.9, 26-10-2026 |
| Estado | Borrador para revisión: procedimiento oficial de Docker para Ubuntu 24.04. Nicolás confirma que el servidor lo instaló así |
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

**Debe mostrar:** en `0.0.0.0` (o `*`) sólo el 22 (SSH) y el 1514; el resto, en la IP de NetBird.

## 4. Prueba de reinicio

Coordinarla con el equipo en el grupo de Telegram: mientras el servidor reinicia no hay detección ni respuesta.

```
[servidor] sudo reboot
[servidor] sudo docker ps --format '{{.Names}}\t{{.Status}}'
```

**Debe mostrar:** todos los contenedores `Up` sin haberlos levantado a mano (todos tienen `restart: always` o
`unless-stopped`). Después, dejar el modelo cargado otra vez (parte 06, paso 5).

## 5. Lista de comprobación

- [ ] Docker y Compose instalados desde el repositorio oficial; Docker habilitado al arranque.
- [ ] Nadie en el grupo `docker`.
- [ ] Sólo 22 y 1514 abiertos a internet.
- [ ] Los contenedores vuelven solos después de un reinicio.
