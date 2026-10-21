# Imagen para correr las pruebas de integración dentro de la red interna de Docker,
# donde está la base (la base no publica puertos al host).
#
#   docker build -t kronos-pruebas -f tests/integracion/Dockerfile .
#   docker run --rm --network kronos_interna -v "${PWD}:/app" -e KRONOS_DSN=... kronos-pruebas
FROM python:3.12-slim
WORKDIR /app
COPY persistencia/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "-m", "unittest", "-v", "tests.integracion.test_repositorio", "tests.integracion.test_ejecucion", "tests.integracion.test_notificacion", "tests.integracion.test_consola_rol", "tests.integracion.test_validate_alerta", "tests.integracion.test_validate_ciclo", "tests.integracion.test_alertas_guardadas", "tests.integracion.test_tickets_huerfanos"]
