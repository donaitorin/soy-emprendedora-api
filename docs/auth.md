# Autenticación y autorización

## Sesión propia

- Password hashing: `argon2-cffi` (`app/core/security.py::hash_password/verify_password`).
  Se eligió sobre `passlib[bcrypt]` porque `passlib` está sin mantenimiento desde 2020 y
  su self-test interno de bcrypt (`detect_wrap_bug`) rompe con versiones modernas del
  paquete `bcrypt` (≥4.1), que ahora validan estrictamente el límite de 72 bytes.
- JWT propio firmado con `PyJWT` (`create_access_token`/`decode_access_token`), secreto
  en `JWT_SECRET`, expiración en `JWT_EXPIRATION_MINUTES`. El `sub` del payload es el
  `user.id`.
- **Transporte:** Bearer token en el header `Authorization` (no cookie httpOnly) — así
  se evita configurar cookies cross-origin para un frontend en otro origen. Ver
  `app/api/deps.py::_bearer_scheme` (`HTTPBearer`).
- El `access_token` de Meta **nunca** viaja en ninguna respuesta de esta API — es un
  concepto totalmente separado del JWT propio (ver [meta-integration.md](meta-integration.md)).

## Endpoints

- `POST /auth/register` — crea `user` + `account` propio + `user_account(owner)` +
  `entitlement(free, active)`, devuelve JWT. Ver `app/api/routes/auth.py::register`.
- `POST /auth/login` — devuelve JWT.
- `GET /auth/me` — usuario autenticado + sus negocios con el rol en cada uno.

## Dependencias de autorización (`app/api/deps.py`)

Todas son funciones/dependencias de FastAPI reutilizables entre rutas:

| Dependencia | Qué valida |
|---|---|
| `get_current_user` | Decodifica el Bearer token, carga el `User`, falla con 401 si no existe/inactivo/token inválido. |
| `require_platform_admin` | `user.role == PlatformRole.ADMIN`, si no 403. Usado como dependencia de **router** completo en `app/api/routes/admin.py`. |
| `require_business_access` | Admin de plataforma, o tiene fila en `user_accounts` para el `account_id` (path o query param del mismo nombre en la ruta). 403 si no. |
| `require_business_owner` | Igual, pero exige `role == owner` en `user_accounts`. |
| `check_entitlement` | Ver más abajo — hoy siempre permite. |
| `ensure_business_access` | Misma lógica que `require_business_access` pero como función común, para rutas donde el `account_id` viene en el **body** (ej. `POST /meta/select-page`) y FastAPI no puede inyectarlo automáticamente en una dependencia. |

**Detalle importante para quien agregue rutas nuevas:** `require_business_access` y
`require_business_owner` funcionan porque FastAPI resuelve su parámetro `account_id`
contra un parámetro de **path o query** del mismo nombre declarado en la ruta. Si el
`account_id` que hay que validar viene dentro de un body Pydantic, hay que usar
`ensure_business_access` a mano dentro del handler (como en `meta.py::select_page`),
no `Depends(require_business_access)` — si no, FastAPI esperaría un query param
`account_id` separado que nunca llega.

## Entitlements: stub intencional

`check_entitlement` está estructurado para que activar la validación real de acceso
por plan/pago sea un cambio de una sola línea, sin tocar los endpoints que ya
dependen de él (ej. `GET /dashboard/{account_id}/insights`). Ver
[extension-points.md](extension-points.md).
