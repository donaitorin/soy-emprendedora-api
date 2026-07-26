# Guía de integración para el frontend

Documento autocontenido con todo lo que un frontend (o un agente que lo construya)
necesita para consumir esta API: autenticación, modelo de roles, y el contrato exacto
(request/response) de cada endpoint que existe hoy. No asume que quien lo lea tiene
acceso al código del backend.

Fuente de verdad viva: `GET /docs` (Swagger UI) y `GET /openapi.json` sobre la API
corriendo. Este documento es un snapshot legible pensado para pegarse como contexto.

## Base URL y arranque

- Local (Docker): `http://localhost:8000`
- Todas las rutas devuelven JSON. No hay versionado de API todavía (no hay prefijo `/v1`).
- CORS está limitado al origen configurado en `FRONTEND_URL` (variable de entorno del
  backend) — si el frontend corre en otro puerto/dominio, hay que pedir que se actualice
  esa variable en el backend.

## Autenticación

- Esquema: **Bearer token** en el header `Authorization: Bearer <access_token>`. No se
  usan cookies.
- El token se obtiene de `POST /auth/register` o `POST /auth/login` (campo
  `access_token` en la respuesta).
- Formato: JWT (HS256), con expiración configurable en el backend (default 24h). No hay
  refresh token — cuando expira, el frontend debe volver a pedir login. Un 401 en
  cualquier endpoint (salvo `/auth/register` y `/auth/login`) significa "token ausente,
  inválido o expirado" → redirigir a login.
- No existe logout server-side (no hay blacklist de tokens): "cerrar sesión" es
  simplemente que el frontend borre el token guardado.

## Modelo de roles (clave para condicionar la UI)

Hay **dos roles independientes**, no confundirlos:

1. **Rol de plataforma** (`role` en el usuario, campo `role` de `GET /auth/me`):
   `"admin"` | `"user"`. Un usuario `admin` puede ver/editar cualquier negocio, usuario
   o entitlement vía las rutas `/admin/*`. Un `user` normal nunca ve esas rutas en su UI.
2. **Rol dentro de un negocio** (`my_role` en cada objeto de `accounts` dentro de
   `GET /auth/me`, o de `GET /accounts/me`): `"owner"` | `"collaborator"`. Determina si
   el frontend debe mostrar acciones de gestión (editar negocio, agregar/quitar
   colaboradores) para ese negocio puntual.

Un usuario puede pertenecer a varios negocios (el array `accounts` puede tener más de
un elemento), aunque hoy el flujo de registro solo le crea uno propio.

## Convenciones de error

Todos los errores devuelven `{"detail": "<mensaje>"}` con estos códigos:

| Código | Significado |
|---|---|
| 400 | Input inválido no cubierto por validación de schema (ej. `state` de OAuth corrupto) |
| 401 | No autenticado / token inválido o expirado / credenciales incorrectas en login |
| 403 | Autenticado pero sin permiso (no es miembro del negocio, no es owner, no es admin) |
| 404 | Recurso no encontrado (negocio, usuario, entitlement, conexión Meta inexistente) |
| 409 | Conflicto de negocio (email ya registrado, ya es miembro, único owner) |
| 422 | Error de validación de Pydantic (body/query mal formado) — devuelve `{"detail": [...]}` con detalle por campo, formato estándar de FastAPI |
| 502 | La API externa de Meta falló al pedir insights |

## Endpoints

### Auth

#### `POST /auth/register`
Sin auth. Crea usuario + su propio negocio (`owner`) + entitlement inicial `free/active`.

Request:
```json
{ "email": "ana@example.com", "password": "supersecreta123", "first_name": "Ana", "last_name": "Pérez" }
```
`password` mínimo 8 caracteres.

