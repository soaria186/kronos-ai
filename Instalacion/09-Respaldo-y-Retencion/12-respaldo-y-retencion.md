# 12 · Respaldo, restauración y retención

| Campo | Valor |
| :--- | :--- |
| Parte | 12 de 15 |
| Responsable | Rodrigo Riveros (revisa: Patricio González) |
| Versión | 1.0, 01-11-2026 |
| Estado | Vigente: comprobada en SOAR-CORE-01 el 01-11-2026 (los tres temporizadores activos, 14 copias `root:sudo` 640, un destinatario de `age` y la purga diaria sin errores). La restauración se probó el 15-10-2026. La copia fuera del servidor (sección 5) la confirma Nicolás |
| Requisitos | Parte 07 |

| Qué | Cuándo (UTC) | Dónde |
| :--- | :--- | :--- |
| Respaldo de la configuración de Wazuh, certificados y `client.keys` | 04:00 | Parte 04, sección 10 |
| Respaldo cifrado de SOAR-AUDIT (base completa y roles) | 04:15 | `/var/backups/kronos`, 14 copias |
| Purga de las alertas guardadas con más de 90 días (D-46) | 04:45 | En la base |
| Copia fuera del servidor (D-26) | Periódica | PC de escritorio de Nicolás, por NetBird |

---

## 1. Llaves de `age`

El respaldo se cifra en el servidor con `age`, **sólo con llaves públicas**. La llave privada no está en el
servidor: queda en el gestor de contraseñas del equipo.

```
[PC]       age-keygen -o kronos-respaldo.key
[PC]       age-keygen -y kronos-respaldo.key
```

La segunda línea muestra la llave pública (`age1…`). La privada (`kronos-respaldo.key`) va al gestor y se borra
del PC. En el servidor:

```
[servidor] sudo apt-get install -y age
[servidor] sudo install -d -m 755 /etc/kronos
[servidor] echo 'age1XXXX' | sudo tee /etc/kronos/respaldo-destinatarios.txt
```

Se pueden poner varias llaves públicas, una por línea (por ejemplo, una por integrante).

## 2. Respaldo diario de SOAR-AUDIT

```
[servidor] cd /opt/kronos/audit/infra/docker
[servidor] sudo install -m 755 respaldo/kronos-respaldo-postgres.sh /usr/local/sbin/
[servidor] sudo install -m 644 respaldo/kronos-respaldo-postgres.service respaldo/kronos-respaldo-postgres.timer /etc/systemd/system/
[servidor] sudo systemctl daemon-reload
[servidor] sudo systemctl enable --now kronos-respaldo-postgres.timer
[servidor] sudo systemctl start kronos-respaldo-postgres.service
[servidor] sudo ls -l /var/backups/kronos
```

**Debe mostrar:** un archivo `postgres-kronos-<fecha UTC>.tar.age`, dueño `root:sudo` y permiso 640. Adentro
van la base (`pg_dump -Fc`), los roles con el hash de sus contraseñas (por eso va cifrado) y las sumas SHA-256. Se
conservan las 14 copias más recientes.

```
[servidor] systemctl list-timers 'kronos-*'
```

**Debe mostrar:** la próxima ejecución a las 04:15 UTC. En SOAR-CORE-01 aparecen tres temporizadores: `kronos-respaldo-wazuh` (04:00, parte 04), `kronos-respaldo-postgres` (04:15) y `kronos-retencion-alertas` (04:45). En la misma carpeta quedan también los respaldos de Wazuh (`respaldo-wazuh-<fecha>.tar.gz.age`).

Para comprobar que la llave privada no quedó en el servidor (debe dar 0; muestra sólo cuántos archivos, nunca su contenido):

```
[servidor] sudo grep -rlsE 'AGE-SECRET-KEY-1[0-9A-Z]{50,}' /etc /root /home /opt/kronos /tmp /var/tmp /dev/shm 2>/dev/null | wc -l
```

El patrón busca una llave completa y no sólo su prefijo: esta guía y los scripts del repositorio, que están en `/opt/kronos`, nombran el prefijo y no deben contar. Si da más de 0, se cambia `wc -l` por `xargs ls -l` para ver la ruta, el dueño y la fecha, y se confirma que el gestor tiene la llave antes de borrarla.

## 3. Probar la restauración

El script restaura el respaldo en una base nueva del mismo contenedor y la compara con la original, así que se
corre donde está la base. La llave privada llega al servidor **sólo durante la prueba**, en memoria, y se borra al
terminar. Si se prefiere que nunca toque el servidor, la prueba se hace en un PC con la base de desarrollo y un
respaldo de esa base.

```
[PC]       scp kronos-respaldo.key soar-core-01:/dev/shm/
[servidor] sudo bash /opt/kronos/audit/infra/docker/respaldo/probar_restauracion.sh /var/backups/kronos/postgres-kronos-XXXX.tar.age /dev/shm/kronos-respaldo.key
[servidor] shred -u /dev/shm/kronos-respaldo.key
```

**Debe mostrar:** las sumas en orden, el mismo número de filas que la base original, la cadena de hash de cada
inquilino sin cortes (`fn_verificar_cadena` en `NULL`) y que `auditoria` sigue rechazando `DELETE`. El script
borra la base de prueba al terminar. Resultado del 15-10-2026: **2822 de 2822 eventos, 12 inquilinos y 0
cadenas rotas**.

No se restaura con `--data-only` sobre un esquema existente: el disparador de encadenamiento recalcularía la
cadena.

## 4. Retención de las alertas guardadas

La alerta completa de Wazuh tiene datos personales, así que no se guarda en la bitácora (que no se puede borrar)
sino en `alertas_guardadas`, que se purga a los 90 días. La bitácora conserva su huella SHA-256.

```
[servidor] cd /opt/kronos/audit/infra/docker
[servidor] sudo install -m 755 retencion/kronos-retencion-alertas.sh /usr/local/sbin/
[servidor] sudo install -m 644 retencion/kronos-retencion-alertas.service retencion/kronos-retencion-alertas.timer /etc/systemd/system/
[servidor] sudo systemctl daemon-reload
[servidor] sudo systemctl enable --now kronos-retencion-alertas.timer
[servidor] sudo systemctl start kronos-retencion-alertas.service
[servidor] journalctl -u kronos-retencion-alertas.service -n 5 --no-pager
```

**Debe mostrar:** `plazo 90 días; nada que purgar` en una instalación nueva. Nunca se purga la alerta de un
ticket en curso, con un temporizador pendiente o con la última reversión fallida.

Para cambiar el plazo (mínimo 7 días): `sudo systemctl edit kronos-retencion-alertas.service` y
`Environment=KRONOS_RETENCION_DIAS=180`.

## 5. Copia fuera del servidor (D-26)

El respaldo sigue cifrado al salir del servidor. Desde el PC de escritorio de Nicolás, con NetBird:

```
[PC] scp soar-core-01:/var/backups/kronos/postgres-kronos-XXXX.tar.age <carpeta de respaldos del PC>
```

La llave privada no se guarda junto a las copias.

## 6. Lista de comprobación

- [ ] Llave privada de `age` en el gestor, no en el servidor ni junto a las copias.
- [ ] Temporizador de respaldo activo; un archivo `.tar.age` en `/var/backups/kronos`.
- [ ] Restauración probada con `probar_restauracion.sh`.
- [ ] Temporizador de purga activo (04:45 UTC).
- [ ] Una copia reciente fuera del servidor.
