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

## Extraction des compétences obligatoires d'une offre

`POST /api/v1/jobs/extract` accepte une requête stricte :

```json
{"job_text": "Annonce entièrement fictive. Python obligatoire. SQL apprécié."}
```

Réponse HTTP 200 illustrative :

```json
{"required_skills": ["Python"]}
```

`job_text` est une chaîne obligatoire de 1 à 20 000 caractères après `strip()`.
Les champs supplémentaires, types incorrects et textes blancs sont rejetés en
HTTP 422. La réponse stricte `JobRequirements` exige `required_skills: list[str]`
et refuse les champs supplémentaires. Une liste vide est une extraction valide
lorsqu'aucune compétence explicitement obligatoire n'est identifiable. Les
libellés extraits sont conservés, sans synonymes ni normalisation métier ; le
matching applique ensuite ses propres règles. Aucune nouvelle borne de liste ou
de longueur des compétences n'est imposée à cette sortie.

Les instructions d'extraction excluent les compétences souhaitées, facultatives,
appréciées, simplement contextuelles ou ambiguës. Une alternative non résolue
comme « Python ou Java » est omise, mais les exigences indépendantes sont
conservées : « Python ou Java, et Docker obligatoire » attend uniquement Docker.
**Cette omission peut sous-estimer les exigences réelles** : le contrat plat ne
représente pas les alternatives. Le modèle ne doit inventer aucune compétence et
les instructions parasites de l'annonce sont traitées comme des données non
fiables. Le schéma strict ne garantit pas la justesse métier ni une défense
parfaite contre ces instructions ; les tests simulés ne prouvent pas la qualité
réelle du modèle.

L'offre utilise le même déploiement `AZURE_OPENAI_DEPLOYMENT` que le CV
(`gpt-4.1-mini` prévu), la même configuration validée et la même fabrique de client.
Aucun service Azure supplémentaire. L'adaptateur offre est distinct : Responses
v1, `text_format=JobRequirements`, `store=False`, 2 000 tokens de sortie maximum,
timeout de 30 secondes par opération, un retry SDK maximum, redirections
interdites. Le client est fermé après la requête, y compris en cas d'échec.
L'application ne journalise ni annonce brute, ni réponse brute, ni clé ; ne pas
activer les logs de diagnostic HTTP/SDK contenant ces données. `store=False` ne
constitue pas une garantie générale de rétention nulle chez Azure.

| Situation | HTTP | Message public fixe |
| --- | --- | --- |
| Entrée invalide | 422 | Validation FastAPI/Pydantic |
| Configuration absente ou invalide | 503 | `Job extraction service is not configured.` |
| Connexion, quota, fournisseur indisponible | 503 | `Job extraction provider is unavailable.` |
| Timeout | 504 | `Job extraction provider timed out.` |
| Réponse invalide ou incomplète | 502 | `Job extraction provider returned an invalid response.` |
| Refus | 502 | `Job extraction was refused by the provider.` |
| Autre erreur fournisseur | 502 | `Job extraction failed.` |

### Corpus d'offres et évaluation hors ligne

`evaluation/fictional_jobs.json` contient huit annonces entièrement fictives et
leurs `expected_required_skills` : exigences explicites, souhaits, contexte,
absence d'exigences, ambiguïté, alternative avec exigence indépendante, anglais
et instruction parasite. Aucun document personnel réel n'est utilisé.

Depuis `backend/`, créer un fichier local de prédictions simulées au format :

```json
[
  {"id": "explicit", "requirements": {"required_skills": ["Python", "FastAPI"]}},
  {"id": "preferred", "requirements": {"required_skills": ["Python"]}},
  {"id": "context", "requirements": {"required_skills": ["Excel"]}},
  {"id": "none", "requirements": {"required_skills": []}},
  {"id": "ambiguous", "requirements": {"required_skills": []}},
  {"id": "alternative", "requirements": {"required_skills": ["Docker"]}},
  {"id": "english", "requirements": {"required_skills": ["Rust", "Git"]}},
  {"id": "untrusted", "requirements": {"required_skills": ["SQL"]}}
]
```

