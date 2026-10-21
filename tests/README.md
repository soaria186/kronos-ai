# Pruebas automatizadas

- **Unitarias** (`tests/unit`): no necesitan base ni red. `python -m unittest discover -s tests/unit`
- **Integración** (`tests/integracion`): usan PostgreSQL. Se corren con `bash tests/integracion/ejecutar.sh`,
  que crea una base aparte (`kronos_pruebas`), le copia el esquema de la base real, corre las pruebas en la
  red interna de Docker y borra la base al terminar. Nunca escriben en la base real: `_base.py` se niega a
  arrancar si `KRONOS_DSN` apunta a una base cuyo nombre no termina en `_pruebas`.
- **SQL** (`tests/sql`): ver `tests/sql/ejecutar.sh`.
