"""Garde-fou d'anonymisation des fixtures (SPEC 9).

Les fixtures sont de vrais mails reçus sur la boîte dédiée, et le dépôt est
public — il doit l'être pour que la veille du matin puisse le cloner sans
identifiants. Tout ce qui identifie le destinataire doit donc avoir été retiré
avant le commit.

Ce test existe parce que l'anonymisation à la main a déjà laissé passer quelque
chose : un pixel de suivi portait encore l'identifiant de l'alerte. Au jalon 3,
trois autres mails réels arriveront ici. Mieux vaut que la machine vérifie.
"""

from __future__ import annotations

import pathlib
import re

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

# Chaînes qui ne doivent jamais entrer dans le dépôt, quelle qu'en soit la forme.
IDENTIFIANTS_INTERDITS = ("tgvshome", "vansieleghem")

# Adresses d'expéditeur publiques des portails : légitimes dans une fixture.
EXPEDITEURS_PUBLICS = re.compile(r"^(no-?reply|contact|hello|info)@", re.I)

# Chemins dont le segment suivant identifie le destinataire ou son alerte.
CHEMINS_PERSONNELS = re.compile(
    r"/(email-alert|desinscrire|unsubscribe|uitschrijven)/([^/\"'?\s]+)", re.I
)

# Charge utile encodant les critères de recherche sauvegardés.
CHARGE_RECHERCHE = re.compile(r"search=([A-Za-z0-9+/=%._-]+)")

MARQUEUR = "ANONYMISE"


def fichiers():
    return sorted(FIXTURES.glob("*.html"))


def test_il_y_a_bien_des_fixtures_a_verifier():
    assert fichiers(), "aucune fixture trouvée — le garde-fou ne vérifierait rien"


@pytest.mark.parametrize("chemin", fichiers(), ids=lambda p: p.name)
class TestAnonymisation:
    def test_aucun_identifiant_personnel(self, chemin):
        contenu = chemin.read_text(encoding="utf-8").lower()
        presents = [i for i in IDENTIFIANTS_INTERDITS if i in contenu]
        assert presents == [], f"{chemin.name} contient {presents}"

    def test_aucune_adresse_mail_privee(self, chemin):
        contenu = chemin.read_text(encoding="utf-8")
        adresses = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", contenu))
        privees = [a for a in adresses if not EXPEDITEURS_PUBLICS.match(a)]
        assert privees == [], f"{chemin.name} contient {privees}"

    def test_les_chemins_personnels_sont_neutralises(self, chemin):
        """Désinscription et identifiant d'alerte : ils désignent le destinataire."""
        contenu = chemin.read_text(encoding="utf-8")
        fuites = [
            f"/{prefixe}/{segment}"
            for prefixe, segment in CHEMINS_PERSONNELS.findall(contenu)
            if MARQUEUR not in segment
        ]
        assert fuites == [], f"{chemin.name} expose {fuites}"

    def test_les_criteres_de_recherche_sont_neutralises(self, chemin):
        """La charge base64 encode le budget, les communes et le polygone tracé."""
        contenu = chemin.read_text(encoding="utf-8")
        fuites = [
            c[:40] for c in CHARGE_RECHERCHE.findall(contenu)
            if MARQUEUR not in c and len(c) > 30
        ]
        assert fuites == [], f"{chemin.name} expose des critères : {fuites}"


def test_les_metadonnees_ne_portent_pas_le_destinataire():
    """Le JSON de métadonnées ne doit garder que l'expéditeur, jamais le destinataire."""
    import json

    for chemin in FIXTURES.glob("*.json"):
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
        interdits = {"toRecipients", "to", "destinataire", "bcc", "cc"}
        assert not (interdits & donnees.keys()), f"{chemin.name} : {interdits & donnees.keys()}"
