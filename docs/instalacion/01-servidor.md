# 01 · Servidor SOAR-CORE-01 y endurecimiento

| Campo | Valor |
| :--- | :--- |
| Parte | 01 de 15 |
| Responsable | Nicolás Zamora (revisa: Rodrigo Riveros) |
| Versión | 0.9, 26-10-2026 |
| Estado | Borrador para revisión: escrito desde la configuración del repositorio y los registros del proyecto, no desde el historial de comandos del servidor. Nicolás compara cada paso con lo que hizo y lo corrige |
| Requisitos | El VPS contratado y acceso a su panel |

SOAR-CORE-01 es el único servidor de Kronos: un **Cloud VDS XL de Contabo** (16 vCPU AMD EPYC 7282, 64 GB de RAM,
480 GB NVMe, sin GPU, x86_64) en Francia, con Ubuntu 24.04 LTS. Todo lo demás corre ahí, en Docker.

Esta parte deja el servidor listo para lo siguiente: usuarios personales con llave, SSH sin contraseña ni
`root`, hora en UTC y un firewall que deniega por defecto.

---

## 1. Comprobar el servidor

```
[servidor] lsb_release -ds; uname -m; nproc; free -g | head -2; df -h /
```

**Debe mostrar:** `Ubuntu 24.04…`, `x86_64`, `16`, unos 62 GB de memoria total y unos 470 GB en `/`.

## 2. Una cuenta personal por integrante

Cada integrante entra con su propia cuenta, nunca con una compartida ni como `root`. La llave privada queda en
su PC y en el gestor de contraseñas del equipo; al servidor sólo va la pública.

```
[servidor] sudo adduser XXXX
[servidor] sudo usermod -aG sudo XXXX
[PC]       ssh-copy-id -i ~/.ssh/XXXX.pub XXXX@XXXX
```

Las cuentas **no** van al grupo `docker`: ese grupo equivale a `root`. Los comandos de Docker se escriben con
`sudo`.

En el PC conviene un atajo en `~/.ssh/config`, así el comando no lleva la dirección:

```
Host soar-core-01
    HostName XXXX
    User XXXX
    IdentityFile ~/.ssh/XXXX
```

## 3. SSH sólo con llave y sin `root`

Con una sesión abierta (por si algo falla), crear `/etc/ssh/sshd_config.d/10-kronos.conf`:

```
[servidor] sudo tee /etc/ssh/sshd_config.d/10-kronos.conf >/dev/null <<'FIN'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
FIN
[servidor] sudo sshd -t && sudo systemctl reload ssh
```

**Debe mostrar:** nada (`sshd -t` no encuentra errores). Desde **otra** ventana, comprobar que se sigue
entrando con la llave (`ssh soar-core-01`) antes de cerrar la primera sesión.

```
[servidor] sudo sshd -T | grep -E '^(permitrootlogin|passwordauthentication|pubkeyauthentication)'
```

**Debe mostrar:** `permitrootlogin no`, `passwordauthentication no` y `pubkeyauthentication yes`.

## 4. Hora en UTC (D-13)

Las alertas de Wazuh, la bitácora y los temporizadores de systemd usan UTC.

```
[servidor] sudo timedatectl set-timezone Etc/UTC
[servidor] timedatectl
```

**Debe mostrar:** `Time zone: Etc/UTC (UTC, +0000)` y `System clock synchronized: yes`.

## 5. Firewall: deniega por defecto

Sólo dos puertos quedan abiertos a internet: **22** (SSH, sólo con llave) y **1514** (los agentes de las PyME
envían ahí sus eventos). Todo lo demás llega por NetBird (parte 02).

```
[servidor] sudo ufw default deny incoming
[servidor] sudo ufw default allow outgoing
[servidor] sudo ufw allow 22/tcp
[servidor] sudo ufw allow 1514/tcp
[servidor] sudo ufw enable
[servidor] sudo ufw status verbose
```

**Debe mostrar:** `Status: active`, `Default: deny (incoming), allow (outgoing)` y las reglas de 22 y 1514.

> **Docker y el firewall.** Docker publica los puertos de sus contenedores con reglas propias de `iptables`,
> por fuera de `ufw`. Por eso los puertos internos no se protegen con `ufw`, sino publicándolos **sólo en la IP
> de NetBird o en `127.0.0.1`** (partes 04, 06 y 07). La comprobación de la parte 03 revisa que nada más escuche
> en todas las interfaces.

## 6. Panel de Contabo

- El segundo factor de las cuentas de Contabo quedó descartado por ahora (D-14): es un riesgo aceptado (R-07). La
  contraseña del panel va al gestor del equipo.
- La consola VNC del panel da acceso al servidor sin SSH: usarla sólo si se pierde el acceso por SSH.

## 7. Carpetas de Kronos

| Ruta | Qué hay | Parte |
| :--- | :--- | :--- |
| `/opt/wazuh-docker/single-node` | Compose de Wazuh. La carpeta se tiene que llamar `single-node`: de ese nombre salen el volumen de logs y la red que usa Kronos | 04 |
| `/opt/kronos/ollama` | Compose de Ollama | 06 |
| `/opt/kronos/audit` | Clon de git de este repositorio, en una etiqueta de versión (D-55) | 07 |
| `/var/backups/kronos` | Respaldos cifrados de SOAR-AUDIT | 12 |
| `/etc/kronos/` | Destinatarios de `age` (llaves públicas del respaldo) | 12 |

## 8. Lista de comprobación

- [ ] Ubuntu 24.04, 16 vCPU, 64 GB de RAM.
- [ ] Una cuenta personal por integrante, en `sudo` y no en `docker`.
- [ ] SSH sólo con llave y sin `root`; probado desde otra ventana.
- [ ] Hora en UTC, sincronizada.
- [ ] `ufw` activo: entrada denegada salvo 22 y 1514.
- [ ] Contraseña del panel de Contabo en el gestor de contraseñas.
