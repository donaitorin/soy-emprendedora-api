# Prompt para Claude Code — Frontend Next.js

Copia y pega todo lo siguiente en Claude Code, en el repo del frontend.

---

Quiero que construyas la primera versión del frontend de **Soy Emprendedora** en
**Next.js + Tailwind CSS**, que consume una API backend ya construida (FastAPI). El
proyecto de Next.js **ya fue inicializado con `npx create-next-app`** — antes de escribir
nada, revisá la estructura actual (App Router vs Pages Router, TypeScript o JS, si
Tailwind ya quedó configurado por el propio `create-next-app`) y seguí esas convenciones
en vez de asumir una estructura desde cero.

## Contrato de la API (backend)

El backend vive en otro repo (`soy-emprendedora-api`) y expone todo lo necesario para
esta v1 en `docs/frontend-integration.md` de ese repo — documento autocontenido con
autenticación, modelo de roles, y el contrato completo (request/response) de cada
endpoint. **Ese archivo no está disponible en este repo**: pegá/adjuntá su contenido
como contexto adicional al arrancar (o pedile a quien te dio este prompt que te lo
comparta) antes de implementar las llamadas a la API.

Puntos clave que ya sabemos y vas a necesitar sin esperar a leer ese documento:

- Auth: **Bearer token** en header `Authorization` (no cookies del lado del backend —
  el backend nunca setea cookies, el frontend decide cómo guardar el token).
- `POST /auth/register` y `POST /auth/login` devuelven `{ "access_token": "...", "token_type": "bearer" }`.
- `GET /auth/me` devuelve el usuario autenticado + `accounts: [{ id, name, created_at, my_role }]`.
  Hoy un usuario siempre tiene exactamente un negocio propio creado en el registro — usá
  `accounts[0].id` como `account_id` en el resto de las llamadas.
- `GET /meta/connect?account_id=` requiere Bearer y devuelve `{ "url": "..." }` (JSON,
  no un redirect directo — a propósito, porque esta ruta exige el header `Authorization`
  que una navegación de página completa del browser no puede enviar). El flujo correcto
  es: `fetch` con el header → tomar `data.url` → `window.location.href = data.url`.
- `GET /meta/callback?code=&state=` es a quien Facebook redirige después de que el
  usuario autoriza. Por eso la app de Meta for Developers debe tener configurado
  `META_REDIRECT_URI` apuntando a **una ruta de este frontend** (ej.
  `http://localhost:3000/meta/callback`), no directamente al backend — ver sección
  "Flujo de conexión con Meta" más abajo para el detalle de cómo implementar esa página.
- `GET /meta/status?account_id=` devuelve `{ "connected": bool, ... }` sin exponer tokens.
- `GET /dashboard/{account_id}/insights` devuelve `{ ig_business_id, ig_username,
  followers_count, impressions, reach }` (cualquier métrica puede venir `null`). 404 si
  el negocio no tiene conexión Meta activa, 502 si la Graph API de Meta falla.
- Todos los errores tienen forma `{ "detail": "..." }` (o `{"detail": [...]}` en 422).

## Estilo visual

Basá toda la paleta de colores (fondo, primario/acento, texto, bordes, estados) en el
archivo de referencia **`docs/Diseño del tablero/Inicio.dc.html`**, que está en la raíz
de este mismo repo de frontend. Leelo, extraé los colores que use (aunque estén como
estilos inline o en un `<style>` embebido), y armá el tema de Tailwind a partir de esos
valores (`tailwind.config.ts`, o tokens en `globals.css` si el proyecto usa Tailwind v4
con `@theme`). No inventes una paleta nueva ni uses los colores default de Tailwind.

## Variables de entorno

Todo lo que sea configuración de entorno (empezando por la URL de la API) tiene que salir
de variables de entorno, no hardcodeado:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Creá `.env.example` con esta variable documentada, y usá `NEXT_PUBLIC_API_URL` (con ese
prefijo, porque se necesita tanto en Server Components/middleware como en el browser)
en un único lugar centralizado (ej. `lib/api.ts` o similar) — el resto del código nunca
debe leer `process.env` directamente ni hardcodear la URL.

## Alcance funcional de esta primera versión (v1) — nada más que esto

No implementes gestión de colaboradores, panel de admin, entitlements/planes, ni nada
del resto de endpoints que describe `frontend-integration.md` — eso queda para después.
Esta v1 es únicamente:

### 1. `/login`
Formulario de email + password contra `POST /auth/login`. Al loguearse OK, guardá el
`access_token` (ver sección "Dónde guardar el token" abajo) y redirigí a la ruta de
entrada de la app (`/`, ver sección de guards). Tiene que haber un link visible a
`/register` ("¿No tenés cuenta? Registrate").

### 2. `/register`
Formulario de email + password + nombre + apellido contra `POST /auth/register`. Mismo
comportamiento post-registro que el login (ya devuelve el token, no hace falta loguear
de nuevo). Tiene que haber un link visible a `/login` ("¿Ya tenés cuenta? Iniciá sesión").

