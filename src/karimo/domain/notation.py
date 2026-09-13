"""Grille de notation (SPEC 4.6).

Onze criteres ponderes, note de 1 a 5, total sur 125.

Le point delicat est la notation partielle : la grille se remplit debout dans
une maison, on ne note pas tout. Un total calcule sur 125 alors que trois
criteres seulement sont renseignes serait faux et ferait passer un bon bien pour
un mauvais. On calcule donc le score obtenu sur le maximum des seuls criteres
renseignes, et on dit que la notation est partielle.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

NOTE_MIN = 1
NOTE_MAX = 5

SEUIL_PASSER = Decimal("60")
SEUIL_OFFRIR = Decimal("76")


class Critere(StrEnum):
    """Les onze criteres, dans l'ordre d'affichage de la grille."""

    DISTANCE_TRANSPORT = "distance_transport"
    GARAGE = "garage"
    CHAMBRES = "chambres"
    ETAT_ENERGETIQUE = "etat_energetique"
    TRAVAUX = "travaux"
    JARDIN = "jardin"
    LUMINOSITE = "luminosite"
    QUARTIER = "quartier"
    ECOLES_COMMERCES = "ecoles_commerces"
    RANGEMENT = "rangement"
    EXTENSION = "extension"


POIDS: dict[Critere, int] = {
    Critere.DISTANCE_TRANSPORT: 3,
    Critere.GARAGE: 3,
    Critere.CHAMBRES: 3,
    Critere.ETAT_ENERGETIQUE: 3,
    Critere.TRAVAUX: 3,
    Critere.JARDIN: 2,
    Critere.LUMINOSITE: 2,
    Critere.QUARTIER: 2,
    Critere.ECOLES_COMMERCES: 2,
    Critere.RANGEMENT: 1,
    Critere.EXTENSION: 1,
}

LIBELLES: dict[Critere, str] = {
    Critere.DISTANCE_TRANSPORT: "Distance tram ou métro à pied",
    Critere.GARAGE: "Garage ou possibilité d'en créer",
    Critere.CHAMBRES: "Chambres, 4 à terme",
    Critere.ETAT_ENERGETIQUE: "État énergétique",
    Critere.TRAVAUX: "Ampleur réelle des travaux",
    Critere.JARDIN: "Jardin, extérieur",
    Critere.LUMINOSITE: "Luminosité",
    Critere.QUARTIER: "Quartier, calme",
    Critere.ECOLES_COMMERCES: "Écoles, commerces",
    Critere.RANGEMENT: "Cave, grenier, rangement",
    Critere.EXTENSION: "Potentiel d'extension",
}

TOTAL_POIDS = sum(POIDS.values())          # 25
SCORE_MAXIMUM = TOTAL_POIDS * NOTE_MAX     # 125


class Verdict(StrEnum):
    PASSER = "passer"
    REVOIR = "revoir"
    OFFRIR = "offrir"

    @property
    def libelle(self) -> str:
        return {
            Verdict.PASSER: "Passer",
            Verdict.REVOIR: "Revoir",
            Verdict.OFFRIR: "Offrir vite",
        }[self]


@dataclass(frozen=True)
class Score:
    """Resultat d'une notation, complete ou partielle."""

    obtenu: int
    maximum: int
    criteres_notes: int
    pourcentage: Decimal | None
    partielle: bool
    verdict: Verdict | None

    @property
    def sur_125(self) -> int | None:
        """Le score ramene sur 125, uniquement si la grille est complete.

        Volontairement None en notation partielle : extrapoler un total sur 125
        a partir de quatre criteres reviendrait a inventer les sept autres.
        """
        return self.obtenu if not self.partielle else None


def verdict_pour(pourcentage: Decimal) -> Verdict:
    """Reperes du SPEC : sous 60 % passer, 60 a 76 % revoir, au-dessus offrir vite."""
    if pourcentage < SEUIL_PASSER:
        return Verdict.PASSER
    if pourcentage <= SEUIL_OFFRIR:
        return Verdict.REVOIR
    return Verdict.OFFRIR


def calculer_score(notes: dict[Critere, int]) -> Score:
    """Score pondere sur le maximum des seuls criteres renseignes.

    Les notes hors de l'intervalle 1-5 sont refusees : une note a 0 ou a 7
    viendrait forcement d'un bug d'appel, et la faire passer silencieusement
    fausserait le classement de tous les biens.
    """
    retenues = {c: n for c, n in notes.items() if n is not None}
    for critere, note in retenues.items():
        if not NOTE_MIN <= note <= NOTE_MAX:
            raise ValueError(
                f"Note invalide pour {critere.value} : {note} (attendu {NOTE_MIN}-{NOTE_MAX})"
            )

    if not retenues:
        return Score(
            obtenu=0,
            maximum=0,
            criteres_notes=0,
            pourcentage=None,
            partielle=True,
            verdict=None,
        )

    obtenu = sum(note * POIDS[critere] for critere, note in retenues.items())
    maximum = sum(NOTE_MAX * POIDS[critere] for critere in retenues)
    pourcentage = (Decimal(obtenu) * 100 / Decimal(maximum)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )

    return Score(
        obtenu=obtenu,
        maximum=maximum,
        criteres_notes=len(retenues),
        pourcentage=pourcentage,
        partielle=len(retenues) < len(POIDS),
        verdict=verdict_pour(pourcentage),
    )
