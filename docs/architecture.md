# Arquitectura

## Qué es esta API

Backend que sirve un dashboard de datos de Meta/Instagram Business a un frontend
externo (no incluido en este repo). No hay renderizado de UI acá: todo es JSON sobre
FastAPI.

## Stack

- **FastAPI** + **Pydantic v2** para la capa HTTP y validación de schemas.
- **SQLAlchemy 2.0 (async)** + **asyncpg** para acceso a datos.
- **Alembic** para migraciones (`alembic/versions/`).
- **PostgreSQL 16** como base de datos.
- **pydantic-settings** para configuración vía variables de entorno (`app/core/config.py`).
- **passlib[bcrypt]** para hash de contraseñas, **PyJWT** para el JWT propio,
  **cryptography (Fernet)** para encriptar en reposo el `access_token` de Meta
  (`app/core/security.py`).
- **httpx** async para llamar a la Graph API de Meta (`app/services/meta_client.py`).
- **uv** como gestor de dependencias (`pyproject.toml` / `uv.lock`), con
  `requirements.txt` exportado para el build de Docker.

## Dos capas de roles independientes

Este es el punto de diseño más importante a tener en cuenta antes de tocar
autorización: hay **dos roles completamente separados**, en columnas distintas, que
nunca deben mezclarse.

1. **Rol de plataforma** — `users.role`: `admin` | `user`. Ver [`app/models/user.py`](../app/models/user.py)
   (`PlatformRole`). Los `admin` son del equipo de la app y pueden gestionar cualquier
   usuario, negocio o entitlement vía `/admin/*`.
2. **Rol dentro de un negocio** — `user_accounts.role`: `owner` | `collaborator`. Ver
   [`app/models/user_account.py`](../app/models/user_account.py) (`BusinessRole`). Un
   `owner` administra su negocio (edita datos, agrega/quita colaboradores); un
   `collaborator` solo puede ver el dashboard.

Un usuario `admin` de plataforma puede no tener ninguna fila en `user_accounts` y aun
así acceder a cualquier negocio — las dependencias de autorización (`app/api/deps.py`)
le dan bypass explícito antes de mirar `user_accounts`.

## Capas de la aplicación

```
app/main.py            # instancia FastAPI, CORS, incluye routers
app/core/               # config (env vars) y security (hash, JWT, Fernet)
app/db/                 # engine async, sessionmaker, Base declarativa
app/models/              # tablas SQLAlchemy (ver docs/data-model.md)
app/schemas/             # entrada/salida Pydantic — nunca se devuelven modelos SQLAlchemy
app/api/deps.py          # dependencias de autorización reutilizables
app/api/routes/          # un módulo por recurso (auth, accounts, meta, admin, dashboard)
app/services/meta_client.py  # toda llamada HTTP a Graph API vive acá, no en las rutas
```

Ver [docs/api-reference.md](api-reference.md) para el detalle de endpoints,
[docs/auth.md](auth.md) para las dependencias de autorización, y
[docs/meta-integration.md](meta-integration.md) para el flujo OAuth.

## Diseño "1 hoy, muchos mañana"

Varias relaciones son 1-a-1 en la práctica actual (un usuario con un negocio, un
negocio con un entitlement activo, un negocio con una conexión de Meta), pero están
modeladas como 1-a-muchos a nivel de base de datos a propósito, para no requerir una
migración cuando esa restricción se relaje. El detalle de cada caso está en
[docs/data-model.md](data-model.md).
