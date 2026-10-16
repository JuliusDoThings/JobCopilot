# Job Copilot — Interface MVP

Interface française Next.js App Router, TypeScript et React, avec CSS simple.
Aucune authentification, base de données, bibliothèque de composants ou analyse
simulée dans l’application. Aucun changement au backend.

## Démarrage local

Prérequis : Node.js 22 LTS récent (22.13 minimum), npm, Python 3.12 et uv pour
le backend. Les dépendances frontend sont verrouillées par `package-lock.json`.

Dans un premier terminal, depuis la racine du dépôt :

```sh
cd backend
uv sync --frozen
uv run uvicorn job_copilot_api.main:app --host 127.0.0.1 --port 8000
```

Sans configuration Azure, le backend renvoie une erreur 503 contrôlée et aucune
analyse fictive n’est affichée. Pour une analyse réelle, configurer Azure côté
backend selon `backend/README.md`, puis lancer explicitement le backend avec sa
configuration locale. Ne jamais copier une clé Azure dans le frontend.

Dans un second terminal :

```sh
cd frontend
npm install
npm run dev
```

Ouvrir http://127.0.0.1:3000. Utiliser uniquement des CV et annonces entièrement
fictifs pour essayer ce prototype. **Chaque analyse réelle peut déclencher deux
extractions Azure facturables**, avec jusqu’à quatre tentatives à cause des retries
SDK du backend. Le bouton prévient les soumissions répétées pendant une analyse.

Pour reproduire strictement une installation verrouillée : `npm ci`.
Pour servir une compilation de production : `npm run build`, puis `npm start`.
Les serveurs de développement et de production écoutent sur la boucle locale.

## Proxy serveur et confidentialité

Le navigateur appelle uniquement `POST /api/analyze` sur le serveur Next.js.
Celui-ci transmet une requête à `POST /api/v1/matching/analyze` de FastAPI :
aucun paramétrage CORS supplémentaire n’est nécessaire.

`FASTAPI_BASE_URL` est une variable **serveur uniquement**, lue au moment de la
requête, avec `http://127.0.0.1:8000` par défaut. Pour un backend différent :

```sh
FASTAPI_BASE_URL=http://127.0.0.1:8001 npm run dev
```

Un fichier local `.env.local` peut aussi définir cette URL ; il est ignoré par Git.
Ne pas utiliser de préfixe `NEXT_PUBLIC_` pour la configuration serveur ou Azure.
L’URL est définie par l’opérateur, jamais par les données envoyées du navigateur.
HTTP/HTTPS sont acceptés, sans identifiants, query string ni fragment. Les
redirections du proxy sont refusées. Les clés Azure restent exclusivement dans
le backend ; le frontend n’en lit ni n’en transmet aucune.

Les textes sont validés côté navigateur **et côté serveur** : deux chaînes non
blanches, sans champs supplémentaires, de 1 à 20 000 caractères Unicode après
`trim()`. Le backend conserve sa propre validation. Les réponses sont vérifiées
à l’exécution selon l’union `scored`/`not_scorable` : `0` et `null` sont distincts.
Un résultat `not_scorable` n’affiche aucun pourcentage. Les scores sont seulement
arrondis à deux décimales pour l’affichage ; leur valeur reçue est conservée.

Les erreurs 422, 502, 503 et 504 sont converties en messages français fixes. Les
autres erreurs réseau, réponses incorrectes ou statuts inattendus produisent une
erreur contrôlée sans score. Aucun corps d’erreur fournisseur n’est renvoyé au
navigateur. Le proxy ne journalise ni texte ni corps de réponse.

Le proxy utilise un timeout de **300 secondes**, sans retry supplémentaire, pour
laisser le temps aux deux extractions séquentielles et à leurs retries SDK. Il
retourne 504 à expiration ; ce délai n’est pas une garantie de fin du travail
Azure : l’annulation HTTP ne garantit pas l’arrêt ni l’absence de facturation du
backend. Un hébergement futur devra autoriser cette durée (limite de fonction et
reverse proxy) ; `maxDuration=300` la déclare sans remplacer ces réglages.

