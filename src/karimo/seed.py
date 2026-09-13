"""Jeu de donnees d'exemple : `python -m karimo.seed`.

Trois biens choisis pour rendre visibles les trois choses que l'app doit dire
d'un coup d'oeil : l'ecart de fiscalite entre la Flandre et Bruxelles, une
baisse de prix, et un PEB qui demande une question plutot qu'un rejet.
"""

from __future__ import annotations

from datetime import date, timedelta

from karimo.db.models import Bien, Statut, hacher_url
from karimo.db.repository import creer_bien, enregistrer_prix, noter
from karimo.db.session import session_portee
from karimo.domain.cout import Region
from karimo.domain.notation import Critere
from karimo.domain.peb import LabelPeb
from karimo.domain.perimetre import arret_le_plus_proche
from karimo.money import euros

AUJOURD_HUI = date.today()


def _situer(bien: Bien) -> Bien:
    if bien.latitude is not None and bien.longitude is not None:
        proximite = arret_le_plus_proche(bien.latitude, bien.longitude)
        bien.arret_proche = proximite.arret.libelle
        bien.minutes_marche = proximite.minutes
    return bien


EXEMPLES = [
    dict(
        source="Immoweb",
        url="https://www.immoweb.be/fr/annonce/exemple-kraainem",
        adresse="Avenue des Mésanges 12",
        commune="Kraainem",
        region=Region.FLANDRE,
        latitude=50.8455,
        longitude=4.4535,
        prix=430000,
        chambres=4,
        surface_habitable=168,
        surface_terrain=420,
        peb_label=LabelPeb.C,
        peb_score=210,
        garage=True,
        statut=Statut.VISITE_PREVUE,
        telephone_agence="02 123 45 67",
        description_brute=(
            "Belle maison familiale de 168 m², quatre chambres, jardin orienté sud, "
            "garage. Toiture refaite en 2019, châssis double vitrage, chaudière à "
            "condensation récente. Cuisine équipée. Proche du métro."
        ),
        notes={
            Critere.DISTANCE_TRANSPORT: 5,
            Critere.GARAGE: 5,
            Critere.CHAMBRES: 4,
            Critere.ETAT_ENERGETIQUE: 4,
            Critere.TRAVAUX: 4,
            Critere.JARDIN: 4,
        },
    ),
    dict(
        source="Casalina",
        url="https://casalina.be/fr/a-vendre/exemple-wezembeek",
        adresse="Rue de l'Église 88",
        commune="Wezembeek-Oppem",
        region=Region.FLANDRE,
        latitude=50.8440,
        longitude=4.4905,
        prix=449000,
        prix_precedent=469000,  # baisse depuis la premiere vue
        chambres=4,
        surface_habitable=185,
        surface_terrain=610,
        peb_label=LabelPeb.E,
        peb_score=395,
        peb_cause="toiture non isolée et simple vitrage à l'arrière",
        garage=False,
        garage_potentiel=True,
        statut=Statut.A_APPELER,
        telephone_agence="02 731 00 00",
        description_brute=(
            "Maison de caractère à rafraîchir, 185 m² habitables, quatre chambres, "
            "grand jardin. Toiture à isoler, châssis d'origine à l'arrière. "
            "Chauffage central au gaz. Possibilité de créer un garage."
        ),
        notes={
            Critere.DISTANCE_TRANSPORT: 4,
            Critere.CHAMBRES: 5,
            Critere.ETAT_ENERGETIQUE: 2,
            Critere.JARDIN: 5,
        },
    ),
    dict(
        source="Latour et Petit",
        url="https://latouretpetit.be/fr/exemple-stockel",
        adresse="Avenue Orban 240",
        commune="Woluwe-Saint-Pierre",
        region=Region.BRUXELLES,
        latitude=50.8390,
        longitude=4.4655,
        prix=449000,
        chambres=3,
        surface_habitable=150,
        surface_terrain=200,
        peb_label=LabelPeb.D,
        peb_score=285,
        garage=True,
        statut=Statut.NOUVEAU,
        description_brute=(
            "Maison bruxelloise de 150 m², trois chambres, terrasse et petit jardin, "
            "garage. Électricité conforme, cuisine à rafraîchir."
        ),
        notes={},
    ),
]


def peupler() -> None:
    with session_portee() as session:
        for exemple in EXEMPLES:
            notes = exemple.pop("notes", {})
            prix = euros(exemple.pop("prix"))
            prix_precedent = exemple.pop("prix_precedent", None)
            url = exemple["url"]

            premiere_vue = AUJOURD_HUI - timedelta(days=len(EXEMPLES) * 3)
            depart = euros(prix_precedent) if prix_precedent else prix

            bien = creer_bien(
                session,
                _situer(
                    Bien(
                        **exemple,
                        prix_cents=depart,
                        prix_initial_cents=depart,
                        url_hash=hacher_url(url),
                        premiere_vue=premiere_vue,
                        derniere_vue=AUJOURD_HUI,
                    )
                ),
            )

            if prix_precedent:
                # Passe par le repository : la baisse doit laisser une trace.
                enregistrer_prix(session, bien, prix)

            for critere, note in notes.items():
                noter(session, bien, critere, note)

        session.flush()
        print(f"{len(EXEMPLES)} biens d'exemple enregistrés.")


if __name__ == "__main__":
    peupler()
