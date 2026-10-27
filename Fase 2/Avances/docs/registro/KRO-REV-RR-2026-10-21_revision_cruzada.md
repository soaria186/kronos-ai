# KRO-REV-RR-2026-10-21 — Revisión cruzada de Rodrigo

Revisión de los PR de Nicolás abiertos (#31 y #33) y de los PR #25 a #30, ya mezclados sin revisión registrada (revisión «después del hecho»). Cada sección trae el texto listo para pegar como comentario en GitHub **desde la cuenta personal de Rodrigo**. La sesión del asistente de IA usa la cuenta compartida `soaria186`, y una revisión desde ahí no quedaría a nombre de Rodrigo.

Severidad: 🔴 bloquea el merge · 🟡 corregir pronto, en este PR u otro · ⚪ observación.

---

## PR #31 — script `kronos-bloquear-ip` (Linux) y guía 08 (Nicolás, abierto)

**Veredicto propuesto: aprobar con cambios pedidos** (los dos 🟡 pueden ir en este mismo PR; son de pocas líneas).

> Revisado. El script hace lo que dice y la guía se puede seguir. Antes o justo después de mezclar:
>
> 🟡 **1. Rechazar la puerta de enlace.** Es el hallazgo del 20-10: bloquear la puerta de enlace deja al equipo sin red, y la lista de exclusión todavía no la trae. El script de Windows (#32) ya la rechaza. Propuesta:
> ```python
> ruta = subprocess.run(["ip", "-j", "route", "show", "default"], capture_output=True, text=True).stdout
> puertas = {r.get("gateway") for r in json.loads(ruta or "[]")}
> if ... or str(ip) in puertas:
> ```
> (y lo mismo con `ip -6` para IPv6).
>
> 🟡 **2. Exigir exactamente dos argumentos.** Hoy `extra_args` con tres o más valores se acepta y el resto se ignora en silencio. Mejor `if len(args) != 2: rechazar`, igual que en Windows.
>
> ⚪ **3. Multicast, enlace local y difusión** no se rechazan en el script. EXECUTE ya los filtra (`ordenes.py`), así que no es urgente; agregarlos dejaría las dos barreras iguales a las de Windows.
>
> ⚪ **4. Guía, sección 3.2, paso 5:** `printf '{"username":"kronos-execute","password":"%s"}'` arma un JSON inválido si la contraseña trae `"` o `\`, y la política de Wazuh exige un símbolo. Sugiero decir que la contraseña no lleve `"` ni `\`, o armar el JSON con `python3 -c 'import json,sys; ...'`.
>
> ⚪ **5.** `docker exec -e T="$TOKEN"` deja el token en los argumentos del proceso (visible en `ps` del servidor mientras corre). Dura poco y vence; basta con mencionarlo.
>
> ⚪ **6.** Que las reglas no sobrevivan a un reinicio afecta más al nivel 2 (PB-F1-03, PB-F3-02) que al nivel 1: la bitácora diría «aplicado» y la regla ya no existiría. Lo llevo al punto de encuentro 1.

---

## PR #33 — EP-WKS-01 pasa al PC de escritorio y estado del laboratorio (Nicolás, abierto)

**Veredicto propuesto: aprobar cuando se aclare el punto 1.**

> 🟡 **1. Contradicción con el #31.** Aquí dice «en Linux quedaron confirmados de punta a punta el bloqueo de una IP y su reversión automática a los 60 minutos». El #31 y su lista de comprobación dicen que la reversión automática está **pendiente**, y NOTIFY avisó hoy que la reversión del ticket #20 terminó en `REVERSION_FALLIDA` («agent is not active»). Si hubo una prueba nueva el 21-10 que la confirmó, ¿qué ticket fue? Así se anota en los dos PR. Si no la hubo, hay que corregir la frase.
>
> ⚪ **2.** La nota sobre HVCI e hipervisor apagados en el PC de escritorio está bien registrada. Sugiero agregar la fecha en que se vuelven a activar, para que no quede pendiente sin dueño.

---

## PR #25 — VALIDATE guarda la alerta completa en `ALERTA_RECIBIDA` (mezclado)

> ⚪ Revisado después del merge. El contrato con EXECUTE y la normalización de las IP de la lista de exclusión (forma canónica, `::ffff:`) están bien y con pruebas.
>
> 🟡 Guardar la alerta completa **dentro de la bitácora** hacía imposible borrar sus datos personales (R-09). Queda corregido en el **#34**: la alerta pasa a `alertas_guardadas` y la bitácora guarda su huella. VALIDATE no cambia.

## PR #26 — omitir en Windows tres pruebas (mezclado)

> ⚪ Correcto. Queda anotado que la causa de `test_servidor_apagado` en Windows no está investigada; como el cliente corre en Linux, no bloquea nada.

## PR #27 — plazos de reversión de 60 minutos en KRO-CAT-01 0.2 (mezclado)

> ⚪ Correcto, con prueba que exige plazo entero positivo en las cinco medidas de reversión automática. Recordar que **PB-F4-01** y **PB-F6-03** tienen plazo, pero su acción no tiene comando (EXECUTE las deja en `ACCION_NO_IMPLEMENTADA`). Los 60 minutos siguen como propuesta: se confirman en el punto de encuentro 1.

## PR #28 — ciclo de VALIDATE y `python -m validacion` (mezclado)

> 🟡 **1. Tickets huérfanos.** Si `procesar` falla después de crear el ticket (por ejemplo, un error de la base en `usos` o en `registrar_decision`), el ticket queda en `PENDING` **sin playbook ni decisión**. Al releer la alerta sale como `REPETIDA` y no se vuelve a procesar. EXECUTE no lo toma y NOTIFY no avisa, así que se pierde en silencio. Es el «recuperador de tickets sin decisión» que está en mis pendientes: lo tomo yo en un PR aparte (recorrer los `PENDING` sin playbook de más de N minutos y pasarlos a `MANUAL_TRIAGE` con aviso).
>
> 🟡 **2. El cortacircuito mide la velocidad de procesamiento, no la de llegada.** `alertas_en_ventana` cuenta **tickets creados** en la ventana, y VALIDATE crea uno cada ~20 s porque espera al modelo. Con una inundación de alertas, los tickets se crean al ritmo del modelo: a ~20 s por alerta, como mucho unos 30 cada 10 minutos, justo el disparo. Así, el cortacircuito se abre tarde (o no se abre, si el modelo va más lento), mientras las primeras alertas ya se procesan y aprueban. Los contadores de tasa sí limitan las acciones. Propuesta: contar por `timestamp` de la alerta, o contar las alertas del lote pendientes antes de llamar al modelo. Afecta la prueba de estrés comprometida (30 alertas en 10 min → cortacircuito). **Para Patricio.**
>
> ⚪ **3.** `comprobar_prompt` al arrancar (el prompt del paso 2 debe describir el catálogo) es una muy buena barrera.

## PR #29 — SOAR-VALIDATE en `servicios.yml` (mezclado)

> ⚪ **1.** `validate` y `execute` declaran los dos `build` con la misma imagen `kronos-servicios:local`; Compose la construye dos veces. Basta con que construya uno y el otro use `pull_policy: never`, como `notify`.
>
> ⚪ **2.** Ollama queda conectado de forma permanente a la red `salida` (internet), que sólo necesita para bajar modelos. Se podría desconectar después de bajar el modelo. Es un riesgo bajo, porque Ollama no recibe datos de afuera, pero conviene anotarlo en el modelo de amenazas.

## PR #30 — permiso del secreto de la base antes de levantar VALIDATE (mezclado)

> ⚪ Correcto. Corrige la numeración del README (había dos pasos 4).

---

## Resumen

| PR | Estado | Veredicto | Lo principal |
| :---: | :--- | :--- | :--- |
| #31 | Abierto | Aprobar con cambios | Rechazar la puerta de enlace; exigir 2 argumentos |
| #33 | Abierto | Aprobar al aclarar | ¿La reversión de 60 min se confirmó o sigue pendiente? |
| #25 | Mezclado | OK | R-09, corregido por el #34 |
| #26 | Mezclado | OK | — |
| #27 | Mezclado | OK | 60 min siguen como propuesta |
| #28 | Mezclado | Observaciones | Tickets huérfanos (Rodrigo); cortacircuito por llegada (Patricio) |
| #29 | Mezclado | OK | Imagen construida dos veces; Ollama con salida a internet |
| #30 | Mezclado | OK | — |
