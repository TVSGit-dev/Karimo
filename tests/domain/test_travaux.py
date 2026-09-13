"""Tests de la detection d'indices de gros travaux (SPEC 4.4)."""

import pytest

from karimo.domain.travaux import MOTS_CLES_FEU_ROUGE, detecter_travaux


@pytest.mark.parametrize("mot_cle", MOTS_CLES_FEU_ROUGE)
def test_chaque_mot_cle_est_detecte(mot_cle):
    indices = detecter_travaux(f"Belle maison. {mot_cle}. Proche transports.")
    assert [i.mot_cle for i in indices] == [mot_cle]


@pytest.mark.parametrize(
    "texte,attendu",
    [
        ("Maison A RENOVER entierement", "à rénover"),
        ("maison à rénover", "à rénover"),
        ("Maison À RÉNOVER", "à rénover"),
        ("bien a renover", "à rénover"),
        ("Woning TE RENOVEREN", "te renoveren"),
        ("Présence d'humidité", "humidité"),
        ("presence d humidite", "humidité"),
        ("Traces d'AMIANTE au grenier", "amiante"),
    ],
)
def test_insensible_a_la_casse_et_aux_accents(texte, attendu):
    assert attendu in [i.mot_cle for i in detecter_travaux(texte)]


class TestFauxPositifs:
    def test_vochtvrij_ne_declenche_pas_vocht(self):
        """"vochtvrij" veut dire "sans humidite" : l'inverse du signal cherche."""
        assert detecter_travaux("Kelder volledig vochtvrij") == []

    def test_asbestvrij_ne_declenche_pas_asbest(self):
        assert detecter_travaux("Dak asbestvrij gerenoveerd") == []

    def test_mot_colle_ne_declenche_pas(self):
        assert detecter_travaux("superamiantex") == []


class TestTexteVide:
    @pytest.mark.parametrize("texte", [None, "", "   "])
    def test_pas_de_texte_pas_d_indice(self, texte):
        assert detecter_travaux(texte) == []

    def test_annonce_propre_ne_declenche_rien(self):
        texte = (
            "Magnifique maison lumineuse de 180 m², 4 chambres, jardin sud, "
            "garage, cuisine équipée récente, toiture refaite en 2020."
        )
        assert detecter_travaux(texte) == []


class TestExtraits:
    def test_l_extrait_entoure_le_mot_cle(self):
        texte = "Maison spacieuse mais à rénover, idéale pour bricoleur averti."
        indice = detecter_travaux(texte)[0]
        assert "à rénover" in indice.extrait

    def test_plusieurs_mots_cles_plusieurs_indices(self):
        texte = "Bien à rénover, gros travaux à prévoir, traces d'humidité."
        codes = {i.mot_cle for i in detecter_travaux(texte)}
        assert codes == {"à rénover", "gros travaux", "humidité"}

    def test_espaces_multiples_toleres(self):
        assert detecter_travaux("bien  à   rénover") != []
