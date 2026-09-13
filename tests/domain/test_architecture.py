"""Garde-fou d'architecture (SPEC 9).

"Les regles metier dans un module isole et teste. Le reste peut bouger, pas elles."

Ce test lit les imports de chaque module de karimo.domain et verifie qu'aucun ne
depend de la base, du web, ou du reseau. Sans lui, la frontiere s'erode au
premier jalon ou il sera tentant d'aller chercher un bien en base depuis une
regle — et les regles cessent d'etre testables seules.
"""

import ast
import pathlib

import karimo.domain

PAQUET = pathlib.Path(karimo.domain.__file__).parent

INTERDITS = {
    # Couches superieures
    "karimo.db",
    "karimo.web",
    "karimo.config",
    # Reseau et IO
    "requests",
    "httpx",
    "urllib",
    "urllib.request",
    "socket",
    "sqlite3",
    "sqlalchemy",
    "fastapi",
    "os",
}

AUTORISES_DANS_KARIMO = {"karimo.money", "karimo.domain"}


def _modules():
    return sorted(PAQUET.glob("*.py"))


def _imports(chemin: pathlib.Path) -> set[str]:
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    trouves: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            trouves.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            trouves.add(noeud.module)
    return trouves


def test_le_paquet_contient_bien_des_modules():
    assert len(_modules()) >= 7


def test_aucun_module_du_domaine_ne_touche_la_base_le_web_ou_le_reseau():
    fautes = []
    for chemin in _modules():
        for importe in _imports(chemin):
            racine = importe.split(".")[0]
            if importe in INTERDITS or racine in INTERDITS:
                fautes.append(f"{chemin.name} importe {importe}")
    assert fautes == [], "Le domaine doit rester pur :\n" + "\n".join(fautes)


def test_les_imports_internes_restent_dans_le_domaine_ou_money():
    fautes = []
    for chemin in _modules():
        for importe in _imports(chemin):
            if not importe.startswith("karimo"):
                continue
            if not any(importe.startswith(prefixe) for prefixe in AUTORISES_DANS_KARIMO):
                fautes.append(f"{chemin.name} importe {importe}")
    assert fautes == [], "\n".join(fautes)
