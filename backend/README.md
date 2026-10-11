# AI Job Copilot — Backend

Base FastAPI minimale, sans base de données ni intégration LLM.

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
