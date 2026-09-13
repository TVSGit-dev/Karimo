"""Orchestration d'une execution (SPEC 7 et 9).

Sequence : lire les mails non libelles, dedoublonner par `url_hash`, appliquer
les filtres, qualifier, enregistrer, appliquer le libelle Gmail, ecrire au
journal.

Regle structurante du SPEC 9 : « Aucune source ne doit pouvoir faire echouer
l'execution entiere. Chaque adaptateur s'execute dans son propre try/catch et
journalise. » L'isolation est donc posee a deux niveaux — un mail qui explose
n'emporte pas les autres mails, et une annonce illisible n'emporte pas les
autres annonces du meme mail.

Un fil dont le traitement a echoue n'est volontairement pas libelle : la fenetre
de 48 h du SPEC 5.1 le representera au prochain passage.
"""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from karimo.db.models import Bien, JournalExecution, hacher_url
from karimo.db.repository import creer_bien, enregistrer_prix
from karimo.domain.communes import region_depuis_code_postal
from karimo.domain.qualification import qualifier
from karimo.sources.gmail import ClientGmail, MessageGmail
from karimo.sources.portails import ADAPTATEURS, Adaptateur, AnnonceBrute

journal_technique = logging.getLogger(__name__)


@dataclass
class Bilan:
    """Ce qu'une source a produit pendant une execution."""

    source: str
    annonces_vues: int = 0
    annonces_retenues: int = 0
    biens_crees: int = 0
    prix_mis_a_jour: int = 0
    erreurs: list[str] = field(default_factory=list)

    @property
    def en_erreur(self) -> bool:
        return bool(self.erreurs)


def executer(
    session: Session,
    client: ClientGmail,
    adaptateurs: tuple[Adaptateur, ...] = ADAPTATEURS,
) -> list[Bilan]:
    """Lit la boite, enregistre ce qui passe les filtres, journalise tout."""
    bilans: dict[str, Bilan] = {}

    try:
        messages = client.messages_non_traites()
    except Exception as erreur:  # noqa: BLE001 - on journalise, on n'echoue pas
        bilan = Bilan(source="Gmail", erreurs=[_resumer(erreur)])
        journal_technique.exception("Lecture de la boîte Gmail impossible")
        _ecrire_journal(session, [bilan])
        return [bilan]

    for message in messages:
        adaptateur = next((a for a in adaptateurs if a.reconnait(message.expediteur)), None)

        if adaptateur is None:
            # Mail d'un portail sans adaptateur, ou courrier marketing : on le
            # libelle pour ne pas le relire tous les jours, et on le dit.
            bilan = bilans.setdefault("Sans adaptateur", Bilan("Sans adaptateur"))
            bilan.annonces_vues += 0
            _marquer(client, message, bilan)
            continue

        bilan = bilans.setdefault(adaptateur.nom, Bilan(adaptateur.nom))
        _traiter_message(session, client, adaptateur, message, bilan)

    resultats = list(bilans.values())
    _ecrire_journal(session, resultats)
    return resultats


def _traiter_message(
    session: Session,
    client: ClientGmail,
    adaptateur: Adaptateur,
    message: MessageGmail,
    bilan: Bilan,
) -> None:
    """Traite un mail. Une erreur ici ne doit pas toucher les autres mails."""
    try:
        annonces = adaptateur.extraire(message.html)
    except Exception as erreur:  # noqa: BLE001
        # Parseur casse : on journalise et on NE libelle PAS, pour que la
        # fenetre de 48 h represente ce fil au prochain passage.
        bilan.erreurs.append(f"{message.sujet} : {_resumer(erreur)}")
        journal_technique.exception("Parsing %s impossible", adaptateur.nom)
        return

    bilan.annonces_vues += len(annonces)

    for annonce in annonces:
        try:
            if _enregistrer(session, annonce, message.date.date(), bilan):
                bilan.annonces_retenues += 1
        except Exception as erreur:  # noqa: BLE001
            # Une annonce illisible n'emporte pas les autres annonces du mail.
            bilan.erreurs.append(f"{annonce.url} : {_resumer(erreur)}")
            journal_technique.exception("Annonce %s inexploitable", annonce.url)

    # Libelle applique en fin de traitement, y compris quand tout a ete ecarte.
    _marquer(client, message, bilan)


def _enregistrer(
    session: Session, annonce: AnnonceBrute, vu_le: date, bilan: Bilan
) -> bool:
    """Cree ou met a jour un bien. Renvoie True s'il a passe les filtres."""
    url_hash = hacher_url(annonce.url)
    existant = session.scalar(select(Bien).where(Bien.url_hash == url_hash))

    if existant is not None:
        # Deja en base : on ne recree pas, mais une baisse de prix est un signal
        # fort qu'il ne faut surtout pas perdre (SPEC 3).
        existant.derniere_vue = vu_le
        if annonce.prix_cents and enregistrer_prix(session, existant, annonce.prix_cents):
            bilan.prix_mis_a_jour += 1
        return False

    region = region_depuis_code_postal(annonce.code_postal)
    if region is None:
        # Ni Flandre ni Bruxelles : hors des deux regions du SPEC.
        return False

    qualification = qualifier(
        prix_cents=annonce.prix_cents or 0,
        chambres=annonce.chambres,
        surface_habitable=annonce.surface_habitable,
        minutes_marche=None,
        commune=annonce.commune,
        code_postal=annonce.code_postal,
        description_brute=annonce.description,
    )

    # A l'ingestion automatique les filtres sont bloquants : c'est leur raison
    # d'etre (SPEC 7). En saisie manuelle ils restent consultatifs.
    if not qualification.retenu or annonce.prix_cents is None:
        return False

    creer_bien(
        session,
        Bien(
            source=annonce.source,
            url=annonce.url,
            url_hash=url_hash,
            adresse=annonce.adresse,
            commune=annonce.commune or "",
            region=region,
            prix_cents=annonce.prix_cents,
            prix_initial_cents=annonce.prix_cents,
            chambres=annonce.chambres,
            surface_habitable=annonce.surface_habitable,
            description_brute=annonce.description,
            premiere_vue=vu_le,
            derniere_vue=vu_le,
        ),
    )
    bilan.biens_crees += 1
    return True


def _marquer(client: ClientGmail, message: MessageGmail, bilan: Bilan) -> None:
    try:
        client.marquer_traite(message.fil_id)
    except Exception as erreur:  # noqa: BLE001
        # Echec du libelle : le fil sera relu demain, c'est benin, mais il faut
        # le voir dans le journal — sinon la boite se remplit en silence.
        bilan.erreurs.append(f"Libellé non appliqué sur {message.fil_id} : {_resumer(erreur)}")
        journal_technique.exception("Libellé Gmail non appliqué")


def _ecrire_journal(session: Session, bilans: list[Bilan]) -> None:
    """Une ligne de journal par source.

    Sans cet ecran, une source qui tombe en panne passe inapercue pendant des
    semaines (SPEC 6).
    """
    for bilan in bilans:
        session.add(
            JournalExecution(
                source=bilan.source,
                annonces_vues=bilan.annonces_vues,
                annonces_retenues=bilan.annonces_retenues,
                erreurs="\n".join(bilan.erreurs) or None,
            )
        )
    session.flush()


def _resumer(erreur: Exception) -> str:
    """Message court pour le journal : le detail va dans les logs techniques."""
    journal_technique.debug("%s", traceback.format_exc())
    return f"{type(erreur).__name__}: {erreur}".strip()[:500]
