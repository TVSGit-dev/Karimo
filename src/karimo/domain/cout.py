"""Calcul du cout reel d'un achat (SPEC 4.1).

Le prix affiche ne dit rien du cout reel : entre la Flandre et Bruxelles,
l'ecart de droits d'enregistrement atteint 22 000 EUR sur un bien a 450 000 EUR.
C'est la raison d'etre de ce module, et la seule information que l'app doit
rendre visible sans effort.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from karimo.domain.bareme_notaire import (
    detail_tranches,
    honoraires_approximation,
    honoraires_bareme,
)
from karimo.domain.parametres import PARAMETRES_DEFAUT, Parametres
from karimo.money import applique_taux

TAUX_FLANDRE = Decimal("0.02")
TAUX_BRUXELLES = Decimal("0.125")
ABATTEMENT_BRUXELLES_CENTS = 200_000_00

MOIS_PAR_AN = 12


class Region(StrEnum):
    """Region fiscale. C'est elle qui decide des droits d'enregistrement."""

    FLANDRE = "flandre"
    BRUXELLES = "bruxelles"

    @property
    def libelle(self) -> str:
        return "Flandre" if self is Region.FLANDRE else "Bruxelles"


@dataclass(frozen=True)
class Cout:
    """Resultat complet du calcul. Tous les montants sont en centimes."""

    prix_cents: int
    region: Region

    droits_cents: int
    honoraires_ht_cents: int
    tva_honoraires_cents: int
    debours_cents: int
    frais_achat_cents: int

    emprunt_cents: int
    frais_credit_cents: int
    cout_total_cents: int
    mensualite_cents: int

    ecart_plafond_cents: int

    @property
    def sous_plafond(self) -> bool:
        """Vrai si le cout total tient sous le plafond. Affiche en vert."""
        return self.ecart_plafond_cents >= 0

    @property
    def honoraires_ttc_cents(self) -> int:
        return self.honoraires_ht_cents + self.tva_honoraires_cents

    @property
    def surcout_cents(self) -> int:
        """Tout ce qui s'ajoute au prix affiche."""
        return self.cout_total_cents - self.prix_cents


def droits_enregistrement(prix_cents: int, region: Region) -> int:
    """Droits d'enregistrement selon la region (SPEC 4.1).

    Flandre : 2 %, taux habitation propre et unique — conditions rappelees a
    l'ecran, voir domain/conditions.py.
    Bruxelles : 12,5 % avec abattement sur la premiere tranche de 200 000 EUR.
    """
    if prix_cents <= 0:
        return 0
    if region is Region.FLANDRE:
        return applique_taux(prix_cents, TAUX_FLANDRE)
    base = max(0, prix_cents - ABATTEMENT_BRUXELLES_CENTS)
    return applique_taux(base, TAUX_BRUXELLES)


def mensualite(emprunt_cents: int, taux_annuel: Decimal, duree_annees: int) -> int:
    """Annuite classique : m = C * t / (1 - (1+t)^-n), t mensuel, n en mois.

    Le taux mensuel est le taux annuel divise par 12 (convention nominale, celle
    qu'utilisent les tableaux d'amortissement des banques belges), et non un
    taux actuariel equivalent.
    """
    if emprunt_cents <= 0 or duree_annees <= 0:
        return 0

    n = duree_annees * MOIS_PAR_AN
    t = Decimal(taux_annuel) / MOIS_PAR_AN
    if t == 0:
        return applique_taux(emprunt_cents, Decimal(1) / n)

    facteur = (1 + t) ** n
    # C * t * (1+t)^n / ((1+t)^n - 1), ecrit ainsi pour rester en Decimal.
    return applique_taux(emprunt_cents, t * facteur / (facteur - 1))


def calculer_cout(
    prix_cents: int,
    region: Region,
    parametres: Parametres = PARAMETRES_DEFAUT,
) -> Cout:
    """Chaine complete : droits, frais d'achat, emprunt, credit, total, mensualite."""
    prix_cents = max(0, prix_cents)

    droits = droits_enregistrement(prix_cents, region)

    if parametres.honoraires_approximation:
        # L'approximation du SPEC agrege honoraires et debours : pas de TVA
        # separee, sinon on compterait deux fois.
        honoraires_ht = honoraires_approximation(prix_cents)
        tva = 0
    else:
        honoraires_ht = honoraires_bareme(prix_cents)
        tva = applique_taux(honoraires_ht, parametres.tva_honoraires)

    debours = parametres.debours_cents
    frais_achat = droits + honoraires_ht + tva + debours

    emprunt = max(0, prix_cents + frais_achat - parametres.apport_cents)
    frais_credit = (
        applique_taux(emprunt, parametres.frais_credit_taux) + parametres.frais_credit_fixe_cents
        if emprunt > 0
        else 0
    )

    cout_total = prix_cents + frais_achat + frais_credit

    return Cout(
        prix_cents=prix_cents,
        region=region,
        droits_cents=droits,
        honoraires_ht_cents=honoraires_ht,
        tva_honoraires_cents=tva,
        debours_cents=debours,
        frais_achat_cents=frais_achat,
        emprunt_cents=emprunt,
        frais_credit_cents=frais_credit,
        cout_total_cents=cout_total,
        mensualite_cents=mensualite(emprunt, parametres.taux_annuel, parametres.duree_annees),
        ecart_plafond_cents=parametres.plafond_prix_cents - cout_total,
    )


def detail_honoraires(prix_cents: int, parametres: Parametres = PARAMETRES_DEFAUT):
    """Detail tranche par tranche des honoraires, vide si on est en approximation."""
    if parametres.honoraires_approximation:
        return []
    return detail_tranches(prix_cents)


def prix_cible(
    region: Region,
    parametres: Parametres = PARAMETRES_DEFAUT,
) -> int:
    """Prix d'achat le plus eleve dont le cout total tient sous le plafond.

    C'est l'ecart au plafond rendu actionnable : plutot que de constater qu'un
    bien a 450 000 EUR coute en realite 468 000 EUR, on affiche le prix auquel
    il faut negocier pour tenir le budget.

    Recherche par dichotomie parce que la chaine de calcul n'est pas inversible
    proprement : le bareme est par tranches, et l'emprunt est borne a zero.
    """
    plafond = parametres.plafond_prix_cents
    if calculer_cout(0, region, parametres).cout_total_cents > plafond:
        return 0

    bas, haut = 0, plafond
    while bas < haut:
        milieu = (bas + haut + 1) // 2
        if calculer_cout(milieu, region, parametres).cout_total_cents <= plafond:
            bas = milieu
        else:
            haut = milieu - 1
    return bas
