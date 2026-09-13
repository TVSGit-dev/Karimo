# Karimo

Recherche d'une maison à l'est de Bruxelles : Kraainem, Wezembeek-Oppem et
alentours. Outil personnel pour deux utilisateurs, pas de multi-tenant, pas
d'authentification.

L'application répond à deux questions que le prix affiché ne dit pas :
**ce que le bien coûte réellement** (l'écart de droits d'enregistrement entre la
Flandre et Bruxelles atteint 22 250 € sur un bien à 450 000 €) et **ce qu'il
faut aller vérifier** (PEB, travaux, périmètre).

---

## État : jalons 1 et 2 livrés

| Jalon | Contenu | État |
|---|---|---|
| 1 | Modèle de données, règles métier testées, saisie manuelle, calcul financier, grille de notation | **livré** |
| 2 | Lecture Gmail, un adaptateur de portail, déduplication par libellé | **livré** |
| 3 | Les trois autres adaptateurs de portails | à venir |
| 4 | casalina.be, puis les autres sites d'agences | à venir |
| 5 | Cron et mail récapitulatif | à venir |
| 6 | Déploiement | à venir |

À ce stade l'application remplace déjà un tableur et lit les alertes Zimmo
toute seule : elle calcule le coût réel, signale les alertes, tient la grille de
notation et journalise chaque exécution.

## Stack

Python 3.11, FastAPI, Jinja2 en rendu serveur, SQLite via SQLAlchemy 2.0,
migrations Alembic, tests pytest, gestion des dépendances par uv.

Python parce que les jalons 2 à 4 sont du parsing HTML, du scraping poli et de
l'OAuth Gmail. Rendu serveur plutôt qu'une SPA parce que l'usage principal est
le téléphone, pendant les visites : des pages qui s'affichent tout de suite,
sans build ni bundle.

## Démarrage

```bash
uv sync --extra dev
uv run alembic upgrade head
uv run pytest                        # 201 tests
uv run python -m karimo.seed         # trois biens d'exemple (facultatif)
uv run uvicorn karimo.web.app:app --reload
```

Pour lancer une lecture des mails (jalon 2) :

```bash
uv run python -m karimo.executer
```

Au premier lancement, un consentement OAuth s'ouvre dans le navigateur et le
jeton est écrit dans `KARIMO_GMAIL_TOKEN`. Les exécutions suivantes sont
silencieuses — c'est ce que le cron du jalon 5 appellera.

L'application écoute sur http://127.0.0.1:8000.

## Configuration

Tout est réglable par variables d'environnement, voir `.env.example`. Les
secrets ne sont jamais dans le dépôt.

| Variable | Défaut | Rôle |
|---|---|---|
| `KARIMO_DATABASE_URL` | `sqlite:///karimo.db` | base de données |
| `KARIMO_APPORT` | `200000` | apport disponible |
| `KARIMO_PLAFOND_PRIX` | `450000` | plafond de coût total |
| `KARIMO_TAUX_ANNUEL` | `0.046` | taux du crédit |
| `KARIMO_DUREE_ANNEES` | `25` | durée du crédit |
| `KARIMO_DEBOURS` | `1300` | débours et frais d'acte du notaire |
| `KARIMO_HONORAIRES_APPROXIMATION` | `0` | `1` pour revenir à l'approximation du SPEC |
| `KARIMO_GMAIL_CREDENTIALS` | `gmail_credentials.json` | client OAuth Google |
| `KARIMO_GMAIL_TOKEN` | `gmail_token.json` | jeton obtenu au consentement |

## Architecture

```
src/karimo/
  domain/      ← les règles métier. Fonctions pures, zéro IO, zéro accès base.
  db/          modèles SQLAlchemy, migrations, accès aux données
  sources/     lecture Gmail, adaptateurs de portail, orchestration
  web/         routes FastAPI, gabarits Jinja2, CSS
  money.py     montants en centimes entiers, formatage fr-BE
  config.py    seul endroit qui lit l'environnement
  executer.py  point d'entrée d'une exécution (appelé par le cron au jalon 5)
```

`domain/` est isolé et testé exhaustivement : c'est l'exigence transverse du
SPEC (« le reste peut bouger, pas elles »). Un test d'architecture
(`tests/domain/test_architecture.py`) lit les imports de chaque module du
domaine et échoue si l'un d'eux touche la base, le web ou le réseau — pour que
la frontière ne s'érode pas au jalon 3.

## Lecture des mails (jalon 2)

