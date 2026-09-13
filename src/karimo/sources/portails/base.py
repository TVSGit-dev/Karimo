"""Contrat commun aux adaptateurs de portail (SPEC 5.1).

« Ces mails changent de format sans prévenir : l'app doit survivre à un parseur
cassé, journaliser l'erreur, et continuer avec les autres sources. »

D'ou deux choix :

- Un adaptateur renvoie des `AnnonceBrute`, pas des objets de base. Il ne decide
  rien : il lit ce qu'il trouve et laisse les champs absents a None. La
  qualification et l'enregistrement sont ailleurs, et ne dependent pas de la
  fragilite du parsing.
- Un champ illisible n'est jamais une exception. Seul un mail entierement
  incomprehensible en leve une, et l'orchestrateur l'attrape source par source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class AnnonceBrute:
    """Ce qu'un adaptateur a pu extraire d'une annonce, sans interpretation."""

    source: str
    url: str
    titre: str | None = None
    adresse: str | None = None
    commune: str | None = None
    code_postal: int | None = None
    prix_cents: int | None = None
    chambres: int | None = None
    surface_habitable: int | None = None
    description: str | None = None
    photos: list[str] | None = None

    @property
    def complete(self) -> bool:
        """Vrai si les champs qui pilotent les filtres du SPEC 7 sont presents."""
        return None not in (self.prix_cents, self.commune)


@runtime_checkable
class Adaptateur(Protocol):
    """Un portail. Sans etat : on l'instancie une fois et on le reutilise."""

    nom: str
    expediteurs: tuple[str, ...]

    def reconnait(self, expediteur: str) -> bool:
        """Vrai si ce mail vient de ce portail."""
        ...

    def extraire(self, html: str) -> list[AnnonceBrute]:
        """Annonces trouvees dans le corps HTML du mail."""
        ...


class AdaptateurBase:
    """Implementation commune de la reconnaissance par expediteur."""

    nom: str = ""
    expediteurs: tuple[str, ...] = ()

    def reconnait(self, expediteur: str) -> bool:
        expediteur = (expediteur or "").lower()
        return any(domaine in expediteur for domaine in self.expediteurs)

    def extraire(self, html: str) -> list[AnnonceBrute]:  # pragma: no cover
        raise NotImplementedError
