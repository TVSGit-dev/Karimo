"""Point d'entree d'une execution : `python -m karimo.executer`.

C'est cette commande que le cron du jalon 5 appellera. Elle ne prend aucun
argument et n'echoue jamais sur une source : elle ecrit au journal et rend la
main, pour qu'un portail en panne n'empeche pas les autres d'etre lus.
"""

from __future__ import annotations

import logging
import sys

from karimo.db.session import session_portee
from karimo.sources.gmail import ClientGmailReel
from karimo.sources.ingestion import executer


def principal() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s"
    )

    try:
        client = ClientGmailReel()
    except Exception as erreur:  # noqa: BLE001
        # Pas de boite, pas d'execution : c'est le seul echec qui merite un code
        # de retour non nul, parce qu'il demande une action humaine.
        print(f"Connexion Gmail impossible : {erreur}", file=sys.stderr)
        return 1

    with session_portee() as session:
        bilans = executer(session, client)

    for bilan in bilans:
        etat = "ERREUR" if bilan.en_erreur else "ok"
        print(
            f"[{etat}] {bilan.source} : {bilan.annonces_vues} vue(s), "
            f"{bilan.annonces_retenues} retenue(s), {bilan.biens_crees} créé(s), "
            f"{bilan.prix_mis_a_jour} baisse(s) de prix"
        )
        for erreur in bilan.erreurs:
            print(f"        {erreur}")

    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
