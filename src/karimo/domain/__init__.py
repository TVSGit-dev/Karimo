"""Regles metier.

Ce paquet est le coeur de l'application (SPEC 9 : "le reste peut bouger, pas elles").

Contrainte d'architecture, verifiee par tests/domain/test_architecture.py :
ce paquet n'importe rien de `karimo.db`, `karimo.web`, ni aucune bibliotheque
reseau. Toutes ses fonctions sont pures : memes entrees, memes sorties, aucun
effet de bord. C'est ce qui permet de les tester exhaustivement et de brancher
dessus, aux jalons suivants, des adaptateurs qui, eux, seront fragiles.
"""
