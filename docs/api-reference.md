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
| POST | `/accounts/{account_id}/incomes` | miembro del negocio o admin | Registra un ingreso (`amount`, `occurred_on`, `source`, `payment_method`). |
| GET | `/accounts/{account_id}/incomes?from=&to=` | miembro del negocio o admin | Lista ingresos, más reciente primero por `occurred_on`, filtro opcional por rango de fechas. |
| POST | `/accounts/{account_id}/expenses` | miembro del negocio o admin | Registra un gasto (`amount`, `occurred_on`, `category`). |
| GET | `/accounts/{account_id}/expenses?from=&to=` | miembro del negocio o admin | Lista gastos, más reciente primero por `occurred_on`, filtro opcional por rango de fechas. |
| GET | `/accounts/{account_id}/movements?page=&page_size=&from=&to=&type=` | miembro del negocio o admin | Vista combinada de ingresos y gastos, paginada (`page`/`page_size`), con `type` expuesto. |
| GET | `/accounts/{account_id}/movements/export?from=&to=` | miembro del negocio o admin | Descarga `.xlsx` de ingresos + gastos del rango (`from`/`to` obligatorios, inclusivos). 422 si falta alguno o `from > to`. Ver [frontend-integration.md](frontend-integration.md). |
| DELETE | `/accounts/{account_id}/movements/{movement_id}` | miembro del negocio o admin | Soft-delete de un ingreso o gasto (`deleted_at`). 404 si no existe o ya estaba borrado. |

## Leads (`app/api/routes/leads.py`)

| Método | Path | Auth | Descripción |
|---|---|---|---|
| POST | `/accounts/{account_id}/leads` | miembro del negocio o admin | Crea un lead, siempre en `stage: "nuevo"`. |
| GET | `/accounts/{account_id}/leads?page=&page_size=&stage=&archived=&archive_reason=&created_from=&created_to=` | miembro del negocio o admin | Tabla paginada, activos + archivados, nunca soft-deleted. `created_from`/`created_to` filtran por fecha de `created_at`. |
| GET | `/accounts/{account_id}/leads/board` | miembro del negocio o admin | Data cruda del kanban, sin paginar — solo leads activos. |
| GET | `/accounts/{account_id}/leads/stats` | miembro del negocio o admin | `active_count`, `conversion_rate`, `avg_conversion_days`. |
| POST | `/accounts/{account_id}/leads/archive-converted` | miembro del negocio o admin | Archiva de una todos los activos en `stage: "convertida"` (`archive_reason: "converted"` forzado). |
| PATCH | `/accounts/{account_id}/leads/{lead_id}` | miembro del negocio o admin | Edita `name`/`channel`/`description` (parcial, solo las claves enviadas; `{}` da 422). Activos y archivados. |
| PATCH | `/accounts/{account_id}/leads/{lead_id}/stage` | miembro del negocio o admin | Mueve de etapa (drag and drop). Limpia `converted_at` si sale de `"convertida"`. |
| PATCH | `/accounts/{account_id}/leads/{lead_id}/schedule` | miembro del negocio o admin | Fija o quita (`null`) `scheduled_at`. Solo leads activos. No cambia etapa ni métricas. |
| POST | `/accounts/{account_id}/leads/{lead_id}/archive` | miembro del negocio o admin | Archiva un lead puntual con el `reason` recibido y un `note` opcional (solo se guarda con `not_converted`). |
| POST | `/accounts/{account_id}/leads/{lead_id}/pdf` | miembro del negocio o admin | Sube (o reemplaza) el PDF del lead, `multipart` campo `file`. Máx 10 MB; 413/415/422 según el caso. Activos y archivados. |
| GET | `/accounts/{account_id}/leads/{lead_id}/pdf` | miembro del negocio o admin | `{url, filename, expires_in}` con URL presignada (300 s) de descarga. 404 si no hay PDF. |
| DELETE | `/accounts/{account_id}/leads/{lead_id}/pdf` | miembro del negocio o admin | Borra el PDF del bucket y limpia los campos `pdf_*`. 204; 404 si no hay. |
| DELETE | `/accounts/{account_id}/leads/{lead_id}` | miembro del negocio o admin | Soft-delete. Funciona sobre leads activos o archivados. |

## Suggestions (`app/api/routes/suggestions.py`)

| Método | Path | Auth | Descripción |
|---|---|---|---|
| POST | `/accounts/{account_id}/suggestions` | miembro del negocio o admin | Envía una sugerencia (`message` markdown, trim, 1–5000 chars). `user_id` sale del token. |

## Tasks (`app/api/routes/tasks.py`)

| Método | Path | Auth | Descripción |
|---|---|---|---|
| POST | `/accounts/{account_id}/tasks` | miembro del negocio o admin | Crea una tarea, siempre `done: false`. |
| GET | `/accounts/{account_id}/tasks?date=` | miembro del negocio o admin | Tareas de un día (default hoy en UTC), sin paginar. |
| PATCH | `/accounts/{account_id}/tasks/{task_id}` | miembro del negocio o admin | Cambia `done`. 404 si no existe. |

## Meta (`app/api/routes/meta.py`)

| Método | Path | Auth | Descripción |
|---|---|---|---|
| GET | `/meta/connect?account_id=` | miembro del negocio o admin | Devuelve `{"url": "..."}` con la URL de OAuth de Facebook (JSON, no redirect — ver [meta-integration.md](meta-integration.md)). |
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
| GET | `/admin/suggestions?page=&page_size=` | Sugerencias de todos los negocios, paginadas, más reciente primero, con negocio y datos de quien la envió. |
| PATCH | `/admin/accounts/{account_id}` | Edita cualquier negocio. |
| GET | `/admin/accounts/{account_id}/entitlement` | Historial completo de entitlements del negocio. |
| POST | `/admin/accounts/{account_id}/entitlement` | Crea/asigna un nuevo entitlement (nuevo plan, reactivación). |
| PATCH | `/admin/entitlements/{entitlement_id}` | Revoca/cambia status de un entitlement existente. |

## Dashboard (`app/api/routes/dashboard.py`)

| Método | Path | Auth | Descripción |
|---|---|---|---|
| GET | `/dashboard/{account_id}/insights` | miembro del negocio o admin + `check_entitlement` | Insights de IG: followers, impressions (día en curso), y reach de los últimos dos días *cerrados* (`reach_yesterday`, `reach_two_days_ago` — nunca el día en curso, ver [frontend-integration.md](frontend-integration.md)). 404 si no hay conexión Meta activa; 502 si la Graph API falla. |
| GET | `/dashboard/{account_id}/posting-status` | miembro del negocio o admin + `check_entitlement` | Fecha del último post y días transcurridos. `null`/`null` si nunca publicó (no es error). Mismos 404/502 que `/insights`. |
| GET | `/dashboard/{account_id}/unanswered-conversations?limit=` | miembro del negocio o admin + `check_entitlement` | Conversaciones de IG esperando respuesta nuestra, con `conversation_id` estable (usar como `Task.conversation_ref`). `limit` default 2, máx 50; timeout propio de 60s. **No verificado contra una cuenta real** — ver [frontend-integration.md](frontend-integration.md). |

## Misceláneo

| Método | Path | Descripción |
|---|---|---|
| GET | `/health` | Liveness check simple, sin auth. |
