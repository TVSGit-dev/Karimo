"""Tests PEB (SPEC 4.3).

La regle a ne jamais casser : aucun label ne provoque un ecartement automatique.
"""

import pytest

from karimo.domain.peb import (
    LABEL_CIBLE,
    MENTION_RAPPORT,
    AlertePeb,
    LabelPeb,
    evaluer_peb,
)


@pytest.mark.parametrize("label", [LabelPeb.A, LabelPeb.B, LabelPeb.C, LabelPeb.D])
def test_labels_a_d_sans_alerte(label):
    assert evaluer_peb(label) is None


@pytest.mark.parametrize("label", [LabelPeb.E, LabelPeb.F])
def test_labels_e_f_levent_une_alerte(label):
    alerte = evaluer_peb(label)
    assert isinstance(alerte, AlertePeb)
    assert alerte.label is label


@pytest.mark.parametrize("label", [LabelPeb.E, LabelPeb.F])
def test_l_alerte_demande_le_rapport_detaille(label):
    assert evaluer_peb(label).mention == MENTION_RAPPORT


@pytest.mark.parametrize("label", [LabelPeb.E, LabelPeb.F])
def test_le_message_rappelle_l_obligation(label):
    message = evaluer_peb(label).message
    assert LABEL_CIBLE.value in message
    assert "6 ans" in message
    assert "5000" in message


def test_label_inconnu_ne_leve_pas_d_alerte():
    assert evaluer_peb(None) is None


def test_la_cause_est_transmise_telle_quelle():
    """C'est la cause qui decide, pas la lettre : elle doit remonter a l'ecran."""
    cause = "toiture non isolée et simple vitrage, travaux faisables en habitant"
    assert evaluer_peb(LabelPeb.E, cause).cause == cause


def test_aucun_label_ne_produit_un_rejet():
    """Verrou explicite : evaluer_peb decrit, elle ne tranche jamais."""
    for label in list(LabelPeb) + [None]:
        resultat = evaluer_peb(label)
        assert resultat is None or isinstance(resultat, AlertePeb)