Les CV et annonces restent dans la mémoire de la page jusqu’au rechargement ou à
la fermeture. Aucun localStorage, sessionStorage, cookie de documents, base de
données ou cache applicatif n’est utilisé. Les requêtes et réponses d’analyse
utilisent `no-store`. Le frontend ne promet aucune rétention nulle chez Azure.

## Tests et vérifications

```sh
npm test
npm run typecheck
npm run lint
npm run build
```

Vitest et Testing Library testent les validations, les états 50 %, 0 % et
non calculable, les erreurs, le chargement, les doubles soumissions, le contrat
proxy et son timeout. `fetch` est bloqué par défaut dans les tests et remplacé
par des mocks explicites : aucun backend, réseau externe ou appel Azure requis.
L’installation des dépendances utilise le réseau ; le build ne charge aucune
police ni ressource distante. Les tests ne prouvent pas la qualité du modèle réel.

## CI GitHub Actions

Le workflow `.github/workflows/backend-ci.yml` (« Backend and Frontend CI »)
déclenche les jobs indépendants `backend-checks` et `frontend-checks` sur chaque
Pull Request ciblant `main` et chaque push sur `main`, sans filtre de chemins.
Les exécutions obsolètes d'une même PR ou branche sont annulées automatiquement.
Les permissions sont limitées à `contents: read`.

`frontend-checks` utilise `ubuntu-latest` et Node.js 22, lu depuis `.nvmrc`
(le projet exige au moins 22.13.0 et déclare Next.js 16.4.2). Le cache npm est
indexé par `frontend/package-lock.json`. Depuis `frontend/`, il exécute dans
l'ordre :

```sh
npm ci
npm test
npm run typecheck
npm run lint
npm run build
```

`npm ci` installe les versions du lockfile existant sans le réécrire et échoue
s'il est incohérent avec `package.json`. Chaque échec fait échouer le job,
sans masquer les erreurs ; aucun job ne dépend du succès de l'autre.

L'installation des outils et dépendances nécessite le réseau. Les tests utilisent
exclusivement les mocks existants, sans FastAPI ni Azure réel ; le build ne
télécharge aucune police ou ressource externe. Aucun fichier `backend/.env`,
secret applicatif ou variable Azure n'est nécessaire. Ce workflow ne déploie
rien sur Azure et ne déclenche aucune facturation Azure.

Les tests hors ligne vérifient les contrats et les comportements avec des
réponses simulées. Ils ne valident pas la qualité des extractions Azure.
L'évaluation réelle du modèle est une opération manuelle distincte, explicitement
opt-in et potentiellement payante, décrite dans le [README backend](../backend/README.md).

## Limites du prototype

Le score mesure la couverture lexicale des compétences obligatoires identifiées,
**pas les chances de recrutement**. Les extractions sont probabilistes ; les
synonymes et les alternatives obligatoires non résolues ne sont pas représentés.

**Ce prototype n’est pas destiné à être exposé publiquement sans authentification
et protection contre les abus** : limitation de débit, quotas de coût et règles
de confidentialité devront être ajoutés avant toute ouverture publique. Le
verrouillage du bouton ne remplace pas ces protections serveur. Aucun mécanisme
de ce type n’est ajouté dans ce ticket.

## Banc d’essai fonctionnel local — S4-VAL-001

Le banc utilise le véritable endpoint FastAPI `POST /api/v1/cv/valorization`.
Les 12 scénarios synthétiques et leurs attentes métier sont versionnés dans
`frontend/lib/dev-bench/corpus.json`. Ils ne sont pas calculés depuis le moteur.
L’attente de VAL-007 accepte une expérience formulée naturellement ; le moteur
lexical actuel doit afficher un écart pour ce cas. Ne pas changer l’attente pour
rendre le tableau vert. Le banc ne modifie aucune logique de valorisation.

Depuis la racine du dépôt, terminal 1 (Python 3.12 et uv) :

```bash
cd backend
uv sync --frozen
uv run --no-sync uvicorn job_copilot_api.main:app --host 127.0.0.1 --port 8000
```

Terminal 2 (Node 22.13+ et npm), depuis la racine :

```bash
cd frontend
npm ci
JOB_COPILOT_DEV_BENCH=1 npm run dev
```