```sh
uv run python scripts/evaluate_job_extraction.py --predictions /tmp/job-predictions.json
```

En mode `--predictions`, ce script ne construit aucun client Azure et ne lit pas
la configuration Azure. Les identifiants doivent couvrir chaque cas exactement une fois ; `requirements: null` indique
un échec technique, distinct d'une liste extraite vide. Le rapport JSON imprimé
contient les scores par cas, faux positifs/négatifs et moyennes macro sur les
succès uniquement ; sans succès, les moyennes valent `null`. Les textes bruts et
détails fournisseur ne sont pas inclus. Utiliser exclusivement des prédictions
synthétiques sans secrets. Le code de sortie est 1 pour entrée invalide ou échec
technique, 0 pour succès techniques même de mauvaise qualité.

Les petites fonctions de métriques sont partagées avec S1-003, sans changer ses
résultats : `strip().casefold()`, ensembles, précision/rappel/F1. Si les deux
ensembles sont vides, les trois scores valent 1 ; extrait vide seulement : trois
scores à 0 ; attendu vide seulement : précision/F1 à 0, rappel à 1. Le F1 macro
est la moyenne des F1 individuels. Aucun framework fournisseur n'est introduit.
Ces simulations vérifient les calculs et le transport SDK, pas le modèle réel.
Le script CV conserve son verrou `--allow-paid-requests` ; aucun appel réel n'est
nécessaire pour les tests et les vérifications S2-002.

### Évaluation Azure réelle, explicitement autorisée (S2-003)

Le même script propose un mode réel, mutuellement exclusif avec `--predictions`.
Sans l'un des deux modes, il termine avec le code 2 avant de créer un client ou
lancer une requête. Les tests et la CI utilisent uniquement des mocks : ne jamais
y lancer une évaluation réelle. Les commandes ci-dessous sont destinées à une
exécution manuelle ultérieure et impliquent des appels potentiellement payants.
Depuis `backend/`, avec une configuration Azure locale valide :

```sh
uv run --env-file .env python scripts/evaluate_job_extraction.py --allow-paid-requests
```

Export local optionnel, également disponible en mode hors ligne :

```sh
uv run --env-file .env python scripts/evaluate_job_extraction.py --allow-paid-requests --json-output /tmp/job-report.json
uv run python scripts/evaluate_job_extraction.py --predictions /tmp/job-predictions.json --json-output /tmp/job-report.json
```

Le corpus complet est validé avant toute création de client. Le mode réel utilise
`AzureSettings`, la fabrique sécurisée partagée et `AzureJobExtractor`, avec le
même déploiement que les endpoints d'extraction. **Un appel d'extraction par
annonce est prévu**, soit huit appels ; `max_retries=1` autorise jusqu'à deux
tentatives par appel, donc jusqu'à seize tentatives réseau au total. Aucun retry
applicatif n'est ajouté. Le client est fermé même lorsqu'une extraction échoue.

Le format JSON du rapport console reste identique à celui du mode hors ligne.
Une erreur d'extraction produit `technical_failure` avec `skills: null`, jamais
une liste vide factice ; les cas suivants sont quand même traités. Une extraction
vide valide reste un succès technique. Les moyennes macro portent uniquement sur
les succès techniques, sans seuil de qualité métier. Le code de sortie vaut 1 en
cas d'échec technique, configuration invalide, erreur de lecture ou d'écriture,
et 0 si toutes les extractions réussissent techniquement. Une erreur SDK lors de
la gestion du client entraîne un message fixe sans rapport complet. Les erreurs
inattendues de programmation ne sont pas transformées en extractions.

