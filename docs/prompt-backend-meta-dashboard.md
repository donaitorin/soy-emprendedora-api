# Prompt para Claude Code

Copia y pega todo lo siguiente en Claude Code.

---

Quiero que construyas un backend en Python para una API que sirve un dashboard de datos de Meta/Instagram Business para negocios. Usa las versiones más recientes y estables de cada librería (no fijes versiones antiguas por compatibilidad "segura"; usa lo último disponible hoy). El proyecto debe quedar completamente dockerizado.

## Stack requerido

- **FastAPI** (última versión estable) como framework de la API, con Pydantic v2 para schemas y validación.
- **SQLAlchemy 2.0** en modo async + **asyncpg** como driver de Postgres.
- **Alembic** para migraciones de base de datos.
- **PostgreSQL 16** como base de datos, corriendo en su propio contenedor.
- **pydantic-settings** para manejo de configuración vía variables de entorno.
- **passlib[bcrypt]** (o argon2-cffi si es más moderno) para hash de contraseñas.
- **python-jose** o **pyjwt** para firmar y validar JWT de sesión.
- **httpx** (async) para llamar a la Graph API de Meta y para el intercambio de OAuth.
- **cryptography** (Fernet) para encriptar en reposo el `access_token` de Meta antes de guardarlo en DB.
- **uvicorn** como servidor ASGI.
- Gestor de dependencias moderno (usa `uv` si es viable, si no `pip` con `requirements.txt` generado con versiones actuales).

## Arquitectura general

La API sirve a un frontend externo (no lo construyas tú, solo la API). Hay dos tipos de "identidad" en el sistema:

1. **Rol de plataforma** (`users.role`): `admin` o `user`. Los `admin` son del equipo de la app y pueden gestionar cualquier usuario, negocio y entitlement. Los `user` son dueños o colaboradores de negocios.
2. **Rol dentro de un negocio** (`user_accounts.role`): `owner` o `collaborator`. Un `owner` puede editar su negocio, agregar/quitar colaboradores. Un `collaborator` solo puede ver el dashboard de ese negocio.

Estos dos roles son completamente independientes y no deben mezclarse en la misma columna.

## Modelo de datos

Diseña las tablas para que hoy la relación práctica sea 1 a 1 en varios casos, pero el esquema debe soportar 1 a muchos sin refactor futuro (usa tablas puente / FKs con cardinalidad 1-a-muchos aunque la lógica de negocio actual solo permita una fila activa a la vez donde se indique).

### `users`
- `id` (UUID, PK)
- `email` (unique, not null)
- `password_hash` (not null)
- `first_name` (not null)
- `last_name` (not null)
- `role` (enum: `admin`, `user`; default `user`) — rol de plataforma
- `is_active` (bool, default true)
- `created_at`, `updated_at`

Solo se capturan estos 4 datos en el registro: email, contraseña, nombre, apellido.

### `accounts` (representa el negocio, no la persona)
- `id` (UUID, PK)
- `name` (not null)
- `created_at`, `updated_at`

### `user_accounts` (tabla puente, many-to-many aunque hoy sea casi 1-a-1)
- `id` (UUID, PK)
- `user_id` (FK -> users)
- `account_id` (FK -> accounts)
- `role` (enum: `owner`, `collaborator`)
- `created_at`
- unique constraint en (`user_id`, `account_id`)

Aunque **hoy** un usuario solo tendrá un `account`, no pongas esa restricción a nivel de base de datos ni de modelo — solo a nivel de lógica de negocio (para poder relajarla después sin migrar el esquema). Comenta esto en el código.

### `entitlements`
- `id` (UUID, PK)
- `account_id` (FK -> accounts)
- `plan` (enum o string: `free`, `pro`, `agency`, etc.)
- `status` (enum: `active`, `trialing`, `past_due`, `canceled`, `revoked`)
- `source` (string: `manual`, `stripe`, `promo`, etc.)
- `external_ref` (nullable, para IDs de sistemas de pago futuros)
- `current_period_end` (nullable timestamp)
- `created_at`, `updated_at`

Aunque hoy cada `account` tendrá un único entitlement activo, modela la relación como 1 `account` a muchos `entitlements` (histórico), y expón siempre "el entitlement vigente" vía una query (el más reciente con status activo/trialing), no vía un campo único obligatorio.

Al registrarse un usuario, créale automáticamente un entitlement con `plan=free`, `status=active` (acceso libre por ahora, sin validación real de pago).

