# Integración con Meta (OAuth server-side)

Todo el código vive en `app/api/routes/meta.py` (endpoints) y
`app/services/meta_client.py` (llamadas HTTP a la Graph API vía `httpx` async). El
intercambio de `code` por `access_token` ocurre **siempre en el backend**, nunca en el
frontend.

## Flujo

1. **`GET /meta/connect?account_id=<uuid>`** (requiere `require_business_access`) —
   genera un `state` firmado (JWT corto, 10 min, `app/core/security.py::create_meta_oauth_state`)
   que codifica el `account_id`, y devuelve `{"url": "..."}` con la URL de OAuth de
   Facebook (`meta_client.build_oauth_url`) con los scopes de `META_OAUTH_SCOPES`.
   Devuelve JSON en vez de un redirect 302 directo **a propósito**: esta ruta exige
   Bearer token, que una navegación de página completa del browser no puede enviar —
   el frontend debe llamarla vía `fetch` (con el header `Authorization`) y recién
   ahí navegar él mismo (`window.location.href = data.url`).

2. **`GET /meta/callback?code=&state=`** — Facebook redirige acá tras la autorización.
   - Se decodifica y valida el `state` para recuperar el `account_id`
     (`decode_meta_oauth_state`). Si es inválido o expiró, 400.
   - Se intercambia `code` por un **user access token** server-to-server
     (`meta_client.exchange_code_for_token`).
   - Se listan las Páginas del usuario con `/me/accounts`, incluyendo la cuenta de IG
     Business vinculada si existe (`meta_client.get_user_pages`).
   - Si hay **una sola página**, se persiste la conexión directamente
     (`_persist_connection`) y se responde `requires_selection: false`.
   - Si hay **más de una**, se guardan en una cache en memoria por `account_id`
     (`_pending_page_selection`) y se responde la lista para que el frontend deje
     elegir, con `requires_selection: true`.

3. **`POST /meta/select-page`** (body: `account_id`, `fb_page_id`) — fija la página
   elegida como `is_primary`. Usa `ensure_business_access` (no
   `Depends(require_business_access)`, ver [auth.md](auth.md) para el porqué) porque
   `account_id` viene en el body.

4. **`GET /meta/status?account_id=`** — indica si hay conexión activa (página, IG
   asociado) **sin exponer el token**. Devuelve `MetaConnectionStatus`, que ni
   siquiera tiene un campo para el token.

5. **`DELETE /meta/disconnect?account_id=`** — desactiva (`is_primary = False`) la(s)
   conexión(es) activa(s) del negocio. No borra el historial.

Todas las rutas anteriores (salvo `/callback`, que no tiene el JWT propio disponible
porque es un redirect de Facebook) validan `require_business_access` sobre el
`account_id`.

## Persistencia y encriptación

`_persist_connection` en `meta.py`:
- Desactiva cualquier conexión previa `is_primary=True` del mismo `account_id`.
- Encripta el `access_token` de la página con Fernet (`encrypt_secret`,
  `FERNET_KEY`) antes de guardarlo en `meta_connections.access_token_encrypted`.
- El token se desencripta únicamente en el momento de llamar a la Graph API
  (`app/api/routes/dashboard.py::get_insights`), nunca para serializarlo en una
  respuesta.

## Cache de selección de página

`_pending_page_selection` es un diccionario en memoria (proceso único). Es
suficiente para el ciclo de vida corto de "elegir página tras el callback", pero **no
sobrevive un restart ni escala a múltiples workers/procesos** — si el proyecto crece
a correr con varios workers de uvicorn/gunicorn, esto necesita moverse a Redis o a una
tabla temporal en la DB.

## Insights del dashboard

`GET /dashboard/{account_id}/insights` (`app/api/routes/dashboard.py`):
1. `require_business_access` + `check_entitlement` (stub, ver [extension-points.md](extension-points.md)).
2. Busca la `meta_connection` primaria del negocio; 404 si no hay ninguna o no tiene
   `ig_business_id`.
3. Desencripta el token y llama `meta_client.get_ig_insights` (perfil + insights de
   `impressions`/`reach` a nivel `day`).
4. Mapeo de métricas deliberadamente simple/genérico
   (`followers_count`, `impressions`, `reach`) — pensado para expandirse.

## Configurar la app de Meta for Developers

Ver la sección correspondiente en [el README](../README.md#configurar-la-app-de-meta-for-developers-para-probar-el-oauth-en-local).
