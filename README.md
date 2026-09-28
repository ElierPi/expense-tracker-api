# Expense Tracker API

API de finanzas personales con categorías privadas, ingresos, gastos y reportes mensuales por moneda. Proyecto de portafolio centrado en integridad de datos, aislamiento entre usuarios y pruebas con PostgreSQL real.

**Stack:** Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy 2, Psycopg 3, PostgreSQL 17+, Alembic, JWT, Argon2, pytest, Ruff y Docker Compose.

## Arranque con Docker

Requisitos: Docker Engine con Compose v2. Ejecuta desde esta carpeta:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
# Copia el valor generado a JWT_SECRET en .env.
docker compose up --build -d
```

La migración se ejecuta como un servicio previo al arranque de la API.

- Swagger: [localhost:8001/docs](http://localhost:8001/docs)
- OpenAPI: [localhost:8001/openapi.json](http://localhost:8001/openapi.json)
- Estado de la base: [localhost:8001/ready](http://localhost:8001/ready)

En bash, usa `cp .env.example .env`. Los puertos se publican solo en localhost. Las credenciales de `.env.example` son para desarrollo local; cambia también la contraseña de PostgreSQL para otros entornos. Si contiene caracteres reservados de URL, codifícalos en `DATABASE_URL` y en la URL de Compose.

## Desarrollo local

Requisitos: Python 3.12+ y PostgreSQL (o Docker para levantar solo la base).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
Copy-Item .env.example .env
# Genera y configura JWT_SECRET en .env.
docker compose up -d db
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

En Linux/macOS activa el entorno con `source .venv/bin/activate`. Para PostgreSQL existente, configura `DATABASE_URL` y omite el comando de Docker. La aplicación no crea tablas al arrancar: las migraciones son explícitas.

## Probar el flujo

1. Registra un usuario con `POST /api/v1/auth/register`; contraseña de 12 a 128 caracteres.
2. Solicita un token con `POST /api/v1/auth/token`, formulario `username=<email>&password=...`.
3. En Swagger, usa **Authorize** con el correo y la contraseña.
4. Crea una categoría y después movimientos asociados.
5. Consulta `/api/v1/reports/monthly?year=2026&month=10&currency=COP`.

El archivo [examples.http](./examples.http) contiene solicitudes para REST Client de VS Code o clientes compatibles. También puedes crear datos de demostración con `python -m app.demo` o `docker compose exec api python -m app.demo`: pide correo y contraseña sin guardarlos en el repositorio.

## Endpoints

| Método | Ruta bajo `/api/v1` | Función |
| --- | --- | --- |
| POST | `/auth/register`, `/auth/token` | Registro e inicio de sesión |
| GET | `/auth/me` | Usuario autenticado |
| GET, POST | `/categories` | Consultar y crear categorías |
| DELETE | `/categories/{id}` | Eliminar una categoría vacía |
| GET, POST | `/transactions` | Historial filtrado y creación |
| GET, PUT, DELETE | `/transactions/{id}` | Consulta, reemplazo y eliminación |
| GET | `/reports/monthly` | Ingresos, gastos, saldo y desglose por categoría |

El historial admite `start`, `end` (ambos inclusivos), `kind`, `currency`, `category_id`, `search`, `limit` y `offset`. `PUT` reemplaza el movimiento completo. Los listados tienen límites de página; los movimientos incluyen `total`.

## Decisiones de diseño

```mermaid
erDiagram
    USER ||--o{ CATEGORY : owns
    USER ||--o{ TRANSACTION : owns
    CATEGORY ||--o{ TRANSACTION : classifies
```

- `Decimal` y `NUMERIC(14,2)` evitan aritmética monetaria con `float`. La API devuelve los importes como cadenas decimales.
- Un movimiento tiene importe positivo y tipo `income` o `expense`; no se usan signos para representar el tipo.
- Monedas soportadas: COP, USD, EUR, GBP y MXN, todas con dos decimales. Un reporte trabaja con una moneda explícita; no convierte divisas ni las suma entre sí.
- La FK compuesta `(category_id, owner_id)` garantiza el aislamiento incluso si se escribe directamente en SQL.
- Categorías con movimientos no se eliminan. El historial usa fechas de calendario; los timestamps de auditoría son conscientes de zona horaria.
- JWT de 30 minutos por defecto, con algoritmo fijo, emisor, audiencia y expiración verificados. Las contraseñas se almacenan con Argon2.
- Rutas versionadas, errores HTTP, `X-Request-ID`, logs de duración, `/health` y `/ready`.

`app/api.py` contiene los casos de uso y consultas; `schemas.py` define contratos de entrada/salida; `models.py` y `migrations/` definen persistencia; `core/` concentra configuración y seguridad. Se usan sesiones síncronas con endpoints `def` para delegar trabajo bloqueante al pool de FastAPI.

## Pruebas y calidad

**Usa exclusivamente una base desechable cuyo nombre termine en `_test`: las pruebas vacían sus tablas.** Se valida ese nombre antes de modificar datos. Se prueban las migraciones entregadas, sin sustituirlas por `create_all()` ni por SQLite.

```powershell
docker compose -f compose.test.yaml up -d --wait
$env:TEST_DATABASE_URL='postgresql+psycopg://test:test@localhost:55433/expenses_test'
$env:DATABASE_URL=$env:TEST_DATABASE_URL
$env:JWT_SECRET='test-only-secret-never-use-in-production-12345'
alembic upgrade head
alembic check
pytest --cov=app --cov-report=term-missing
ruff check .
ruff format --check .
docker compose -f compose.test.yaml down
```

En bash define las variables con `export`. Las pruebas cubren aislamiento, FK compuesta, autenticación, tokens inválidos, precisión decimal, cambio de mes, separación por moneda, filtros y validaciones. GitHub Actions ejecuta estas comprobaciones sobre PostgreSQL 17 y Python 3.12/3.13.

`requirements.lock` fija dependencias de ejecución. `requirements-dev.lock` añade herramientas de desarrollo. Para cambiar versiones, resuelve nuevamente las dependencias y ejecuta toda la suite antes de actualizar ambos archivos.

## Funciones añadidas

- `PATCH /api/v1/categories/{id}` cambia el nombre sin alterar los movimientos. Valida propiedad y nombres duplicados.
- `GET /api/v1/transactions?search=texto` busca en descripciones, sin distinguir mayúsculas. `%` y `_` se tratan como texto literal y se combina con los demás filtros.
- `PATCH /api/v1/transactions/{id}` actualiza solo los campos enviados. Rechaza cuerpos vacíos, valores `null`, campos desconocidos e importes inválidos; conserva los campos omitidos y valida categorías del usuario.
- `GET /api/v1/reports/yearly?year=2026&currency=COP` incluye siempre doce meses, también los vacíos, y totales exactos de una sola moneda.
- `GET /api/v1/exports/transactions.csv?start=2026-01-01&end=2026-12-31` exporta un intervalo inclusivo de hasta 366 días. Admite `currency` y `kind`. El límite es 10.000 filas; si se supera devuelve `413` sin truncar. Las celdas de texto que podrían interpretarse como fórmulas se prefijan con apóstrofo.
- Las respuestas bajo `/api/v1/`, incluidos los errores, llevan `Cache-Control: no-store`. También se añaden `X-Content-Type-Options: nosniff` y `Referrer-Policy: no-referrer`.

Los endpoints adicionales se agrupan en `app/features/`. La suite incluye pruebas de los datos de demostración y de la integridad de los datos al fallar una operación. CI construye la imagen Docker y comprueba su importación y esquema OpenAPI como usuario sin privilegios y sin acceso a red, además de ejecutar las pruebas con PostgreSQL.

## Alcance

Incluye operaciones financieras personales; no integra bancos ni pagos reales. No incorpora recuperación de contraseña, verificación por correo, refresh tokens o revocación anticipada de JWT. Para una exposición pública añade TLS y límites de solicitudes en el proxy, además de gestión de secretos y respaldos acordes al entorno.

## Repositorio e historial

Repositorio: [ElierPi/expense-tracker-api](https://github.com/ElierPi/expense-tracker-api).

El historial se preparó el 31 de octubre de 2026 para organizar el portafolio. Las fechas de autor y de commit se distribuyeron entre enero y septiembre de 2026; no representan las fechas originales de desarrollo. Véase [HISTORY.md](./HISTORY.md).

Referencias: [FastAPI y JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [SQLAlchemy con PostgreSQL](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html).
