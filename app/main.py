from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import accounts, admin, auth, dashboard, leads, meta
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="Soy Emprendedora API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(leads.router)
app.include_router(meta.router)
app.include_router(admin.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
