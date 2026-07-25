# Referencia de API

Todos los endpoints usan schemas Pydantic v2 de entrada/salida (`app/schemas/`) — nunca
se devuelven modelos SQLAlchemy directamente. Errores vía `HTTPException` con códigos
apropiados (401/403/404/409/502). Documentación interactiva viva: `/docs` (Swagger) y
`/redoc`.

## Auth (`app/api/routes/auth.py`)

| Método | Path | Auth | Descripción |
|---|---|---|---|
| POST | `/auth/register` | — | Crea user + account propio + owner + entitlement free/active. Devuelve JWT. |
| POST | `/auth/login` | — | Devuelve JWT. |
| GET | `/auth/me` | Bearer | Usuario + lista de sus negocios con rol en cada uno. |

## Accounts (`app/api/routes/accounts.py`)

| Método | Path | Auth | Descripción |
|---|---|---|---|
| GET | `/accounts/me` | Bearer | Negocios del usuario autenticado + su rol en cada uno. |
| GET | `/accounts/{account_id}` | miembro del negocio (owner/collaborator) o admin | Detalle del negocio. |
| PATCH | `/accounts/{account_id}` | owner del negocio o admin | Editar negocio (hoy solo `name`). |
| GET | `/accounts/{account_id}/members` | miembro del negocio o admin | Lista miembros y roles. |
| POST | `/accounts/{account_id}/members` | owner o admin | Agrega colaborador por email. Si el email no existe, crea el user con password temporal (ver [extension-points.md](extension-points.md)). 409 si ya es miembro. |
| DELETE | `/accounts/{account_id}/members/{user_id}` | owner o admin | Quita colaborador. 409 si es el único owner. |

## Meta (`app/api/routes/meta.py`)

| Método | Path | Auth | Descripción |
|---|---|---|---|
| GET | `/meta/connect?account_id=` | miembro del negocio o admin | Redirige a OAuth de Facebook. |
| GET | `/meta/callback?code=&state=` | — (validado por `state` firmado) | Intercambia code por token, lista páginas, persiste si hay una sola. |
| POST | `/meta/select-page` | miembro del negocio o admin (validado del body) | Fija la página elegida cuando el callback devolvió varias opciones. |
| GET | `/meta/status?account_id=` | miembro del negocio o admin | Estado de conexión, sin exponer el token. |
| DELETE | `/meta/disconnect?account_id=` | miembro del negocio o admin | Desactiva la conexión activa. |

Detalle completo del flujo en [meta-integration.md](meta-integration.md).

## Admin (`app/api/routes/admin.py`) — todas requieren `role=admin` de plataforma

| Método | Path | Descripción |
|---|---|---|
| GET | `/admin/users?role=&is_active=` | Lista usuarios con filtros básicos. |
| PATCH | `/admin/users/{user_id}` | Edita cualquier user (incl. `role` de plataforma). |
| GET | `/admin/accounts` | Lista todos los negocios. |
| PATCH | `/admin/accounts/{account_id}` | Edita cualquier negocio. |
| GET | `/admin/accounts/{account_id}/entitlement` | Historial completo de entitlements del negocio. |
| POST | `/admin/accounts/{account_id}/entitlement` | Crea/asigna un nuevo entitlement (nuevo plan, reactivación). |
| PATCH | `/admin/entitlements/{entitlement_id}` | Revoca/cambia status de un entitlement existente. |

## Dashboard (`app/api/routes/dashboard.py`)

| Método | Path | Auth | Descripción |
|---|---|---|---|
| GET | `/dashboard/{account_id}/insights` | miembro del negocio o admin + `check_entitlement` | Insights básicos de IG (followers, impressions, reach) vía Graph API. 404 si no hay conexión Meta activa; 502 si la Graph API falla. |

## Misceláneo

| Método | Path | Descripción |
|---|---|---|
| GET | `/health` | Liveness check simple, sin auth. |
