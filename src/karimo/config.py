"""Lecture de la configuration depuis l'environnement.

Frontiere volontaire : c'est le seul endroit qui lit os.environ. Le domaine
recoit un Parametres deja construit et ne sait pas d'ou il vient. Les secrets
vivent dans l'environnement, jamais dans le depot (SPEC 9) — il n'y en a aucun
au jalon 1, mais le pli est pris pour l'OAuth Gmail du jalon 2.
"""

from __future__ import annotations

import os
from decimal import Decimal
from functools import lru_cache

from karimo.domain.parametres import Parametres
from karimo.money import euros

DATABASE_URL_DEFAUT = "sqlite:///karimo.db"


def _euros_env(cle: str, defaut: int) -> int:
    brut = os.environ.get(cle)
    return euros(brut) if brut else defaut


def _decimal_env(cle: str, defaut: Decimal) -> Decimal:
    brut = os.environ.get(cle)
    return Decimal(brut) if brut else defaut


def _bool_env(cle: str, defaut: bool = False) -> bool:
    brut = os.environ.get(cle)
    if brut is None:
        return defaut
    return brut.strip().lower() in {"1", "true", "vrai", "oui", "yes"}


def database_url() -> str:
    return os.environ.get("KARIMO_DATABASE_URL", DATABASE_URL_DEFAUT)


@lru_cache(maxsize=1)
def parametres() -> Parametres:
    """Parametres financiers, defauts du SPEC surchargeables par l'environnement."""
    defaut = Parametres()
    return Parametres(
        apport_cents=_euros_env("KARIMO_APPORT", defaut.apport_cents),
        plafond_prix_cents=_euros_env("KARIMO_PLAFOND_PRIX", defaut.plafond_prix_cents),
        taux_annuel=_decimal_env("KARIMO_TAUX_ANNUEL", defaut.taux_annuel),
        duree_annees=int(os.environ.get("KARIMO_DUREE_ANNEES", defaut.duree_annees)),
        debours_cents=_euros_env("KARIMO_DEBOURS", defaut.debours_cents),
        frais_credit_taux=_decimal_env("KARIMO_FRAIS_CREDIT_TAUX", defaut.frais_credit_taux),
        frais_credit_fixe_cents=_euros_env(
            "KARIMO_FRAIS_CREDIT_FIXE", defaut.frais_credit_fixe_cents
        ),
        honoraires_approximation=_bool_env("KARIMO_HONORAIRES_APPROXIMATION"),
    )
