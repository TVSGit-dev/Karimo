"""Detection des indices de gros travaux dans le texte des annonces (SPEC 4.4).

Le bien doit etre habitable immediatement : les travaux ne sont acceptes que
s'ils se realisent en habitant.

Feu vert : toiture, isolation des combles, chassis piece par piece, chaudiere ou
pompe a chaleur, remplacement du tableau electrique seul, cuisine, sols,
peinture, salle de bain s'il en existe une seconde.

Feu rouge, eliminatoire : refection complete de l'electricite, refection
complete de la plomberie, isolation des murs par l'interieur, abattage de murs
porteurs, humidite ascensionnelle, amiante.

Ce module ne tranche pas, il signale : les annonces sont ecrites pour vendre, un
mot-cle trouve est une question a poser, pas une condamnation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Mots-cles du SPEC, en francais et en neerlandais.
MOTS_CLES_FEU_ROUGE: tuple[str, ...] = (
    "à rénover",
    "gros travaux",
    "à rafraîchir entièrement",
    "électricité non conforme",
    "pas de chauffage central",
    "humidité",
    "amiante",
    "te renoveren",
    "op te frissen",
    "geen centrale verwarming",
    "vocht",
    "asbest",
)

FEU_VERT = (
    "toiture",
    "isolation des combles",
    "châssis pièce par pièce",
    "chaudière ou pompe à chaleur",
    "remplacement du tableau électrique seul",
    "cuisine",
    "sols",
    "peinture",
    "salle de bain s'il en existe une seconde",
)

FEU_ROUGE = (
    "réfection complète de l'électricité",
    "réfection complète de la plomberie",
    "isolation des murs par l'intérieur",
    "abattage de murs porteurs",
    "humidité ascensionnelle",
    "amiante",
)


@dataclass(frozen=True)
class IndiceTravaux:
    """Un mot-cle trouve, avec l'extrait de texte qui l'entoure."""

    mot_cle: str
    extrait: str


def _normalise(texte: str) -> str:
    """Minuscules, sans accents, apostrophes uniformisees.

    Les annonces melangent apostrophe droite et typographique, majuscules de
    titre et accents absents. Sans normalisation, "A RENOVER" echapperait a
    "à rénover".
    """
    texte = texte.replace("’", "'").replace("ʼ", "'")
    decompose = unicodedata.normalize("NFKD", texte.lower())
    return "".join(c for c in decompose if not unicodedata.combining(c))


def detecter_travaux(texte: str | None) -> list[IndiceTravaux]:
    """Cherche les mots-cles de feu rouge dans le texte d'une annonce.

    La recherche se fait sur frontieres de mots, pour que "vocht" ne se
    declenche pas sur "vochtvrij" (= sans humidite), qui dit exactement
    l'inverse.
    """
    if not texte:
        return []

    normalise = _normalise(texte)
    indices: list[IndiceTravaux] = []

    for mot_cle in MOTS_CLES_FEU_ROUGE:
        motif = re.escape(_normalise(mot_cle)).replace(r"\ ", r"\s+")
        trouve = re.search(rf"(?<!\w){motif}(?!\w)", normalise)
        if trouve is None:
            continue
        debut = max(0, trouve.start() - 45)
        fin = min(len(texte), trouve.end() + 45)
        extrait = " ".join(texte[debut:fin].split())
        if debut > 0:
            extrait = "…" + extrait
        if fin < len(texte):
            extrait = extrait + "…"
        indices.append(IndiceTravaux(mot_cle=mot_cle, extrait=extrait))

    return indices
