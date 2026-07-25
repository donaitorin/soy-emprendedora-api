# Soy Emprendedora API

Backend en FastAPI para un dashboard de datos de Meta/Instagram Business. Sirve a un
frontend externo (no incluido en este repo): autenticación propia, gestión de negocios
y colaboradores, conexión OAuth server-side con Meta, y un endpoint de insights.

Documentación funcional completa en [`docs/`](docs/):
[arquitectura](docs/architecture.md), [modelo de datos](docs/data-model.md),
[auth](docs/auth.md), [integración con Meta](docs/meta-integration.md),
[referencia de API](docs/api-reference.md) y [puntos de extensión](docs/extension-points.md).

Para integrar un frontend contra esta API (o pasarle contexto a un agente que lo
construya), usar [docs/frontend-integration.md](docs/frontend-integration.md) —
documento autocontenido con auth, modelo de roles y el contrato completo de cada
endpoint.

## Stack

FastAPI + Pydantic v2, SQLAlchemy 2.0 (async) + asyncpg, Alembic, PostgreSQL 16,
pydantic-settings, argon2-cffi, PyJWT, httpx (async), cryptography (Fernet),
uvicorn. Dependencias gestionadas con [`uv`](https://docs.astral.sh/uv/).

## Levantar el proyecto con Docker

1. Copiá `.env.example` a `.env` y completá los valores (ver sección de variables abajo).
2. `docker compose up --build`

Esto levanta:
- `db`: Postgres 16 con un volumen persistente y healthcheck.
- `api`: build de la imagen, corre las migraciones de Alembic automáticamente
  (`docker-entrypoint.sh` ejecuta `alembic upgrade head` antes de levantar uvicorn)
  y expone la API en `http://localhost:8000`.

La documentación interactiva queda en `http://localhost:8000/docs`.

## Migraciones (manual, sin Docker)

Con `uv` instalado y un Postgres corriendo localmente:

```bash
uv sync
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/soy_emprendedora
uv run alembic upgrade head

# para generar una nueva migración tras cambiar modelos:
uv run alembic revision --autogenerate -m "descripcion"
```

## Variables de entorno

Ver `.env.example`. Resumen:

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Cadena de conexión async a Postgres (`postgresql+asyncpg://...`) |
| `JWT_SECRET` | Secreto para firmar el JWT propio de la API |
| `JWT_EXPIRATION_MINUTES` | Minutos de validez del JWT |
| `FERNET_KEY` | Clave Fernet para encriptar el `access_token` de Meta en reposo |
| `META_APP_ID` / `META_APP_SECRET` | Credenciales de la app en Meta for Developers |
| `META_REDIRECT_URI` | Debe coincidir exactamente con la configurada en Meta for Developers |
| `META_OAUTH_SCOPES` | Scopes solicitados en el flujo OAuth |
| `FRONTEND_URL` | Origen del frontend, usado para configurar CORS |

Generar `FERNET_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Autenticación (cómo la consume el frontend)

El JWT propio viaja como **Bearer token** en el header `Authorization: Bearer <token>`
(no como cookie httpOnly) — así se evita configurar cookies cross-origin entre el
frontend y esta API. El `access_token` de Meta **nunca** se expone en ninguna
respuesta de la API; se guarda encriptado con Fernet.

Flujo básico:

```bash
# Registro (crea user + account propio + entitlement free/active)
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"ana@example.com","password":"supersecreta","first_name":"Ana","last_name":"Pérez"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ana@example.com","password":"supersecreta"}'

# Usar el token devuelto
curl http://localhost:8000/auth/me -H "Authorization: Bearer <access_token>"
```

## Configurar la app de Meta for Developers (para probar el OAuth en local)

1. Creá una app en [developers.facebook.com](https://developers.facebook.com/apps/) de
   tipo "Business".
2. Agregá el producto **Facebook Login** y, en su configuración, agregá como
   "Valid OAuth Redirect URI" exactamente el valor de `META_REDIRECT_URI`
   (por ejemplo `http://localhost:8000/meta/callback` — Meta exige HTTPS salvo para
   `localhost`).
3. Copiá el **App ID** y **App Secret** a `META_APP_ID` / `META_APP_SECRET` en `.env`.
4. Agregá como usuarios de prueba (Roles → Test Users, o tu propio usuario como Admin/
   Developer de la app) para poder autorizar el flujo mientras la app está en modo
   desarrollo.
5. El negocio de prueba debe tener una Página de Facebook con una cuenta de Instagram
   Business/Creator vinculada para que `/meta/callback` encuentre `instagram_business_account`.
6. Flujo: `GET /meta/connect?account_id=<uuid>` (requiere estar autenticado y tener
   acceso a ese `account_id`) redirige a Facebook. Tras autorizar, Facebook redirige a
   `META_REDIRECT_URI` con `code` y `state`; el backend intercambia el `code` por el
   token del lado del servidor y nunca lo expone al frontend.

## No implementado todavía (a propósito)

Ver [docs/extension-points.md](docs/extension-points.md) para el detalle y los `TODO`
exactos en el código: envío real de emails de invitación, integración con pasarela de
pagos, y validación estricta de entitlements (hoy el acceso es libre).
