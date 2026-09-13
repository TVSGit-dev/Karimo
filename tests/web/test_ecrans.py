"""Tests d'integration des trois ecrans (SPEC 6).

Ils verifient que la chaine complete tient debout — regle metier, base, gabarit —
pas le detail du rendu, qui bougera.
"""

from __future__ import annotations

import pytest

from karimo.db.models import Bien, Statut, hacher_url
from karimo.db.repository import creer_bien
from karimo.domain.cout import Region
from karimo.domain.notation import Critere
from karimo.domain.peb import LabelPeb
from karimo.money import euros


@pytest.fixture
def bien(session) -> Bien:
    b = creer_bien(
        session,
        Bien(
            source="Immoweb",
            url="https://www.immoweb.be/fr/annonce/test",
            url_hash=hacher_url("https://www.immoweb.be/fr/annonce/test"),
            commune="Kraainem",
            region=Region.FLANDRE,
            prix_cents=euros(430000),
            prix_initial_cents=euros(430000),
            chambres=4,
            surface_habitable=165,
            minutes_marche=6,
            peb_label=LabelPeb.C,
        ),
    )
    session.commit()
    return b


class TestListe:
    def test_liste_vide(self, client):
        reponse = client.get("/")
        assert reponse.status_code == 200
        assert "Aucun bien" in reponse.text

    def test_liste_affiche_les_colonnes_du_spec(self, client, bien):
        texte = client.get("/").text
        assert "Kraainem" in texte
        assert "Flandre" in texte          # region fiscale
        assert "Coût total" in texte
        assert "PEB C" in texte
        assert "Visite prévue" in texte or "Nouveau" in texte

    @pytest.mark.parametrize("tri", ["date", "prix", "note"])
    def test_les_tris_repondent(self, client, bien, tri):
        assert client.get(f"/?tri={tri}").status_code == 200

    def test_filtre_par_statut(self, client, bien):
        assert "Kraainem" in client.get("/?statut=nouveau").text
        assert "Kraainem" not in client.get("/?statut=ecarte").text

    def test_tri_inconnu_ne_casse_pas(self, client, bien):
        assert client.get("/?tri=nawak").status_code == 200


class TestFiche:
    def test_fiche_inconnue(self, client):
        assert client.get("/bien/999").status_code == 404

    def test_fiche_montre_le_calcul_complet(self, client, bien):
        texte = client.get(f"/bien/{bien.id}").text
        for poste in (
            "Droits d'enregistrement",
            "Honoraires du notaire",
            "Débours et frais d'acte",
            "Coût total",
            "Mensualité",
            "Écart au plafond",
        ):
            assert poste in texte, poste

    def test_fiche_rappelle_les_conditions_flamandes(self, client, bien):
        """SPEC 4.2 : le rappel doit etre la ou le chiffre qui en depend s'affiche."""
        texte = client.get(f"/bien/{bien.id}").text
        assert "taux flamand" in texte
        assert "pleine propriété" in texte

    def test_la_grille_a_55_boutons(self, client, bien):
        """11 criteres x 5 notes, tous tapables au doigt."""
        assert client.get(f"/bien/{bien.id}").text.count("bouton-note") >= 55


class TestNotation:
    def test_un_tap_enregistre_la_note(self, client, bien):
        client.post(
            f"/bien/{bien.id}/note",
            data={"critere": Critere.GARAGE.value, "note": "4"},
            follow_redirects=False,
        )
        assert "12/15" in client.get(f"/bien/{bien.id}").text

    def test_retaper_la_meme_note_l_efface(self, client, bien):
        for _ in range(2):
            client.post(
                f"/bien/{bien.id}/note",
                data={"critere": Critere.GARAGE.value, "note": "4"},
                follow_redirects=False,
            )
        assert "non notée" in client.get(f"/bien/{bien.id}").text

    def test_le_score_partiel_est_signale(self, client, bien):
        client.post(
            f"/bien/{bien.id}/note",
            data={"critere": Critere.GARAGE.value, "note": "4"},
            follow_redirects=False,
        )
        assert "partielle" in client.get(f"/bien/{bien.id}").text

    @pytest.mark.parametrize("note", ["0", "6", "99"])
    def test_note_hors_bareme_refusee(self, client, bien, note):
        reponse = client.post(
            f"/bien/{bien.id}/note",
            data={"critere": Critere.GARAGE.value, "note": note},
            follow_redirects=False,
        )
        assert reponse.status_code == 400

    def test_critere_inconnu_refuse(self, client, bien):
        reponse = client.post(
            f"/bien/{bien.id}/note",
            data={"critere": "nawak", "note": "3"},
            follow_redirects=False,
        )
        assert reponse.status_code == 400


