"""Communes du perimetre et region fiscale (SPEC 4.5).

La region fiscale decide des droits d'enregistrement : c'est une regle metier,
pas un detail d'adaptateur. Elle vit donc ici, testee, et non dans le code qui
lit les mails — deux portails qui ecrivent une adresse differemment doivent
aboutir a la meme region.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from karimo.domain.cout import Region


@dataclass(frozen=True)
class Commune:
    nom: str
    code_postal: int
    region: Region
    priorite: int  # 1 = cible principale, d'apres l'ordre du SPEC 4.5


# Communes du perimetre, par ordre de priorite (SPEC 4.5).
PERIMETRE: tuple[Commune, ...] = (
    Commune("Kraainem", 1950, Region.FLANDRE, 1),
    Commune("Wezembeek-Oppem", 1970, Region.FLANDRE, 2),
    Commune("Woluwe-Saint-Pierre", 1150, Region.BRUXELLES, 3),
    Commune("Woluwe-Saint-Étienne", 1932, Region.FLANDRE, 4),
    Commune("Sterrebeek", 1933, Region.FLANDRE, 4),
)

# Noms alternatifs rencontres dans les annonces : neerlandais, variantes de
# graphie, communes limitrophes que les portails renvoient pour nos criteres.
ALIAS: dict[str, str] = {
    "kraainem": "Kraainem",
    "crainhem": "Kraainem",
    "wezembeek-oppem": "Wezembeek-Oppem",
    "wezembeek oppem": "Wezembeek-Oppem",
    "woluwe-saint-pierre": "Woluwe-Saint-Pierre",
    "sint-pieters-woluwe": "Woluwe-Saint-Pierre",
    "woluwe-saint-etienne": "Woluwe-Saint-Étienne",
    "sint-stevens-woluwe": "Woluwe-Saint-Étienne",
    "sterrebeek": "Sterrebeek",
}

# Region de Bruxelles-Capitale : 1000 a 1299.
BRUXELLES_MIN, BRUXELLES_MAX = 1000, 1299
# Brabant wallon et Wallonie : hors perimetre, et hors du couple Flandre/Bruxelles.
WALLONIE = ((1300, 1499), (4000, 7999))


def _normalise(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte.strip().lower())
    return "".join(c for c in decompose if not unicodedata.combining(c))


def region_depuis_code_postal(code_postal: int | None) -> Region | None:
    """Region fiscale deduite du code postal belge.

    Renvoie None pour la Wallonie et pour un code hors de Belgique : ce ne sont
    pas des erreurs, seulement des biens qui sortent du perimetre. Le SPEC ne
    connait que la Flandre et Bruxelles, et un bien wallon doit etre ecarte,
    pas rattache de force a une region.
    """
    if code_postal is None or not 1000 <= code_postal <= 9999:
        return None
    if BRUXELLES_MIN <= code_postal <= BRUXELLES_MAX:
        return Region.BRUXELLES
    if any(debut <= code_postal <= fin for debut, fin in WALLONIE):
        return None
    return Region.FLANDRE


def commune_depuis_nom(nom: str | None) -> Commune | None:
    """Retrouve une commune du perimetre a partir d'un nom d'annonce."""
    if not nom:
        return None
    normalise = _normalise(nom)
    canonique = ALIAS.get(normalise)
    if canonique is None:
        return None
    return next(c for c in PERIMETRE if c.nom == canonique)


def dans_le_perimetre(nom: str | None = None, code_postal: int | None = None) -> bool:
    """Vrai si la commune fait partie des cinq communes du SPEC."""
    if code_postal is not None and any(c.code_postal == code_postal for c in PERIMETRE):
        return True
    return commune_depuis_nom(nom) is not None
