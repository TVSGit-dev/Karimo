"""Bareme des honoraires du notaire pour une vente d'immeuble.

Source : tarif annexe a l'arrete royal du 16 decembre 1950. Les honoraires sont
degressifs par tranches et identiques chez tous les notaires de Belgique — un
notaire ne peut facturer ni plus ni moins.

Le SPEC 4.1 proposait l'approximation `prix * 0.0115 + 800` en demandant de la
remplacer par le bareme officiel s'il etait trouvable. Il l'est, et c'est ce que
fait ce module.

DEUX RESERVES, a lever avec le simulateur officiel de notaire.be :

1. Les bornes de tranches (7 500 / 17 500 / 30 000 / 45 495 / 64 095 / 250 095 EUR)
   et le taux plancher de 0,057 % au-dela de 250 095 EUR sont confirmes par
   recoupement de plusieurs sources. Les pourcentages intermediaires viennent de
   sources secondaires, le PDF officiel n'ayant pas pu etre ouvert au moment de
   l'ecriture. D'ou la table isolee ci-dessous : elle se corrige en une ligne,
   et tests/domain/test_cout.py contient un test en or qui rend tout changement
   de chiffre visible en diff.

2. TODO (2026-09) — L'arrete tarifaire a ete modifie debut 2026 : version
   consolidee du 9 fevrier 2026, introduction de baremes "bis" et de reductions
   pour les habitations unifamiliales modestes et moyennes. C'est exactement le
   cas vise par cette application, donc les honoraires reels sont peut-etre plus
   bas encore que ce que calcule cette table. A verifier sur le PDF officiel.

Attention en comparant a l'approximation du SPEC : elle agregeait honoraires et
debours dans une seule ligne. Ici les honoraires sont seuls ; les debours sont
un poste distinct de Parametres. Sur 450 000 EUR l'ecart de total est d'environ
2 900 EUR, l'approximation surestimant.
"""

from __future__ import annotations

from decimal import Decimal

from karimo.money import applique_taux

# (borne superieure de la tranche en centimes, taux applique a cette tranche).
# La derniere borne est None : elle couvre tout le solde au-dela.
TRANCHES: tuple[tuple[int | None, Decimal], ...] = (
    (7_500_00, Decimal("0.0456")),
    (17_500_00, Decimal("0.0285")),
    (30_000_00, Decimal("0.0228")),
    (45_495_00, Decimal("0.0171")),
    (64_095_00, Decimal("0.0114")),
    (250_095_00, Decimal("0.0057")),
    (None, Decimal("0.00057")),
)

# Approximation d'origine du SPEC, conservee comme point de comparaison.
APPROX_TAUX = Decimal("0.0115")
APPROX_FIXE_CENTS = 800_00


def honoraires_bareme(prix_cents: int) -> int:
    """Honoraires hors TVA, bareme officiel par tranches degressives."""
    if prix_cents <= 0:
        return 0

    total = 0
    plancher = 0
    for plafond, taux in TRANCHES:
        if plafond is None:
            assiette = max(0, prix_cents - plancher)
        else:
            assiette = max(0, min(prix_cents, plafond) - plancher)
            plancher = plafond
        if assiette:
            total += applique_taux(assiette, taux)
        if plafond is not None and prix_cents <= plafond:
            break
    return total


def honoraires_approximation(prix_cents: int) -> int:
    """Approximation du SPEC : prix * 1,15 % + 800 EUR.

    Conservee pour pouvoir confronter les deux modeles a un vrai devis de
    notaire. Elle agrege honoraires et debours, contrairement au bareme.
    """
    if prix_cents <= 0:
        return 0
    return applique_taux(prix_cents, APPROX_TAUX) + APPROX_FIXE_CENTS


def detail_tranches(prix_cents: int) -> list[tuple[int, Decimal, int]]:
    """Detail (assiette, taux, honoraires) tranche par tranche.

    Sert a afficher le calcul dans la fiche : face a un devis de notaire, on veut
    pouvoir pointer la ligne qui differe, pas seulement constater un ecart.
    """
    if prix_cents <= 0:
        return []

    lignes: list[tuple[int, Decimal, int]] = []
    plancher = 0
    for plafond, taux in TRANCHES:
        if plafond is None:
            assiette = max(0, prix_cents - plancher)
        else:
            assiette = max(0, min(prix_cents, plafond) - plancher)
            plancher = plafond
        if assiette:
            lignes.append((assiette, taux, applique_taux(assiette, taux)))
        if plafond is not None and prix_cents <= plafond:
            break
    return lignes
