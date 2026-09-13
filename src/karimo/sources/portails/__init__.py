"""Registre des adaptateurs de portail.

Ajouter un portail (jalon 3) revient a ecrire un module et a l'inscrire ici.
"""

from __future__ import annotations

from karimo.sources.portails.base import Adaptateur, AdaptateurBase, AnnonceBrute
from karimo.sources.portails.zimmo import AdaptateurZimmo

ADAPTATEURS: tuple[Adaptateur, ...] = (AdaptateurZimmo(),)


def adaptateur_pour(expediteur: str) -> Adaptateur | None:
    """Adaptateur capable de lire un mail de cet expediteur, None sinon."""
    return next((a for a in ADAPTATEURS if a.reconnait(expediteur)), None)


__all__ = [
    "ADAPTATEURS",
    "Adaptateur",
    "AdaptateurBase",
    "AdaptateurZimmo",
    "AnnonceBrute",
    "adaptateur_pour",
]