Ouvrir **http://127.0.0.1:3000/dev/valorization** puis cliquer sur
« Exécuter tous les scénarios ». Le résultat de référence est actuellement
**11 conformes, 1 écart (VAL-007), 0 non exécuté**. Les écarts sont des observations
métier, pas des échecs des tests du comparateur.

Dans PowerShell, activer avec `$env:JOB_COPILOT_DEV_BENCH="1"` avant `npm run dev`.
Aucune variable Azure n’est nécessaire. Sans Compose, le banc appelle `http://127.0.0.1:8000`. Avec Compose, la variable
serveur `JOB_COPILOT_BENCH_API_BASE=http://backend:8000` sélectionne le service
Docker. Seules ces deux adresses exactes sont autorisées ; `FASTAPI_BASE_URL`
reste réservé au formulaire d’analyse. Voir le README à la racine pour le
démarrage Docker en une commande.
Ne pas démarrer Next.js ou FastAPI avec `--host 0.0.0.0`, ne pas utiliser de tunnel
ou de reverse proxy public pour ce banc. Le serveur de développement Next.js
n’est pas une frontière d’authentification.

### Lecture et preuves

Chaque carte expose l’ID, la justification métier, le CV synthétique, les cibles,
les attentes, le résultat API et les différences champ par champ. Les suggestions
et preuves doivent être des citations exactes du CV. Les questions sont vérifiées
par présence, sans imposer une formulation exacte.

- **Conforme** : réponse HTTP 200 exécutée et toutes les attentes satisfaites.
- **Écart** : résultat API reçu mais différent ou incompatible avec le contrat.
- **Non exécuté** : aucun appel effectué, panne réseau, délai de connexion ou erreur HTTP.

Une relance efface l’ancien résultat des scénarios sélectionnés avant de commencer.
Les boutons sont verrouillés pendant l’exécution séquentielle. Un résultat HTTP 200
illisible ou hors contrat est un écart, jamais un succès. Les horodatages sont en
UTC et les durées en millisecondes.

« Exporter les preuves JSON » télécharge le corpus, sa version, les attentes,
les résultats, HTTP, dates, durées, diagnostics et comparaisons. Aucun stockage
serveur, cookie ou localStorage n’est utilisé ; recharger efface les résultats.
L’export téléchargé est une preuve de session éditable, pas une attestation signée.
Ne fournir que les scénarios synthétiques versionnés. Les corps d’erreur,
exceptions et champs hors contrat sont masqués ; aucun secret ou configuration
serveur n’est inclus. Taille de réponse limitée à 64 ko, délai API de 5 secondes.

Pour conserver le même rapport sans navigateur, avec FastAPI déjà lancé :

```bash
cd frontend
JOB_COPILOT_DEV_BENCH=1 node scripts/run-valorization-bench.mjs valorization-report.json
```

Code de sortie : 0 si tout est conforme, 1 s’il existe un écart métier,
2 si un scénario n’a pas été exécuté. Arrêter FastAPI et relancer doit produire
12 « non exécuté » et le code 2. Le script utilise le même comparateur et le même
client HTTP que l’interface, sans mock. Les tests unitaires utilisent des mocks
pour contrôler les pannes et les réponses adverses ; ce sont des preuves distinctes.

### Accès et vérification

La page et son proxy retournent 404 sauf si `NODE_ENV=development` **et**
`JOB_COPILOT_DEV_BENCH=1`. En production (`npm run build` puis `npm start`),
le banc reste désactivé même si le drapeau vaut 1. Le proxy refuse les origines
externes, les hôtes non locaux, les identifiants inconnus et toute entrée libre.
Le corpus n’est pas servi depuis `public/` et aucun lien n’est ajouté au produit.
Ne pas modifier ces contrôles pour partager le serveur de développement.

Depuis `frontend/` :

```bash
npm test
npm run typecheck
npm run lint
npm run build
```

Les tests vérifient les comparaisons, les divergences, les preuves hors source,
les chiffres inventés, les pannes, les délais, les réponses invalides, les gardes
production et les anciens résultats verts lors d’une relance. La CI existante
exécute ces tests sans accéder à Azure. Les rapports générés ne doivent pas être
confondus avec les résultats des tests automatisés.
