## Qué cambia

<!-- Una o dos frases. Si cierra una tarea del milestone, «Parte de #NN». -->

## Por qué

<!-- El problema, la decisión (D-xx) o el hallazgo que lo motiva. -->

## Cómo se probó

<!-- Pega la salida de las pruebas corridas en tu PC antes de pedir la mezcla (D-66): el CI está configurado,
     pero no habilitado en la cuenta. Los comandos se corren desde la carpeta del proyecto: cd "Fase 2/Avances".
     Agrega las de integración (sólo en kronos_pruebas), del laboratorio o del servidor si las corriste. -->

- [ ] `python -m unittest discover -s tests/unit`
- [ ] `python -m ruff check .` y `python tools/check_r1.py`
- [ ] Sin secretos, IP reales, identificadores de Telegram ni usuarios del servidor

## Qué falta para desplegar

<!-- Migraciones, secretos, variables nuevas, servicios que hay que recrear. «Nada» si no aplica. -->

## Revisión (D-54)

- **Autor:** <!-- integrante; si se abre desde soaria186, quien lo pidió -->
- **Aprueba:** <!-- Nicolás → Rodrigo · Patricio → Nicolás · Rodrigo → Patricio -->
- Lo mezcla un integrante distinto del autor, desde su cuenta personal, con las pruebas del autor pegadas en este PR (CI manual).
