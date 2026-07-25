# Puntos de extensión (a propósito no implementados)

Estas tres cosas están explícitamente fuera del alcance de esta primera versión, pero
el código ya está estructurado para que activarlas más adelante sea acotado. No las
implementes "de paso" al tocar código cercano sin que el usuario lo pida explícitamente.

## 1. Invitación de colaboradores por email

`POST /accounts/{account_id}/members` (`app/api/routes/accounts.py::add_member`): si el
email no corresponde a un usuario existente, hoy se crea el `User` con una contraseña
temporal aleatoria (`secrets.token_urlsafe(16)`) que **no se comunica a nadie** — queda
un `# TODO: reemplazar por flujo de invitación por email` en el código, justo en ese
bloque. Para activarlo: reemplazar la generación de password temporal por un flujo de
invitación (token de invitación + endpoint para que el usuario setee su propia
contraseña + envío de email), sin cambiar la firma del endpoint.

## 2. Pasarela de pagos / facturación real

`entitlements.source` ya contempla valores como `stripe` además de `manual`/`promo`, y
`external_ref` existe para guardar IDs de sistemas de pago futuros. Hoy todo
entitlement se crea con `source=manual` (el que se genera automáticamente en
`/auth/register`, o los que cree un admin vía `/admin/accounts/{account_id}/entitlement`).
Para integrar una pasarela: agregar un webhook que cree/actualice filas de
`entitlements` con `source` correspondiente, sin tocar el modelo de datos.

## 3. Validación estricta de entitlements

`app/api/deps.py::check_entitlement` — comentario explícito en el código:
`# TODO: activar validación real de entitlement cuando se integre facturación`.
Hoy la función consulta si existe un entitlement `active`/`trialing` vigente para el
`account_id`, pero **siempre retorna `True`** sin importar el resultado — acceso libre
para todos. Ya está conectada como dependencia de `GET /dashboard/{account_id}/insights`,
así que activar la restricción real (devolver el resultado de la consulta en vez de
`True` fijo, y que `deps.py` la traduzca en un 403 si no hay entitlement vigente) es un
cambio acotado a esa única función — ningún endpoint necesita tocarse.

## Otras limitaciones conocidas (no roadmap, solo para tenerlas presentes)

- `_pending_page_selection` en `app/api/routes/meta.py` es un dict en memoria de un
  solo proceso — no sobrevive restarts ni escala a múltiples workers. Ver
  [meta-integration.md](meta-integration.md#cache-de-selección-de-página).
- El mapeo de métricas de IG en `app/services/meta_client.py::get_ig_insights` es
  deliberadamente mínimo (`followers_count`, `impressions`, `reach`) — pensado para
  crecer, no para ser exhaustivo.
