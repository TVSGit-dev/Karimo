"""Tests du calcul de cout reel (SPEC 4.1).

Les valeurs attendues sont calculees a la main, tranche par tranche, et ecrites
en centimes. Si un chiffre bouge ici, c'est soit le bareme qui a change, soit
un bug : dans les deux cas il faut le regarder.
"""

from decimal import Decimal

import pytest

from karimo.domain.bareme_notaire import honoraires_approximation, honoraires_bareme
from karimo.domain.cout import (
    ABATTEMENT_BRUXELLES_CENTS,
    Region,
    calculer_cout,
    droits_enregistrement,
    mensualite,
    prix_cible,
)
from karimo.domain.parametres import Parametres
from karimo.money import euros


class TestDroitsEnregistrement:
    def test_flandre_2_pourcent(self):
        assert droits_enregistrement(euros(450000), Region.FLANDRE) == euros(9000)

    def test_bruxelles_abattement_sur_premiere_tranche(self):
        # (450 000 - 200 000) * 12,5 % = 31 250
        assert droits_enregistrement(euros(450000), Region.BRUXELLES) == euros(31250)

    def test_bruxelles_sous_abattement_donne_zero(self):
        assert droits_enregistrement(euros(180000), Region.BRUXELLES) == 0

    def test_bruxelles_exactement_a_l_abattement(self):
        assert droits_enregistrement(ABATTEMENT_BRUXELLES_CENTS, Region.BRUXELLES) == 0

    def test_bruxelles_un_euro_au_dessus_de_l_abattement(self):
        droits = droits_enregistrement(ABATTEMENT_BRUXELLES_CENTS + euros(1), Region.BRUXELLES)
        assert droits == euros("0.125")

    def test_prix_nul_ou_negatif(self):
        assert droits_enregistrement(0, Region.FLANDRE) == 0
        assert droits_enregistrement(-1, Region.BRUXELLES) == 0

    def test_ecart_flandre_bruxelles_a_450k(self):
        """Le chiffre qui justifie l'application : 22 250 EUR d'ecart (SPEC 1)."""
        flandre = droits_enregistrement(euros(450000), Region.FLANDRE)
        bruxelles = droits_enregistrement(euros(450000), Region.BRUXELLES)
        assert bruxelles - flandre == euros(22250)


class TestBaremeNotaire:
    def test_premiere_tranche_seule(self):
        # 7 500 * 4,56 % = 342
        assert honoraires_bareme(euros(7500)) == euros(342)

    def test_deux_premieres_tranches(self):
        # 342 + 10 000 * 2,85 % = 342 + 285
        assert honoraires_bareme(euros(17500)) == euros(627)

    def test_derniere_borne_de_tranche(self):
        # 342 + 285 + 285 + 264,96 + 212,04 + 186 000 * 0,57 %
        assert honoraires_bareme(euros(250095)) == euros("2449.20")

    def test_au_dela_de_la_derniere_borne(self):
        # 2 449,20 + 199 905 * 0,057 % = 2 449,20 + 113,95 (arrondi commercial)
        assert honoraires_bareme(euros(450000)) == euros("2563.15")

    def test_prix_nul(self):
        assert honoraires_bareme(0) == 0
        assert honoraires_bareme(-5) == 0

    def test_bareme_est_croissant(self):
        precedent = 0
        for prix in range(0, 600_000, 7_500):
            courant = honoraires_bareme(euros(prix))
            assert courant >= precedent
            precedent = courant

    def test_approximation_du_spec(self):
        # 450 000 * 1,15 % + 800 = 5 975
        assert honoraires_approximation(euros(450000)) == euros(5975)

    def test_approximation_surestime_le_bareme(self):
        """L'ecart qui a motive le remplacement : environ 2 900 EUR a 450 000.

        La comparaison honnete se fait TVA comprise, puisque l'approximation
        du SPEC agregeait honoraires et debours en un seul montant.
        """
        bareme_ttc = calculer_cout(euros(450000), Region.FLANDRE).honoraires_ttc_cents
        ecart = honoraires_approximation(euros(450000)) - bareme_ttc
        assert euros(2800) < ecart < euros(3000)


class TestMensualite:
    def test_annuite_classique(self):
        """263 401,41 EUR sur 25 ans a 4,6 % nominal : environ 1 479 EUR/mois."""
        m = mensualite(euros("263401.41"), Decimal("0.046"), 25)
        assert euros(1478) <= m <= euros(1480)

    def test_emprunt_nul(self):
        assert mensualite(0, Decimal("0.046"), 25) == 0

    def test_taux_zero_repartit_le_capital(self):
        assert mensualite(euros(120000), Decimal("0"), 10) == euros(1000)

    def test_duree_nulle(self):
        assert mensualite(euros(100000), Decimal("0.046"), 0) == 0

    def test_mensualite_baisse_quand_la_duree_augmente(self):
        courte = mensualite(euros(250000), Decimal("0.046"), 20)
        longue = mensualite(euros(250000), Decimal("0.046"), 30)
        assert longue < courte


