"""Chiffrage d'une liste de biens : `python -m karimo.chiffrer`.

Point d'entree prevu pour la veille automatique. Elle collecte les annonces,
nous lui rendons les montants exacts — calcules par le module de regles, pas
approximes ailleurs. C'est l'exigence du SPEC 9 : les regles ne vivent qu'a un
seul endroit.

Lit du JSON sur l'entree standard, ecrit du JSON sur la sortie standard :

    {"plafond": 450000,
     "biens": [{"id": "casalina-123", "prix": 539000, "region": "fl",
                "notes": {"garage": 4, "jardin": 5}}]}

Les montants d'entree comme de sortie sont en euros entiers, parce que c'est
l'unite qu'affiche le carnet. A l'interieur, tout passe en centimes.

Aucun bien ne peut faire echouer le lot : un prix absent ou une region inconnue
produisent une ligne dans `erreurs`, et les autres biens sont chiffres quand
meme.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from karimo.domain.cout import Region, calculer_cout, prix_cible
from karimo.domain.notation import Critere, calculer_score
from karimo.domain.parametres import Parametres
from karimo.money import cents_vers_decimal, euros

# Le carnet ecrit « fl » et « bxl » ; le domaine parle « flandre » et « bruxelles ».
REGIONS = {
    "fl": Region.FLANDRE,
    "flandre": Region.FLANDRE,
    "vl": Region.FLANDRE,
    "bxl": Region.BRUXELLES,
    "bruxelles": Region.BRUXELLES,
    "brussel": Region.BRUXELLES,
}


def _euros_arrondis(cents: int) -> int:
    """Ramene des centimes a l'euro entier, pour l'affichage du carnet."""
    return round(float(cents_vers_decimal(cents)))


def _lire_region(valeur: Any) -> Region | None:
    if not isinstance(valeur, str):
        return None
    return REGIONS.get(valeur.strip().lower())


def _lire_notes(valeur: Any) -> dict[Critere, int]:
    """Notes de la grille, en ignorant silencieusement les criteres inconnus."""
    if not isinstance(valeur, dict):
        return {}
    notes: dict[Critere, int] = {}
    for cle, note in valeur.items():
        try:
            critere = Critere(str(cle))
        except ValueError:
            continue
        if isinstance(note, int) and 1 <= note <= 5:
            notes[critere] = note
    return notes


def chiffrer_un(bien: dict[str, Any], parametres: Parametres) -> dict[str, Any]:
    """Montants exacts pour un bien. Leve ValueError si l'entree est inexploitable."""
    prix = bien.get("prix")
    if not isinstance(prix, int | float) or prix <= 0:
        raise ValueError("prix absent ou non numérique")

    region = _lire_region(bien.get("region"))
    if region is None:
        raise ValueError(f"région inconnue : {bien.get('region')!r}")

    cout = calculer_cout(euros(str(prix)), region, parametres)

    resultat: dict[str, Any] = {
        "id": bien.get("id"),
        "region": region.value,
        "droits": _euros_arrondis(cout.droits_cents),
        "honorairesNotaire": _euros_arrondis(cout.honoraires_ttc_cents),
        "debours": _euros_arrondis(cout.debours_cents),
        "fraisAchat": _euros_arrondis(cout.frais_achat_cents),
        "emprunt": _euros_arrondis(cout.emprunt_cents),
        "fraisCredit": _euros_arrondis(cout.frais_credit_cents),
        "coutTotal": _euros_arrondis(cout.cout_total_cents),
        "mensualite": _euros_arrondis(cout.mensualite_cents),
        "ecartPlafond": _euros_arrondis(cout.ecart_plafond_cents),
        "sousPlafond": cout.sous_plafond,
        "prixCible": _euros_arrondis(prix_cible(region, parametres)),
    }

    notes = _lire_notes(bien.get("notes"))
    if notes:
        score = calculer_score(notes)
        resultat |= {
            "note": score.obtenu,
            "noteMaximum": score.maximum,
            "notePourcentage": float(score.pourcentage) if score.pourcentage else None,
            "notePartielle": score.partielle,
            "verdictNote": score.verdict.libelle if score.verdict else None,
        }

    return resultat


def chiffrer(entree: dict[str, Any]) -> dict[str, Any]:
    """Chiffre un lot. Un bien en erreur n'empêche jamais les autres."""
    defaut = Parametres()
    plafond = entree.get("plafond")
    parametres = (
        Parametres(plafond_prix_cents=euros(str(plafond)))
        if isinstance(plafond, int | float) and plafond > 0
        else defaut
    )

    biens = entree.get("biens")
    if not isinstance(biens, list):
        return {"biens": [], "erreurs": [{"id": None, "motif": "clé « biens » absente"}]}

    chiffres: list[dict[str, Any]] = []
    erreurs: list[dict[str, Any]] = []

    for brut in biens:
        if not isinstance(brut, dict):
            erreurs.append({"id": None, "motif": "entrée qui n'est pas un objet"})
            continue
        try:
            chiffres.append(chiffrer_un(brut, parametres))
        except Exception as erreur:  # noqa: BLE001 - un bien ne fait pas tomber le lot
            erreurs.append({"id": brut.get("id"), "motif": str(erreur)})

    return {
        "plafond": _euros_arrondis(parametres.plafond_prix_cents),
        "apport": _euros_arrondis(parametres.apport_cents),
        "tauxAnnuel": float(parametres.taux_annuel),
        "dureeAnnees": parametres.duree_annees,
        "biens": chiffres,
        "erreurs": erreurs,
    }


def principal(flux_entree=None, flux_sortie=None) -> int:
    flux_entree = flux_entree or sys.stdin
    flux_sortie = flux_sortie or sys.stdout

    try:
        entree = json.load(flux_entree)
    except json.JSONDecodeError as erreur:
        json.dump({"biens": [], "erreurs": [{"id": None, "motif": f"JSON invalide : {erreur}"}]},
                  flux_sortie, ensure_ascii=False)
        flux_sortie.write("\n")
        return 2

    json.dump(chiffrer(entree), flux_sortie, ensure_ascii=False, indent=2)
    flux_sortie.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
