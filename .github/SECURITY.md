# Seguridad

Kronos AI actúa sobre los equipos de una PyME, así que un error de seguridad en el proyecto importa. Gracias por avisarlo.

## Cómo reportar un problema

- **No abras una issue pública con el detalle.**
- Si el repositorio es público, usa el aviso privado de GitHub: pestaña *Security* → *Report a vulnerability*.
- Si no, escribe directamente a un integrante del equipo (Nicolás Zamora, Rodrigo Riveros o Patricio González).
- Incluye qué componente es (SOAR-VALIDATE, EXECUTE, NOTIFY, CONSOLE, AUDIT, scripts de Active Response o reglas de Wazuh), cómo reproducirlo y qué impacto tiene.
- Intentamos responder en 2 días hábiles mientras dure el proyecto (hasta el 10-12-2026).

## Qué cubre

- El código y la configuración de este repositorio, en la última versión publicada en `main`.
- Interesa en especial cualquier forma de que el texto de una alerta haga ejecutar algo distinto de una medida del catálogo, de saltarse la aprobación del nivel 3, de alterar la bitácora sin que la cadena de hash lo detecte o de leer datos de otro inquilino.

## Lo que no está en el repositorio, a propósito

- Contraseñas, tokens, llaves y certificados: se generan en el servidor, viven como secretos de Docker (`Fase 2/Avances/infra/docker/secrets/`, fuera de git) y se resguardan en el gestor de contraseñas del equipo.
- `.env`, identificadores de Telegram, IP reales y usuarios del servidor.
- gitleaks revisa todo el historial en cada pull request y en el gancho de `pre-commit`.

## Si se filtra un secreto

1. Avisar al equipo de inmediato.
2. Revocarlo donde se emitió: BotFather para el token de Telegram, la API de Wazuh para `kronos-execute`, `ALTER ROLE` para los roles de la base, y un certificado o una llave nueva para TLS y age.
3. Generar uno nuevo, cargarlo en el servidor sin que pase por el chat ni por la terminal (`read -rs` o desde el portapapeles por `ssh`) y recrear el servicio que lo usa.
4. Si llegó a un commit, rotarlo igual: borrarlo del historial no lo invalida.
5. Dejar constancia en el registro del día (`Fase 2/Avances/docs/registro/`), sin el valor.
