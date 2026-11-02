# Ramas borradas el 01-11-2026

Ramas cuyo contenido ya estaba completo en `develop` (`git merge-base --is-ancestor <rama> develop`), borradas de GitHub por Rodrigo Riveros (issue #25, orden del repositorio). No se pierde ningún commit: todos siguen en `develop`.

Para recuperar una rama, con su punta de la tabla:

```
git push origin <punta>:refs/heads/<rama>
```

Total: 51 ramas. Las puntas de `KRO-LOG-2026-10-26_ramas_mezcladas.md` son del repositorio anterior (`soarai2026/kronos-ai`) y no sirven para recuperar ramas en este; las de esta tabla sí.

| Rama | Punta | Autor del último commit | Fecha |
| :--- | :--- | :--- | :--- |
| `chore/sincronizar-main` | `e2c2add42626f18ec40513a0d79c427956a511ef` | Rodrigo Riveros | 2026-10-29 |
| `ci/e2-tests-unitarios` | `a8a977e39716b0e495504535cb1ce8c81ffce84c` | Rodrigo Riveros | 2026-10-15 |
| `ci/e4-consola-y-verificacion` | `e1cf01e8ddcd5191d37ad1bf0ccb4e036bae145e` | Nicolás Zamora | 2026-10-26 |
| `docs/e3-doc02-estados` | `7c109ea4bc2312cae5c49785df9da2dfc8e2860c` | Patricio Gonzalez | 2026-10-21 |
| `docs/e3-regla-de-merge` | `0fa452c5cfa5e7230b19a4da6a7449bbd478b4cb` | Rodrigo Riveros | 2026-10-21 |
| `docs/e4-diagramas` | `cf1bd21949357e8b0ec68d5d40e798064f802cbd` | Nicolás Zamora | 2026-10-26 |
| `docs/e4-experimentos-archivados` | `c2528406b5510f62fa7a95571453936541f49648` | Nicolás Zamora | 2026-10-26 |
| `docs/e4-guia-instalacion` | `4df726291d56734a831006c8215776290bc19649` | Nicolás Zamora | 2026-10-26 |
| `docs/e4-orden-docs` | `674efbe61c4c5d593936f79483bf908af9567856` | Nicolás Zamora | 2026-10-26 |
| `docs/e4-portada` | `a8ee4c6b1d2eb670fa75821f1e74fa89ba4ff637` | Nicolás Zamora | 2026-10-26 |
| `docs/lab-ep-wks-01-escritorio` | `2ca738d4a8b3494af9fc0025ed3d8b10ef3d5b97` | Nicolás Zamora | 2026-10-21 |
| `docs/validate-permiso-secreto` | `f79fa9e7d9a0d6ab59304321728e5035d51edf09` | Patricio Gonzalez | 2026-10-16 |
| `feat/ar-windows-aislar-equipo` | `902ad47cc33ad4339850848bb89f87528a7eeeac` | Rodrigo Riveros | 2026-10-29 |
| `feat/ar-windows-deshabilitar-cuenta` | `8c062bb26324ede0813c740da43c956522d96ca4` | Rodrigo Riveros | 2026-10-29 |
| `feat/cortacircuito-alertas-recibidas` | `e032223a5b7b640d1e93b9e62c7a79c8d12a0b43` | Patricio González | 2026-10-29 |
| `feat/e1-ar-bloquear-ip` | `9c8cfa2385914f6c663f939e7f6f0816d1a4669a` | Nicolás Zamora | 2026-10-21 |
| `feat/e1-casos-frontera` | `fbf92282a9d38e5cc8f51fd371319498e99ab371` | Patricio Gonzalez | 2026-10-14 |
| `feat/e1-ci` | `9f445ed93bbfde57b854939b4e63462e2e35e335` | Rodrigo Riveros | 2026-10-06 |
| `feat/e1-documentacion` | `a03e69bc450089c4320d8ce97854b5513cb63a90` | Rodrigo Riveros | 2026-10-14 |
| `feat/e1-medicion-inferencia` | `0ec56f358c5fe7985a537807079db687b48ded05` | Patricio González | 2026-10-06 |
| `feat/e1-reglas-sobre` | `bdb5a4a288d667100aa1786ed92ba8ee50278775` | Nicolás Zamora | 2026-10-14 |
| `feat/e1-test-r1` | `ae85df7a7eed88b0b07d44cd266a431a2ddc6066` | soarai2026 | 2026-10-06 |
| `feat/e1-wazuh-compose` | `c870d96116c3c584cfed44b5ec43ee6bafd7d87d` | Nicolás Zamora | 2026-10-14 |
| `feat/e2-casos-150` | `4fcb0fed49c236daafd31634e4ca92c6b9289532` | Patricio Gonzalez | 2026-10-15 |
| `feat/e2-casos-formato-wazuh` | `155fc42104aa3b90f09049f2f1d63abf9f432812` | Patricio Gonzalez | 2026-10-15 |
| `feat/e2-config-validate` | `6ca082a065b826186b2aa19255d3c8770ac5929f` | Patricio Gonzalez | 2026-10-15 |
| `feat/e2-consola-app` | `ccf00d7582c91a509879daafb65a2a52486ab4d0` | Rodrigo Riveros | 2026-10-15 |
| `feat/e2-consola-base` | `ac7638adb5af5dfc7ab4c6ed08f4a07520b79523` | Rodrigo Riveros | 2026-10-15 |
| `feat/e2-despliegue` | `60a7df0f2363081bb86b01314eecf399039f8294` | Rodrigo Riveros | 2026-10-15 |
| `feat/e2-esquema-motivos` | `4855ff1c3a57e72a71b3324a55c1a96a9a953ca1` | Rodrigo Riveros | 2026-10-15 |
| `feat/e2-execute-nucleo` | `7d065f12e0a24ffc58515ebbfa340b70c35b8a7a` | Rodrigo Riveros | 2026-10-15 |
| `feat/e2-lector-alertas` | `0a93e4ee13e405c83c2a22f25df5b5ba5b95eea1` | Patricio Gonzalez | 2026-10-15 |
| `feat/e2-mediciones-14-10` | `068be44124657c0cb0aa285c1b3337fe7a69094d` | Patricio Gonzalez | 2026-10-15 |
| `feat/e2-notify` | `a25a51faaaa9da362a9056df312d47202a734faa` | Rodrigo Riveros | 2026-10-15 |
| `feat/e2-ollama-guia` | `909c20eadf3bb76fc09f80226477dd7012c52ae9` | Patricio Gonzalez | 2026-10-15 |
| `feat/e2-persistencia-validate` | `a68daaa23df15d7537fe0cda7b8063a487881faa` | Rodrigo Riveros | 2026-10-15 |
| `feat/e2-plazos-reversion` | `7fd58958180bf8ce07ae616b02277a788d952288` | Patricio Gonzalez | 2026-10-15 |
| `feat/e2-respaldo-postgres` | `6679b616f2cbe5e5458c901f90b2fc009de14fb2` | Rodrigo Riveros | 2026-10-15 |
| `feat/e2-validate-alerta-completa` | `a4e014e1c467344c6dd5d56ce9b94637d21aae92` | Patricio Gonzalez | 2026-10-15 |
| `feat/e2-validate-ciclo` | `fdf7e3144ca504549bb113cddf3b640593852851` | Patricio Gonzalez | 2026-10-16 |
| `feat/e2-validate-contrato` | `2f5dd0cd721a016e37e296f19027b424fa191094` | Patricio Gonzalez | 2026-10-14 |
| `feat/e2-validate-servicio` | `ebab631ffd11066709d445c3449f9d631d0248a0` | Patricio Gonzalez | 2026-10-16 |
| `feat/e3-ar-windows-bloquear-ip` | `6793580fccb8965628a46025875ea8bf493427b2` | Rodrigo Riveros | 2026-10-20 |
| `feat/e3-retencion-alertas` | `4646371d11fa2d637ecba97c9f5597760693aee3` | Rodrigo Riveros | 2026-10-21 |
| `feat/e3-tickets-huerfanos` | `6a68fce0a61c086ec1c4451f1870be1c25b88225` | Rodrigo Riveros | 2026-10-21 |
| `feat/e4-avisos-claros` | `7c540cd17fbe9c879613e52b64156ee974fae0b0` | Nicolás Zamora | 2026-10-26 |
| `feat/e4-catalogo-v1` | `db845b2e13c6e747dc8e449c56d41144d74fb71f` | Nicolás Zamora | 2026-10-26 |
| `feat/e4-validate-v1` | `2d374226157a4e70938102915f70618f363934c0` | Nicolás Zamora | 2026-10-26 |
| `feat/validate-mejoras-prueba-20-10` | `8bd22f4e60c87ee1e4768032f5bbf4922f139335` | Patricio Gonzalez | 2026-10-21 |
| `fix/e4-coherencia` | `77766b4cb44e36abb45a97364e47087bd11d6c85` | Nicolás Zamora | 2026-10-26 |
| `fix/pruebas-solo-linux` | `fd88610242e9c98bd595d91142967d89077aa389` | Patricio Gonzalez | 2026-10-15 |

## Ramas que no se borran

| Rama | Por qué |
| :--- | :--- |
| `docs/documentos-rodrigo-v2` | PR #40 abierto |
| `docs/instalacion-07-11-12-vigentes` | PR #39 abierto |
| `feat/e1-mediciones-servidor` | Experimento de medición: se archiva como etiqueta `archivo/<rama>` (issue #32) |
| `feat/e2-mediciones-prompt-v1` | Experimento de medición: se archiva como etiqueta `archivo/<rama>` (issue #32) |
| `feat/e2-mediciones-prompt-v2` | Experimento de medición: se archiva como etiqueta `archivo/<rama>` (issue #32) |
| `feat/e2-prompt-confianza` | Experimento de medición: se archiva como etiqueta `archivo/<rama>` (issue #32) |
| `feat/medir-escenarios` | Trabajo en curso de Patricio (qué medida elige la IA en E1 a E4) |
| `fix/consola-revertir-nivel-3` | PR #41 abierto |
