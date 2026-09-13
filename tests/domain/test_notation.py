"""Tests de la grille de notation (SPEC 4.6).

Le coeur du sujet est la notation partielle : une grille remplie a moitie doit
donner un pourcentage juste, pas un total sur 125 qui ferait passer un bon bien
pour un mauvais.
"""

import pytest

from karimo.domain.notation import (
    LIBELLES,
    POIDS,
    SCORE_MAXIMUM,
    TOTAL_POIDS,
    Critere,
    Verdict,
    calculer_score,
)


class TestGrille:
    def test_onze_criteres(self):
        assert len(POIDS) == 11
        assert len(Critere) == 11

    def test_poids_total_de_25(self):
        assert TOTAL_POIDS == 25

    def test_score_maximum_de_125(self):
        assert SCORE_MAXIMUM == 125

    def test_chaque_critere_a_un_libelle(self):
        assert set(LIBELLES) == set(Critere)

    def test_poids_du_spec(self):
        assert POIDS[Critere.DISTANCE_TRANSPORT] == 3
        assert POIDS[Critere.GARAGE] == 3
        assert POIDS[Critere.CHAMBRES] == 3
        assert POIDS[Critere.ETAT_ENERGETIQUE] == 3
        assert POIDS[Critere.TRAVAUX] == 3
        assert POIDS[Critere.JARDIN] == 2
        assert POIDS[Critere.LUMINOSITE] == 2
        assert POIDS[Critere.QUARTIER] == 2
        assert POIDS[Critere.ECOLES_COMMERCES] == 2
        assert POIDS[Critere.RANGEMENT] == 1
        assert POIDS[Critere.EXTENSION] == 1


class TestNotationComplete:
    def test_tout_a_cinq(self):
        score = calculer_score({c: 5 for c in Critere})
        assert score.obtenu == 125
        assert score.maximum == 125
        assert score.pourcentage == 100
        assert score.partielle is False
        assert score.sur_125 == 125
        assert score.verdict is Verdict.OFFRIR

    def test_tout_a_un(self):
        score = calculer_score({c: 1 for c in Critere})
        assert score.obtenu == 25
        assert score.pourcentage == 20
        assert score.partielle is False
        assert score.verdict is Verdict.PASSER

    def test_tout_a_trois(self):
        score = calculer_score({c: 3 for c in Critere})
        assert score.obtenu == 75
        assert score.pourcentage == 60
        assert score.verdict is Verdict.REVOIR


class TestNotationPartielle:
    def test_un_seul_critere(self):
        score = calculer_score({Critere.GARAGE: 4})
        # 4 * 3 = 12 sur 5 * 3 = 15
        assert score.obtenu == 12
        assert score.maximum == 15
        assert score.pourcentage == 80
        assert score.partielle is True
        assert score.criteres_notes == 1

    def test_le_maximum_ne_compte_que_les_criteres_notes(self):
        score = calculer_score({Critere.RANGEMENT: 5, Critere.EXTENSION: 5})
        assert score.maximum == 10
        assert score.pourcentage == 100

    def test_sur_125_est_masque_en_partiel(self):
        """Extrapoler un total sur 125 depuis deux criteres serait une invention."""
        score = calculer_score({Critere.GARAGE: 5, Critere.JARDIN: 5})
        assert score.sur_125 is None

    def test_grille_vide(self):
        score = calculer_score({})
        assert score.obtenu == 0
        assert score.maximum == 0
        assert score.pourcentage is None
        assert score.verdict is None
        assert score.partielle is True

    def test_les_none_sont_ignores(self):
        score = calculer_score({Critere.GARAGE: 4, Critere.JARDIN: None})
        assert score.criteres_notes == 1
        assert score.maximum == 15

    def test_une_note_basse_partielle_ne_devient_pas_bonne(self):
        """Regression : calculer sur 125 donnerait 9,6 % au lieu de 40 %."""
        score = calculer_score({Critere.DISTANCE_TRANSPORT: 2, Critere.GARAGE: 2})
        assert score.pourcentage == 40
        assert score.verdict is Verdict.PASSER


class TestSeuils:
    @pytest.mark.parametrize(
        "notes,attendu",
        [
            ({Critere.GARAGE: 2}, Verdict.PASSER),       # 40 %
            ({Critere.GARAGE: 3}, Verdict.REVOIR),       # 60 %, borne basse incluse
            ({Critere.GARAGE: 4}, Verdict.OFFRIR),       # 80 %
        ],
    )
    def test_reperes(self, notes, attendu):
        assert calculer_score(notes).verdict is attendu

    def test_borne_76_pourcent_est_encore_revoir(self):
        """95/125 = 76,0 % exactement : la borne haute est incluse dans "revoir"."""
        notes = {c: 4 for c in Critere}
        notes[Critere.DISTANCE_TRANSPORT] = 3  # poids 3 : -3 points
        notes[Critere.JARDIN] = 3              # poids 2 : -2 points
        score = calculer_score(notes)
        assert score.obtenu == 95
        assert score.pourcentage == 76
        assert score.verdict is Verdict.REVOIR

    def test_juste_au_dessus_de_76_pourcent_bascule_en_offrir(self):
        notes = {c: 4 for c in Critere}
        notes[Critere.EXTENSION] = 5  # poids 1 : 101/125 = 80,8 %
        assert calculer_score(notes).verdict is Verdict.OFFRIR


class TestNotesInvalides:
    @pytest.mark.parametrize("note", [0, 6, -1, 100])
    def test_note_hors_intervalle_refusee(self, note):
        with pytest.raises(ValueError, match="Note invalide"):
            calculer_score({Critere.GARAGE: note})
