# Infraestructura

Lo que corre en SOAR-CORE-01 y en los equipos de la PyME. Cada carpeta tiene su README, y la instalación paso
a paso está en la guía de [`docs/instalacion/`](../docs/instalacion/).

| Carpeta | Qué tiene | Guía |
| :--- | :--- | :--- |
| `docker/` | SOAR-AUDIT (PostgreSQL 17.11): `docker-compose.yml`, esquema inicial (`initdb/`) y migraciones | 07 |
| `docker/servicios.yml` y `docker/servicios/` | Imagen y despliegue de VALIDATE, EXECUTE, NOTIFY y CONSOLE, con el ejemplo de `.env` | 07 y 11 |
| `docker/respaldo/` | Respaldo diario cifrado con age y prueba de restauración | 12 |
| `docker/retencion/` | Purga diaria de las alertas guardadas a los 90 días | 12 |
| `ollama/` | Ollama 0.40.0 con el modelo, sólo en `127.0.0.1` y en la red interna de VALIDATE | 06 |
| `wazuh/docker-compose.yml.example` | Compose de Wazuh 4.14.8 sin secretos: 1514 público y el resto sólo en la IP de NetBird | 04 |
| `wazuh/reglas/` | Las 15 reglas de sobre (100101 a 100115) | 05 |
| `wazuh/active-response/` | Scripts `kronos-*` que aplican y revierten las medidas en los agentes Linux y Windows | 08 a 10 |

Nada de esto lleva secretos: las contraseñas, tokens, llaves y certificados se generan en el servidor y quedan
fuera de git (`.gitignore`).
