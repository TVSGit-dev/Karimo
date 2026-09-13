"""Perimetre geographique (SPEC 4.5).

Critere : moins de 12 minutes a pied d'un des six arrets retenus.

Methode de la v1, telle que suggeree par le SPEC : coordonnees des arrets en
dur, distance a vol d'oiseau, 12 minutes estimees a 900 metres. C'est
approximatif — un vol d'oiseau ignore les detours, une chaussee a traverser, un
talus — mais c'est suffisant pour filtrer, et cela n'introduit aucune dependance
payante. Le geocodage de l'adresse du bien via Nominatim arrive au jalon 2 et
alimentera ces memes fonctions.

TODO (2026-09) — Les coordonnees ci-dessous sont des estimations posees a la
main, pas des relevés officiels. Elles sont bonnes a quelques dizaines de metres
pres, ce qui suffit au filtrage a 900 m mais peut faire basculer un bien
exactement sur la limite. A reprendre sur OpenStreetMap (rechercher chaque arret
et relever lat/lon), ou depuis les donnees ouvertes de la STIB. Le test
tests/domain/test_perimetre.py verifie au moins qu'elles restent dans la boite
englobante Kraainem / Wezembeek-Oppem et que l'ordre des arrets le long du
tram 39 est coherent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# 12 minutes a pied, estimees a 900 metres (SPEC 4.5) : environ 4,5 km/h.
SEUIL_METRES = 900
MINUTES_SEUIL = 12
METRES_PAR_MINUTE = SEUIL_METRES / MINUTES_SEUIL

RAYON_TERRE_METRES = 6_371_000


@dataclass(frozen=True)
class Arret:
    nom: str
    ligne: str
    latitude: float
    longitude: float

    @property
    def libelle(self) -> str:
        return f"{self.nom} ({self.ligne})"


ARRETS: tuple[Arret, ...] = (
    # Metro 1 (STIB)
    Arret("Stockel", "métro 1", 50.8397, 4.4642),
    Arret("Kraainem", "métro 1", 50.8461, 4.4520),
    # Tram 39 (STIB), d'ouest en est jusqu'au terminus de Ban Eik
    Arret("Hippodrome", "tram 39", 50.8408, 4.4714),
    Arret("Ruisseau", "tram 39", 50.8419, 4.4782),
    Arret("Louis Marcelis", "tram 39", 50.8433, 4.4855),
    Arret("Ban Eik", "tram 39", 50.8446, 4.4930),
)


@dataclass(frozen=True)
class Proximite:
    """Arret le plus proche d'un point, et ce qu'on en conclut."""

    arret: Arret
    metres: int
    minutes: int
    dans_perimetre: bool


def distance_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance a vol d'oiseau entre deux points (formule de haversine)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * RAYON_TERRE_METRES * math.asin(math.sqrt(a))


def arret_le_plus_proche(latitude: float, longitude: float) -> Proximite:
    """Arret le plus proche du point donne, avec la distance et les minutes estimees."""
    arret, metres = min(
        (
            (a, distance_metres(latitude, longitude, a.latitude, a.longitude))
            for a in ARRETS
        ),
        key=lambda couple: couple[1],
    )
    return Proximite(
        arret=arret,
        metres=round(metres),
        minutes=math.ceil(metres / METRES_PAR_MINUTE),
        dans_perimetre=metres <= SEUIL_METRES,
    )


def dans_perimetre(minutes_marche: int | None) -> bool | None:
    """Verdict a partir d'un temps de marche deja connu (saisi ou calcule).

    Renvoie None si l'information manque : c'est une inconnue, pas un rejet.
    Le SPEC 9 interdit de perdre un bien, y compris par omission.
    """
    if minutes_marche is None:
        return None
    return minutes_marche <= MINUTES_SEUIL