### `meta_connections`
- `id` (UUID, PK)
- `account_id` (FK -> accounts)
- `fb_page_id`
- `ig_business_id` (nullable)
- `page_name` (nullable)
- `ig_username` (nullable)
- `access_token_encrypted` (texto, guardado encriptado con Fernet)
- `token_expires_at` (nullable)
- `is_primary` (bool, default true)
- `created_at`, `updated_at`

Modela esta relación como `account` (1) a `meta_connections` (muchos), aunque hoy cada negocio tenga una sola fila activa.

## Autenticación y sesión

- El JWT de tu API (access token propio) es lo único que debe viajar al frontend. Nunca expongas el `access_token` de Meta en ninguna respuesta de la API.
- Implementa `POST /auth/register` (email, password, first_name, last_name):
  - Crea el `user`.
  - Crea un `account` nuevo para ese usuario.
  - Crea la fila en `user_accounts` con `role=owner`.
  - Crea un `entitlement` inicial (`plan=free`, `status=active`).
  - Devuelve JWT.
- Implementa `POST /auth/login` (email, password) -> JWT.
- Implementa `GET /auth/me` -> datos del usuario autenticado + su(s) negocio(s) y rol en cada uno.
- Usa cookies httpOnly para el JWT si es sencillo de configurar con CORS, o Bearer token en header como alternativa — deja el mecanismo bien documentado en el README.

## Conexión con Meta (OAuth server-side)

Implementa el flujo completo, siempre intercambiando el `code` por el token **desde el backend**, nunca desde el frontend:

- `GET /meta/connect` -> redirige al usuario a la URL de OAuth de Facebook con los scopes necesarios (`pages_show_list`, `instagram_basic`, `instagram_manage_insights`, `business_management`, etc.). El `state` debe llevar el `account_id` codificado/firmado para saber a qué negocio asociar la conexión al volver.
- `GET /meta/callback` -> recibe el `code`, lo intercambia server-to-server por el `access_token`, obtiene las páginas disponibles (`/me/accounts`) y la cuenta de IG asociada, encripta el token y lo guarda en `meta_connections`. Si el negocio tiene más de una página disponible, devuelve la lista para que el frontend deje elegir cuál usar como `is_primary` (implementa un endpoint adicional `POST /meta/select-page` para fijarla).
- `GET /meta/status?account_id=` -> indica si el negocio tiene conexión activa, con qué página/IG, sin exponer el token.
- `DELETE /meta/disconnect?account_id=` -> borra o desactiva la conexión.
- Todas estas rutas deben verificar que el usuario autenticado tenga acceso (owner o collaborator) al `account_id` en cuestión.

## Endpoints de negocio (`accounts`)

- `GET /accounts/me` -> lista los negocios del usuario autenticado con su rol en cada uno.
- `GET /accounts/{account_id}` -> detalle (requiere ser miembro del negocio).
- `PATCH /accounts/{account_id}` -> editar (solo `owner` del negocio, o `admin` de plataforma).
- `POST /accounts/{account_id}/members` -> el `owner` agrega otro usuario como `collaborator`. Body: `email`. Si el email ya existe como `user`, solo crea la fila en `user_accounts`. Si no existe, créalo (puedes generar una contraseña temporal o dejar un campo `must_set_password` para más adelante — no implementes el envío de emails de invitación todavía, solo deja la lógica de asociación lista y documentada como "TODO: reemplazar por flujo de invitación por email").
- `GET /accounts/{account_id}/members` -> lista miembros y roles (owner o collaborator del negocio, o admin de plataforma).
- `DELETE /accounts/{account_id}/members/{user_id}` -> el `owner` quita un colaborador (no puede quitarse a sí mismo si es el único owner).

## Endpoints de administración de plataforma (`admin` only)

- `GET /admin/users` -> lista todos los usuarios, filtros básicos.
- `PATCH /admin/users/{user_id}` -> editar cualquier usuario (incluido cambiar su `role` de plataforma).
- `GET /admin/accounts` -> lista todos los negocios.
- `PATCH /admin/accounts/{account_id}` -> editar cualquier negocio.
- `GET /admin/accounts/{account_id}/entitlement` -> ver entitlement vigente e histórico.
- `POST /admin/accounts/{account_id}/entitlement` -> crear/asignar un nuevo entitlement (cambiar plan, reactivar).
- `PATCH /admin/entitlements/{entitlement_id}` -> revocar/cambiar status de un entitlement existente.

