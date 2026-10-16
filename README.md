# Job Copilot — environnement local

Prérequis : Docker Desktop démarré (avec Docker Compose v2), ou Docker Engine
avec le plugin Compose v2. Aucun Python, uv, Node ou npm à installer sur l’hôte.

Depuis la racine du dépôt :

```bash
docker compose up --build
```

Attendre le démarrage des deux services. La première construction télécharge les
images et dépendances ; elle nécessite Internet. Les appels métier du banc
restent locaux et ne nécessitent aucun compte ni identifiant Azure.

- Produit : **http://localhost:3000**
- Banc fonctionnel : **http://localhost:3000/dev/valorization**
- Santé FastAPI : **http://localhost:8000/health**

Cliquer sur « Exécuter tous les scénarios ». Résultat actuel attendu :
**11 conformes, 1 écart connu (VAL-007), 0 non exécuté**. L’écart met en évidence
une formulation naturelle refusée par le moteur lexical : il reste visible.
L’export JSON du banc conserve les résultats de la session.

Le formulaire d’analyse du produit reste accessible, mais son extraction Azure
n’est pas configurée dans cet environnement et retourne une erreur contrôlée.
Le banc de valorisation appelle uniquement FastAPI, sans Azure.

## Démarrage, arrêt et diagnostic

```bash
# Démarrer en arrière-plan et attendre des healthchecks réussis
docker compose up --build --wait --wait-timeout 180

# État des services et diagnostics de démarrage
docker compose ps
docker compose logs --tail 100 backend frontend

# Arrêter les services et supprimer leurs conteneurs/réseau
docker compose down
```

En mode attaché, `Ctrl+C` arrête les services ; `docker compose down` nettoie
ensuite les conteneurs. Aucun volume ni base de données n’est créé. Après un
changement de code, relancer `docker compose up --build` : les sources sont
copiées dans les images, sans montage du répertoire hôte.

Si un port est occupé, arrêter l’autre application qui utilise 3000 ou 8000,
puis relancer. Ne pas remplacer les publications `127.0.0.1` par `0.0.0.0`.
Le délai de 180 secondes peut être augmenté sur une machine lente ; il concerne
l’attente des services, pas le temps de téléchargement/construction des images.

## Vérifier une panne du backend

```bash
docker compose stop backend
```

Dans le banc, relancer un scénario : il doit afficher **Non exécuté** avec un
diagnostic d’indisponibilité, jamais « Conforme ». Le frontend reste disponible.
Pour revenir à la normale :

```bash
docker compose start backend
```

Le navigateur parle à Next.js ; Next.js appelle `http://backend:8000` sur le
réseau privé Compose. L’adresse Docker et sa configuration restent côté serveur.
Sans Compose, les commandes manuelles de `frontend/README.md` restent valides
et le banc utilise FastAPI sur `127.0.0.1:8000` par défaut.

## Périmètre et sécurité

Deux services applicatifs seulement, exécutés avec des utilisateurs non root.
Les ports sont publiés uniquement sur l’interface locale. Les healthchecks
contrôlent FastAPI `/health` et la réponse du frontend `/` ; le frontend démarre
après que FastAPI est sain. Ils ne prétendent pas prouver la conformité métier.

Aucun fichier `.env`, identifiant ou secret de l’hôte n’est transmis. Les contextes
Docker utilisent une liste de fichiers autorisés et excluent les fichiers `.env`.
Ne pas ajouter `env_file`, de secret, de montage hôte ni de tunnel public pour
utiliser le banc. Les images de développement ne sont pas destinées à un
hébergement public. Le serveur écoute `0.0.0.0` **dans le conteneur** pour être
joignable par Docker ; la publication sur l’hôte reste limitée à `127.0.0.1`.
Le banc reste désactivé par ses gardes applicatives en mode production.

La CI valide la configuration, construit et démarre les conteneurs, exécute le
corpus via le proxy Next.js et le vrai FastAPI, puis arrête le backend pour
vérifier les erreurs. Elle ne masque pas l’écart métier VAL-007. Les tests backend
et frontend existants restent des jobs indépendants.

Pour reproduire les contrôles HTTP dans les conteneurs sans installer Python :

```bash
docker compose exec frontend node scripts/run-valorization-bench.mjs /tmp/valorization-report.json
```

Le code de sortie 1 est normal tant que VAL-007 diverge ; 2 indique une exécution
incomplète. Télécharger les preuves via l’interface est plus simple pour le PO.
