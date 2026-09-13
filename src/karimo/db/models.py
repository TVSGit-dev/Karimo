"""Schema de la base (SPEC 3).

Deux regles structurantes :

- Tous les montants sont des entiers de centimes (SPEC 9). Le suffixe `_cents`
  est dans le nom de colonne pour qu'aucune addition douteuse ne passe la
  relecture.
- On ne supprime jamais un bien (SPEC 9). Le statut `ecarte` avec une raison
  suffit : revenir sur un bien ecarte deux mois plus tot arrive souvent.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from karimo.domain.cout import Region
from karimo.domain.notation import Critere
from karimo.domain.peb import LabelPeb


class Base(DeclarativeBase):
    pass


class Statut(StrEnum):
    NOUVEAU = "nouveau"
    A_APPELER = "a_appeler"
    VISITE_PREVUE = "visite_prevue"
    VISITE = "visite"
    ECARTE = "ecarte"

    @property
    def libelle(self) -> str:
        return {
            Statut.NOUVEAU: "Nouveau",
            Statut.A_APPELER: "À appeler",
            Statut.VISITE_PREVUE: "Visite prévue",
            Statut.VISITE: "Visité",
            Statut.ECARTE: "Écarté",
        }[self]


# Parametres de suivi que les portails collent aux URL. Deux liens vers la meme
# annonce ne doivent pas donner deux `url_hash` differents, sinon la
# deduplication du jalon 2 laisse passer des doublons.
PARAMS_DE_SUIVI = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "source", "ref", "referrer",
}


def normaliser_url(url: str) -> str:
    """Forme canonique d'une URL d'annonce, avant hachage."""
    parties = urlsplit(url.strip())
    # Le schema est force a https : http://x et https://x sont la meme annonce,
    # et deux hachages differents laisseraient passer un doublon.
    schema = "https"
    hote = parties.netloc.lower().removeprefix("www.")
    chemin = parties.path.rstrip("/") or "/"
    query = urlencode(
        sorted(
            (cle, valeur)
            for cle, valeur in parse_qsl(parties.query, keep_blank_values=True)
            if cle.lower() not in PARAMS_DE_SUIVI
        )
    )
    return urlunsplit((schema, hote, chemin, query, ""))


def hacher_url(url: str) -> str:
    """SHA-256 de l'URL normalisee : la cle de deduplication."""
    return hashlib.sha256(normaliser_url(url).encode("utf-8")).hexdigest()


class Bien(Base):
    __tablename__ = "bien"

    id: Mapped[int] = mapped_column(primary_key=True)

    source: Mapped[str] = mapped_column(String(120))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    adresse: Mapped[str | None] = mapped_column(Text, nullable=True)
    commune: Mapped[str] = mapped_column(String(120))
    region: Mapped[Region] = mapped_column(String(20))

    # Ajout au modele du SPEC : sans ces colonnes, chaque recalcul de perimetre
    # redemanderait le reseau au geocodeur du jalon 2.
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)

    prix_cents: Mapped[int] = mapped_column(Integer)
    prix_initial_cents: Mapped[int] = mapped_column(Integer)
    chambres: Mapped[int | None] = mapped_column(nullable=True)
    surface_habitable: Mapped[int | None] = mapped_column(nullable=True)
    surface_terrain: Mapped[int | None] = mapped_column(nullable=True)

    peb_label: Mapped[LabelPeb | None] = mapped_column(String(1), nullable=True)
    peb_score: Mapped[int | None] = mapped_column(nullable=True)
    peb_cause: Mapped[str | None] = mapped_column(Text, nullable=True)

    garage: Mapped[bool] = mapped_column(default=False)
    garage_potentiel: Mapped[bool] = mapped_column(default=False)

    arret_proche: Mapped[str | None] = mapped_column(String(120), nullable=True)
    minutes_marche: Mapped[int | None] = mapped_column(nullable=True)

    statut: Mapped[Statut] = mapped_column(String(20), default=Statut.NOUVEAU)
    raison_ecart: Mapped[str | None] = mapped_column(Text, nullable=True)

    premiere_vue: Mapped[date] = mapped_column(Date, default=date.today)
    derniere_vue: Mapped[date] = mapped_column(Date, default=date.today)

    description_brute: Mapped[str | None] = mapped_column(Text, nullable=True)
    photos: Mapped[list | None] = mapped_column(JSON, nullable=True)

    notes_libres: Mapped[str | None] = mapped_column(Text, nullable=True)
    telephone_agence: Mapped[str | None] = mapped_column(String(40), nullable=True)

    cree_le: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    notes: Mapped[list[NoteVisite]] = relationship(
        back_populates="bien", cascade="all, delete-orphan", lazy="selectin"
    )
    historique: Mapped[list[HistoriquePrix]] = relationship(
        back_populates="bien",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="HistoriquePrix.date",
    )

    __table_args__ = (Index("ix_bien_statut", "statut"),)

    @property
    def baisse_cents(self) -> int:
        """Baisse depuis la premiere vue, 0 s'il n'y en a pas.

        Une baisse de prix est un signal fort (SPEC 3) : elle se lit dans la
        liste sans ouvrir la fiche.
        """
        return max(0, self.prix_initial_cents - self.prix_cents)

    @property
    def a_baisse(self) -> bool:
        return self.baisse_cents > 0


class NoteVisite(Base):
    """Une note par critere et par bien : la grille se met a jour, elle ne s'empile pas."""

    __tablename__ = "note_visite"

    id: Mapped[int] = mapped_column(primary_key=True)
    bien_id: Mapped[int] = mapped_column(ForeignKey("bien.id", ondelete="CASCADE"), index=True)
    critere: Mapped[Critere] = mapped_column(String(30))
    note: Mapped[int] = mapped_column(Integer)
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)
    date: Mapped[date] = mapped_column(Date, default=date.today)

    bien: Mapped[Bien] = relationship(back_populates="notes")

    __table_args__ = (UniqueConstraint("bien_id", "critere", name="uq_note_bien_critere"),)


class HistoriquePrix(Base):
    __tablename__ = "historique_prix"

    id: Mapped[int] = mapped_column(primary_key=True)
    bien_id: Mapped[int] = mapped_column(ForeignKey("bien.id", ondelete="CASCADE"), index=True)
    prix_cents: Mapped[int] = mapped_column(Integer)
    date: Mapped[date] = mapped_column(Date, default=date.today)

    bien: Mapped[Bien] = relationship(back_populates="historique")


class JournalExecution(Base):
    """Journal des executions (SPEC 6).

    Vide au jalon 1 : l'ecran existe pour que le jalon 2 n'ait qu'a ecrire des
    lignes. Sans lui, une source qui tombe en panne passe inapercue pendant des
    semaines.
    """

    __tablename__ = "journal_execution"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    source: Mapped[str] = mapped_column(String(120))
    annonces_vues: Mapped[int] = mapped_column(Integer, default=0)
    annonces_retenues: Mapped[int] = mapped_column(Integer, default=0)
    erreurs: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def en_erreur(self) -> bool:
        return bool(self.erreurs)
