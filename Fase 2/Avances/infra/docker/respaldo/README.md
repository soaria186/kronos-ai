# Respaldo de PostgreSQL (SOAR-AUDIT)

Mismo patrón que el respaldo de Wazuh: copia diaria cifrada con `age`, en
`/var/backups/kronos` (`root:sudo`, `640`), con las últimas 14 copias.

| Archivo | Qué hace |
|---|---|
| `kronos-respaldo-postgres.sh` | `pg_dump -Fc` de la base y `pg_dumpall --globals-only`, sumas SHA-256, todo en un `.tar.age`. Rotación de copias. |
| `kronos-respaldo-postgres.service` / `.timer` | Ejecución diaria a las 04:15 UTC (el de Wazuh corre a las 04:00). |
| `probar_restauracion.sh` | Descifra un respaldo, lo restaura en una base de prueba, compara filas, verifica la cadena de hash de cada inquilino y que `auditoria` siga rechazando `DELETE`. Borra la base de prueba al terminar. |

## Notas

- La llave privada de `age` no va al servidor: está en el gestor de contraseñas. El
  servidor sólo tiene el archivo de destinatarios (llaves públicas).
- `globales.sql` incluye los roles con el hash de sus contraseñas; por eso el
  respaldo va cifrado.
- La restauración conserva `seq`, `creado_en` y `hash` de `auditoria`: `pg_restore`
  carga los datos antes de crear los disparadores (sección post-data). No restaurar
  con `--data-only` sobre un esquema existente, porque el disparador de
  encadenamiento recalcularía la cadena.
- Variables `KRONOS_PG_*` y `KRONOS_RESPALDO_*`: ver el encabezado del script. Sus
  valores por omisión son los de SOAR-CORE-01.
