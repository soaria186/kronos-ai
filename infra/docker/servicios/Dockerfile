# Imagen de SOAR-EXECUTE, SOAR-NOTIFY y SOAR-CONSOLE (el comando lo elige servicios.yml).
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

# Sólo el código que usan los servicios. El catálogo va como datos (R2).
COPY validacion/ validacion/
COPY decision/catalogo/ decision/catalogo/
COPY persistencia/ persistencia/
COPY ejecucion/ ejecucion/
COPY notificacion/ notificacion/
COPY consola/ consola/

# uid y gid 10001: los secretos del servidor van con grupo 10001 y permiso 640.
USER 10001:10001
