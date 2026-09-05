import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse

from app.api.v1.interaction_routes import router as interaction_router
from app.api.v1.routes import router
from app.bass.api import router as bass_router
from app.config import ENGINE_VERSION
from app.keyboard.api import router as keyboard_router

app = FastAPI(
    title="Human Groove Engine API",
    version=ENGINE_VERSION,
    description="Deterministic rhythm generation, measurement, mutation and MIDI export.",
)
cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1_000)
app.include_router(router)
app.include_router(bass_router)
app.include_router(interaction_router)
app.include_router(keyboard_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


web_dist_dir = Path(os.environ.get("HGE_WEB_DIST_DIR", ""))
if web_dist_dir.is_dir() and (web_dist_dir / "index.html").is_file():

    @app.get("/{requested_path:path}", include_in_schema=False)
    def web_app(requested_path: str) -> FileResponse:
        requested_file = (web_dist_dir / requested_path).resolve()
        if (
            requested_path
            and requested_file.is_relative_to(web_dist_dir)
            and requested_file.is_file()
        ):
            return FileResponse(requested_file)
        return FileResponse(web_dist_dir / "index.html")
