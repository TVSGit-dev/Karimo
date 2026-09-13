"""Manipulation des montants.

Regle du SPEC 9 : les montants sont des entiers de centimes, jamais des flottants.
Les calculs intermediaires passent par Decimal, et on ne quantifie en centimes
qu'une seule fois, en fin de calcul de chaque poste.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENTS_PAR_EURO = 100

# Typographie francaise, et surtout : ces deux espaces sont insecables, donc un
# montant ne se coupe jamais en fin de ligne sur l'ecran d'un telephone.
SEPARATEUR_MILLIERS = "\u202f"  # espace fine insecable
ESPACE_AVANT_SYMBOLE = "\u00a0"  # espace insecable
SYMBOLE_EURO = "\u20ac"


def euros(montant: int | str | Decimal) -> int:
    """Convertit un montant exprime en euros vers des centimes entiers."""
    return vers_cents(Decimal(str(montant)))


def vers_cents(valeur: Decimal) -> int:
    """Quantifie un Decimal d'euros en centimes entiers (arrondi commercial)."""
    return int((valeur * CENTS_PAR_EURO).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cents_vers_decimal(cents: int) -> Decimal:
    """Repasse des centimes entiers en euros Decimal, pour un calcul intermediaire."""
    return Decimal(cents) / CENTS_PAR_EURO


def applique_taux(cents: int, taux: Decimal) -> int:
    """Applique un pourcentage a un montant en centimes, resultat en centimes.

    Le produit se fait en Decimal sur les centimes eux-memes : cela evite un
    aller-retour euros/centimes et la perte de precision qui va avec.
    """
    return int((Decimal(cents) * taux).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def formate_euros(cents: int, *, decimales: bool = False) -> str:
    """Formate des centimes a la belge : 12 345 EUR ou 12 345,67 EUR.

    Les espaces utilisees sont insecables (voir les constantes en tete de
    module) : un montant ne doit jamais se couper en fin de ligne.
    """
    signe = "-" if cents < 0 else ""
    reste = abs(cents)

    if not decimales:
        # Arrondi a l'euro pour l'affichage compact, sans rien changer au stockage.
        entier = (reste + CENTS_PAR_EURO // 2) // CENTS_PAR_EURO
        corps = f"{entier:,}".replace(",", SEPARATEUR_MILLIERS)
    else:
        entier, centimes = divmod(reste, CENTS_PAR_EURO)
        groupes = f"{entier:,}".replace(",", SEPARATEUR_MILLIERS)
        corps = f"{groupes},{centimes:02d}"

    return f"{signe}{corps}{ESPACE_AVANT_SYMBOLE}{SYMBOLE_EURO}"


def formate_pourcentage(valeur: Decimal | float, decimales: int = 1) -> str:
    """Formate un pourcentage a la francaise : virgule decimale, zeros inutiles retires.

    `Decimal("4.600")` doit s'ecrire "4,6 %" et non "4.600 %" : le format `:g`
    de Python garde les zeros significatifs d'un Decimal, ce qui n'est pas ce
    qu'on veut a l'ecran.
    """
    arrondi = Decimal(valeur).quantize(
        Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP
    )
    texte = format(arrondi.normalize(), "f")
    if "." in texte:
        texte = texte.rstrip("0").rstrip(".")
    return f"{texte.replace('.', ',')}{ESPACE_AVANT_SYMBOLE}%"
