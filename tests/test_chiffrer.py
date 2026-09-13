"""Tests du chiffrage appelé par la veille automatique.

Cette interface est le contrat entre la Routine du matin et le module de
règles. Si elle bouge, le carnet affiche des chiffres faux sans que rien ne
proteste — d'où le soin mis ici.
"""

from __future__ import annotations

import io
import json

import pytest

from karimo.chiffrer import chiffrer, chiffrer_un, principal
from karimo.domain.parametres import Parametres


def lot(*biens, plafond=None):
    entree = {"biens": list(biens)}
    if plafond is not None:
        entree["plafond"] = plafond
    return chiffrer(entree)


class TestChiffrageSimple:
    def test_un_bien_flamand(self):
        resultat = lot({"id": "x", "prix": 450000, "region": "fl"})["biens"][0]
        assert resultat["droits"] == 9000
        assert resultat["coutTotal"] == 468235
        assert resultat["mensualite"] == 1479
        assert resultat["sousPlafond"] is False

    def test_un_bien_bruxellois(self):
        resultat = lot({"id": "x", "prix": 450000, "region": "bxl"})["biens"][0]
        assert resultat["droits"] == 31250
        assert resultat["coutTotal"] == 490708

    def test_l_ecart_fiscal_saute_aux_yeux(self):
        """Le chiffre qui justifie tout : 22 250 € entre les deux régions."""
        fl = lot({"id": "a", "prix": 450000, "region": "fl"})["biens"][0]
        bxl = lot({"id": "b", "prix": 450000, "region": "bxl"})["biens"][0]
        assert bxl["droits"] - fl["droits"] == 22250

    def test_un_bien_sous_le_plafond(self):
        resultat = lot({"id": "x", "prix": 300000, "region": "fl"})["biens"][0]
        assert resultat["sousPlafond"] is True
        assert resultat["ecartPlafond"] > 0

    def test_le_prix_cible_est_fourni(self):
        """Le prix auquel négocier pour tenir le budget, frais compris."""
        assert lot({"id": "x", "prix": 500000, "region": "fl"})["biens"][0]["prixCible"] == 432311

    def test_les_postes_s_additionnent(self):
        r = lot({"id": "x", "prix": 420000, "region": "fl"})["biens"][0]
        assert r["fraisAchat"] == pytest.approx(
            r["droits"] + r["honorairesNotaire"] + r["debours"], abs=1
        )
        assert r["coutTotal"] == pytest.approx(420000 + r["fraisAchat"] + r["fraisCredit"], abs=1)


class TestRegions:
    @pytest.mark.parametrize("ecriture", ["fl", "FL", "flandre", "Flandre", "vl"])
    def test_variantes_flandre(self, ecriture):
        chiffre = lot({"id": "x", "prix": 400000, "region": ecriture})["biens"][0]
        assert chiffre["region"] == "flandre"

    @pytest.mark.parametrize("ecriture", ["bxl", "BXL", "bruxelles", "Brussel"])
    def test_variantes_bruxelles(self, ecriture):
        chiffre = lot({"id": "x", "prix": 400000, "region": ecriture})["biens"][0]
        assert chiffre["region"] == "bruxelles"

    @pytest.mark.parametrize("region", ["wallonie", "", None, 42])
    def test_region_inconnue_va_en_erreur(self, region):
        resultat = lot({"id": "x", "prix": 400000, "region": region})
        assert resultat["biens"] == []
        assert resultat["erreurs"][0]["id"] == "x"


