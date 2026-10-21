# Retención de las alertas guardadas (R-09)

Purga diaria de `alertas_guardadas`: la alerta completa de Wazuh se conserva **90 días**
(propuesta, por confirmar en el punto de encuentro 1) y después se borra. La bitácora no
se toca: conserva la huella (SHA-256) de cada alerta y un evento `ALERTAS_PURGADAS` por
cada purga. Detalle del diseño: `persistencia/README.md`.

| Archivo | Qué hace |
| :--- | :--- |
| `kronos-retencion-alertas.sh` | Ejecuta `fn_purgar_alertas(KRONOS_RETENCION_DIAS)` como `kronos_admin` dentro del contenedor de la base e informa cuántas alertas borró por inquilino |
| `kronos-retencion-alertas.service` / `.timer` | Ejecución diaria a las 04:45 UTC, después del respaldo de las 04:15 |

Nunca se purga la alerta de un ticket en curso, con un temporizador pendiente (reversión,
revisión del nivel 2 o aprobación del nivel 3) o cuya última reversión falló: EXECUTE la
necesita para revertir. Un plazo menor a 7 días se rechaza.

## Instalar en SOAR-CORE-01

Primero, la migración (una vez; es idempotente), desde `infra/docker`:

```bash
sudo docker exec -i kronos-db-1 psql -U kronos_admin -d kronos -v ON_ERROR_STOP=1 \
    < initdb/06_alertas_guardadas.sql
```

Después, el script y el temporizador:

```bash
sudo install -m 755 retencion/kronos-retencion-alertas.sh /usr/local/sbin/
sudo install -m 644 retencion/kronos-retencion-alertas.service \
    retencion/kronos-retencion-alertas.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kronos-retencion-alertas.timer
sudo systemctl start kronos-retencion-alertas.service
journalctl -u kronos-retencion-alertas.service -n 5 --no-pager
```

La primera ejecución debe decir `plazo 90 días; nada que purgar`: las alertas guardadas
recién empiezan a acumularse.

## Cambiar el plazo

```bash
sudo systemctl edit kronos-retencion-alertas.service
```

y agregar:

```ini
[Service]
Environment=KRONOS_RETENCION_DIAS=180
```

## Límites

- Los respaldos diarios (14 copias) conservan una alerta purgada hasta 14 días más.
- Las alertas de los tickets anteriores a esta tabla quedaron dentro de la bitácora y
  no se pueden borrar (tickets #1 al último antes de la migración).
