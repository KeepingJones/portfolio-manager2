from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from database import init_db
from routers import positions, refresh, dividends, projections, t212, export, settings, summary

app = FastAPI(title="Portfolio Manager")

init_db()

app.include_router(positions.router)
app.include_router(refresh.router)
app.include_router(dividends.router)
app.include_router(projections.router)
app.include_router(t212.router)
app.include_router(export.router)
app.include_router(settings.router)
app.include_router(summary.router)

# Serve frontend
_frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/css", StaticFiles(directory=os.path.join(_frontend, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(_frontend, "js")), name="js")


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(_frontend, "index.html"))
