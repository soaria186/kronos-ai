# Imagen de SOAR-VALIDATE, SOAR-EXECUTE, SOAR-NOTIFY y SOAR-CONSOLE (el comando lo elige
# servicios.yml).
# Se construye desde la raíz del repositorio:
#   docker build -t kronos-servicios -f infra/docker/servicios/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY persistencia/requirements.txt /tmp/requirements.txt
COPY consola/requirements.txt /tmp/requirements-consola.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt -r /tmp/requirements-consola.txt \
 && groupadd --system --gid 10001 kronos \
 && useradd --system --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin kronos

# Sólo el código que usan los servicios. El catálogo va como datos (R2). VALIDATE usa de
# decision/ el cliente del modelo, las plantillas y los prompts; no las mediciones.
COPY validacion/ validacion/
COPY conectores/ conectores/
COPY decision/__init__.py decision/inferencia.py decision/ollama.py decision/plantillas.py decision/
COPY decision/prompts/ decision/prompts/
COPY decision/catalogo/ decision/catalogo/
COPY persistencia/ persistencia/
COPY ejecucion/ ejecucion/
COPY notificacion/ notificacion/
COPY consola/ consola/

# Carpeta de estado de VALIDATE (posición de lectura de alerts.json). Un volumen nuevo
# hereda este dueño; el resto del sistema de archivos va de sólo lectura (servicios.yml).
RUN mkdir /estado && chown 10001:10001 /estado

# uid y gid 10001: los secretos del servidor van con grupo 10001 y permiso 640.
USER 10001:10001
