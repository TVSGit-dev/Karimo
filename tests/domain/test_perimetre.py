"""Tests du perimetre geographique (SPEC 4.5)."""

import pytest

from karimo.domain.perimetre import (
    ARRETS,
    MINUTES_SEUIL,
    SEUIL_METRES,
    arret_le_plus_proche,
    dans_perimetre,
    distance_metres,
)


class TestArrets:
    def test_les_six_arrets_du_spec(self):
        noms = {a.nom for a in ARRETS}
        assert noms == {
            "Ban Eik", "Hippodrome", "Ruisseau", "Louis Marcelis",  # tram 39
            "Stockel", "Kraainem",                                   # metro 1
        }

    def test_quatre_arrets_de_tram_et_deux_de_metro(self):
        assert sum(1 for a in ARRETS if a.ligne == "tram 39") == 4
        assert sum(1 for a in ARRETS if a.ligne == "métro 1") == 2

    def test_coordonnees_dans_la_boite_englobante(self):
        """Garde-fou sur des coordonnees posees a la main : zone Kraainem / Wezembeek."""
        for arret in ARRETS:
            assert 50.82 < arret.latitude < 50.87, arret.nom
            assert 4.44 < arret.longitude < 4.51, arret.nom

    def test_les_arrets_du_tram_39_vont_d_ouest_en_est(self):
        """Hippodrome, Ruisseau, Louis Marcelis, Ban Eik se suivent vers Wezembeek."""
        ordre = ["Hippodrome", "Ruisseau", "Louis Marcelis", "Ban Eik"]
        longitudes = [next(a.longitude for a in ARRETS if a.nom == nom) for nom in ordre]
        assert longitudes == sorted(longitudes)

    def test_les_arrets_restent_a_portee_les_uns_des_autres(self):
        """Aucun arret isole : une faute de frappe dans une coordonnee se verrait."""
        for arret in ARRETS:
            autres = [
                distance_metres(arret.latitude, arret.longitude, a.latitude, a.longitude)
                for a in ARRETS
                if a is not arret
            ]
            assert min(autres) < 2_000, arret.nom


class TestDistance:
    def test_distance_nulle(self):
        assert distance_metres(50.84, 4.48, 50.84, 4.48) == 0

    def test_distance_symetrique(self):
        aller = distance_metres(50.84, 4.46, 50.85, 4.49)
        retour = distance_metres(50.85, 4.49, 50.84, 4.46)
        assert aller == pytest.approx(retour)

    def test_un_degre_de_latitude_vaut_environ_111_km(self):
        assert distance_metres(50.0, 4.48, 51.0, 4.48) == pytest.approx(111_000, rel=0.01)


class TestArretLePlusProche:
    def test_sur_un_arret_donne_zero_metre(self):
        ban_eik = next(a for a in ARRETS if a.nom == "Ban Eik")
        proche = arret_le_plus_proche(ban_eik.latitude, ban_eik.longitude)
        assert proche.arret.nom == "Ban Eik"
        assert proche.metres == 0
        assert proche.minutes == 0
        assert proche.dans_perimetre is True

    def test_bruxelles_centre_est_hors_perimetre(self):
        proche = arret_le_plus_proche(50.8466, 4.3528)
        assert proche.dans_perimetre is False
        assert proche.metres > 5_000

    def test_choisit_bien_le_plus_proche(self):
        stockel = next(a for a in ARRETS if a.nom == "Stockel")
        proche = arret_le_plus_proche(stockel.latitude + 0.0005, stockel.longitude)
        assert proche.arret.nom == "Stockel"

    def test_juste_sous_le_seuil(self):
        """~800 m au nord de Ban Eik : dans le perimetre."""
        ban_eik = next(a for a in ARRETS if a.nom == "Ban Eik")
        proche = arret_le_plus_proche(ban_eik.latitude + 0.0072, ban_eik.longitude)
        assert proche.metres < SEUIL_METRES
        assert proche.dans_perimetre is True

    def test_juste_au_dessus_du_seuil(self):
        """~1 100 m au nord de Ban Eik : hors perimetre."""
        ban_eik = next(a for a in ARRETS if a.nom == "Ban Eik")
        proche = arret_le_plus_proche(ban_eik.latitude + 0.0099, ban_eik.longitude)
        assert proche.metres > SEUIL_METRES
        assert proche.dans_perimetre is False

    def test_les_minutes_suivent_la_distance(self):
        """~890 m, soit 12 minutes arrondies au-dessus : la derniere minute utile."""
        ban_eik = next(a for a in ARRETS if a.nom == "Ban Eik")
        proche = arret_le_plus_proche(ban_eik.latitude + 0.0080, ban_eik.longitude)
        assert proche.metres <= SEUIL_METRES
        assert proche.minutes == MINUTES_SEUIL
        assert proche.dans_perimetre is True


class TestDansPerimetre:
    def test_sous_le_seuil(self):
        assert dans_perimetre(5) is True

    def test_au_seuil_exactement(self):
        assert dans_perimetre(MINUTES_SEUIL) is True

    def test_au_dessus_du_seuil(self):
        assert dans_perimetre(MINUTES_SEUIL + 1) is False

    def test_inconnu_reste_inconnu(self):
        """Une information manquante n'est pas un rejet (SPEC 9)."""
        assert dans_perimetre(None) is None
