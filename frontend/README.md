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
