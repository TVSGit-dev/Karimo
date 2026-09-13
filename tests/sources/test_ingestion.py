"""Tests de l'orchestration (SPEC 7 et 9).

L'exigence centrale : aucune source ne doit pouvoir faire echouer l'execution
entiere. C'est l'essentiel de ce fichier.
"""

from __future__ import annotations

import pathlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from karimo.db.models import Bien, JournalExecution, hacher_url
from karimo.db.repository import creer_bien
from karimo.domain.cout import Region
from karimo.money import euros
from karimo.sources.gmail import MessageGmail
from karimo.sources.ingestion import executer
from karimo.sources.portails import AdaptateurZimmo
from karimo.sources.portails.base import AdaptateurBase, AnnonceBrute

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
MAINTENANT = datetime(2026, 9, 13, 5, 0, tzinfo=UTC)


def message(html: str, expediteur: str = "no-reply@zimmo.be", fil: str = "fil-1") -> MessageGmail:
    return MessageGmail(
        id=fil, fil_id=fil, expediteur=expediteur,
        sujet="Nouveaux biens sur Zimmo", html=html, date=MAINTENANT,
    )


class BoiteFausse:
    """Boite Gmail en memoire : l'orchestrateur se teste sans reseau."""

    def __init__(self, messages, echec_lecture=False, echec_libelle=False):
        self.messages = messages
        self.echec_lecture = echec_lecture
        self.echec_libelle = echec_libelle
        self.libelles: list[str] = []

    def messages_non_traites(self):
        if self.echec_lecture:
            raise ConnectionError("Gmail injoignable")
        return self.messages

    def marquer_traite(self, fil_id):
        if self.echec_libelle:
            raise PermissionError("Libellé refusé")
        self.libelles.append(fil_id)


class AdaptateurCasse(AdaptateurBase):
    """Un parseur qui explose : le cas que le SPEC 5.1 dit d'anticiper."""

    nom = "PortailCassé"
    expediteurs = ("casse.be",)

    def extraire(self, html):
        raise ValueError("format du mail changé sans prévenir")


class AdaptateurKraainem(AdaptateurBase):
    """Renvoie une annonce conforme, dans le perimetre."""

    nom = "PortailTest"
    expediteurs = ("test.be",)

    def __init__(self, annonces=None):
        self.annonces = annonces

    def extraire(self, html):
        if self.annonces is not None:
            return self.annonces
        return [
            AnnonceBrute(
                source=self.nom,
                url="https://test.be/bien/1",
                adresse="Avenue des Mésanges 12",
                commune="Kraainem",
                code_postal=1950,
                prix_cents=euros(430000),
                chambres=4,
                surface_habitable=165,
            )
        ]


@pytest.fixture(scope="module")
def mail_multiple() -> str:
    return (FIXTURES / "zimmo_alerte_multiple.html").read_text(encoding="utf-8")


class TestChaineComplete:
    def test_un_bien_conforme_est_enregistre(self, session):
        boite = BoiteFausse([message("", expediteur="alerte@test.be")])
        bilans = executer(session, boite, (AdaptateurKraainem(),))

        bien = session.scalar(select(Bien))
        assert bien is not None
        assert bien.commune == "Kraainem"
        assert bien.region == Region.FLANDRE
        assert bien.prix_cents == euros(430000)
        assert bilans[0].annonces_retenues == 1

    def test_le_fil_est_libelle_apres_traitement(self, session):
        boite = BoiteFausse([message("", expediteur="alerte@test.be")])
        executer(session, boite, (AdaptateurKraainem(),))
        assert boite.libelles == ["fil-1"]

    def test_le_mail_reel_zimmo_passe_de_bout_en_bout(self, session, mail_multiple):
        boite = BoiteFausse([message(mail_multiple)])
        bilans = executer(session, boite, (AdaptateurZimmo(),))

        assert bilans[0].source == "Zimmo"
        assert bilans[0].annonces_vues == 3
        # Seul Kraainem passe : Woluwe-Saint-Lambert est hors perimetre et
        # Wezembeek-Oppem n'a pas de prix.
        communes = {b.commune for b in session.scalars(select(Bien))}
        assert communes == {"Kraainem"}