`--json-output` écrit le même rapport dans un fichier UTF-8, en remplaçant le
fichier s'il existe. Ne pas cibler un fichier du projet ; le corpus et le fichier
de prédictions sont explicitement protégés contre cet écrasement. Le rapport
contient seulement identifiants, statuts, métriques et différences de compétences.
Il exclut les annonces complètes, la configuration et les exceptions fournisseur
brutes. Les échos de documents et des valeurs de configuration connues sont
masqués avant affichage et export. Aucun texte brut ni secret n'est journalisé
par le script ; ne pas activer les logs HTTP/SDK de diagnostic.

Huit annonces fictives donnent une **première mesure exploratoire**, pas une
garantie de qualité en production. Les conventions lexicales ne reconnaissent
pas les synonymes ; les alternatives non résolues restent volontairement omises.
Aucun résultat Azure réel n'est produit lors du développement ou des tests S2-003.

## Matching déterministe des compétences

`POST /api/v1/matching/skills` compare deux listes sans appel Azure, LLM,
stockage ni configuration fournisseur. Les deux champs sont obligatoires :

```json
{
  "candidate_skills": [" Python ", "SQL", "Git", "PYTHON"],
  "required_skills": ["Python", "SQL", "FastAPI"]
}
```

Réponse HTTP 200 :

```json
{
  "score": 66.66666666666667,
  "matched_skills": ["python", "sql"],
  "missing_skills": ["fastapi"]
}
```

Les deux listes sont normalisées avec `strip().casefold()` ; les chaînes devenues
vides sont ignorées et les doublons supprimés. Les compétences retournées sont
normalisées et triées lexicographiquement, indépendamment de l'ordre des entrées.
Le score vaut `100.0 * len(matched) / len(required_distinct)`, sans arrondi métier.
Les compétences supplémentaires du candidat ne diminuent pas le score. Un candidat
sans compétence non blanche obtient 0 si les exigences sont valides.

Chaque liste accepte au maximum **1 000 éléments** et chaque chaîne au maximum
**200 caractères bruts**. Ces bornes sont contrôlées avant normalisation, y compris
pour les doublons, les espaces périphériques et les chaînes entièrement blanches.
Les champs absents ou supplémentaires, les listes ou éléments mal typés (sans
conversion), les dépassements et les exigences sans compétence non blanche
retournent HTTP 422. Le contrat est également décrit dans `/docs` et `/openapi.json`.

Ce score mesure uniquement la couverture littérale des compétences requises ;
**ce n'est pas une probabilité d'embauche**. Il n'y a ni synonymes, ni matching
sémantique, ni pondération. Les espaces internes, accents et ponctuations ne sont
pas modifiés : `C`, `C++` et `C#` sont distincts. Les expériences et formations
ne participent pas au calcul. Les fonctions métier sont pures et les tests restent
entièrement hors ligne, avec blocage du réseau externe.

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
Le corpus unique `evaluation/fictional_cvs.json` contient **12 CV entièrement
synthétiques** : développement, analyse, intentions d'apprentissage, instructions
parasites, commerce, menuiserie, début de carrière, reconversion, carrière longue,
anglais, variations de présentation et informations distractrices. Ce petit corpus
ne constitue pas une mesure représentative de la qualité sur de vrais CV.

Chaque cas possède un identifiant stable, `cv_text`, `expected_skills`, ainsi que
des attentes `experiences` et `education`. Ces dernières sont des métadonnées
d'évaluation ; elles ne changent pas le contrat public `CVProfile` :

```json
{
  "min_items": 1,
  "max_items": 2,
  "fragment_groups": [["Atlas", "2024"]]
}
```

Le script valide intégralement le corpus avant toute création de client : 10 à 15
cas (12 actuellement), identifiants uniques, entrées conformes à `CVExtractRequest`,
compétences attendues non blanches, intervalles cohérents et groupes/fragments non
vides. Une liste attendue vide (`max_items=0`) ne peut avoir de fragments.

Depuis `backend/`, pour lancer **12 extractions potentiellement payantes**, jamais
automatiquement par pytest ou la CI :

