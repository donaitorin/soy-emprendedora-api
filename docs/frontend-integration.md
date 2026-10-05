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
{ "connected": false, "fb_page_id": null, "ig_business_id": null, "page_name": null, "ig_username": null, "profile_picture_url": null, "token_expires_at": null, "is_primary": null }
```
Response `200` (con conexión):
```json
{ "connected": true, "fb_page_id": "123", "ig_business_id": "456", "page_name": "Mi Negocio", "ig_username": "minegocio", "profile_picture_url": "https://scontent.xx.fbcdn.net/...", "token_expires_at": null, "is_primary": true }
```
`profile_picture_url` es la foto de perfil de la cuenta de Instagram conectada (o de la
Página de Facebook si el negocio no tiene IG vinculado). Puede venir `null` aunque
`connected: true` — no solo cuando no hay conexión, sino también si Meta no pudo
responder la imagen en ese momento (token vencido, rate limit, etc.); usá siempre un
fallback visual (inicial del nombre) para ese caso, no asumas que `connected: true`
implica que la imagen está disponible.

#### `DELETE /meta/disconnect?account_id=<uuid>`
Requiere Bearer + ser miembro del negocio o admin. Response `204` sin contenido.

### Dashboard

#### `GET /dashboard/{account_id}/insights`
Requiere Bearer + ser miembro del negocio o admin.

Response `200`:
```json
{ "ig_business_id": "456", "ig_username": "minegocio", "followers_count": 1200, "impressions": 340, "reach_yesterday": 107, "reach_two_days_ago": 130 }
```
Cualquier campo de métricas puede venir `null` si la Graph API no lo devuelve.
Errores: `404` si el negocio no tiene conexión Meta activa (mostrar CTA para conectar
Instagram); `502` si la Graph API de Meta falla (mostrar estado de error transitorio,
reintentable).

**No hay campo de `reach` del día en curso, a propósito.** El reach de Meta se va
acumulando durante el día del lado de ellos, así que "el reach de hoy" viene `null` o
engañosamente bajo la mayor parte del día — no es un bug, es que la métrica todavía no
está consolidada. Por eso la tarjeta de "Alcance" compara los **últimos dos días ya
cerrados**:
- `reach_yesterday`: reach de ayer (día ya cerrado) — el número grande de la tarjeta.
- `reach_two_days_ago`: reach de antesdeayer — solo como base de comparación.

Ambos usan `since`/`until` fijados explícitamente a un día calendario exacto en UTC, no
una ventana default de Meta (sin esto, la Graph API cae en un rango no documentado —
confirmado como problema real en un proyecto anterior, ver `docs/AUTH_FLOW_REFERENCE.md`).
Para la variación (`↑15%`/`↓8%`), calcular `(reach_yesterday - reach_two_days_ago) /
reach_two_days_ago` del lado del cliente — el backend no manda el porcentaje ni el
signo. Cualquiera de los dos puede venir `null` si Meta no tiene dato para ese día (ej.
cuenta recién conectada).

`impressions` sigue leyendo la ventana del día en curso (no cambió) — probablemente
tenga el mismo problema de "no consolidado todavía" que tenía `reach`, pero como no lo
consume ninguna pantalla todavía, se dejó así por ahora. Tenerlo en cuenta para cuando
se implemente `/dashboard/audience`.

#### `GET /dashboard/{account_id}/posting-status`
Para el aviso de "Llevás X días sin publicar". Mismos requisitos y errores que
`/insights` (`404` sin conexión activa, `502` si la Graph API falla).

Response `200`:
```json
{ "last_post_at": "2026-07-28T14:00:00Z", "days_since_last_post": 2 }
```
Si la cuenta nunca publicó nada, ambos campos vienen `null` — es un estado válido
("todavía no publicaste"), no un error ni un 404 (eso queda reservado para "no hay
conexión").

#### `GET /dashboard/{account_id}/unanswered-conversations?limit=`
Para el aviso de "Fulana y Mengana llevan +48h sin respuesta". Mismos requisitos y
errores que `/insights`.

`limit` (query param opcional, default `2`, máximo `50`): cuántas conversaciones recientes
escanea/devuelve como máximo. **Está en `2` a propósito mientras se valida este endpoint
contra una cuenta real** — ver nota abajo.

Response `200`:
```json
[
  { "conversation_id": "17841400000000000_1234567890", "contact_name": "Laura", "hours_since_last_message": 50 },
  { "conversation_id": "17841400000000000_9876543210", "contact_name": "Carmen", "hours_since_last_message": 76 }
]
```
Lista vacía si no hay ninguna conversación esperando respuesta (dentro de las `limit`
escaneadas — no es un barrido de *todas* las conversaciones del negocio, ver nota).
`contact_name` sale de `username` (preferido) o `name` del participante que no es la
propia Página/cuenta de IG; si no hay ninguno de los dos, cae al `id` crudo del
participante como último recurso. `conversation_id` es el `id` de la conversación tal
cual lo devuelve la Graph API — úsalo como `conversation_ref` al crear una tarea desde
esta sugerencia (ver sección "Tareas"), nunca `contact_name`, porque dos contactos
distintos pueden compartir el mismo nombre visible.

**Puede tardar hasta 60 segundos.** El edge `/{page-id}/conversations` de Meta es
notablemente lento mientras la app está en Development Mode — mucho más que el resto de
la Graph API — así que este endpoint tiene un timeout propio de 60s en el backend (el
resto usa 10s). Mostrar un loading state acorde en el frontend, no asumir la latencia
rápida del resto del dashboard. Pasado ese minuto sin respuesta, el backend devuelve
`502` en vez de colgarse.

**⚠️ No probado contra una cuenta de Instagram real todavía** (no hay forma de validarlo
sin credenciales reales de Meta en este entorno) — a diferencia del resto de la API, este
endpoint puntual está implementado siguiendo la forma documentada de la Graph API pero
sin una llamada real de punta a punta. Antes de depender de él en producción, probarlo
con una cuenta con conversaciones reales y avisar si `contact_name` termina saliendo de
un campo distinto al esperado, o si la forma de la respuesta de
`/{page-id}/conversations` no coincide con lo asumido acá.

### Dinero (ingresos y gastos)

Requiere Bearer + ser miembro del negocio (`owner` o `collaborator`) o admin — a
diferencia de editar el negocio o gestionar miembros, cargar movimientos de dinero no
requiere ser `owner`.

Internamente ambos recursos viven en una sola tabla con un campo `type` interno
(no expuesto en las respuestas), por eso comparten formato de error y paginación, pero
cada uno tiene su propio shape de request/response.

#### `POST /accounts/{account_id}/incomes`
Registra un ingreso.

Request:
```json
{ "amount": 15000.50, "occurred_on": "2026-07-15", "source": "mentoria", "payment_method": "transferencia" }
```
- `amount`: número > 0.
- `occurred_on`: fecha (`YYYY-MM-DD`) en que ocurrió el ingreso — no es necesariamente hoy (carga tardía).
- `source`: uno de `"mentoria" | "comunidad" | "claridad" | "producto" | "otro"`.
- `payment_method`: uno de `"transferencia" | "stripe" | "mercadopago" | "paypal" | "efectivo"`.

Response `201`:
```json
{ "id": "uuid", "account_id": "uuid", "amount": 15000.50, "occurred_on": "2026-07-15", "source": "mentoria", "payment_method": "transferencia", "created_at": "2026-07-29T10:00:00Z" }
```
Errores: `404` si el negocio no existe, `422` si falta un campo o el valor de un enum no es válido.

#### `GET /accounts/{account_id}/incomes?from=&to=`
Lista de ingresos del negocio, más reciente primero por `occurred_on` (no por
`created_at`). `from`/`to` son fechas opcionales (`YYYY-MM-DD`) que filtran por
`occurred_on`, inclusive. Sin agregados todavía (totales, breakdown por fuente) — esto
es la lista cruda, para calcular eso en el frontend por ahora.

Response `200`: `list` del mismo shape que la respuesta de `POST /incomes`.

#### `POST /accounts/{account_id}/expenses`
Registra un gasto.

Request:
```json
{ "amount": 4000, "occurred_on": "2026-07-10", "category": "herramientas" }
```
- `amount`: número > 0.
- `occurred_on`: fecha (`YYYY-MM-DD`) en que ocurrió el gasto.
- `category`: uno de `"herramientas" | "publicidad" | "educacion" | "servicios" | "otro"`.

Response `201`:
```json
{ "id": "uuid", "account_id": "uuid", "amount": 4000, "occurred_on": "2026-07-10", "category": "herramientas", "created_at": "2026-07-29T10:00:00Z" }
```
Errores: igual que `POST /incomes`.

#### `GET /accounts/{account_id}/expenses?from=&to=`
Igual que `GET /incomes`, pero para gastos: más reciente primero por `occurred_on`,
mismos filtros `from`/`to` opcionales.

Response `200`: `list` del mismo shape que la respuesta de `POST /expenses`.

#### `GET /accounts/{account_id}/movements?page=&page_size=&from=&to=&type=`
Vista combinada de ingresos y gastos, paginada — pensada para una tabla mixta (no
reemplaza `/incomes` ni `/expenses`, que siguen sin paginar para tarjetas/gráficos).

Query params, todos opcionales: `page` (default `1`), `page_size` (default `20`, máximo
`100`), `from`/`to` (fecha, filtran por `occurred_on`), `type` (`"income"` | `"expense"`,
para filtrar por tipo si hace falta).

Response `200`:
```json
{
  "items": [
    { "id": "uuid", "account_id": "uuid", "type": "income", "amount": 800.0, "occurred_on": "2026-07-29", "created_at": "2026-07-29T10:00:00Z", "source": "mentoria", "payment_method": "transferencia", "category": null },
    { "id": "uuid", "account_id": "uuid", "type": "expense", "amount": 500.0, "occurred_on": "2026-07-29", "created_at": "2026-07-29T09:00:00Z", "source": null, "payment_method": null, "category": "servicios" }
  ],
  "page": 1,
  "page_size": 20,
  "total": 57,
  "total_pages": 3
}
```
Cada item trae **todos** los campos de ambos tipos, con `null` en los que no aplican
según `type` — mismo criterio que `MetaConnectionStatus`. Orden: más reciente primero
por `occurred_on`, `created_at` como desempate. `total_pages` es `0` si `total` es `0`.

Esta es la primera ruta paginada de la API (antes no había ninguna — ver
"Limitaciones conocidas" más abajo, que ya no aplica a este endpoint puntual).

#### `DELETE /accounts/{account_id}/movements/{movement_id}`
Borra (soft-delete) un ingreso o gasto ya cargado. Un movimiento borrado deja de
aparecer en este endpoint, en `/incomes` y en `/expenses` — no se puede deshacer todavía.

Response `204` sin contenido. Errores: `404` si `movement_id` no existe en ese negocio
o si ya estaba borrado.

**Fuera de alcance todavía**: edición de movimientos existentes, restaurar un borrado,
exportar (CSV, etc.), endpoints de agregados (total del día/mes, breakdown por fuente o
categoría, histórico), y la "meta del mes" (objetivo mensual configurable) — todo eso
queda para un pedido posterior sobre este mismo modelo.

### Leads (tablero kanban)

Requiere Bearer + ser miembro del negocio (`owner` o `collaborator`) o admin en los 8
endpoints — igual que Dinero, no hace falta ser `owner`.

**Dos estados independientes a no confundir:**
- `archived` (bool): un lead archivado sale del tablero pero **sigue contando para las
  métricas** (`/leads/stats`) y sigue apareciendo en la tabla paginada (`/leads`).
- Soft delete (`deleted_at`, no expuesto en la respuesta): un lead borrado desaparece de
  **todo** — tablero, tabla paginada y métricas.

**Decisión de diseño sobre `converted_at`:** si un lead que ya estaba en `stage:
"convertida"` se mueve (drag and drop) a cualquier otra etapa, `converted_at` se limpia
(vuelve a `null`). Si más adelante vuelve a `"convertida"`, `converted_at` se completa de
nuevo con la fecha de ese momento — no la original. No asumir que `converted_at`, una vez
seteado, se mantiene para siempre.

#### `POST /accounts/{account_id}/leads`
Crea un lead. Siempre nace en `stage: "nuevo"` — no se manda `stage` en el request.

Request:
```json
{ "name": "María", "channel": "instagram" }
```
`channel`: uno de `"instagram" | "whatsapp" | "referido" | "web" | "otro"`.

Response `201`, un `LeadRead` completo:
```json
{
  "id": "uuid",
  "account_id": "uuid",
  "name": "María",
  "channel": "instagram",
  "stage": "nuevo",
  "stage_changed_at": "2026-07-30T10:00:00Z",
  "converted_at": null,
  "archived": false,
  "archive_reason": null,
  "archived_at": null,
  "created_at": "2026-07-30T10:00:00Z"
}
```

#### `GET /accounts/{account_id}/leads/board`
Sin paginar. Solo leads activos (`archived: false`, sin soft delete) — es la data cruda
para las columnas del tablero; agrupar por `stage` del lado del cliente. Orden: más
reciente primero por `created_at`.

Response `200`: `list[LeadRead]` (mismo shape que arriba).

#### `PATCH /accounts/{account_id}/leads/{lead_id}/stage`
Mueve un lead a otra etapa — esto es lo que dispara el drag and drop. Sin restricción de
orden: se puede mover para adelante, para atrás, o saltear columnas.

Request:
```json
{ "stage": "conversacion" }
```
`stage`: uno de `"nuevo" | "conversacion" | "propuesta" | "agendada" | "convertida"`.

Efecto: actualiza `stage_changed_at` a ahora. Si `stage` pasa a `"convertida"` y
`converted_at` era `null`, lo completa. Si pasa a cualquier otra etapa, limpia
`converted_at` (ver nota de diseño arriba).

Response `200`: `LeadRead` actualizado.
Errores: `404` si el lead no existe, está archivado, o tiene soft delete — no se puede
mover algo que no está en el tablero.

#### `POST /accounts/{account_id}/leads/{lead_id}/archive`
Archiva un lead individual (botón por card, fuera de la columna `convertida`).

Request:
```json
{ "reason": "not_converted" }
```
`reason`: uno de `"converted" | "not_converted"`.

Efecto: `archived: true`, `archive_reason` = lo recibido, `archived_at` = ahora. El
`stage` no cambia.

Response `200`: `LeadRead` actualizado.
Errores: `404` si no existe, ya está archivado o tiene soft delete. `422` si `reason` no
es un valor válido.

#### `POST /accounts/{account_id}/leads/archive-converted`
Botón "Archivar convertidos": archiva de una **todos** los leads activos que están en
`stage: "convertida"`, con `archive_reason: "converted"` forzado del lado del servidor
(no hace falta mandar nada en el body). Atómico — evita loopear `POST .../archive` una
vez por card desde el frontend.

Response `200`: `list[LeadRead]` — todos los leads que quedaron archivados por esta
llamada (lista vacía si no había ninguno en `"convertida"`).

#### `DELETE /accounts/{account_id}/leads/{lead_id}`
Soft-delete — mismo patrón que `DELETE /accounts/{account_id}/movements/{movement_id}`.
Funciona tanto sobre un lead activo como uno ya archivado.

Response `204` sin contenido.
Errores: `404` si no existe o ya estaba borrado.

#### `GET /accounts/{account_id}/leads?page=&page_size=&stage=&archived=&archive_reason=&created_from=&created_to=`
Tabla paginada con todos los leads (activos y archivados, nunca soft-deleted) — mismo
shape de paginación que `GET /accounts/{account_id}/movements`.

Query params, todos opcionales: `page` (default `1`), `page_size` (default `20`, máximo
`100`), `stage` (filtra por etapa exacta), `archived` (`true`/`false` — sin este filtro
trae activos y archivados juntos), `archive_reason` (`"converted"` | `"not_converted"`),
`created_from`/`created_to` (fecha `YYYY-MM-DD`, filtran por la fecha de `created_at`,
inclusive — mismo criterio que `from`/`to` en `/incomes` y `/expenses`). Un lead que se
archivó después sigue contando en el día en que se creó — este filtro no distingue
estado actual, solo fecha de creación.

Response `200`:
```json
{
  "items": [ { "...": "LeadRead" } ],
  "page": 1,
  "page_size": 20,
  "total": 34,
  "total_pages": 2
}
```
Orden: más reciente primero por `created_at`.

#### `GET /accounts/{account_id}/leads/stats`
Métricas para las tarjetas de arriba del tablero.

Response `200`:
```json
{ "active_count": 8, "conversion_rate": 0.25, "avg_conversion_days": 4.2 }
```
- `active_count`: cantidad de leads con `archived: false` (sin soft-deleted), sin
  importar en qué columna están.
- `conversion_rate`: `convertidos / (convertidos + no_convertidos)`, como fracción
  `0..1` (multiplicar por 100 en el frontend para el %). `convertidos` = archivados con
  `archive_reason: "converted"` **más** activos que están en `stage: "convertida"`
  todavía sin archivar. `no_convertidos` = archivados con `archive_reason:
  "not_converted"`. Los leads activos en las otras 4 columnas no entran en esta cuenta.
  `null` si el denominador da `0` (todavía no hay ningún convertido ni no convertido).
- `avg_conversion_days`: promedio en días de `(converted_at - created_at)` sobre el
  mismo conjunto de "convertidos" de arriba. `null` si ese conjunto está vacío.

**Fuera de alcance todavía**: editar campos de un lead ya creado (nombre, canal),
restaurar un soft-delete o des-archivar uno archivado, notas/comentarios, asignación a
colaboradores, recordatorios.

### Tareas

Requiere Bearer + ser miembro del negocio (`owner` o `collaborator`) o admin, igual que
Dinero y Leads.

El mismo modal de "Agregar tarea" se usa en dos lugares: el botón directo de
`/dashboard/actions` (campos en blanco), y los botones "Crear tarea" de "Atención hoy"
en `/dashboard/home` (pre-cargado con título/notas/prioridad alta según la sugerencia).
La tarjeta "Tareas de hoy" del home y la lista de `/dashboard/actions` salen del mismo
`GET /accounts/{account_id}/tasks?date=` — no hay endpoint de resumen aparte.

**Sin dedup del lado del servidor**: si ya existe una tarea de hoy con
`suggestion_type: "posting_reminder"`, o con `suggestion_type: "unanswered_conversation"`
y el `conversation_ref` que corresponde a esa conversación puntual, el frontend es quien
decide no volver a ofrecer esa sugerencia — comparando contra la lista que ya trae de
`GET /tasks?date=`. El backend no valida ni bloquea nada de esto.

#### `POST /accounts/{account_id}/tasks`
Crea una tarea. Nace siempre en `done: false`.

Request:
```json
{ "title": "Publicar contenido hoy", "notes": "Llevás 2 días sin publicar", "priority": "alta", "suggestion_type": "posting_reminder", "conversation_ref": null }
```
- `title`: requerido.
- `notes`: opcional.
- `priority`: requerido, uno de `"alta" | "media" | "baja"`.
- `suggestion_type`: opcional (`null` si no se manda) — uno de `"posting_reminder" |
  "unanswered_conversation"`. `null` cuando la creó la usuaria manualmente.
- `conversation_ref`: opcional (`null` si no se manda). Solo tiene sentido cuando
  `suggestion_type` es `"unanswered_conversation"` — mandar ahí el `conversation_id` que
  devolvió `GET /dashboard/{account_id}/unanswered-conversations`, no `contact_name`. El
  backend lo guarda tal cual, sin validarlo contra la Graph API.

Response `201`, un `TaskRead` completo:
```json
{
  "id": "uuid",
  "account_id": "uuid",
  "title": "Publicar contenido hoy",
  "notes": "Llevás 2 días sin publicar",
  "priority": "alta",
  "done": false,
  "suggestion_type": "posting_reminder",
  "conversation_ref": null,
  "created_at": "2026-07-30T09:00:00Z"
}
```

#### `GET /accounts/{account_id}/tasks?date=`
Sin paginar (siempre son pocas). `date` (`YYYY-MM-DD`, opcional) filtra por la fecha de
`created_at`; si no se manda, el backend usa el día de hoy en UTC — pero mandalo siempre
explícito, calculado en el huso horario del browser, para no depender de qué "hoy"
asuma el servidor.

Response `200`: `list[TaskRead]`, más reciente primero por `created_at`. Agrupar por
`priority` del lado del cliente — no vienen ordenadas por eso.

#### `PATCH /accounts/{account_id}/tasks/{task_id}`
Cambia el estado de una tarea (el checkbox pendiente ⇄ completa).

Request:
```json
{ "done": true }
```
Response `200`: `TaskRead` actualizado. Errores: `404` si no existe.

**Fuera de alcance todavía**: editar `title`/`notes`/`priority` de una tarea ya creada,
borrarla, categorías (Dinero/Audiencia/Leads/Operaciones), deshacer/restaurar,
recordatorios, asignación a colaboradores, tareas con fecha futura (todas nacen "para
hoy").

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
- Fuente de ingreso (`IncomeRead.source`): `"mentoria"`, `"comunidad"`, `"claridad"`, `"producto"`, `"otro"`
- Método de pago (`IncomeRead.payment_method`): `"transferencia"`, `"stripe"`, `"mercadopago"`, `"paypal"`, `"efectivo"`
- Categoría de gasto (`ExpenseRead.category`): `"herramientas"`, `"publicidad"`, `"educacion"`, `"servicios"`, `"otro"`
- Tipo de movimiento (`MovementRead.type`, filtro `type` de `/movements`): `"income"`, `"expense"`
- Canal de lead (`LeadRead.channel`): `"instagram"`, `"whatsapp"`, `"referido"`, `"web"`, `"otro"`
- Etapa de lead (`LeadRead.stage`, filtro `stage` de `/leads`): `"nuevo"`, `"conversacion"`, `"propuesta"`, `"agendada"`, `"convertida"`
- Motivo de archivado (`LeadRead.archive_reason`): `"converted"`, `"not_converted"`
- Prioridad de tarea (`TaskRead.priority`): `"alta"`, `"media"`, `"baja"`
- Origen de tarea sugerida (`TaskRead.suggestion_type`): `"posting_reminder"`, `"unanswered_conversation"`

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
- **Paginación solo en `/movements` y `/leads`**: son las únicas rutas paginadas de la
  API (misma convención `page`/`page_size` en ambas). `GET /admin/users`,
  `GET /admin/accounts`, `/incomes`, `/expenses`, `/leads/board`, listas de miembros,
  etc. siguen devolviendo todo sin paginar — con pocos datos hoy no importa, pero no
  asumir que seguirá así indefinidamente.
- **Sin rate limiting ni CSRF** implementados todavía a nivel de API.

## Ver también

Para contexto de por qué el backend está diseñado así (roles, modelo de datos,
extensiones pendientes): [architecture.md](architecture.md), [data-model.md](data-model.md),
[auth.md](auth.md), [meta-integration.md](meta-integration.md), [extension-points.md](extension-points.md).
