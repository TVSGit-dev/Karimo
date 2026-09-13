"""Objets de presentation.

Le domaine renvoie des centimes et des dataclasses ; les gabarits veulent des
chaines prêtes a afficher. Cette couche fait la traduction, et elle seule — pour
qu'aucun calcul ne se glisse dans un gabarit (SPEC 4 : les regles ne doivent pas
s'eparpiller dans les vues).
"""

from __future__ import annotations

from dataclasses import dataclass

from karimo.config import parametres
from karimo.db.models import Bien, Statut
from karimo.db.repository import notes_du_bien, score_du_bien
from karimo.domain.cout import Cout, Region, calculer_cout, detail_honoraires, prix_cible
from karimo.domain.notation import LIBELLES, POIDS, Critere, Score
from karimo.domain.peb import LabelPeb
from karimo.domain.qualification import Qualification, qualifier
from karimo.money import formate_euros, formate_pourcentage


@dataclass(frozen=True)
class LigneBien:
    """Une ligne de la liste : tout ce qui doit se lire sans ouvrir la fiche."""

    bien: Bien
    cout: Cout
    score: Score

    @property
    def prix(self) -> str:
        return formate_euros(self.bien.prix_cents)

    @property
    def cout_total(self) -> str:
        return formate_euros(self.cout.cout_total_cents)

    @property
    def ecart_plafond(self) -> str:
        return formate_euros(abs(self.cout.ecart_plafond_cents))

    @property
    def baisse(self) -> str:
        return formate_euros(self.bien.baisse_cents)

    @property
    def note_affichee(self) -> str:
        if self.score.pourcentage is None:
            return "—"
        suffixe = " *" if self.score.partielle else ""
        return f"{formate_pourcentage(self.score.pourcentage, 0)}{suffixe}"


@dataclass(frozen=True)
class FicheBien:
    """Le detail d'un bien : calcul complet, alertes, grille."""

    bien: Bien
    cout: Cout
    score: Score
    qualification: Qualification
    notes: dict[Critere, int]
    lignes_honoraires: list[tuple[str, str, str]]
    prix_cible: str

    @property
    def criteres(self) -> list[tuple[Critere, str, int, int | None]]:
        """(critere, libelle, poids, note actuelle) dans l'ordre de la grille."""
        return [(c, LIBELLES[c], POIDS[c], self.notes.get(c)) for c in Critere]


def ligne(bien: Bien) -> LigneBien:
    return LigneBien(
        bien=bien,
        cout=calculer_cout(bien.prix_cents, Region(bien.region), parametres()),
        score=score_du_bien(bien),
    )


def fiche(bien: Bien) -> FicheBien:
    p = parametres()
    region = Region(bien.region)
    cout = calculer_cout(bien.prix_cents, region, p)

    lignes_honoraires = [
        (
            formate_euros(assiette),
            formate_pourcentage(taux * 100, 3),
            formate_euros(montant, decimales=True),
        )
        for assiette, taux, montant in detail_honoraires(bien.prix_cents, p)
    ]

    return FicheBien(
        bien=bien,
        cout=cout,
        score=score_du_bien(bien),
        qualification=qualifier(
            prix_cents=bien.prix_cents,
            chambres=bien.chambres,
            surface_habitable=bien.surface_habitable,
            minutes_marche=bien.minutes_marche,
            peb_label=LabelPeb(bien.peb_label) if bien.peb_label else None,
            peb_cause=bien.peb_cause,
            description_brute=bien.description_brute,
        ),
        notes=notes_du_bien(bien),
        lignes_honoraires=lignes_honoraires,
        prix_cible=formate_euros(prix_cible(region, p)),
    )


def contexte_commun() -> dict:
    """Valeurs disponibles dans tous les gabarits."""
    p = parametres()
    return {
        "formate_euros": formate_euros,
        "formate_pourcentage": formate_pourcentage,
        "Statut": Statut,
        "Region": Region,
        "LabelPeb": LabelPeb,
        "Critere": Critere,
        "libelles_criteres": LIBELLES,
        "plafond": formate_euros(p.plafond_prix_cents),
        "apport": formate_euros(p.apport_cents),
        "taux_annuel": formate_pourcentage(p.taux_annuel * 100, 2),
        "duree_annees": p.duree_annees,
        "mode_approximation": p.honoraires_approximation,
    }
