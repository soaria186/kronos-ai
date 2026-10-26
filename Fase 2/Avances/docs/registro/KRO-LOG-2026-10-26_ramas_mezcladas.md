# KRO-LOG-2026-10-26 · Ramas ya mezcladas en `develop`

Las 37 ramas cuyo trabajo ya estaba en `develop` el 26-10 en la mañana (punto B1 de la lista de corrección). Se borran en la semana de
cierre; aquí quedan sus puntas por si hay que recuperar una:

```bash
git push origin <punta>:refs/heads/<rama>
```

`git branch -r --merged origin/develop` las lista a todas, así que borrarlas no pierde ningún commit. Las 4
ramas de experimentos no están aquí: quedan como etiquetas `archivo/<rama>` (#74).

| Rama | Punta | Último commit |
| :--- | :--- | :--- |
| `ci/e2-tests-unitarios` | `89f1829d132b12753ca81515cfd4d5dc9da45c73` | 15-10-2026 |
| `docs/e3-doc02-estados` | `d87476ad250802c33804e2b091e3116e06bf7d74` | 21-10-2026 |
| `docs/e3-regla-de-merge` | `da2140ae3261fe7038e55eb81082525f77ec5c1c` | 21-10-2026 |
| `docs/lab-ep-wks-01-escritorio` | `50a71b9db2bb18c54c5f04f1c811c4697488b009` | 21-10-2026 |
| `docs/validate-permiso-secreto` | `e4789105652886bc2b6c62a666b7f2066b9a470f` | 16-10-2026 |
| `feat/e1-ar-bloquear-ip` | `c0aca952bcfc81bb7f022bae87605f47f7a73a25` | 21-10-2026 |
| `feat/e1-casos-frontera` | `fbf92282a9d38e5cc8f51fd371319498e99ab371` | 14-10-2026 |
| `feat/e1-ci` | `9f445ed93bbfde57b854939b4e63462e2e35e335` | 06-10-2026 |
| `feat/e1-documentacion` | `a4dc3b16bbfb1765bef68f4f4170ad7a21623d73` | 14-10-2026 |
| `feat/e1-medicion-inferencia` | `0ec56f358c5fe7985a537807079db687b48ded05` | 06-10-2026 |
| `feat/e1-reglas-sobre` | `bdb5a4a288d667100aa1786ed92ba8ee50278775` | 14-10-2026 |
| `feat/e1-test-r1` | `ae85df7a7eed88b0b07d44cd266a431a2ddc6066` | 06-10-2026 |
| `feat/e1-wazuh-compose` | `c870d96116c3c584cfed44b5ec43ee6bafd7d87d` | 14-10-2026 |
| `feat/e2-casos-150` | `e273aa4d7a38d41858239c3cbbdb87ad63a29758` | 15-10-2026 |
| `feat/e2-casos-formato-wazuh` | `8b6180d66be469d988a81eb7a022344369df7d6c` | 15-10-2026 |
| `feat/e2-config-validate` | `b36f09f7751caab9dbafcc7459ae5977581ddef2` | 15-10-2026 |
| `feat/e2-consola-app` | `c2e8bd443b9d30839049100372c7e4462cf3c5c4` | 15-10-2026 |
| `feat/e2-consola-base` | `31708baca93dc9bfd0fc8fdc54b1cfa1690a615b` | 15-10-2026 |
| `feat/e2-despliegue` | `5edeed28a0c2869ac1126e1272ee173c39ba22a7` | 15-10-2026 |
| `feat/e2-esquema-motivos` | `e7b42305efd6cdc9d7ab8ab0fce5b63bfbe9cd0a` | 15-10-2026 |
| `feat/e2-execute-nucleo` | `574665bb749aba904c233aaf35d7615733ebade5` | 15-10-2026 |
| `feat/e2-lector-alertas` | `c5a112e827fbf31959d7b60d0d4cd1d8eb3a7afb` | 15-10-2026 |
| `feat/e2-mediciones-14-10` | `4fa336d2c9bc1b12dbbb7d200b27250a2efd7876` | 15-10-2026 |
| `feat/e2-notify` | `dad5c2a1098322c9cc33fb7b9d335fccde78fb7d` | 15-10-2026 |
| `feat/e2-ollama-guia` | `131ff4255129ac77d23f65e0a9ced7aaa12ade8b` | 15-10-2026 |
| `feat/e2-persistencia-validate` | `7027b6c3d70ca50f79fefe8774d8cf7856cbbf64` | 15-10-2026 |
| `feat/e2-plazos-reversion` | `a15f8a6ac19b0b60b21e87a943c5a7a89afc8971` | 15-10-2026 |
| `feat/e2-respaldo-postgres` | `6d03e1285daa355ed3a4dc6a96ef08a936a8af72` | 15-10-2026 |
| `feat/e2-validate-alerta-completa` | `060d22075ad6cb4176e31c7cbf80b587b6dd924e` | 15-10-2026 |
| `feat/e2-validate-ciclo` | `5868432db7a47f23c41bba60959a3ba55969473d` | 16-10-2026 |
| `feat/e2-validate-contrato` | `2f5dd0cd721a016e37e296f19027b424fa191094` | 14-10-2026 |
| `feat/e2-validate-servicio` | `2307985c4ec6d4d449591108c20c84909255d727` | 16-10-2026 |
| `feat/e3-ar-windows-bloquear-ip` | `4bab0705f0f0e0b712fbcad7e8f1921dd0c05039` | 20-10-2026 |
| `feat/e3-retencion-alertas` | `f825322894852e91ad6b1e4e42e0bcaa3b4813b2` | 21-10-2026 |
| `feat/e3-tickets-huerfanos` | `99e056a5f0fd1792401f9b7d33ce64daf4b504f2` | 21-10-2026 |
| `feat/validate-mejoras-prueba-20-10` | `2eb838cf74d010b82bfdafbf124cbab28244498e` | 21-10-2026 |
| `fix/pruebas-solo-linux` | `dc4145392a290d16f64ca82b8b42ead3d956d7f5` | 15-10-2026 |

## Después de la reestructuración del 26-10

Al ordenar el repositorio por fases se integraron los PR #75 a #84 y las 4 ramas de experimentos (el prompt v2
quedó en `decision/mediciones/experimentos/prompt-v2.patch`). Estas 14 ramas también se pueden borrar; con ellas,
el repositorio queda sólo con `main` y `develop`.

