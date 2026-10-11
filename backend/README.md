# AI Job Copilot — Backend

Base FastAPI minimale, sans base de données ni intégration LLM.

## Extraction structurée de CV

`POST /api/v1/cv/extract` reçoit un objet JSON :

```json
{"cv_text": "CV entièrement fictif : projet Python et formation informatique."}
```

`cv_text` est une chaîne obligatoire. Les espaces en début et fin sont supprimés
avec `strip()` avant de vérifier une longueur de 1 à 20 000 caractères inclus.
Une entrée invalide reçoit HTTP 422.

Le contrat de réponse HTTP 200 est :

```json
{"skills": ["Python"], "experiences": ["Projet fictif"], "education": []}
```

Ces trois champs sont obligatoires et contiennent des listes de chaînes ; les
listes vides sont autorisées. Cet exemple illustre uniquement le schéma.

**Aucun fournisseur LLM n'est configuré actuellement.** Une requête valide en
exécution normale retourne HTTP 503 avec :

```json
{"detail": "CV extraction service is not configured."}
```

Le endpoint et ses réponses sont décrits dans `/docs` et `/openapi.json`.
Utiliser exclusivement des CV fictifs pour cette étape, sans clés API.

Les tests injectent un `FakeExtractor` via `app.dependency_overrides`. Il retourne
un profil prédéfini et mémorise le texte reçu pour vérifier la normalisation,
sans appel réseau ni simulation de LLM. Les overrides sont restaurés après
chaque test. Les tests couvrent également la validation, les frontières de
longueur après `strip()`, les listes vides, HTTP 503 et OpenAPI. Le test `/health`
est conservé.

Voir la [note d'architecture](docs/cv-extraction.md) pour le contrat fournisseur
et son évolution vers Azure OpenAI.

## Installer les dépendances

Prérequis : [uv](https://docs.astral.sh/uv/) et Python 3.12 (version indiquée
dans `.python-version`). Depuis la racine du dépôt :

```sh
cd backend
uv sync --locked
```

Cette commande installe le package et les dépendances de développement dans
`.venv/`, à partir de `uv.lock`. Toutes les commandes suivantes sont à exécuter
depuis `backend/`.

## Lancer l'API

```sh
uv run uvicorn job_copilot_api.main:app --reload
```

L'API est disponible sur `http://127.0.0.1:8000` et sa documentation interactive
sur `http://127.0.0.1:8000/docs`.

```sh
curl http://127.0.0.1:8000/health
```

Réponse attendue : HTTP 200 avec exactement `{"status":"ok"}`.

## Tests et qualité du code

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Pour appliquer le formatage : `uv run ruff format .`.

Le code applicatif se trouve dans `src/job_copilot_api/` et les tests dans
`tests/`. `httpx` sert au `TestClient` de FastAPI ; pytest et Ruff sont des
dépendances de développement.

## Fichiers versionnés

Conserver `pyproject.toml`, `uv.lock` et `.python-version` dans Git pour reproduire
l'environnement. Après une modification des dépendances, exécuter `uv lock`
et versionner le verrouillage actualisé.

`.gitignore` exclut `.venv/`, les fichiers `.env` et `.env.*`, les clés privées
et les caches. Ne jamais placer de secrets dans le code ou les fichiers suivis.
Aucun fichier `.env` n'est nécessaire pour démarrer cette base.
