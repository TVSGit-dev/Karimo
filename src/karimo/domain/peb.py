"""PEB et obligation de renovation (SPEC 4.3).

En Flandre, l'acheteur d'un bien classe E ou F doit atteindre le label D dans
les 6 ans, sous peine d'une amende pouvant atteindre 5 000 EUR. L'obligation
reste due meme apres paiement de l'amende. Les primes flamandes ont ete
supprimees au 1er janvier 2026 pour les revenus moyens et eleves.

Regle la plus importante du module : ON N'ECARTE JAMAIS SUR LE SEUL LABEL.
Un E cause par une toiture non isolee et du simple vitrage reste acceptable,
ces travaux se font en habitant. Un E cause par des murs pleins non isoles ou
l'absence de chauffage central ne l'est pas. C'est la cause qui decide, pas la
lettre — donc ce module leve une alerte, il ne renvoie jamais un rejet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LabelPeb(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"


LABELS_A_RENOVER = (LabelPeb.E, LabelPeb.F)

AMENDE_MAX_EUROS = 5000
DELAI_RENOVATION_ANS = 6
LABEL_CIBLE = LabelPeb.D

MENTION_RAPPORT = "demander le rapport PEB détaillé"


@dataclass(frozen=True)
class AlertePeb:
    label: LabelPeb
    message: str
    mention: str
    cause: str | None


def evaluer_peb(label: LabelPeb | None, cause: str | None = None) -> AlertePeb | None:
    """Renvoie une alerte pour un label E ou F, None sinon.

    Un label absent ne leve pas d'alerte mais n'est pas non plus un feu vert :
    la vue affiche "PEB inconnu", ce qui est une question a poser a l'agence,
    pas une conclusion.
    """
    if label is None or label not in LABELS_A_RENOVER:
        return None

    return AlertePeb(
        label=label,
        message=(
            f"Label {label.value} : obligation d'atteindre le label "
            f"{LABEL_CIBLE.value} dans les {DELAI_RENOVATION_ANS} ans "
            f"(amende jusqu'à {AMENDE_MAX_EUROS} €, l'obligation reste due). "
            "Plus de primes flamandes depuis le 1er janvier 2026 pour les "
            "revenus moyens et élevés."
        ),
        mention=MENTION_RAPPORT,
        cause=cause,
    )
