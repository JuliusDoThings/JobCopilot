# AI Job Copilot — Backend

Backend FastAPI minimal avec extraction Azure OpenAI optionnelle, sans base de données.

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

**Sans configuration Azure**, une requête valide retourne HTTP 503 avec :

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
et les choix de l'intégration Azure OpenAI.

## Configurer Azure OpenAI en local

Le SDK `openai` utilise Responses et l'API Azure **v1 GA**, sans variable
`AZURE_OPENAI_API_VERSION`. `AZURE_OPENAI_DEPLOYMENT` désigne le nom du déploiement
(`gpt-4.1-mini` ici), pas un nom de projet Foundry. L'endpoint est celui de la
ressource, par exemple `https://your-resource.openai.azure.com`, ou son URL
complète finissant par `/openai/v1/`.

La configuration accepte uniquement les URLs HTTPS en minuscules de la forme
`https://<ressource>.openai.azure.com` ou
`https://<ressource>.services.ai.azure.com`, avec le port 443 implicite ou explicite,
et le chemin vide, `/` ou `/openai/v1/` (barre finale facultative pour ce dernier).
Les domaines arbitraires, IP, identifiants dans l'URL, paramètres et fragments
sont refusés avant de créer le client ; les redirections HTTP sont désactivées.
Les domaines personnalisés et les clouds souverains ne sont pas pris en charge
par cette liste volontairement restreinte. Le client simulé reste injectable
directement dans les tests, sans assouplir la configuration de production.

**Ni l'application ni `uv run` ne chargent automatiquement `.env`.** Aucun
chargeur dotenv n'est installé. Pour charger explicitement un fichier local,
depuis `backend/` :

```sh
cp .env.example .env
chmod 600 .env
```

Modifier `.env` dans un éditeur local avec l'endpoint de la ressource, le nom du
déploiement et la clé Azure. Les valeurs du modèle sont fictives. Ne jamais
copier la vraie clé dans une commande, un chat, une capture ou un fichier suivi.
Le fichier `.env` est ignoré par Git ; seul `.env.example` peut être versionné.

Lancer ensuite avec le chargement explicite fourni par uv :

```sh
uv run --env-file .env uvicorn job_copilot_api.main:app --reload
```

Ne pas utiliser `set -x`, `OPENAI_LOG=debug` ou des logs HTTP détaillés : les logs
de diagnostic tiers peuvent contenir des données sensibles. Notre code ne logue
ni le CV, ni la réponse brute, ni la clé. L'exemple suivant utilise uniquement
un CV fictif et n'expose pas la clé au client HTTP :

```sh
curl --fail-with-body http://127.0.0.1:8000/api/v1/cv/extract \
  -H 'Content-Type: application/json' \
  -d '{"cv_text":"CV entièrement fictif. Compétence maîtrisée : Python. Formation : licence fictive en informatique."}'
```

Avec une configuration valide et un fournisseur accessible, la réponse est HTTP
200 avec les trois listes du profil. Cet appel est **payant** et envoie le texte
à Azure. Ne pas utiliser de vrais CV pour cette expérimentation. L'authentification
Microsoft Entra ID, évitant une clé longue durée, est une évolution ultérieure.

| Situation | HTTP | Message |
| --- | --- | --- |
| Entrée invalide | 422 | Erreur de validation FastAPI |
| Configuration absente, partielle ou invalide | 503 | `CV extraction service is not configured.` |
| Connexion, quota ou indisponibilité fournisseur | 503 | `CV extraction provider is unavailable.` |
| Timeout fournisseur | 504 | `CV extraction provider timed out.` |
| Réponse invalide ou incomplète | 502 | `CV extraction provider returned an invalid response.` |
| Refus du modèle | 502 | `CV extraction was refused by the provider.` |
| Autre erreur fournisseur, dont authentification | 502 | `CV extraction failed.` |

Le client synchrone fixe `timeout=30.0`, `max_retries=1` (deux tentatives au plus)
et `max_output_tokens=2000`. Aucune boucle de retry applicative. Le timeout est
par opération réseau ; les retries et délais serveur peuvent allonger la durée
totale. Une sortie tronquée n'est pas retournée comme succès. Le SDK est verrouillé
à `openai 2.54.0`, et les tests vérifient réellement son plafond de tentatives.

## Évaluation LLM manuelle, explicitement opt-in

Les tests pytest sont déterministes et bloquent les appels HTTP externes. Ils
vérifient les contrats et les erreurs, pas la qualité sémantique du modèle.
Le fichier `evaluation/fictional_cvs.json` contient quatre CV entièrement fictifs
avec leurs compétences attendues : développeur, analyste, intentions d'apprentissage
et instructions parasites à ignorer.

Pour exécuter **quatre appels potentiellement payants**, jamais lancés par pytest
ni automatiquement en CI :

```sh
uv run --env-file .env python scripts/evaluate_cv_extraction.py --allow-paid-requests
```

Sans le drapeau, le script refuse tout appel. Il utilise uniquement le jeu fourni,
affiche les scores par identifiant et ne journalise ni CV ni réponse brute.
Un retry SDK peut augmenter le nombre de tentatives jusqu'à huit pour quatre CV.

La **précision** est la proportion de compétences extraites qui sont attendues ;
le **rappel** est la proportion de compétences attendues qui sont extraites.
Le script compare des ensembles après suppression des espaces et conversion en
minuscules, sans résoudre les synonymes. Par convention, le rappel vaut 1 si
aucune compétence n'est attendue ; la précision vaut 1 si les deux ensembles
sont vides, et 0 si aucune compétence n'est extraite alors qu'une est attendue.
Les expériences et formations ne sont pas notées dans cette évaluation initiale.

La synthèse technique indique le nombre de succès et d'échecs sur tous les cas.
La synthèse métier donne une moyenne **macro** : chaque extraction réussie pèse
autant dans la moyenne de précision et de rappel. Les échecs techniques sont
exclus de ces moyennes et leur nombre reste visible pour ne pas masquer une
couverture partielle. Sans succès, les scores sont indiqués comme indisponibles.
Les conventions sur les ensembles vides s'appliquent aussi aux moyennes.
Le code de sortie est 1 en cas d'échec technique, 0 si tous les appels ont réussi,
même si la qualité est faible. Aucun seuil de qualité n'est imposé.

Quatre exemples ne constituent pas une mesure représentative. Le schéma strict
garantit la structure, pas l'absence d'hallucination ni une défense parfaite contre
les instructions parasites. Aucun juge LLM n'est utilisé. L'accès réel dépend
de la région, de la version du déploiement, des droits et quotas Azure ; les tests
simulés ne le confirment pas.

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
