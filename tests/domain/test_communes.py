"""Tests des communes du perimetre et de la region fiscale."""

import pytest

from karimo.domain.communes import (
    PERIMETRE,
    Commune,
    commune_depuis_nom,
    dans_le_perimetre,
    region_depuis_code_postal,
)
from karimo.domain.cout import Region


class TestRegionDepuisCodePostal:
    @pytest.mark.parametrize("code", [1000, 1150, 1200, 1210, 1299])
    def test_bruxelles(self, code):
        assert region_depuis_code_postal(code) is Region.BRUXELLES

    @pytest.mark.parametrize("code", [1500, 1932, 1933, 1950, 1970, 3000, 8000, 9999])
    def test_flandre(self, code):
        assert region_depuis_code_postal(code) is Region.FLANDRE

    @pytest.mark.parametrize("code", [1300, 1400, 1499, 4000, 5000, 7999])
    def test_wallonie_hors_perimetre(self, code):
        """Ni Flandre ni Bruxelles : le bien doit être écarté, pas rattaché de force."""
        assert region_depuis_code_postal(code) is None

    @pytest.mark.parametrize("code", [None, 0, 999, 10000, -1])
    def test_code_invalide(self, code):
        assert region_depuis_code_postal(code) is None

    def test_les_communes_du_perimetre_sont_coherentes(self):
        """La région déclarée doit correspondre au code postal."""
        for commune in PERIMETRE:
            assert region_depuis_code_postal(commune.code_postal) is commune.region


class TestCommuneDepuisNom:
    @pytest.mark.parametrize(
        "nom,attendu",
        [
            ("Kraainem", "Kraainem"),
            ("kraainem", "Kraainem"),
            ("KRAAINEM", "Kraainem"),
            ("Crainhem", "Kraainem"),
            ("Wezembeek-Oppem", "Wezembeek-Oppem"),
            ("Sint-Pieters-Woluwe", "Woluwe-Saint-Pierre"),
            ("Woluwe-Saint-Étienne", "Woluwe-Saint-Étienne"),
            ("Sint-Stevens-Woluwe", "Woluwe-Saint-Étienne"),
            ("Sterrebeek", "Sterrebeek"),
        ],
    )
    def test_noms_et_alias(self, nom, attendu):
        commune = commune_depuis_nom(nom)
        assert isinstance(commune, Commune)
        assert commune.nom == attendu

    @pytest.mark.parametrize("nom", [None, "", "Anvers", "Liège", "Woluwe-Saint-Lambert"])
    def test_hors_perimetre(self, nom):
        assert commune_depuis_nom(nom) is None

    def test_les_priorites_suivent_le_spec(self):
        assert commune_depuis_nom("Kraainem").priorite == 1
        assert commune_depuis_nom("Wezembeek-Oppem").priorite == 2


class TestDansLePerimetre:
    def test_par_nom(self):
        assert dans_le_perimetre(nom="Kraainem") is True

    def test_par_code_postal(self):
        assert dans_le_perimetre(code_postal=1970) is True

    def test_commune_voisine_hors_perimetre(self):
        """Woluwe-Saint-Lambert (1200) n'est pas dans les cinq communes du SPEC."""
        assert dans_le_perimetre(nom="Woluwe-Saint-Lambert", code_postal=1200) is False

    def test_rien_de_renseigne(self):
        assert dans_le_perimetre() is False
