"""Ecrans Liste, Fiche et saisie (SPEC 6)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from karimo.db.models import Bien, Statut, hacher_url
from karimo.db.repository import (
    compter_par_statut,
    creer_bien,
    enregistrer_prix,
    lister_biens,
    noter,
    obtenir_bien,
)
from karimo.db.session import obtenir_session
from karimo.domain.conditions import CONDITIONS_TAUX_FLAMAND, TITRE_TAUX_FLAMAND
from karimo.domain.cout import Region
from karimo.domain.notation import NOTE_MAX, NOTE_MIN, Critere
from karimo.domain.peb import LabelPeb
from karimo.domain.perimetre import arret_le_plus_proche
from karimo.money import euros
from karimo.web.app import GABARITS
from karimo.web.vues import contexte_commun, fiche, ligne

routeur = APIRouter()

TRIS = {"date": "Date d'ajout", "note": "Note", "prix": "Prix"}


def _rendre(request: Request, gabarit: str, **contexte) -> HTMLResponse:
    return GABARITS.TemplateResponse(
        request=request, name=gabarit, context={**contexte_commun(), **contexte}
    )


@routeur.get("/", response_class=HTMLResponse)
def liste(
    request: Request,
    statut: str | None = None,
    tri: str = "date",
    session: Session = Depends(obtenir_session),
) -> HTMLResponse:
    filtre = Statut(statut) if statut in set(Statut) else None
    tri = tri if tri in TRIS else "date"

    biens = lister_biens(session, statut=filtre, tri=tri)
    return _rendre(
        request,
        "liste.html",
        lignes=[ligne(b) for b in biens],
        statut_actif=filtre,
        tri_actif=tri,
        tris=TRIS,
        comptes=compter_par_statut(session),
        total=sum(compter_par_statut(session).values()),
    )


@routeur.get("/bien/nouveau", response_class=HTMLResponse)
def formulaire_creation(request: Request) -> HTMLResponse:
    return _rendre(request, "formulaire.html", bien=None)


@routeur.get("/bien/{bien_id}", response_class=HTMLResponse)
def detail(
    request: Request, bien_id: int, session: Session = Depends(obtenir_session)
) -> HTMLResponse:
    bien = obtenir_bien(session, bien_id)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")

    return _rendre(
        request,
        "fiche.html",
        f=fiche(bien),
        note_min=NOTE_MIN,
        note_max=NOTE_MAX,
        conditions_flamandes=CONDITIONS_TAUX_FLAMAND,
        titre_conditions=TITRE_TAUX_FLAMAND,
    )


@routeur.get("/bien/{bien_id}/modifier", response_class=HTMLResponse)
def formulaire_modification(
    request: Request, bien_id: int, session: Session = Depends(obtenir_session)
) -> HTMLResponse:
    bien = obtenir_bien(session, bien_id)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")
    return _rendre(request, "formulaire.html", bien=bien)


def _entier(valeur: str | None) -> int | None:
    valeur = (valeur or "").strip()
    return int(valeur) if valeur else None


def _flottant(valeur: str | None) -> float | None:
    valeur = (valeur or "").strip().replace(",", ".")
    return float(valeur) if valeur else None


def _texte(valeur: str | None) -> str | None:
    valeur = (valeur or "").strip()
    return valeur or None


@routeur.post("/bien")
def enregistrer(
    source: str = Form(...),
    commune: str = Form(...),
    region: str = Form(...),
    prix: str = Form(...),
    bien_id: str = Form(""),
    url: str = Form(""),
    adresse: str = Form(""),
    chambres: str = Form(""),
    surface_habitable: str = Form(""),
    surface_terrain: str = Form(""),
    peb_label: str = Form(""),
    peb_score: str = Form(""),
    peb_cause: str = Form(""),
    garage: str = Form(""),
    garage_potentiel: str = Form(""),
    latitude: str = Form(""),
    longitude: str = Form(""),
    minutes_marche: str = Form(""),
    statut: str = Form(Statut.NOUVEAU),
    raison_ecart: str = Form(""),
    telephone_agence: str = Form(""),
    description_brute: str = Form(""),
    notes_libres: str = Form(""),
    session: Session = Depends(obtenir_session),
) -> RedirectResponse:
    """Cree ou met a jour un bien saisi a la main."""
    prix_cents = euros(prix.replace(" ", "").replace(",", "."))
    lat, lon = _flottant(latitude), _flottant(longitude)

    arret_proche = None
    minutes = _entier(minutes_marche)
    if lat is not None and lon is not None:
        # Les coordonnees priment sur la saisie manuelle : elles sont verifiables.
        proximite = arret_le_plus_proche(lat, lon)
        arret_proche = proximite.arret.libelle
        minutes = proximite.minutes

    champs = dict(
        source=source.strip(),
        url=_texte(url),
        adresse=_texte(adresse),
        commune=commune.strip(),
        region=Region(region),
        latitude=lat,
        longitude=lon,
        chambres=_entier(chambres),
        surface_habitable=_entier(surface_habitable),
        surface_terrain=_entier(surface_terrain),
        peb_label=LabelPeb(peb_label) if peb_label else None,
        peb_score=_entier(peb_score),
        peb_cause=_texte(peb_cause),
        garage=bool(garage),
        garage_potentiel=bool(garage_potentiel),
        arret_proche=arret_proche,
        minutes_marche=minutes,
        statut=Statut(statut),
        raison_ecart=_texte(raison_ecart),
        telephone_agence=_texte(telephone_agence),
        description_brute=_texte(description_brute),
        notes_libres=_texte(notes_libres),
    )

    if bien_id:
        bien = obtenir_bien(session, int(bien_id))
        if bien is None:
            raise HTTPException(status_code=404, detail="Bien introuvable")
        for cle, valeur in champs.items():
            setattr(bien, cle, valeur)
        # Passe par le repository : un changement de prix doit laisser une trace.
        enregistrer_prix(session, bien, prix_cents)
        bien.derniere_vue = date.today()
    else:
        # Sans URL, on hache une cle de repli : deux saisies manuelles du meme
        # bien resteraient sinon indistinguables.
        cle = url.strip() or f"manuel:{source}:{commune}:{adresse or prix}"
        bien = creer_bien(
            session,
            Bien(**champs, prix_cents=prix_cents, prix_initial_cents=prix_cents,
                 url_hash=hacher_url(cle)),
        )

    session.flush()
    return RedirectResponse(f"/bien/{bien.id}", status_code=303)


@routeur.post("/bien/{bien_id}/note")
def poser_note(
    bien_id: int,
    critere: str = Form(...),
    note: str = Form(...),
    session: Session = Depends(obtenir_session),
) -> RedirectResponse:
    """Enregistre un tap sur la grille. Retaper la meme note l'efface."""
    bien = obtenir_bien(session, bien_id)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")

    try:
        critere_enum = Critere(critere)
    except ValueError as erreur:
        raise HTTPException(status_code=400, detail="Critère inconnu") from erreur

    valeur = _entier(note)
    if valeur is not None and not NOTE_MIN <= valeur <= NOTE_MAX:
        raise HTTPException(status_code=400, detail="Note hors barème")

    actuelle = next((n.note for n in bien.notes if n.critere == critere_enum), None)
    noter(session, bien, critere_enum, None if valeur == actuelle else valeur)

    return RedirectResponse(f"/bien/{bien_id}#grille", status_code=303)


@routeur.post("/bien/{bien_id}/statut")
def changer_statut(
    bien_id: int,
    statut: str = Form(...),
    raison_ecart: str = Form(""),
    session: Session = Depends(obtenir_session),
) -> RedirectResponse:
    """Change le statut. On n'efface jamais un bien (SPEC 9) : `ecarte` suffit."""
    bien = obtenir_bien(session, bien_id)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")

    bien.statut = Statut(statut)
    if bien.statut is Statut.ECARTE:
        bien.raison_ecart = _texte(raison_ecart)
    return RedirectResponse(f"/bien/{bien_id}", status_code=303)


@routeur.post("/bien/{bien_id}/notes-libres")
def enregistrer_notes_libres(
    bien_id: int,
    notes_libres: str = Form(""),
    session: Session = Depends(obtenir_session),
) -> RedirectResponse:
    bien = obtenir_bien(session, bien_id)
    if bien is None:
        raise HTTPException(status_code=404, detail="Bien introuvable")
    bien.notes_libres = _texte(notes_libres)
    return RedirectResponse(f"/bien/{bien_id}#notes", status_code=303)
