"""Tests des montants (SPEC 9 : entiers de centimes, jamais de flottants)."""

from decimal import Decimal

import pytest

from karimo.money import (
    ESPACE_AVANT_SYMBOLE,
    SEPARATEUR_MILLIERS,
    applique_taux,
    cents_vers_decimal,
    euros,
    formate_euros,
    vers_cents,
)


def eur(texte: str) -> str:
    """Ecrit un montant attendu avec les vraies espaces insecables."""
    return texte.replace(" ", SEPARATEUR_MILLIERS).replace("_", ESPACE_AVANT_SYMBOLE)


class TestConversion:
    def test_euros_entiers(self):
        assert euros(450000) == 45_000_000

    def test_euros_avec_centimes(self):
        assert euros("1234.56") == 123_456

    def test_tout_est_entier(self):
        for valeur in (0, 1, "0.01", "1234.567", 450000):
            assert isinstance(euros(valeur), int)

    def test_arrondi_commercial_a_la_demie(self):
        assert vers_cents(Decimal("0.005")) == 1
        assert vers_cents(Decimal("0.004")) == 0

    def test_aller_retour(self):
        assert cents_vers_decimal(euros("1234.56")) == Decimal("1234.56")


class TestAppliqueTaux:
    def test_pourcentage_simple(self):
        assert applique_taux(euros(450000), Decimal("0.02")) == euros(9000)

    def test_resultat_entier(self):
        assert isinstance(applique_taux(euros(333333), Decimal("0.0115")), int)

    def test_taux_nul(self):
        assert applique_taux(euros(1000), Decimal("0")) == 0

    def test_pas_de_derive_flottante(self):
        """0,1 + 0,2 en flottants ne fait pas 0,3 : on veut l'arithmetique exacte."""
        total = applique_taux(euros(10), Decimal("0.1")) + applique_taux(
            euros(10), Decimal("0.2")
        )
        assert total == euros(3)


class TestFormatage:
    @pytest.mark.parametrize(
        "cents,attendu",
        [
            (euros(450000), eur("450 000_€")),
            (euros(1000), eur("1 000_€")),
            (euros(0), eur("0_€")),
            (euros(999), eur("999_€")),
            (-euros(18235), eur("-18 235_€")),
        ],
    )
    def test_sans_decimales(self, cents, attendu):
        assert formate_euros(cents) == attendu

    def test_avec_decimales(self):
        assert formate_euros(123_456, decimales=True) == eur("1 234,56_€")

    def test_negatif_avec_decimales(self):
        assert formate_euros(-123_456, decimales=True) == eur("-1 234,56_€")

    def test_arrondi_a_l_euro_en_affichage_compact(self):
        assert formate_euros(euros("1234.60")) == eur("1 235_€")
        assert formate_euros(euros("1234.40")) == eur("1 234_€")


def test_les_espaces_sont_insecables():
    """Un montant ne doit pas pouvoir se couper en fin de ligne."""
    rendu = formate_euros(euros(450000))
    assert " " not in rendu
    assert SEPARATEUR_MILLIERS in rendu
    assert ESPACE_AVANT_SYMBOLE in rendu
