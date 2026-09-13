"""Filtres d'exclusion et agregation des alertes (SPEC 4.3, 4.4, 4.5, 7).

Les filtres du SPEC 7 (prix > 500 000 EUR, moins de 3 chambres, moins de 110 m2,
hors perimetre) visent l'ingestion automatique des jalons 2 a 4. Au jalon 1, sur
une saisie manuelle, ils sont consultatifs : ils s'affichent en avertissement
sans bloquer, parce qu'on ajoute parfois exprès un bien limite pour le comparer.
Le mode strict existe deja, il sera branche par le cron.

Aucune de ces fonctions ne supprime ni n'ecarte : elles decrivent. Le statut
`ecarte` avec une raison reste une decision humaine (SPEC 9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from karimo.domain.communes import dans_le_perimetre
from karimo.domain.peb import AlertePeb, LabelPeb, evaluer_peb
from karimo.domain.perimetre import MINUTES_SEUIL, dans_perimetre
from karimo.domain.travaux import IndiceTravaux, detecter_travaux
from karimo.money import formate_euros

PRIX_MAX_CENTS = 500_000_00
CHAMBRES_MIN = 3
SURFACE_MIN_M2 = 110


class Gravite(StrEnum):
    """Une exclusion ferme la porte, une alerte demande une question."""

    EXCLUSION = "exclusion"
    ALERTE = "alerte"


@dataclass(frozen=True)
class Signal:
    gravite: Gravite
    code: str
    message: str


@dataclass(frozen=True)
class Qualification:
    signaux: list[Signal] = field(default_factory=list)
    alerte_peb: AlertePeb | None = None
    indices_travaux: list[IndiceTravaux] = field(default_factory=list)

    @property
    def exclusions(self) -> list[Signal]:
        return [s for s in self.signaux if s.gravite is Gravite.EXCLUSION]

    @property
    def alertes(self) -> list[Signal]:
        return [s for s in self.signaux if s.gravite is Gravite.ALERTE]

    @property
    def retenu(self) -> bool:
        """Vrai si aucun filtre d'exclusion ne se declenche."""
        return not self.exclusions


def qualifier(
    *,
    prix_cents: int,
    chambres: int | None,
    surface_habitable: int | None,
    minutes_marche: int | None,
    commune: str | None = None,
    code_postal: int | None = None,
    peb_label: LabelPeb | None = None,
    peb_cause: str | None = None,
    description_brute: str | None = None,
) -> Qualification:
    """Passe un bien au crible des filtres et des alertes.

    Une donnee manquante ne declenche jamais une exclusion : on ne peut pas
    ecarter un bien sur une information qu'on n'a pas. Elle devient une alerte,
    c'est-a-dire une question a poser a l'agence.
    """
    signaux: list[Signal] = []

    if prix_cents > PRIX_MAX_CENTS:
        signaux.append(
            Signal(
                Gravite.EXCLUSION,
                "prix",
                f"Prix supérieur à {formate_euros(PRIX_MAX_CENTS)}",
            )
        )

    if chambres is None:
        signaux.append(Signal(Gravite.ALERTE, "chambres_inconnues", "Nombre de chambres inconnu"))
    elif chambres < CHAMBRES_MIN:
        signaux.append(
            Signal(Gravite.EXCLUSION, "chambres", f"Moins de {CHAMBRES_MIN} chambres")
        )

    if surface_habitable is None:
        signaux.append(Signal(Gravite.ALERTE, "surface_inconnue", "Surface habitable inconnue"))
    elif surface_habitable < SURFACE_MIN_M2:
        signaux.append(
            Signal(Gravite.EXCLUSION, "surface", f"Moins de {SURFACE_MIN_M2} m² habitables")
        )

    # A l'ingestion automatique on connait la commune mais pas encore les
    # coordonnees : la commune suffit a ecarter ce qui est clairement hors zone.
    commune_connue = commune is not None or code_postal is not None
    if commune_connue and not dans_le_perimetre(commune, code_postal):
        signaux.append(
            Signal(
                Gravite.EXCLUSION,
                "commune",
                f"Commune hors périmètre : {commune or code_postal}",
            )
        )

    match dans_perimetre(minutes_marche):
        case None:
            if not commune_connue:
                signaux.append(
                    Signal(Gravite.ALERTE, "perimetre_inconnu", "Distance à pied non renseignée")
                )
        case False:
            signaux.append(
                Signal(
                    Gravite.EXCLUSION,
                    "perimetre",
                    f"À plus de {MINUTES_SEUIL} minutes à pied d'un arrêt",
                )
            )
        case True:
            pass

    alerte_peb = evaluer_peb(peb_label, peb_cause)
    if alerte_peb is not None:
        # Jamais une exclusion : le SPEC 4.3 l'interdit explicitement.
        signaux.append(
            Signal(Gravite.ALERTE, "peb", f"{alerte_peb.message} — {alerte_peb.mention}")
        )
    elif peb_label is None:
        signaux.append(Signal(Gravite.ALERTE, "peb_inconnu", "Label PEB inconnu"))

    indices = detecter_travaux(description_brute)
    for indice in indices:
        signaux.append(
            Signal(Gravite.ALERTE, "travaux", f"Indice de gros travaux : « {indice.mot_cle} »")
        )

    return Qualification(signaux=signaux, alerte_peb=alerte_peb, indices_travaux=indices)
