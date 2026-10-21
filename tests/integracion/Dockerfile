# Imagen para correr las pruebas de integración dentro de la red interna de Docker,
# donde está la base (la base no publica puertos al host).
#
# Lo normal es correrlas con tests/integracion/ejecutar.sh, que crea la base de pruebas
# (kronos_pruebas), arma la conexión y la borra al terminar. A mano:
#
#   docker build -t kronos-pruebas -f tests/integracion/Dockerfile .
#   docker run --rm --network kronos_interna -v "${PWD}:/app" -e KRONOS_DSN kronos-pruebas
#
# KRONOS_DSN tiene que apuntar a una base cuyo nombre termine en «_pruebas»
# (tests/integracion/_base.py): contra la base real las pruebas ni arrancan.
FROM python:3.12-slim
WORKDIR /app
COPY persistencia/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "-m", "unittest", "-v", "tests.integracion.test_repositorio", "tests.integracion.test_ejecucion", "tests.integracion.test_notificacion", "tests.integracion.test_consola_rol", "tests.integracion.test_validate_alerta", "tests.integracion.test_validate_agrupacion", "tests.integracion.test_validate_ciclo", "tests.integracion.test_alertas_guardadas", "tests.integracion.test_tickets_huerfanos"]
