"""Ecran Journal (SPEC 6).

Vide au jalon 1 : aucune source n'est encore branchee. L'ecran existe des
maintenant parce que, sans lui, une source qui tombe en panne au jalon 2 passe
inapercue pendant des semaines.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from karimo.db.repository import lister_journal
from karimo.db.session import obtenir_session
from karimo.web.app import GABARITS
from karimo.web.vues import contexte_commun

routeur = APIRouter()


@routeur.get("/journal", response_class=HTMLResponse)
def journal(
    request: Request, session: Session = Depends(obtenir_session)
) -> HTMLResponse:
    return GABARITS.TemplateResponse(
        request=request,
        name="journal.html",
        context={**contexte_commun(), "executions": lister_journal(session)},
    )