class TestFiltres:
    """A l'ingestion automatique, les filtres du SPEC 7 sont bloquants."""

    def _executer_avec(self, session, annonce):
        boite = BoiteFausse([message("", expediteur="alerte@test.be")])
        return executer(session, boite, (AdaptateurKraainem([annonce]),))

    def _annonce(self, **surcharges):
        defauts = dict(
            source="PortailTest", url="https://test.be/bien/x", commune="Kraainem",
            code_postal=1950, prix_cents=euros(430000), chambres=4, surface_habitable=165,
        )
        return AnnonceBrute(**{**defauts, **surcharges})

    def test_commune_hors_perimetre_ecartee(self, session):
        self._executer_avec(session, self._annonce(commune="Anvers", code_postal=2000))
        assert session.scalar(select(Bien)) is None

    def test_region_wallonne_ecartee(self, session):
        """Ni Flandre ni Bruxelles : le bien n'est pas rattaché de force."""
        self._executer_avec(session, self._annonce(commune="Wavre", code_postal=1300))
        assert session.scalar(select(Bien)) is None

    def test_prix_trop_eleve_ecarte(self, session):
        self._executer_avec(session, self._annonce(prix_cents=euros(600000)))
        assert session.scalar(select(Bien)) is None

    def test_trop_peu_de_chambres_ecarte(self, session):
        self._executer_avec(session, self._annonce(chambres=2))
        assert session.scalar(select(Bien)) is None

    def test_surface_insuffisante_ecartee(self, session):
        self._executer_avec(session, self._annonce(surface_habitable=80))
        assert session.scalar(select(Bien)) is None

    def test_sans_prix_ecarte(self, session):
        self._executer_avec(session, self._annonce(prix_cents=None))
        assert session.scalar(select(Bien)) is None

    def test_le_fil_est_libelle_meme_quand_tout_est_ecarte(self, session):
        """SPEC 5.1 : « y compris aux biens écartés »."""
        boite = BoiteFausse([message("", expediteur="alerte@test.be")])
        executer(session, boite, (AdaptateurKraainem([self._annonce(chambres=1)]),))
        assert boite.libelles == ["fil-1"]


class TestDeduplication:
    def test_un_bien_deja_en_base_n_est_pas_recree(self, session):
        url = "https://test.be/bien/1"
        creer_bien(
            session,
            Bien(
                source="Zimmo", url=url, url_hash=hacher_url(url), commune="Kraainem",
                region=Region.FLANDRE, prix_cents=euros(430000),
                prix_initial_cents=euros(430000),
            ),
        )
        session.flush()

        boite = BoiteFausse([message("", expediteur="alerte@test.be")])
        executer(session, boite, (AdaptateurKraainem(),))

        assert len(list(session.scalars(select(Bien)))) == 1

    def test_une_baisse_de_prix_est_enregistree(self, session):
        """Une baisse est un signal fort : on ne la perd pas sous prétexte de doublon."""
        url = "https://test.be/bien/1"
        creer_bien(
            session,
            Bien(
                source="Zimmo", url=url, url_hash=hacher_url(url), commune="Kraainem",
                region=Region.FLANDRE, prix_cents=euros(450000),
                prix_initial_cents=euros(450000),
            ),
        )
        session.flush()

        boite = BoiteFausse([message("", expediteur="alerte@test.be")])
        bilans = executer(session, boite, (AdaptateurKraainem(),))

        bien = session.scalar(select(Bien))
        assert bien.prix_cents == euros(430000)
        assert bien.prix_initial_cents == euros(450000)
        assert bien.a_baisse is True
        assert bilans[0].prix_mis_a_jour == 1

    def test_la_derniere_vue_est_rafraichie(self, session):
        url = "https://test.be/bien/1"
        vieux = (MAINTENANT - timedelta(days=30)).date()
        creer_bien(
            session,
            Bien(
                source="Zimmo", url=url, url_hash=hacher_url(url), commune="Kraainem",
                region=Region.FLANDRE, prix_cents=euros(430000),
                prix_initial_cents=euros(430000),
                premiere_vue=vieux, derniere_vue=vieux,
            ),
        )
        session.flush()

        executer(session, BoiteFausse([message("", expediteur="alerte@test.be")]),
                 (AdaptateurKraainem(),))
        assert session.scalar(select(Bien)).derniere_vue == MAINTENANT.date()


