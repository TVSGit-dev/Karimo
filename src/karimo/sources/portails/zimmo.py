"""Adaptateur des alertes Zimmo.

Ecrit d'apres un mail reel du 13 septembre 2026, conserve anonymise dans
tests/sources/fixtures/zimmo_alerte.html. Zimmo est le premier portail branche
parce que c'est celui dont l'alerte porte reellement les donnees : url, adresse,
prix, surface et chambres sont dans le mail. (Immovlan, par comparaison, envoie
un simple renvoi vers son site, sans les annonces.)

La structure s'appuie sur des classes CSS stables :
    a.listing_title    / a.listing_address / a.listing_image_link
    span.listing_price_number
    td.listing_feature  (surface et chambres, distinguees par l'icone)

Deux pieges verifies sur le mail reel :

- L'attribut alt des icones vaut « Surface » pour les deux caracteristiques, y
  compris pour les chambres. On lit donc le nom de fichier de l'icone, jamais
  l'alt.
- Le mail ne contient aucune photo du bien : a.listing_image_link est vide, et
  les seules images sont les icones de caracteristiques et de reseaux sociaux.
  Le champ `photos` reste donc None pour cette source. Il faudra aller les
  chercher sur la fiche du bien, ce qui n'est pas du ressort de ce jalon.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from karimo.money import euros
from karimo.sources.portails.base import AdaptateurBase, AnnonceBrute

# « € 395.000 », « €1.250.000 », « 395 000 € »
MOTIF_PRIX = re.compile(r"(\d[\d.\s  ]*)")
MOTIF_SURFACE = re.compile(r"(\d+)\s*m")
MOTIF_ENTIER = re.compile(r"(\d+)")
# « THÉODORE DE CUYPERSTRAAT 90 D1, 1200 Woluwe-Saint-Lambert »
MOTIF_ADRESSE = re.compile(r"^(?P<rue>.*?),\s*(?P<cp>\d{4})\s+(?P<commune>.+)$", re.S)
# « /fr/woluwe-saint-lambert-1200/a-vendre/appartement/LRPUN »
MOTIF_URL = re.compile(r"/(?P<commune>[a-z-]+)-(?P<cp>\d{4})/a-vendre/")


def _nombre(texte: str) -> int | None:
    """Lit un entier ecrit a la belge : points ou espaces comme separateurs."""
    trouve = MOTIF_PRIX.search(texte or "")
    if trouve is None:
        return None
    chiffres = re.sub(r"[.\s  ]", "", trouve.group(1))
    return int(chiffres) if chiffres.isdigit() else None


def _url_propre(url: str) -> str:
    """Retire les parametres de suivi : ils changent a chaque envoi.

    Sans ca, le meme bien recu deux jours de suite produirait deux url_hash
    differents et donc un doublon en base.
    """
    parties = urlsplit(url)
    return f"{parties.scheme}://{parties.netloc}{parties.path}"


class AdaptateurZimmo(AdaptateurBase):
    nom = "Zimmo"
    expediteurs = ("zimmo.be",)

    def extraire(self, html: str) -> list[AnnonceBrute]:
        soupe = BeautifulSoup(html, "lxml")
        annonces: list[AnnonceBrute] = []
        vues: set[str] = set()

        for titre in soupe.select("a.listing_title"):
            url = titre.get("href")
            if not url:
                continue
            url = _url_propre(url)
            if url in vues:
                continue
            vues.add(url)

            bloc = self._bloc(titre)
            adresse, commune, code_postal = self._situer(bloc, url)

            annonces.append(
                AnnonceBrute(
                    source=self.nom,
                    url=url,
                    titre=titre.get_text(" ", strip=True) or None,
                    adresse=adresse,
                    commune=commune,
                    code_postal=code_postal,
                    prix_cents=self._prix(bloc),
                    chambres=self._caracteristique(bloc, "bedroom"),
                    surface_habitable=self._caracteristique(bloc, "surface"),
                )
            )

        return annonces

    # -- Decoupage ---------------------------------------------------------

    def _bloc(self, titre):
        """Remonte au conteneur de l'annonce.

        Les mails Zimmo sont des tableaux imbriques : on remonte jusqu'a trouver
        un ancetre qui porte a la fois le prix et l'adresse, sans jamais sortir
        du document.
        """
        noeud = titre
        for _ in range(12):
            parent = noeud.parent
            if parent is None:
                break
            noeud = parent
            if noeud.select_one("span.listing_price_number") and noeud.select_one(
                "a.listing_address"
            ):
                return noeud
        return titre.parent or titre

    # -- Champs ------------------------------------------------------------

    def _prix(self, bloc) -> int | None:
        noeud = bloc.select_one("span.listing_price_number")
        if noeud is None:
            return None
        montant = _nombre(noeud.get_text(" ", strip=True))
        # « Prix sur demande » : pas de prix, pas d'invention.
        return euros(montant) if montant else None

    def _situer(self, bloc, url: str) -> tuple[str | None, str | None, int | None]:
        """Adresse, commune et code postal, du plus fiable au plus approximatif."""
        noeud = bloc.select_one("a.listing_address")
        if noeud is not None:
            texte = noeud.get_text(" ", strip=True)
            trouve = MOTIF_ADRESSE.match(texte)
            if trouve:
                return (
                    trouve.group("rue").strip() or None,
                    trouve.group("commune").strip() or None,
                    int(trouve.group("cp")),
                )
            if texte:
                return texte, None, None

        # Repli sur l'URL, qui porte commune et code postal.
        trouve = MOTIF_URL.search(url)
        if trouve:
            commune = trouve.group("commune").replace("-", " ").title()
            return None, commune, int(trouve.group("cp"))
        return None, None, None

    def _caracteristique(self, bloc, motif_icone: str) -> int | None:
        """Lit une caracteristique en s'appuyant sur le nom de fichier de l'icone.

        L'attribut alt est inutilisable : dans le mail reel il vaut « Surface »
        aussi bien pour la surface que pour les chambres.
        """
        for cellule in bloc.select("td.listing_feature"):
            icones = " ".join(img.get("src", "") for img in cellule.select("img"))
            if motif_icone not in icones.lower():
                continue
            texte = cellule.get_text(" ", strip=True)
            motif = MOTIF_SURFACE if motif_icone == "surface" else MOTIF_ENTIER
            trouve = motif.search(texte)
            if trouve:
                return int(trouve.group(1))
        return None