class TestNotation:
    def test_notes_partielles(self):
        r = lot({"id": "x", "prix": 400000, "region": "fl",
                 "notes": {"garage": 4, "jardin": 5}})["biens"][0]
        assert r["note"] == 22
        assert r["noteMaximum"] == 25
        assert r["notePartielle"] is True

    def test_grille_complete(self):
        notes = {c: 4 for c in [
            "distance_transport", "garage", "chambres", "etat_energetique", "travaux",
            "jardin", "luminosite", "quartier", "ecoles_commerces", "rangement", "extension",
        ]}
        r = lot({"id": "x", "prix": 400000, "region": "fl", "notes": notes})["biens"][0]
        assert r["note"] == 100
        assert r["noteMaximum"] == 125
        assert r["notePartielle"] is False
        assert r["verdictNote"] == "Offrir vite"

    def test_sans_notes_pas_de_champ_note(self):
        assert "note" not in lot({"id": "x", "prix": 400000, "region": "fl"})["biens"][0]

    def test_critere_inconnu_ignore(self):
        r = lot({"id": "x", "prix": 400000, "region": "fl",
                 "notes": {"garage": 4, "piscine": 5}})["biens"][0]
        assert r["noteMaximum"] == 15

    @pytest.mark.parametrize("note", [0, 6, "quatre", None])
    def test_note_invalide_ignoree(self, note):
        r = lot({"id": "x", "prix": 400000, "region": "fl",
                 "notes": {"garage": 4, "jardin": note}})["biens"][0]
        assert r["noteMaximum"] == 15


class TestRobustesse:
    """Aucun bien ne doit faire tomber le lot."""

    def test_un_bien_casse_n_empeche_pas_les_autres(self):
        resultat = lot(
            {"id": "casse", "region": "fl"},
            {"id": "bon", "prix": 400000, "region": "fl"},
        )
        assert [b["id"] for b in resultat["biens"]] == ["bon"]
        assert [e["id"] for e in resultat["erreurs"]] == ["casse"]

    @pytest.mark.parametrize("prix", [None, 0, -1000, "450000", "", {}])
    def test_prix_inexploitable(self, prix):
        assert lot({"id": "x", "prix": prix, "region": "fl"})["biens"] == []

    def test_entree_qui_n_est_pas_un_objet(self):
        assert lot("pas un objet", 42)["erreurs"][0]["motif"] == "entrée qui n'est pas un objet"

    def test_cle_biens_absente(self):
        assert chiffrer({})["erreurs"][0]["motif"] == "clé « biens » absente"

    def test_lot_vide(self):
        assert chiffrer({"biens": []})["biens"] == []


class TestParametres:
    def test_le_plafond_est_surchargeable(self):
        """La Routine travaille avec un plafond ferme de 500 000 €."""
        resultat = lot({"id": "x", "prix": 430000, "region": "fl"}, plafond=500000)
        assert resultat["plafond"] == 500000
        assert resultat["biens"][0]["sousPlafond"] is True

    def test_plafond_absent_prend_le_defaut_du_spec(self):
        assert chiffrer({"biens": []})["plafond"] == 450000

    def test_les_parametres_sont_rappeles_dans_la_reponse(self):
        """Pour que le carnet puisse afficher sur quelle base il chiffre."""
        resultat = chiffrer({"biens": []})
        assert resultat["apport"] == Parametres().apport_cents // 100
        assert resultat["tauxAnnuel"] == 0.046
        assert resultat["dureeAnnees"] == 25


class TestInterfaceLigneDeCommande:
    def test_entree_sortie_json(self):
        entree = io.StringIO(json.dumps({"biens": [{"id": "x", "prix": 450000, "region": "fl"}]}))
        sortie = io.StringIO()
        assert principal(entree, sortie) == 0
        assert json.loads(sortie.getvalue())["biens"][0]["coutTotal"] == 468235

    def test_json_invalide_ne_leve_pas(self):
        sortie = io.StringIO()
        assert principal(io.StringIO("{pas du json"), sortie) == 2
        assert "JSON invalide" in json.loads(sortie.getvalue())["erreurs"][0]["motif"]

    def test_la_sortie_est_toujours_du_json(self):
        sortie = io.StringIO()
        principal(io.StringIO('{"biens": [{"id": "a"}]}'), sortie)
        json.loads(sortie.getvalue())


def test_chiffrer_un_leve_sur_entree_invalide():
    with pytest.raises(ValueError, match="prix absent"):
        chiffrer_un({"id": "x", "region": "fl"}, Parametres())
