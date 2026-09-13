"""Application web.

Rendu serveur, priorite au telephone : la grille de notation se remplit debout
dans une maison, avec une seule main (SPEC 6).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

RACINE = Path(__file__).parent
GABARITS = Jinja2Templates(directory=str(RACINE / "templates"))


def creer_app() -> FastAPI:
    app = FastAPI(title="Karimo", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(RACINE / "static")), name="static")

    from karimo.web.routes import biens, journal

    app.include_router(biens.routeur)
    app.include_router(journal.routeur)
    return app


app = creer_app()
