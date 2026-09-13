"""Tests des filtres d'exclusion et de l'agregation des alertes (SPEC 7)."""

import pytest

from karimo.domain.peb import LabelPeb
from karimo.domain.qualification import (
    CHAMBRES_MIN,
    PRIX_MAX_CENTS,
    SURFACE_MIN_M2,
    Gravite,
    qualifier,
)
from karimo.money import euros

BIEN_CONFORME = dict(
    prix_cents=euros(430000),
    chambres=4,
    surface_habitable=165,
    minutes_marche=8,
    peb_label=LabelPeb.C,
    description_brute="Belle maison lumineuse, toiture refaite, cuisine équipée.",
)


def _codes(qualification, gravite=None):
    return {
        s.code for s in qualification.signaux if gravite is None or s.gravite is gravite
    }


class TestBienConforme:
    def test_aucun_signal(self):
        q = qualifier(**BIEN_CONFORME)
        assert q.signaux == []
        assert q.retenu is True


class TestExclusions:
    def test_prix_trop_eleve(self):
        q = qualifier(**{**BIEN_CONFORME, "prix_cents": PRIX_MAX_CENTS + euros(1)})
        assert "prix" in _codes(q, Gravite.EXCLUSION)
        assert q.retenu is False

    def test_prix_pile_au_plafond_passe(self):
        """500 000 EUR est la marge de negociation, pas une exclusion."""
        q = qualifier(**{**BIEN_CONFORME, "prix_cents": PRIX_MAX_CENTS})
        assert "prix" not in _codes(q)

    def test_trop_peu_de_chambres(self):
        q = qualifier(**{**BIEN_CONFORME, "chambres": CHAMBRES_MIN - 1})
        assert "chambres" in _codes(q, Gravite.EXCLUSION)

    def test_trois_chambres_passent(self):
        q = qualifier(**{**BIEN_CONFORME, "chambres": CHAMBRES_MIN})
        assert "chambres" not in _codes(q)

    def test_surface_trop_petite(self):
        q = qualifier(**{**BIEN_CONFORME, "surface_habitable": SURFACE_MIN_M2 - 1})
        assert "surface" in _codes(q, Gravite.EXCLUSION)

    def test_surface_pile_au_minimum_passe(self):
        q = qualifier(**{**BIEN_CONFORME, "surface_habitable": SURFACE_MIN_M2})
        assert "surface" not in _codes(q)

    def test_hors_perimetre(self):
        q = qualifier(**{**BIEN_CONFORME, "minutes_marche": 25})
        assert "perimetre" in _codes(q, Gravite.EXCLUSION)

    def test_plusieurs_exclusions_cumulees(self):
        q = qualifier(
            prix_cents=euros(600000),
            chambres=1,
            surface_habitable=60,
            minutes_marche=40,
            peb_label=LabelPeb.A,
        )
        assert _codes(q, Gravite.EXCLUSION) == {"prix", "chambres", "surface", "perimetre"}


class TestDonneesManquantes:
    """Une donnee absente devient une question, jamais une exclusion (SPEC 9)."""

    @pytest.mark.parametrize(
        "champ,code",
        [
            ("chambres", "chambres_inconnues"),
            ("surface_habitable", "surface_inconnue"),
            ("minutes_marche", "perimetre_inconnu"),
            ("peb_label", "peb_inconnu"),
        ],
    )
    def test_champ_absent_donne_une_alerte_pas_une_exclusion(self, champ, code):
        q = qualifier(**{**BIEN_CONFORME, champ: None})
        assert code in _codes(q, Gravite.ALERTE)
        assert q.retenu is True

    def test_bien_totalement_inconnu_reste_retenu(self):
        q = qualifier(
            prix_cents=euros(400000),
            chambres=None,
            surface_habitable=None,
            minutes_marche=None,
        )
        assert q.retenu is True
        assert q.exclusions == []


class TestPeb:
    @pytest.mark.parametrize("label", [LabelPeb.E, LabelPeb.F])
    def test_peb_e_f_alerte_mais_n_ecarte_jamais(self, label):
        """Interdiction explicite du SPEC 4.3."""
        q = qualifier(**{**BIEN_CONFORME, "peb_label": label})
        assert "peb" in _codes(q, Gravite.ALERTE)
        assert q.retenu is True
        assert q.alerte_peb is not None

    def test_la_cause_remonte(self):
        q = qualifier(
            **{**BIEN_CONFORME, "peb_label": LabelPeb.E, "peb_cause": "toiture non isolée"}
        )
        assert q.alerte_peb.cause == "toiture non isolée"

    @pytest.mark.parametrize("label", [LabelPeb.A, LabelPeb.B, LabelPeb.C, LabelPeb.D])
    def test_peb_a_d_silencieux(self, label):
        q = qualifier(**{**BIEN_CONFORME, "peb_label": label})
        assert q.alerte_peb is None
        assert "peb" not in _codes(q)


class TestTravaux:
    def test_mot_cle_leve_une_alerte_pas_une_exclusion(self):
        q = qualifier(**{**BIEN_CONFORME, "description_brute": "Maison à rénover"})
        assert "travaux" in _codes(q, Gravite.ALERTE)
        assert q.retenu is True

    def test_les_indices_sont_exposes(self):
        q = qualifier(
            **{**BIEN_CONFORME, "description_brute": "à rénover, traces d'humidité"}
        )
        assert {i.mot_cle for i in q.indices_travaux} == {"à rénover", "humidité"}

    def test_description_propre_ne_leve_rien(self):
        q = qualifier(**BIEN_CONFORME)
        assert q.indices_travaux == []
