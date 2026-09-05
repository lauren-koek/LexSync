import os

from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import app


def frontend_origins() -> list[str]:
    configured = os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
