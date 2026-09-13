"""Rappels a afficher, verifiables uniquement a la main (SPEC 4.2).

L'app ne peut pas verifier ces conditions : elle les rappelle, au moment ou le
chiffre qui en depend est sous les yeux. Le taux flamand a 2 % est applique dans
le calcul du cout ; si l'une de ces conditions n'est pas remplie, tout le calcul
est faux de plusieurs milliers d'euros.
"""

from __future__ import annotations

CONDITIONS_TAUX_FLAMAND: tuple[str, ...] = (
    "Achat par des personnes physiques uniquement.",
    "Aucun autre bien en pleine propriété, y compris à l'étranger.",
    "Domiciliation dans les 3 ans, puis inscription maintenue au moins 1 an "
    "sans interruption (compromis signés depuis le 1er janvier 2026).",
)

TITRE_TAUX_FLAMAND = "Conditions du taux flamand à 2 % — à vérifier à la main"
