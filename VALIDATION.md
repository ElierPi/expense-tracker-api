# Validación de las mejoras

Preparadas y verificadas el 31 de octubre de 2026, usando Python 3.12.14 y PostgreSQL 18.6 real, con una base de pruebas desechable.

- 27 pruebas aprobadas; cobertura de sentencias de `app/`: 97%.
- `alembic check`: sin diferencias entre modelos y esquema migrado.
- Ruff: lint y formato correctos.
- Pruebas nuevas: edición de categorías, búsqueda literal, actualizaciones parciales, reporte anual, límites y celdas de CSV, cabeceras y datos de demostración.
- El workflow prueba Python 3.12/3.13 con PostgreSQL 17. En Python 3.12 también construye la imagen Docker y valida su importación y OpenAPI sin privilegios y sin red.

Docker no está instalado en el entorno local; esa comprobación se delega al workflow de GitHub Actions. La suite local emite un aviso de deprecación del adaptador HTTPX de Starlette; no afecta al resultado de las pruebas. Las fechas asignadas a los commits se explican en `HISTORY.md`.
