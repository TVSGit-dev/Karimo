"""Tests de l'adaptateur Zimmo, sur un mail reel enregistre en fixture (SPEC 5.1)."""

from __future__ import annotations

import json
import pathlib

import pytest

from karimo.money import euros
from karimo.sources.portails import AdaptateurZimmo, adaptateur_pour

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def mail_reel() -> str:
    return (FIXTURES / "zimmo_alerte.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def mail_multiple() -> str:
    return (FIXTURES / "zimmo_alerte_multiple.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def adaptateur() -> AdaptateurZimmo:
    return AdaptateurZimmo()


class TestReconnaissance:
    def test_reconnait_son_expediteur(self, adaptateur):
        metadonnees = json.loads((FIXTURES / "zimmo_alerte.json").read_text())
        assert adaptateur.reconnait(metadonnees["expediteur"]) is True

    @pytest.mark.parametrize(
        "expediteur",
        ["no-reply@zimmo.be", "Zimmo <no-reply@zimmo.be>", "NO-REPLY@ZIMMO.BE"],
    )
    def test_variantes_d_expediteur(self, adaptateur, expediteur):
        assert adaptateur.reconnait(expediteur) is True

    @pytest.mark.parametrize(
        "expediteur",
        ["contact@my.immoweb.be", "noreply@mail.immovlan.be", "", "quelqun@example.org"],
    )
    def test_refuse_les_autres(self, adaptateur, expediteur):
        assert adaptateur.reconnait(expediteur) is False

    def test_le_registre_route_vers_zimmo(self):
        assert adaptateur_pour("no-reply@zimmo.be").nom == "Zimmo"

    def test_le_registre_ignore_un_inconnu(self):
        assert adaptateur_pour("noreply@realomail.com") is None


class TestMailReel:
    """Le mail du 13 septembre 2026 contient une annonce."""

    def test_une_annonce(self, adaptateur, mail_reel):
        assert len(adaptateur.extraire(mail_reel)) == 1

    def test_champs_extraits(self, adaptateur, mail_reel):
        annonce = adaptateur.extraire(mail_reel)[0]
        assert annonce.source == "Zimmo"
        assert annonce.titre == "Appartement à vendre"
        assert annonce.adresse == "THÉODORE DE CUYPERSTRAAT 90 D1"
        assert annonce.commune == "Woluwe-Saint-Lambert"
        assert annonce.code_postal == 1200
        assert annonce.prix_cents == euros(395000)
        assert annonce.chambres == 2
        assert annonce.surface_habitable == 89

    def test_l_url_est_debarrassee_du_suivi(self, adaptateur, mail_reel):
        """Sinon le meme bien recu deux jours de suite ferait deux url_hash."""
        url = adaptateur.extraire(mail_reel)[0].url
        assert url == "https://www.zimmo.be/fr/woluwe-saint-lambert-1200/a-vendre/appartement/LRPUN"
        assert "utm_" not in url

    def test_les_chambres_ne_sont_pas_confondues_avec_la_surface(self, adaptateur, mail_reel):
        """Piege reel : l'attribut alt vaut « Surface » pour les deux icônes."""
        annonce = adaptateur.extraire(mail_reel)[0]
        assert annonce.chambres == 2
        assert annonce.surface_habitable == 89

    def test_pas_de_photo_dans_les_alertes_zimmo(self, adaptateur, mail_reel):
        """Constat sur le mail reel : le lien photo est vide."""
        assert adaptateur.extraire(mail_reel)[0].photos is None


class TestPlusieursAnnonces:
    """Les blocs ne doivent pas deborder l'un sur l'autre."""

    def test_trois_annonces(self, adaptateur, mail_multiple):
        assert len(adaptateur.extraire(mail_multiple)) == 3

    def test_chaque_annonce_garde_ses_valeurs(self, adaptateur, mail_multiple):
        par_commune = {a.commune: a for a in adaptateur.extraire(mail_multiple)}

        assert par_commune["Woluwe-Saint-Lambert"].prix_cents == euros(395000)
        assert par_commune["Woluwe-Saint-Lambert"].surface_habitable == 89
        assert par_commune["Woluwe-Saint-Lambert"].chambres == 2

        assert par_commune["Kraainem"].prix_cents == euros(430000)
        assert par_commune["Kraainem"].surface_habitable == 168
        assert par_commune["Kraainem"].chambres == 4

        assert par_commune["Wezembeek-Oppem"].surface_habitable == 185
        assert par_commune["Wezembeek-Oppem"].chambres == 3

    def test_prix_sur_demande_ne_donne_pas_de_prix(self, adaptateur, mail_multiple):
        """« Prix sur demande » : pas de prix, surtout pas un nombre invente."""
        sans_prix = next(
            a for a in adaptateur.extraire(mail_multiple) if a.commune == "Wezembeek-Oppem"
        )
        assert sans_prix.prix_cents is None
        assert sans_prix.complete is False

    def test_les_urls_sont_distinctes(self, adaptateur, mail_multiple):
        urls = [a.url for a in adaptateur.extraire(mail_multiple)]
        assert len(set(urls)) == 3


class TestRobustesse:
    """Un mail deforme ne doit jamais lever d'exception (SPEC 5.1)."""

    @pytest.mark.parametrize(
        "html",
        [
            "",
            "<html><body></body></html>",
            "<html><body>Bonjour, rien à signaler.</body></html>",
            "<a class='listing_title'>Sans href</a>",
            "<a class='listing_title' href='https://www.zimmo.be/x'>Sans rien d'autre</a>",
            "<div><a class='listing_title' href='https://zimmo.be/fr/a-vendre/x'>Titre</a></div>",
        ],
    )
    def test_html_degrade(self, adaptateur, html):
        assert isinstance(adaptateur.extraire(html), list)

    def test_annonce_sans_prix_ni_caracteristiques(self, adaptateur):
        html = "<a class='listing_title' href='https://www.zimmo.be/fr/kraainem-1950/a-vendre/maison/X'>Maison</a>"
        annonce = adaptateur.extraire(html)[0]
        assert annonce.prix_cents is None
        assert annonce.chambres is None
        # Le repli sur l'URL retrouve tout de meme la commune.
        assert annonce.commune == "Kraainem"
        assert annonce.code_postal == 1950

    def test_html_tronque(self, adaptateur, mail_reel):
        assert isinstance(adaptateur.extraire(mail_reel[: len(mail_reel) // 2]), list)