| Rama | Punta | Último commit |
| :--- | :--- | :--- |
| `docs/e4-diagramas` | `b0eb8a83eb70cb6b06d15c4d1f4d05c93127ea76` | 26-10-2026 |
| `docs/e4-experimentos-archivados` | `5051038ebbc82fd0fb58a2caeef715e5e470ec7d` | 26-10-2026 |
| `docs/e4-guia-instalacion` | `8c1ea26dac88730323d977f707db3529c1b606ed` | 26-10-2026 |
| `docs/e4-orden-docs` | `2d4081a99f114db0b8bd84a76abca450e19e4359` | 26-10-2026 |
| `docs/e4-portada` | `9caf1951ca2567d0947b8609a5dd88e4cea56c08` | 26-10-2026 |
| `feat/e4-avisos-claros` | `da9c1d0f48523f738556f703a073037ba3833b00` | 26-10-2026 |
| `feat/e4-catalogo-v1` | `17c71b95cba47d9648c179fd6ab9cadac768e4e0` | 26-10-2026 |
| `feat/e4-validate-v1` | `eb3737f2b6232d313cd0b710b059bd2b44ac6169` | 26-10-2026 |
| `fix/e4-coherencia` | `a5f0c1f8ae895119a20b530af5bfa3ad69a252f7` | 26-10-2026 |
| `ci/e4-consola-y-verificacion` | `9613f0d87c287a519540e69c92b92b9ea18c876a` | 26-10-2026 |
| `feat/e1-mediciones-servidor` | `408c8a1f560018d80df15392a0c9caba934e50e8` | 14-10-2026 |
| `feat/e2-mediciones-prompt-v1` | `8ca7be041f611315fb9013d5720410c37cba039c` | 14-10-2026 |
| `feat/e2-mediciones-prompt-v2` | `1f1cf6679894f0e581f1d8ffdad9bc582d649161` | 14-10-2026 |
| `feat/e2-prompt-confianza` | `63ac0fe54572299f6391dc7bb429777325cb7513` | 14-10-2026 |