Une exécution lit les fils Gmail non porteurs du libellé `Suivi-Vus` des
dernières 48 heures, en extrait les annonces, déduplique par `url_hash`,
applique les filtres, enregistre ce qui passe, puis applique le libellé — y
compris quand tout a été écarté. La fenêtre de 48 h est un filet : un fil dont
le parsing a échoué n'est **pas** libellé, et sera repris au passage suivant.

**Zimmo d'abord, et pas Immoweb.** Le SPEC suppose que les quatre portails
envoient des mails contenant les annonces. C'est faux pour au moins l'un d'eux :
l'alerte Immovlan annonce « 37 nouveaux biens » mais ne contient aucune donnée,
seulement un lien vers le site. L'alerte Zimmo, elle, porte tout : URL, adresse,
prix, surface et chambres. C'est donc elle qui a été branchée en premier, et le
parseur est écrit contre un vrai mail conservé en fixture, anonymisé.

Deux pièges relevés sur ce mail réel et couverts par les tests : l'attribut
`alt` des icônes vaut « Surface » pour les chambres comme pour la surface (on
lit donc le nom de fichier de l'icône), et les URL portent des paramètres de
suivi qui changent à chaque envoi — non nettoyés, ils produiraient un doublon
par jour.

Ce qu'il reste à faire pour les autres portails : Immovlan demandera de visiter
le site (hors périmètre du SPEC, qui interdit de contourner les protections —
à rediscuter), Immoweb et Realo n'avaient pas encore envoyé d'alerte au moment
de l'écriture.

## Décisions à connaître

**Honoraires de notaire au barème officiel.** Le SPEC proposait l'approximation
`prix × 1,15 % + 800` en demandant de la remplacer par le barème légal s'il
était trouvable. Il l'est : tarif annexé à l'arrêté royal du 16 décembre 1950,
tranches dégressives, identique chez tous les notaires de Belgique. Le calcul
est donc décomposé en trois postes — honoraires au barème, TVA 21 %, débours et
frais d'acte — au lieu d'un seul montant agrégé. Sur 450 000 €, le total baisse
d'environ 2 900 € par rapport à l'approximation, qui surestimait.

Deux réserves, documentées dans `domain/bareme_notaire.py` :
les pourcentages intermédiaires viennent de sources secondaires (le PDF officiel
n'était pas accessible au moment de l'écriture), et l'arrêté tarifaire a été
modifié début 2026 avec des barèmes « bis » et des réductions pour les
habitations unifamiliales modestes et moyennes — soit exactement le cas visé
ici. **À confronter au simulateur officiel de notaire.be avant de s'appuyer sur
le chiffre.** Le barème vit dans une table de données isolée, remplaçable en une
ligne, et un test en or rend visible tout changement de chiffre.

**Coordonnées des arrêts estimées.** Les six arrêts (tram 39 et métro 1) ont des
coordonnées posées à la main, bonnes à quelques dizaines de mètres près. Assez
pour filtrer à 900 m, mais un bien pile sur la limite peut basculer. À reprendre
sur OpenStreetMap — voir le `TODO` dans `domain/perimetre.py`.

**Filtres d'exclusion : consultatifs à la main, bloquants à l'ingestion.** Les
filtres du SPEC (prix > 500 000 €, moins de 3 chambres, moins de 110 m², hors
périmètre) s'affichent en avertissement sans bloquer une saisie manuelle, mais
écartent bel et bien une annonce lue dans un mail.

**Périmètre par commune à l'ingestion.** Faute de coordonnées au moment de lire
un mail, le périmètre est vérifié sur la commune, exacte pour les cinq communes
du SPEC. Le géocodage Nominatim, qui donnera les minutes à pied, reste à faire.
Un code postal wallon n'est rattaché ni à la Flandre ni à Bruxelles : le bien
est écarté plutôt que classé de force.

**Ajouts au modèle du SPEC.** `latitude` / `longitude` (sans elles, chaque
recalcul de périmètre redemanderait le réseau au géocodeur du jalon 2),
`notes_libres` et `telephone_agence` (demandés par les écrans Fiche et
récapitulatif).

**Une note par critère et par bien.** La grille se met à jour, elle n'empile pas
un historique de notations. Retaper la note déjà choisie l'efface.

**Mensualité.** `taux_annuel / 12`, la convention nominale des tableaux
d'amortissement belges, et non un taux actuariel équivalent.

## Règles invariantes

- Les montants sont des entiers de centimes, jamais des flottants.
- On ne supprime jamais un bien : le statut `ecarte` avec une raison suffit.
- Aucune source ne doit pouvoir faire échouer l'exécution entière (jalon 2).
- Les secrets vivent dans l'environnement.
- Interface en français.
