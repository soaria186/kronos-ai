# 06 · Ollama y modelos (SOAR-CLASSIFY)

| Campo | Valor |
| :--- | :--- |
| Responsable | Patricio |
| Revisor | [POR CONFIRMAR: otro integrante] |
| Componente | SOAR-CLASSIFY |
| Versiones | Ollama 0.40.0 · qwen2.5:7b · Ubuntu 24.04 |
| Requisitos | Partes 01 (servidor y NetBird) y 02 (Docker) terminadas |

SOAR-CLASSIFY es el modelo de lenguaje que clasifica cada alerta en dos pasos (familia y
playbook). Corre en SOAR-CORE-01, sin GPU, con Ollama en un contenedor. Sólo escucha en
`127.0.0.1:11434`: no se publica a internet ni por NetBird.

**Modelo elegido: `qwen2.5:7b`** (medición del 14-10-2026, ver
`decision/mediciones/resultados/README.md`). El `qwen2.5:3b` es el doble de rápido, pero 4
de 10 ataques de inyección lograron cambiar su clasificación; al 7B, ninguno. Se instalan
los dos para poder repetir la comparación.

Convenciones: **[PC]** es el computador del integrante y **[servidor]** es SOAR-CORE-01. No
se copia el rótulo al escribir el comando. `XXXX` reemplaza datos que no van en el
repositorio: usuario, dirección del servidor y llave.

---

## 1. Copiar la configuración al servidor

Se despliega sólo lo versionado, con `git archive`. Con NetBird conectado:

```
[PC] git fetch origin
[PC] git archive --format=tar.gz -o ollama.tar.gz origin/develop infra/ollama
[PC] scp -i XXXX ollama.tar.gz XXXX@XXXX:~/
```

**Debe mostrar:** la transferencia al 100 %.

```
[servidor] sudo mkdir -p /opt/kronos/ollama
[servidor] sudo tar -xzf ~/ollama.tar.gz -C /opt/kronos/ollama --strip-components=2
[servidor] ls /opt/kronos/ollama
```

**Debe mostrar:** `docker-compose.yml`.

## 2. Levantar el contenedor

```
[servidor] cd /opt/kronos/ollama
[servidor] sudo docker compose up -d
```

**Debe mostrar:** `Container ollama  Started` (la primera vez descarga la imagen
`ollama/ollama:0.40.0`).

```
[servidor] sudo docker ps --filter name=ollama --format '{{.Names}} | {{.Image}} | {{.Ports}} | {{.Status}}'
```

**Debe mostrar:** `ollama | ollama/ollama:0.40.0 | 127.0.0.1:11434->11434/tcp | Up ...`. Si el
puerto aparece como `0.0.0.0:11434`, **detener** (`sudo docker compose down`) y revisar el
archivo: Ollama no debe quedar expuesto.

## 3. Descargar los modelos

```
[servidor] sudo docker exec ollama ollama pull qwen2.5:7b
[servidor] sudo docker exec ollama ollama pull qwen2.5:3b
[servidor] sudo docker exec ollama ollama list
```

**Debe mostrar:**

```
NAME          ID              SIZE
qwen2.5:7b    845dbda0ea48    4.7 GB
qwen2.5:3b    357c53fb659c    1.9 GB
```

Los ID son los de los modelos medidos el 14-10-2026. Si no coinciden, el modelo cambió en
el registro de Ollama y hay que repetir la medición antes de usarlo.

## 4. Verificar versión, reinicio y puerto

```
[servidor] sudo docker exec ollama ollama --version
[servidor] sudo docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' ollama
[servidor] curl -s http://127.0.0.1:11434/api/version
```

**Debe mostrar:** `ollama version is 0.40.0`, `unless-stopped` y `{"version":"0.40.0"}`.

## 5. Dejar el 7B cargado en memoria

Con `OLLAMA_KEEP_ALIVE=-1` el modelo no se descarga, pero tras un reinicio hay que cargarlo
una vez. Esta petición sólo carga el modelo, sin generar texto:

```
[servidor] curl -s http://127.0.0.1:11434/api/generate -d '{"model": "qwen2.5:7b", "keep_alive": -1}'
[servidor] sudo docker exec ollama ollama ps
```

**Debe mostrar:** una respuesta con `"done":true` y, en `ollama ps`, la fila de
`qwen2.5:7b` con `Forever` en la columna `UNTIL`.

SOAR-VALIDATE también pide `keep_alive: -1` en cada llamada (`decision/ollama.py`), así que
el modelo vuelve a quedar cargado aunque se olvide este paso; la diferencia es que la
primera alerta después de un reinicio pagaría el arranque en frío.

## 6. Probar desde el PC

El PC llega a Ollama por un túnel SSH: el puerto 11435 del PC queda conectado al 11434 del
servidor. Ventana 1 (dejarla abierta):

```
[PC] ssh -i XXXX -o ServerAliveInterval=30 -L 11435:127.0.0.1:11434 XXXX@XXXX
```

Ventana 2:

```
[PC] curl.exe -s http://127.0.0.1:11435/api/version
```

**Debe mostrar:** `{"version":"0.40.0"}`.

Medición de comprobación (unos 7 minutos, sólo en tibio):

```
[PC] python decision\mediciones\medir_inferencia.py qwen2.5:7b --condiciones tibio
```

**Debe mostrar,** al final: `tibio  t_total mediana ~20 s ... | JSON válido 100.0 % | precisión paso 1 95.0 %`
(referencia del 14-10: 19/20, mediana 20,0 s). Una precisión muy distinta o un JSON válido
bajo 100 % indican que cambió el modelo o el prompt.

## 7. Prueba de reinicio

Coordinar con el equipo antes de reiniciar el servidor (prueba de reinicio de la parte 02).
Después del reinicio:

```
[servidor] sudo docker ps --filter name=ollama --format '{{.Names}} | {{.Status}}'
```

**Debe mostrar:** `ollama | Up ...`. Luego repetir el paso 5 para dejar el 7B cargado.

---

## Valores de referencia (14-10-2026, servidor sin GPU, con Wazuh y PostgreSQL corriendo)

| Modelo | Tibio (mediana) | Frío (mediana) | Precisión paso 1, 20 casos | Inyección: ataques que lograron su objetivo |
| :--- | :--- | :--- | :--- | :--- |
| qwen2.5:7b | 20,0 s | 58,4 s | 19/20 | 0/10 |
| qwen2.5:3b | 9,8 s | 27,2 s | 16/20 | 4/10 |

Parámetros de cada llamada: `temperature = 0`, `num_ctx = 4096`, esquema JSON en `format`,
`keep_alive = -1`. Los prompts están en `decision/prompts/`.

## Pendientes

- [POR CONFIRMAR: el contenedor `ollama` que corre hoy en el servidor se creó antes de este
  archivo, con la imagen `ollama/ollama` sin versión fijada. Para pasar al compose hay que
  detenerlo y crear el nuevo; coordinar con Nicolás. Los modelos se vuelven a descargar en
  el volumen `kronos_ollama_modelos` (paso 3); el volumen anterior se borra sólo después de
  comprobar el paso 6.]
- [POR CONFIRMAR: SOAR-VALIDATE se conectará a Ollama por la red `kronos_inferencia` cuando
  exista su propio compose; se define con Rodrigo.]
