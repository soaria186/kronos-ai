# Imagen de SOAR-EXECUTE y SOAR-NOTIFY (el comando lo elige servicios.yml).
# Se construye desde la raíz del repositorio:
#   docker build -t kronos-servicios -f infra/docker/servicios/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY persistencia/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin kronos

# Sólo el código que usan los servicios. El catálogo va como datos (R2).
COPY validacion/ validacion/
COPY decision/catalogo/ decision/catalogo/
COPY persistencia/ persistencia/
COPY ejecucion/ ejecucion/
COPY notificacion/ notificacion/

USER kronos