Response `201`:
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```
Errores: `409` si el email ya existe. `422` si falta un campo o el password es corto.

#### `POST /auth/login`
Sin auth.

Request:
```json
{ "email": "ana@example.com", "password": "supersecreta123" }
```
Response `200`: igual forma que register (`access_token`, `token_type`).
Errores: `401` si email/password no matchean o el usuario está inactivo.

#### `GET /auth/me`
Requiere Bearer. Usuario autenticado + sus negocios.

Response `200`:
```json
{
  "id": "uuid",
  "email": "ana@example.com",
  "first_name": "Ana",
  "last_name": "Pérez",
  "role": "user",
  "is_active": true,
  "created_at": "2026-07-25T19:29:53.237101Z",
  "accounts": [
    { "id": "uuid", "name": "Ana Pérez", "created_at": "2026-07-25T19:29:53.237101Z", "my_role": "owner" }
  ]
}
```

### Accounts (negocios)

#### `GET /accounts/me`
Requiere Bearer. Devuelve `list[AccountWithRole]` — misma forma que el array `accounts`
de `/auth/me`, sin el resto de datos del usuario. Útil para un selector de negocio si el
usuario tiene más de uno.

#### `GET /accounts/{account_id}`
Requiere ser miembro del negocio (cualquier rol) o admin de plataforma.

Response `200`:
```json
{ "id": "uuid", "name": "Ana Pérez", "created_at": "2026-07-25T19:29:53.237101Z" }
```
Errores: `403` si no es miembro, `404` si el negocio no existe.

#### `PATCH /accounts/{account_id}`
Requiere ser `owner` del negocio o admin.

Request (todos los campos opcionales, hoy solo hay uno):
```json
{ "name": "Nuevo nombre del negocio" }
```
Response `200`: mismo shape que `GET /accounts/{account_id}`.

#### `GET /accounts/{account_id}/members`
Requiere ser miembro del negocio o admin.

Response `200`, `list[MemberRead]`:
```json
[
  { "user_id": "uuid", "email": "ana@example.com", "first_name": "Ana", "last_name": "Pérez", "role": "owner", "created_at": "..." },
  { "user_id": "uuid", "email": "colaborador@example.com", "first_name": "Pendiente", "last_name": "Pendiente", "role": "collaborator", "created_at": "..." }
]
```
Nota: si el colaborador fue agregado por email sin tener cuenta previa, `first_name`/
`last_name` quedan como `"Pendiente"` (ver sección "Limitaciones conocidas" abajo).

#### `POST /accounts/{account_id}/members`
Requiere ser `owner` del negocio o admin. Agrega un colaborador por email.

Request:
```json
{ "email": "colaborador@example.com" }
```
Response `201`, un `MemberRead` (ver arriba) con `role: "collaborator"`.
Errores: `409` si ese email ya es miembro de este negocio.

#### `DELETE /accounts/{account_id}/members/{user_id}`
Requiere ser `owner` del negocio o admin. Sin body. Response `204` sin contenido.
Errores: `404` si no es miembro, `409` si `user_id` es el único `owner` del negocio
(no se puede quitar).

### Meta / Instagram (conexión OAuth)

#### `GET /meta/connect?account_id=<uuid>`
Requiere Bearer + ser miembro del negocio o admin.

Response `200`:
```json
{ "url": "https://www.facebook.com/v21.0/dialog/oauth?client_id=...&state=...&scope=..." }
```
Devuelve la URL como JSON (no un redirect 302 directo) **a propósito**: esta ruta exige
Bearer token, que una navegación de página completa del browser no puede enviar. El
frontend debe:
1. Llamar este endpoint con `fetch` (con el header `Authorization`).
2. Con la respuesta, navegar el browser él mismo: `window.location.href = data.url`.

#### `GET /meta/callback?code=&state=`
Facebook redirige acá directamente (no lo llama el frontend). Sin auth propia (se valida
con el `state` firmado que generó `/meta/connect`). El backend debe estar configurado
para que esta URL sea accesible; después de procesar, típicamente conviene que el
frontend tenga una página en `META_REDIRECT_URI` que lea la respuesta y continúe el flujo
(hoy este endpoint responde JSON directamente en vez de redirigir de vuelta al frontend —
ver nota en "Limitaciones conocidas").

Response `200`:
```json
{ "account_id": "uuid", "pages": [], "requires_selection": false }
```
o, si el negocio tiene varias Páginas de Facebook disponibles:
```json
{
  "account_id": "uuid",
  "requires_selection": true,
  "pages": [
    { "fb_page_id": "123", "page_name": "Mi Negocio", "ig_business_id": "456", "ig_username": "minegocio" },
    { "fb_page_id": "789", "page_name": "Otra Página", "ig_business_id": null, "ig_username": null }
  ]
}
```
Si `requires_selection: true`, el frontend debe mostrar esta lista y dejar elegir una,
llamando después a `/meta/select-page`.

#### `POST /meta/select-page`
Requiere Bearer + ser miembro del negocio o admin. Solo se usa cuando el callback anterior
devolvió `requires_selection: true`.

Request:
```json
{ "account_id": "uuid", "fb_page_id": "123" }
```
Response `200`: un `MetaConnectionStatus` (ver `/meta/status` abajo).

#### `GET /meta/status?account_id=<uuid>`
Requiere Bearer + ser miembro del negocio o admin. Nunca expone tokens.

Response `200` (sin conexión):
```json
{ "connected": false, "fb_page_id": null, "ig_business_id": null, "page_name": null, "ig_username": null, "token_expires_at": null, "is_primary": null }
```
Response `200` (con conexión):
```json
{ "connected": true, "fb_page_id": "123", "ig_business_id": "456", "page_name": "Mi Negocio", "ig_username": "minegocio", "token_expires_at": null, "is_primary": true }
```

#### `DELETE /meta/disconnect?account_id=<uuid>`
Requiere Bearer + ser miembro del negocio o admin. Response `204` sin contenido.

### Dashboard

#### `GET /dashboard/{account_id}/insights`
Requiere Bearer + ser miembro del negocio o admin.

Response `200`:
```json
{ "ig_business_id": "456", "ig_username": "minegocio", "followers_count": 1200, "impressions": 340, "reach": 290 }
```
Cualquier campo de métricas puede venir `null` si la Graph API no lo devuelve.
Errores: `404` si el negocio no tiene conexión Meta activa (mostrar CTA para conectar
Instagram); `502` si la Graph API de Meta falla (mostrar estado de error transitorio,
reintentable).

### Admin (solo `role: "admin"` de plataforma — ocultar toda esta sección si `role !== "admin"`)

#### `GET /admin/users?role=&is_active=`
Query params opcionales: `role` (`admin`|`user`), `is_active` (`true`|`false`).
Response `200`, `list[UserRead]`:
```json
[{ "id": "uuid", "email": "...", "first_name": "...", "last_name": "...", "role": "user", "is_active": true, "created_at": "..." }]
```

#### `PATCH /admin/users/{user_id}`
Request (todos opcionales):
```json
{ "first_name": "...", "last_name": "...", "role": "admin", "is_active": false }
```
Response `200`: un `UserRead`.

#### `GET /admin/accounts`
Response `200`, `list[AccountRead]` (mismo shape que `GET /accounts/{id}`).

#### `PATCH /admin/accounts/{account_id}`
Igual que `PATCH /accounts/{account_id}` pero sin restricción de ownership.

#### `GET /admin/accounts/{account_id}/entitlement`
Response `200`, `list[EntitlementRead]` — historial completo, más reciente primero:
```json
[{ "id": "uuid", "account_id": "uuid", "plan": "free", "status": "active", "source": "manual", "external_ref": null, "current_period_end": null, "created_at": "...", "updated_at": "..." }]
```
`status` es uno de: `"active" | "trialing" | "past_due" | "canceled" | "revoked"`.

#### `POST /admin/accounts/{account_id}/entitlement`
Crea un entitlement nuevo (no reemplaza el anterior, queda como historial).

Request:
```json
{ "plan": "pro", "status": "active", "source": "manual", "external_ref": null, "current_period_end": null }
```
Solo `plan` es obligatorio; el resto tiene defaults (`status: active`, `source: manual`).
Response `201`: un `EntitlementRead`.

#### `PATCH /admin/entitlements/{entitlement_id}`
Request (todos opcionales):
```json
{ "status": "revoked", "plan": "free", "current_period_end": null }
```
Response `200`: un `EntitlementRead`.

### Misceláneo

#### `GET /health`
Sin auth. `{"status": "ok"}`. Útil para chequeo de disponibilidad del backend desde el
frontend (splash screen, banner de "backend caído").

## Enums (valores exactos que viajan en JSON)

- Rol de plataforma (`UserRead.role`): `"admin"`, `"user"`
- Rol de negocio (`MemberRead.role`, `AccountWithRole.my_role`): `"owner"`, `"collaborator"`
- Status de entitlement (`EntitlementRead.status`): `"active"`, `"trialing"`, `"past_due"`, `"canceled"`, `"revoked"`

## Limitaciones conocidas a tener en cuenta en el diseño del frontend

- **Entitlements no se validan todavía**: cualquier usuario autenticado con acceso al
  negocio puede usar `/dashboard/*` sin importar su plan — no hay pantallas de
  "actualizá tu plan" bloqueando funcionalidad aún, aunque el dato de `plan`/`status` ya
  está disponible si se quiere mostrar informativamente.
- **Invitación de colaboradores es un stub**: `POST /accounts/{id}/members` con un email
  que no existe crea un usuario con contraseña aleatoria que nadie conoce — hoy no hay
  forma de que ese colaborador nuevo inicie sesión. No construir un flujo de "olvidé mi
  contraseña" contra esto todavía; hay que esperar a que el backend implemente
  invitación real por email.
- **`/meta/callback` no redirige al frontend**: responde JSON directamente en vez de
  hacer un redirect final a una página del frontend. Si se necesita que el navegador
  termine en una URL del frontend después del OAuth, hay que coordinarlo con el equipo de
  backend (cambiar `META_REDIRECT_URI` a una ruta del frontend que llame a este endpoint
  vía fetch, en vez de que Meta pegue directo al backend).
- **Sin paginación**: `GET /admin/users`, `GET /admin/accounts`, listas de miembros, etc.
  devuelven todo sin paginar — con pocos datos hoy no importa, pero no asumir que
  seguirá así indefinidamente.
- **Sin rate limiting ni CSRF** implementados todavía a nivel de API.

## Ver también

Para contexto de por qué el backend está diseñado así (roles, modelo de datos,
extensiones pendientes): [architecture.md](architecture.md), [data-model.md](data-model.md),
[auth.md](auth.md), [meta-integration.md](meta-integration.md), [extension-points.md](extension-points.md).
