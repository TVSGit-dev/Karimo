"""Acces aux donnees.

Tout ce qui touche a la base passe par ici, pour que les vues restent minces et
que le domaine reste pur.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from karimo.db.models import Bien, HistoriquePrix, JournalExecution, NoteVisite, Statut
from karimo.domain.notation import Critere, Score, calculer_score


def lister_biens(
    session: Session,
    *,
    statut: Statut | None = None,
    tri: str = "date",
) -> list[Bien]:
    """Liste des biens, triee et filtree.

    Le tri par note se fait en Python : le score depend de la notation partielle,
    qui n'est pas exprimable en SQL sans dupliquer la regle metier — et la
    dupliquer serait exactement ce que le SPEC 9 interdit.
    """
    requete = select(Bien)
    if statut is not None:
        requete = requete.where(Bien.statut == statut)

    match tri:
        case "prix":
            requete = requete.order_by(Bien.prix_cents)
        case "note":
            requete = requete.order_by(desc(Bien.derniere_vue))
        case _:
            requete = requete.order_by(desc(Bien.premiere_vue), desc(Bien.id))

    biens = list(session.scalars(requete))

    if tri == "note":
        biens.sort(key=_cle_de_tri_par_note, reverse=True)
    return biens


def _cle_de_tri_par_note(bien: Bien) -> tuple[int, float]:
    """Les biens notes passent devant les non notes, a pourcentage decroissant."""
    score = score_du_bien(bien)
    if score.pourcentage is None:
        return (0, 0.0)
    return (1, float(score.pourcentage))


def obtenir_bien(session: Session, bien_id: int) -> Bien | None:
    return session.get(Bien, bien_id)


def notes_du_bien(bien: Bien) -> dict[Critere, int]:
    return {Critere(note.critere): note.note for note in bien.notes}


def score_du_bien(bien: Bien) -> Score:
    return calculer_score(notes_du_bien(bien))


def creer_bien(session: Session, bien: Bien) -> Bien:
    """Enregistre un bien et ouvre son historique de prix."""
    bien.prix_initial_cents = bien.prix_initial_cents or bien.prix_cents
    session.add(bien)
    session.flush()
    session.add(
        HistoriquePrix(bien_id=bien.id, prix_cents=bien.prix_cents, date=bien.premiere_vue)
    )
    return bien


def enregistrer_prix(session: Session, bien: Bien, prix_cents: int) -> bool:
    """Change le prix d'un bien et journalise le mouvement. Renvoie True si ca a bouge."""
    if prix_cents == bien.prix_cents:
        return False

    bien.prix_cents = prix_cents
    bien.derniere_vue = date.today()
    session.add(HistoriquePrix(bien_id=bien.id, prix_cents=prix_cents, date=date.today()))
    return True


def noter(
    session: Session,
    bien: Bien,
    critere: Critere,
    note: int | None,
    commentaire: str | None = None,
) -> None:
    """Pose ou remplace une note. `note=None` efface le critere.

    Effacer une note doit rester possible : un critere note par erreur, debout
    dans une maison, fausserait le score jusqu'a ce qu'on s'en apercoive.
    """
    existante = next((n for n in bien.notes if n.critere == critere), None)

    if note is None:
        if existante is not None:
            # delete-orphan sur la relation : retirer de la collection suffit.
            bien.notes.remove(existante)
            session.flush()
        return

    if existante is None:
        # On passe par la collection, pas par session.add : le score recalcule
        # dans la meme requete doit voir la note qu'on vient de poser.
        bien.notes.append(NoteVisite(critere=critere, note=note, commentaire=commentaire))
    else:
        existante.note = note
        existante.date = date.today()
        if commentaire is not None:
            existante.commentaire = commentaire

    session.flush()


def lister_journal(session: Session, limite: int = 50) -> list[JournalExecution]:
    return list(
        session.scalars(
            select(JournalExecution).order_by(desc(JournalExecution.date)).limit(limite)
        )
    )


def compter_par_statut(session: Session) -> dict[Statut, int]:
    comptes = dict.fromkeys(Statut, 0)
    for bien in session.scalars(select(Bien)):
        comptes[Statut(bien.statut)] += 1
    return comptes