class TestCalculerCout:
    def test_chaine_complete_flandre_450k(self):
        c = calculer_cout(euros(450000), Region.FLANDRE)

        assert c.droits_cents == euros(9000)
        assert c.honoraires_ht_cents == euros("2563.15")
        assert c.tva_honoraires_cents == euros("538.26")
        assert c.debours_cents == euros(1300)
        assert c.frais_achat_cents == euros("13401.41")
        assert c.emprunt_cents == euros("263401.41")
        assert c.frais_credit_cents == euros("4834.01")
        assert c.cout_total_cents == euros("468235.42")

    def test_frais_achat_est_la_somme_de_ses_postes(self):
        c = calculer_cout(euros(380000), Region.BRUXELLES)
        assert c.frais_achat_cents == (
            c.droits_cents + c.honoraires_ht_cents + c.tva_honoraires_cents + c.debours_cents
        )

    def test_cout_total_est_la_somme_de_ses_postes(self):
        c = calculer_cout(euros(380000), Region.BRUXELLES)
        assert c.cout_total_cents == c.prix_cents + c.frais_achat_cents + c.frais_credit_cents

    def test_apport_couvrant_tout_annule_emprunt_et_credit(self):
        p = Parametres(apport_cents=euros(1_000_000))
        c = calculer_cout(euros(300000), Region.FLANDRE, p)
        assert c.emprunt_cents == 0
        assert c.frais_credit_cents == 0
        assert c.mensualite_cents == 0

    def test_ecart_plafond_positif_sous_le_plafond(self):
        c = calculer_cout(euros(300000), Region.FLANDRE)
        assert c.ecart_plafond_cents > 0
        assert c.sous_plafond is True

    def test_ecart_plafond_negatif_au_dessus(self):
        c = calculer_cout(euros(450000), Region.FLANDRE)
        assert c.ecart_plafond_cents < 0
        assert c.sous_plafond is False

    def test_surcout_est_la_difference_au_prix_affiche(self):
        c = calculer_cout(euros(400000), Region.FLANDRE)
        assert c.surcout_cents == c.cout_total_cents - euros(400000)

    def test_prix_negatif_ramene_a_zero(self):
        c = calculer_cout(-euros(1000), Region.FLANDRE)
        assert c.prix_cents == 0
        assert c.droits_cents == 0

    def test_bruxelles_coute_plus_cher_que_la_flandre(self):
        fl = calculer_cout(euros(450000), Region.FLANDRE)
        bx = calculer_cout(euros(450000), Region.BRUXELLES)
        assert bx.cout_total_cents > fl.cout_total_cents

    def test_mode_approximation_ne_compte_pas_la_tva_deux_fois(self):
        p = Parametres(honoraires_approximation=True)
        c = calculer_cout(euros(450000), Region.FLANDRE, p)
        assert c.honoraires_ht_cents == euros(5975)
        assert c.tva_honoraires_cents == 0

    def test_parametres_sont_pris_en_compte(self):
        defaut = calculer_cout(euros(400000), Region.FLANDRE)
        cher = calculer_cout(
            euros(400000), Region.FLANDRE, Parametres(taux_annuel=Decimal("0.06"))
        )
        assert cher.mensualite_cents > defaut.mensualite_cents
        assert cher.cout_total_cents == defaut.cout_total_cents  # le taux ne change pas le total


class TestPrixCible:
    @pytest.mark.parametrize("region", list(Region))
    def test_le_prix_cible_tient_sous_le_plafond(self, region):
        p = prix_cible(region)
        assert calculer_cout(p, region).cout_total_cents <= Parametres().plafond_prix_cents

    @pytest.mark.parametrize("region", list(Region))
    def test_un_euro_de_plus_depasse_le_plafond(self, region):
        p = prix_cible(region)
        depasse = calculer_cout(p + euros(1), region).cout_total_cents
        assert depasse > Parametres().plafond_prix_cents

    def test_bruxelles_impose_de_negocier_plus_bas(self):
        assert prix_cible(Region.BRUXELLES) < prix_cible(Region.FLANDRE)


# --- Test en or -------------------------------------------------------------
# Table figee (prix en euros, region) -> cout total attendu en centimes.
# Toute retouche du bareme ou d'un parametre rend le diff visible ici.
TABLE_OR = [
    (200000, Region.FLANDRE, 21019721),
    (200000, Region.BRUXELLES, 20615721),
    (300000, Region.FLANDRE, 31360094),
    (300000, Region.BRUXELLES, 32016594),
    (400000, Region.FLANDRE, 41669060),
    (400000, Region.BRUXELLES, 43386060),
    (450000, Region.FLANDRE, 46823542),
    (450000, Region.BRUXELLES, 49070792),
    (500000, Region.FLANDRE, 51978026),
    (500000, Region.BRUXELLES, 54755526),
]


@pytest.mark.parametrize("prix,region,attendu", TABLE_OR)
def test_table_en_or(prix, region, attendu):
    assert calculer_cout(euros(prix), region).cout_total_cents == attendu