class TestIsolationDesErreurs:
    """SPEC 9 : aucune source ne doit faire échouer l'exécution entière."""

    def test_un_parseur_casse_n_empeche_pas_les_autres(self, session):
        boite = BoiteFausse([
            message("", expediteur="alerte@casse.be", fil="fil-casse"),
            message("", expediteur="alerte@test.be", fil="fil-bon"),
        ])
        bilans = executer(session, boite, (AdaptateurCasse(), AdaptateurKraainem()))

        # Le bien de la source saine est bien enregistre
        assert session.scalar(select(Bien)).commune == "Kraainem"
        # L'erreur est journalisee
        casse = next(b for b in bilans if b.source == "PortailCassé")
        assert casse.en_erreur
        assert "format du mail changé" in casse.erreurs[0]

    def test_un_fil_en_erreur_n_est_pas_libelle(self, session):
        """La fenêtre de 48 h doit pouvoir le représenter au prochain passage."""
        boite = BoiteFausse([message("", expediteur="alerte@casse.be", fil="fil-casse")])
        executer(session, boite, (AdaptateurCasse(),))
        assert boite.libelles == []

    def test_une_annonce_illisible_n_emporte_pas_les_autres(self, session):
        bonne = AnnonceBrute(
            source="PortailTest", url="https://test.be/ok", commune="Kraainem",
            code_postal=1950, prix_cents=euros(430000), chambres=4, surface_habitable=165,
        )
        # url=None fera echouer le hachage de cette annonce-la, pas des autres
        mauvaise = AnnonceBrute(
            source="PortailTest", url=None, commune="Kraainem", code_postal=1950,
            prix_cents=euros(420000), chambres=4, surface_habitable=160,
        )
        boite = BoiteFausse([message("", expediteur="alerte@test.be")])
        bilans = executer(session, boite, (AdaptateurKraainem([mauvaise, bonne]),))

        assert session.scalar(select(Bien)).url == "https://test.be/ok"
        assert bilans[0].en_erreur

    def test_gmail_injoignable_ne_fait_pas_tomber_l_execution(self, session):
        bilans = executer(session, BoiteFausse([], echec_lecture=True), (AdaptateurKraainem(),))
        assert bilans[0].source == "Gmail"
        assert "Gmail injoignable" in bilans[0].erreurs[0]

    def test_un_libelle_refuse_est_journalise_mais_le_bien_reste(self, session):
        boite = BoiteFausse([message("", expediteur="alerte@test.be")], echec_libelle=True)
        bilans = executer(session, boite, (AdaptateurKraainem(),))

        assert session.scalar(select(Bien)) is not None
        assert any("Libellé non appliqué" in e for e in bilans[0].erreurs)

    def test_mail_sans_adaptateur_est_libelle_et_signale(self, session):
        """Courrier marketing d'un portail : on le libelle pour ne pas le relire."""
        boite = BoiteFausse([message("", expediteur="contact@my.immoweb.be", fil="pub")])
        bilans = executer(session, boite, (AdaptateurKraainem(),))

        assert boite.libelles == ["pub"]
        assert bilans[0].source == "Sans adaptateur"


class TestJournal:
    def test_une_ligne_de_journal_par_source(self, session):
        boite = BoiteFausse([
            message("", expediteur="alerte@casse.be", fil="a"),
            message("", expediteur="alerte@test.be", fil="b"),
        ])
        executer(session, boite, (AdaptateurCasse(), AdaptateurKraainem()))

        lignes = list(session.scalars(select(JournalExecution)))
        assert {ligne.source for ligne in lignes} == {"PortailCassé", "PortailTest"}

    def test_le_journal_porte_les_compteurs(self, session):
        boite = BoiteFausse([message("", expediteur="alerte@test.be")])
        executer(session, boite, (AdaptateurKraainem(),))

        ligne = session.scalar(select(JournalExecution))
        assert ligne.annonces_vues == 1
        assert ligne.annonces_retenues == 1
        assert ligne.en_erreur is False

    def test_le_journal_porte_les_erreurs(self, session):
        boite = BoiteFausse([message("", expediteur="alerte@casse.be")])
        executer(session, boite, (AdaptateurCasse(),))

        ligne = session.scalar(select(JournalExecution))
        assert ligne.en_erreur is True
        assert "format du mail changé" in ligne.erreurs