```sh
uv run --env-file .env python scripts/evaluate_cv_extraction.py --allow-paid-requests
```

Export JSON optionnel, en complément du rapport console :

```sh
uv run --env-file .env python scripts/evaluate_cv_extraction.py --allow-paid-requests --json-output /tmp/cv-evaluation.json
```

Sans `--allow-paid-requests`, aucun client n'est créé. Un retry SDK peut porter
le nombre de tentatives jusqu'à 24 pour 12 extractions. Le fichier d'export est
remplacé s'il existe ; il doit être distinct du corpus et des fichiers du projet.

Les compétences extraites et attendues sont comparées comme des ensembles après
normalisation **symétrique `strip().casefold()`**, sans synonymes ni rapprochement
approximatif. Les doublons n'affectent pas les scores ; `C`, `C++` et `C#` restent
distincts. Avec A l'ensemble extrait et E l'ensemble attendu :

- Vrais positifs : taille de A ∩ E.
- Faux positifs : A − E ; faux négatifs : E − A, affichés triés par CV.
- Précision : taille de A ∩ E divisée par taille de A.
- Rappel : taille de A ∩ E divisée par taille de E.
- F1 : `2 * précision * rappel / (précision + rappel)`, ou 0 si la somme est nulle.

Conventions explicites pour les ensembles vides :

| Extrait | Attendu | Précision | Rappel | F1 |
| --- | --- | --- | --- | --- |
| Vide | Vide | 1 | 1 | 1 |
| Vide | Non vide | 0 | 0 | 0 |
| Non vide | Vide | 0 | 1 | 0 |

Pour les expériences et formations, le rapport expose uniquement des contrôles :

- Cardinalité dans l'intervalle inclusif attendu, dont liste vide si `[0, 0]`.
- Absence de chaînes blanches et de doublons après normalisation.
- Présence de chaque groupe de fragments dans au moins un même élément de liste,
  après `strip().casefold()`. Les groupes sont indépendants ; ils peuvent être
  satisfaits par le même élément. Le rapprochement est une recherche de sous-chaîne.

Le champ `passed` combine ces contrôles. **Il ne mesure pas une exactitude
sémantique** : une reformulation peut échouer, une sous-chaîne peut correspondre
fortuitement et des informations inventées peuvent passer les contrôles. Aucun
juge LLM ni score sémantique n'est utilisé. Les intervalles tolèrent certains
regroupements ou découpages du modèle ; ils ne définissent pas un format public.

La synthèse technique compte tous les cas. Les moyennes **macro** de précision,
rappel et F1 portent seulement sur les extractions techniquement réussies ; chaque
cas pèse autant. Le F1 macro est la moyenne des F1 individuels, pas le F1 calculé
sur les moyennes de précision et rappel. Sans succès, les moyennes valent `null`
dans le JSON et sont indiquées indisponibles dans la console.

Une réponse invalide, un refus ou une erreur fournisseur est un échec technique,
avec catégorie fixe et métriques à `null` dans le JSON. Un profil conforme mais
incorrect reste un succès technique, accompagné de ses scores et contrôles.
Les rapports n'incluent ni texte complet des CV, ni profil brut, ni configuration,
ni détails internes des exceptions fournisseur. Ils contiennent les différences
de compétences normalisées et des booléens pour les contrôles de listes.

Le code de sortie reste 0 si toutes les extractions réussissent techniquement,
même avec une mauvaise qualité. Il vaut 1 en cas d'échec technique, de corpus ou
configuration invalide, ou d'échec d'écriture du rapport ; l'absence d'autorisation
vaut 2. Aucun seuil de qualité n'est imposé. Les exceptions inattendues de
programmation ne sont pas converties en résultats d'extraction.

Les tests utilisent des profils fixes et des extracteurs simulés, sans appel
Azure. Ils vérifient le calcul et les rapports, pas la qualité réelle du modèle.
L'accès Azure réel reste dépendant du déploiement, des droits et quotas.

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
