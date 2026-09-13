"""Parametres du calcul financier (SPEC 4.1).

Les valeurs par defaut sont celles du SPEC. `karimo.config` sait construire un
Parametres a partir de l'environnement ; le domaine, lui, ne lit jamais l'env.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

APPORT_DEFAUT_CENTS = 200_000_00
PLAFOND_PRIX_DEFAUT_CENTS = 450_000_00


@dataclass(frozen=True)
class Parametres:
    """Reglages du calcul de cout reel. Immuable : on en cree un, on le passe."""

    apport_cents: int = APPORT_DEFAUT_CENTS
    plafond_prix_cents: int = PLAFOND_PRIX_DEFAUT_CENTS
    taux_annuel: Decimal = Decimal("0.046")
    duree_annees: int = 25

    # Debours et frais d'acte du notaire, hors honoraires : recherches
    # urbanistiques, transcription au bureau Securite juridique, droits
    # d'ecriture. C'est le `frais_divers` du SPEC, devenu un poste explicite
    # depuis qu'on calcule les honoraires au bareme officiel.
    debours_cents: int = 1_300_00

    # Acte de credit, distinct de l'acte d'achat (SPEC 4.1).
    frais_credit_taux: Decimal = Decimal("0.01")
    frais_credit_fixe_cents: int = 2_200_00

    # TVA sur les honoraires du notaire.
    tva_honoraires: Decimal = Decimal("0.21")

    # Bascule de comparaison : si vrai, on remplace le bareme officiel par
    # l'approximation du SPEC (prix * 0.0115 + 800). Voir bareme_notaire.py.
    honoraires_approximation: bool = False


PARAMETRES_DEFAUT = Parametres()
