"""
main.py
FastAPI Server Entry Point for SoloMom Advisor MVP.
Initializes database, mounts REST API endpoints, and serves the static HTML/Tailwind frontend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api import routes_advisor, routes_dashboard, routes_doctor, routes_logs, routes_voice
from core import database as db

app = FastAPI(
    title="SoloMom Advisor API",
    description="Proactive AI Family Advisor for Single Mothers",
    version="1.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(routes_dashboard.router)
app.include_router(routes_logs.router)
app.include_router(routes_advisor.router)
app.include_router(routes_doctor.router)
app.include_router(routes_voice.router)

# Static directory setup
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def startup_event():
    """Ensure database schema is ready and demo data is populated."""
    db.init_db()
    if not db.get_profile():
        db.seed_demo_data()


@app.get("/")
def read_root():
    """Serves the Single-Page Application (index.html)."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "SoloMom Advisor API running. Frontend static/index.html loading..."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
