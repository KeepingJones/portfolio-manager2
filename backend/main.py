from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from database import active_profile
from routers import positions, refresh, dividends, projections, t212, export, settings, summary, profiles

app = FastAPI(title="Portfolio Manager")

@app.middleware("http")
async def profile_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        profile = request.headers.get("X-Profile", "default")
        safe_profile = "".join(c for c in profile if c.isalnum() or c in "-_")
        if not safe_profile:
            safe_profile = "default"
        token = active_profile.set(safe_profile)
        try:
            return await call_next(request)
        finally:
            active_profile.reset(token)
    return await call_next(request)

app.include_router(positions.router)
app.include_router(refresh.router)
app.include_router(dividends.router)
app.include_router(projections.router)
app.include_router(t212.router)
app.include_router(export.router)
app.include_router(settings.router)
app.include_router(summary.router)
app.include_router(profiles.router)

# Serve frontend
_frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/css", StaticFiles(directory=os.path.join(_frontend, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(_frontend, "js")), name="js")


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(_frontend, "index.html"))