class TestSaisie:
    def test_formulaire_de_creation(self, client):
        assert client.get("/bien/nouveau").status_code == 200

    def test_creation(self, client, session):
        reponse = client.post(
            "/bien",
            data={
                "source": "Casalina",
                "commune": "Wezembeek-Oppem",
                "region": "flandre",
                "prix": "415000",
                "chambres": "4",
                "surface_habitable": "150",
            },
            follow_redirects=False,
        )
        assert reponse.status_code == 303
        assert "Wezembeek-Oppem" in client.get("/").text

    def test_les_coordonnees_calculent_l_arret_le_plus_proche(self, client, session):
        client.post(
            "/bien",
            data={
                "source": "Manuel",
                "commune": "Wezembeek-Oppem",
                "region": "flandre",
                "prix": "415000",
                "latitude": "50.8446",
                "longitude": "4.4930",
            },
            follow_redirects=False,
        )
        cree = session.query(Bien).filter_by(commune="Wezembeek-Oppem").one()
        assert cree.arret_proche == "Ban Eik (tram 39)"
        assert cree.minutes_marche == 0

    def test_un_changement_de_prix_ecrit_l_historique(self, client, session, bien):
        client.post(
            "/bien",
            data={
                "bien_id": str(bien.id),
                "source": bien.source,
                "commune": bien.commune,
                "region": bien.region,
                "prix": "410000",
            },
            follow_redirects=False,
        )
        session.expire_all()
        rafraichi = session.get(Bien, bien.id)
        assert rafraichi.prix_cents == euros(410000)
        assert rafraichi.prix_initial_cents == euros(430000)
        assert rafraichi.a_baisse is True
        assert len(rafraichi.historique) == 2

    def test_la_baisse_se_voit_dans_la_liste(self, client, session, bien):
        client.post(
            "/bien",
            data={
                "bien_id": str(bien.id),
                "source": bien.source,
                "commune": bien.commune,
                "region": bien.region,
                "prix": "410000",
            },
            follow_redirects=False,
        )
        assert "etiquette baisse" in client.get("/").text


class TestSuivi:
    def test_ecarter_conserve_le_bien_et_sa_raison(self, client, session, bien):
        """SPEC 9 : on ne supprime jamais un bien."""
        client.post(
            f"/bien/{bien.id}/statut",
            data={"statut": Statut.ECARTE.value, "raison_ecart": "Trop de travaux"},
            follow_redirects=False,
        )
        session.expire_all()
        rafraichi = session.get(Bien, bien.id)
        assert rafraichi is not None
        assert rafraichi.statut == Statut.ECARTE
        assert rafraichi.raison_ecart == "Trop de travaux"

    def test_notes_libres(self, client, session, bien):
        client.post(
            f"/bien/{bien.id}/notes-libres",
            data={"notes_libres": "Rappeler l'agence lundi"},
            follow_redirects=False,
        )
        session.expire_all()
        assert session.get(Bien, bien.id).notes_libres == "Rappeler l'agence lundi"


class TestJournal:
    def test_journal_vide_explique_pourquoi(self, client):
        reponse = client.get("/journal")
        assert reponse.status_code == 200
        assert "jalon 2" in reponse.text