### 3. Guards de rutas (middleware)
- Si **no** hay sesión válida y se intenta entrar a cualquier ruta privada (todo lo que
  no sea `/login` o `/register`) → redirigir a `/login`.
- Si **hay** sesión válida y se intenta entrar a `/login` o `/register` → redirigir a la
  ruta de entrada de la app (`/`), no dejar volver a esas pantallas con el botón de atrás
  del browser tampoco (por eso el guard va en `middleware.ts`, que corre en cada request
  del lado del servidor antes de renderizar, no solo un chequeo en el cliente).
- Implementá esto con **Next.js Middleware** (`middleware.ts` en la raíz), leyendo el
  token de una cookie (ver siguiente sección) — un middleware no tiene acceso a
  `localStorage`, por eso el token tiene que vivir en una cookie para que este guard
  funcione en cada request.

### Dónde guardar el token
Guardá el `access_token` en una **cookie** (no `httpOnly` — la tiene que poder leer el
JS del cliente para mandarla como header `Authorization` en cada fetch, y el middleware
para el guard). Nombre sugerido: `session_token`. Encapsulá el get/set/clear de esta
cookie en un único módulo (ej. `lib/auth.ts`) — nada más del código debe tocar
`document.cookie` directamente.

Si cualquier llamada a la API devuelve `401`, tratalo como sesión inválida/expirada:
borrar la cookie y redirigir a `/login`.

### 4. Ruta de entrada `/` (decide a dónde mandar al usuario logueado)
Página privada (protegida por el guard) que, apenas carga:
1. Llama a `GET /auth/me` para confirmar que la sesión sigue viva y obtener el `account_id`.
2. Llama a `GET /meta/status?account_id=`.
3. Si `connected: false` → redirige a `/connect-meta`.
4. Si `connected: true` → redirige a `/dashboard`.

Podés mostrar un loader simple mientras se resuelve esto.

### 5. `/connect-meta`
Pantalla privada con **únicamente** un botón "Conectar con Meta" (y algo de texto breve
explicando qué va a pasar). Al hacer click:
1. `fetch` a `GET /meta/connect?account_id=` con el header `Authorization`.
2. Tomar `data.url` de la respuesta.
3. `window.location.href = data.url` (navegación completa del browser hacia Facebook —
   no uses `fetch` para esta segunda parte, tiene que ser una navegación real).

### Flujo de conexión con Meta (necesario para que el botón de arriba lleve a algún lado)
Facebook, al terminar el login/autorización, redirige el browser a la URL configurada
en `META_REDIRECT_URI` — que tiene que apuntar a una ruta de **este frontend**, ej.
`http://localhost:3000/meta/callback` (esto se configura como variable de entorno del
lado del **backend**, no acá; avisale a quien administra el backend que la actualice).

Implementá esa ruta (`/meta/callback`) así:
1. Leer `code` y `state` de los query params que manda Facebook.
2. Llamar (server-side o client-side, lo que sea más simple con la estructura del
   proyecto) a `GET {NEXT_PUBLIC_API_URL}/meta/callback?code=<code>&state=<state>` del
   backend, pasando los mismos valores.
3. Esa llamada devuelve `{ account_id, pages: [...], requires_selection: bool }`.
   - Si `requires_selection: false` → la conexión ya quedó guardada, redirigir a
     `/dashboard`.
   - Si `requires_selection: true` → mostrar la lista de `pages` para que el usuario
     elija una (nombre de página + usuario de IG si tiene), y al elegir, llamar
     `POST /meta/select-page` con `{ account_id, fb_page_id }` (requiere Bearer). Al
     terminar, redirigir a `/dashboard`.

Esta pantalla de callback no es una de las pantallas "de producto" que pediste, es la
pieza técnica que hace falta para que el flujo de conexión funcione de punta a punta —
mantenela simple (loader + manejo de la lista de páginas si aplica).

### 6. `/dashboard`
Pantalla privada. Al cargar, llama a `GET /dashboard/{account_id}/insights` y muestra
lo que devuelva: `followers_count`, `impressions`, `reach` (cualquiera puede venir
`null`, mostrar como "sin datos" en ese caso). Si la respuesta es `404` (no hay conexión
activa — puede pasar si el usuario borra la conexión después), redirigir a
`/connect-meta`. Nada más en esta pantalla por ahora — no agregues gráficos, filtros de
fecha, ni otras métricas todavía.

## Fuera de alcance (no lo implementes ahora)

- Gestión de colaboradores/miembros del negocio.
- Cualquier pantalla de `/admin/*`.
- Entitlements/planes/facturación.
- Selector de negocio (hoy el usuario tiene uno solo).
- Recuperación de contraseña / "olvidé mi contraseña".
- Cualquier persistencia de tokens vía backend-for-frontend o refresh tokens (el backend
  no los tiene).

## Antes de escribir código

Mostrame primero: la estructura de carpetas/rutas que vas a crear, cómo vas a manejar el
guard en el middleware, y un resumen de la paleta de colores que extrajiste de
`docs/Diseño del tablero/Inicio.dc.html`, para confirmarlo antes de generar todo.