Protege todas estas rutas con una dependencia `require_platform_admin` que valida `users.role == 'admin'`.

## Middleware / dependencias de autorización a construir

Crea dependencias de FastAPI reutilizables:

- `get_current_user` -> valida JWT, retorna el `user` actual.
- `require_platform_admin` -> valida rol de plataforma `admin`.
- `require_business_access(account_id)` -> valida que el `user` tenga fila en `user_accounts` para ese `account_id` (cualquier rol) o sea `admin`.
- `require_business_owner(account_id)` -> valida que el `user` sea `owner` de ese `account_id` o `admin`.
- `check_entitlement(account_id)` -> **stub por ahora**: hoy siempre retorna `True` (acceso libre), pero debe estar estructurado como una función clara y centralizada (ej. revisando si existe un entitlement con `status in ('active','trialing')`) para que más adelante, sin tocar los endpoints, se active la validación real. Documenta esto explícitamente con un comentario `# TODO: activar validación real de entitlement cuando se integre facturación`.

## Endpoint de dashboard (datos de Meta)

- `GET /dashboard/{account_id}/insights` -> valida `require_business_access` + `check_entitlement`, obtiene el `meta_connections` del negocio, desencripta el token, llama a la Graph API (usa `httpx` async) para traer insights básicos de la cuenta de IG, y devuelve los datos ya procesados. Deja el mapeo de métricas simple/genérico por ahora (ej. followers, impressions, reach) ya que se puede expandir después.

## Estructura de proyecto sugerida

```
app/
  main.py
  core/
    config.py         # pydantic-settings
    security.py        # JWT, hashing, encriptación Fernet
  db/
    session.py
    base.py
  models/
    user.py
    account.py
    user_account.py
    entitlement.py
    meta_connection.py
  schemas/
    ...  (pydantic schemas por recurso)
  api/
    deps.py            # dependencias de autorización
    routes/
      auth.py
      accounts.py
      meta.py
      admin.py
      dashboard.py
  services/
    meta_client.py      # llamadas a Graph API
alembic/
  ...
Dockerfile
docker-compose.yml
.env.example
requirements.txt
README.md
```

## Docker

- `Dockerfile`: imagen basada en `python:3.13-slim` (o la última estable disponible), multi-stage si aporta valor, instala dependencias, corre con `uvicorn` (o `gunicorn` + workers uvicorn para prod).
- `docker-compose.yml`: dos servicios como mínimo:
  - `api`: build del Dockerfile, expone el puerto, monta `.env`, depende de `db` (con `healthcheck`).
  - `db`: `postgres:16`, con volumen persistente, variables de entorno para user/password/db.
  - Incluye un servicio opcional comentado para `pgadmin` si quieres facilitar debugging local.
- Incluye un comando o script para correr las migraciones de Alembic automáticamente al levantar el contenedor `api` (entrypoint script), o documenta claramente el paso manual en el README.

## Variables de entorno (`.env.example`)

Incluye al menos:
```
DATABASE_URL=
JWT_SECRET=
JWT_EXPIRATION_MINUTES=
FERNET_KEY=
META_APP_ID=
META_APP_SECRET=
META_REDIRECT_URI=
META_OAUTH_SCOPES=
FRONTEND_URL=
```

## Requisitos adicionales

- Configura CORS para permitir el origen del frontend (variable de entorno).
- Genera migraciones de Alembic reales para todas las tablas descritas (no dejes solo los modelos sin migración).
- Escribe un `README.md` con: cómo levantar el proyecto con `docker compose up`, cómo correr migraciones, cómo probar el flujo de registro/login, y cómo configurar la app de Meta Developers (App ID, secret, redirect URI) para que el OAuth funcione en local.
- No implementes todavía: envío real de emails de invitación, integración con pasarela de pagos, ni la validación estricta de entitlements — pero deja los puntos de extensión claramente comentados en el código como se indicó arriba.
- Todos los endpoints deben usar schemas Pydantic de entrada y salida (no devuelvas modelos de SQLAlchemy directamente).
- Usa manejo de errores consistente (HTTPException con códigos apropiados: 401, 403, 404, 409, etc.).

Antes de escribir código, muéstrame primero el plan de archivos que vas a crear y el diagrama final de tablas con sus relaciones, para confirmarlo contigo antes de generar todo el proyecto.
