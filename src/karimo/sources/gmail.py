"""Lecture des mails d'alerte via l'API Gmail (SPEC 5.1).

Mecanisme de deduplication : un libelle `Suivi-Vus` est applique a chaque fil
traite. Chaque execution ne lit que les fils non libelles des dernieres 48 h.
La fenetre de 48 h est un filet en cas d'echec d'une execution — c'est pourquoi
un fil dont le parsing echoue n'est PAS libelle : il sera repris au prochain
passage.

Le client reel est isole derriere un protocole pour que l'orchestrateur, lui,
soit testable sans reseau ni compte Google.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

LIBELLE_SUIVI = "Suivi-Vus"
PORTAILS = ("immoweb", "zimmo", "immovlan", "realo")
FENETRE_JOURS = 2

# Requete du SPEC 5.1.
REQUETE = f"({' OR '.join(PORTAILS)}) -label:{LIBELLE_SUIVI} newer_than:{FENETRE_JOURS}d"

# Lecture des mails et modification des libelles : rien de plus.
PORTEE = ("https://www.googleapis.com/auth/gmail.modify",)


@dataclass(frozen=True)
class MessageGmail:
    """Un mail d'alerte, reduit a ce dont les adaptateurs ont besoin."""

    id: str
    fil_id: str
    expediteur: str
    sujet: str
    html: str
    date: datetime


class ClientGmail(Protocol):
    """Ce que l'orchestrateur attend d'une boite Gmail."""

    def messages_non_traites(self) -> list[MessageGmail]:
        """Mails d'alerte non encore libelles, des dernieres 48 heures."""
        ...

    def marquer_traite(self, fil_id: str) -> None:
        """Applique le libelle de suivi au fil."""
        ...


def _decoder(donnees: str) -> str:
    return base64.urlsafe_b64decode(donnees.encode("ascii")).decode("utf-8", "replace")


def _corps_html(charge: dict) -> str:
    """Extrait le corps HTML, en descendant dans les parties multipart."""
    if charge.get("mimeType") == "text/html":
        donnees = charge.get("body", {}).get("data")
        if donnees:
            return _decoder(donnees)

    for partie in charge.get("parts") or ():
        trouve = _corps_html(partie)
        if trouve:
            return trouve
    return ""


def _entete(message: dict, nom: str) -> str:
    entetes = message.get("payload", {}).get("headers", [])
    return next(
        (e.get("value", "") for e in entetes if e.get("name", "").lower() == nom.lower()),
        "",
    )


class ClientGmailReel:
    """Client Gmail en OAuth.

    Les identifiants viennent de l'environnement, jamais du depot (SPEC 9) :
        KARIMO_GMAIL_CREDENTIALS  fichier client OAuth telecharge chez Google
        KARIMO_GMAIL_TOKEN        jeton obtenu au premier consentement
    """

    def __init__(self, service=None, requete: str = REQUETE) -> None:
        self._service = service or self._connecter()
        self._requete = requete
        self._libelle_id: str | None = None

    # -- Connexion ---------------------------------------------------------

    @staticmethod
    def _connecter():
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        chemin_jeton = os.environ.get("KARIMO_GMAIL_TOKEN", "gmail_token.json")
        chemin_client = os.environ.get("KARIMO_GMAIL_CREDENTIALS", "gmail_credentials.json")

        identifiants = None
        if os.path.exists(chemin_jeton):
            identifiants = Credentials.from_authorized_user_file(chemin_jeton, list(PORTEE))

        if identifiants is None or not identifiants.valid:
            if identifiants and identifiants.expired and identifiants.refresh_token:
                identifiants.refresh(Request())
            else:
                if not os.path.exists(chemin_client):
                    raise RuntimeError(
                        f"Identifiants Gmail introuvables : {chemin_client}. "
                        "Voir KARIMO_GMAIL_CREDENTIALS dans .env.example."
                    )
                flux = InstalledAppFlow.from_client_secrets_file(chemin_client, list(PORTEE))
                identifiants = flux.run_local_server(port=0)
            with open(chemin_jeton, "w", encoding="utf-8") as fichier:
                fichier.write(identifiants.to_json())

        return build("gmail", "v1", credentials=identifiants, cache_discovery=False)

    # -- Lecture -----------------------------------------------------------

    def messages_non_traites(self) -> list[MessageGmail]:
        reponse = (
            self._service.users()
            .messages()
            .list(userId="me", q=self._requete, maxResults=100)
            .execute()
        )

        messages = []
        for entree in reponse.get("messages", []):
            brut = (
                self._service.users()
                .messages()
                .get(userId="me", id=entree["id"], format="full")
                .execute()
            )
            messages.append(
                MessageGmail(
                    id=brut["id"],
                    fil_id=brut.get("threadId", brut["id"]),
                    expediteur=_entete(brut, "From"),
                    sujet=_entete(brut, "Subject"),
                    html=_corps_html(brut.get("payload", {})),
                    date=datetime.fromtimestamp(int(brut["internalDate"]) / 1000, tz=UTC),
                )
            )
        return messages

    # -- Libelle -----------------------------------------------------------

    def _identifiant_libelle(self) -> str:
        """Identifiant du libelle de suivi, cree au besoin."""
        if self._libelle_id is not None:
            return self._libelle_id

        existants = self._service.users().labels().list(userId="me").execute()
        for libelle in existants.get("labels", []):
            if libelle.get("name") == LIBELLE_SUIVI:
                self._libelle_id = libelle["id"]
                return self._libelle_id

        cree = (
            self._service.users()
            .labels()
            .create(
                userId="me",
                body={
                    "name": LIBELLE_SUIVI,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        self._libelle_id = cree["id"]
        return self._libelle_id

    def marquer_traite(self, fil_id: str) -> None:
        self._service.users().threads().modify(
            userId="me", id=fil_id, body={"addLabelIds": [self._identifiant_libelle()]}
        ).execute()
