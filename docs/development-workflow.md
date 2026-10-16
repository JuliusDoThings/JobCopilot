# Développement, QA et promotion — S4-OPS-001

## État réellement vérifié le 16 octobre 2026

- main : de4869f3f608a060741014fe58c1f56effa3c437 (PR #13).
- CI push verte : https://github.com/JuliusDoThings/SASS-Emma/actions/runs/38934155325
- dev créée exactement sur ce SHA après vérification de la CI.
- Aucune PR ouverte au début de l'audit ; un seul workflow : backend-ci.yml.
- API branches : protected=false pour toutes les branches, dont main.
- API rulesets : 403, « Upgrade to GitHub Pro or make this repository public ».
- Lecture branch protection : 403, « Resource not accessible by integration ».
  Les permissions admin affichées dans les métadonnées du compte ne donnent
  donc pas de capacité d'administration à cette connexion.
- allow_auto_merge=false. Aucun auto-merge, bot de fusion ou jeton ajouté.

**Les conventions ci-dessous ne constituent pas des protections GitHub.**
Les contrôles CI ne sont pas vérifiés comme obligatoires. Les pushs directs,
fusions sans CI et promotions sans accord PO ne sont pas techniquement bloqués
pour les détenteurs d'un accès en écriture. Ne pas automatiser la fusion dans
cet état. Le plan et la connexion actuels ne permettent pas de garantir les
conditions de fusion demandées. Ne pas rendre public ce dépôt pour contourner
cette limite.

## Work : créer et intégrer une fonctionnalité

1. Partir de dev à jour ; créer feature/<mission> ou fix/<mission>.
2. Développer une mission limitée et conserver les tests. Aucun secret ni appel
   Azure payant dans les tests. Ouvrir une PR **vers dev**.
3. Décrire comportement, critères d'acceptation, tests, risques, sensibilité et
   limitations. Les changements sensibles nécessitent une revue humaine.
4. En l'état, demander une fusion humaine. Vérifier sur la dernière version :
   PR ouverte et non draft, aucun conflit, branche à jour avec dev, tous les
   workflows et contrôles terminés avec succès, aucun contrôle requis ignoré,
   aucune demande de modification non résolue. Après tout nouveau commit ou
   changement de base, refaire les vérifications. Ne jamais utiliser un bypass.
5. Vérifier la CI push de dev après fusion. CI rouge : suspendre les intégrations
   et ouvrir un correctif ou une PR de revert vers dev.

Sont sensibles au minimum : authentification, autorisations, secrets, paiements,
données personnelles (dont CV et journaux), infrastructure Azure, workflows de
sécurité, permissions GitHub. Inclure les modifications de CI, CODEOWNERS,
AGENTS.md et de cette politique dans la revue humaine. Une simple liste de
chemins ou un label ne prouve pas l'absence d'impact sensible.

## QA : qualifier un SHA de dev

Noter le SHA exact testé, les liens CI, les parcours, résultats et preuves.
Utiliser des données synthétiques, sans identifiants Azure.

- Backend : dans backend, uv sync --frozen puis uv run --no-sync pytest,
  uv run --no-sync ruff check . et uv run --no-sync ruff format --check .
- Frontend : dans frontend, npm ci, npm test, npm run typecheck,
  npm run lint et npm run build (Node 22).
- Racine : python scripts/verify_compose.py --config-only ;
  docker compose up --build --wait --wait-timeout 180 ;
  python scripts/verify_compose.py.
- Navigateur : produit http://localhost:3000 et banc /dev/valorization ;
  exécuter les 12 scénarios, vérifier les messages et exporter les résultats.
- Panne : docker compose stop backend ; python scripts/verify_compose.py
  --unavailable ; vérifier aussi le diagnostic dans le navigateur.
- Nettoyage : docker compose down.

Résultat métier MVP accepté : **11 conformes, 1 écart VAL-007, 0 non exécuté**
avec backend disponible. Garder l'attente métier originale de VAL-007 :
ne pas la modifier pour transformer l'écart en conformité.
Avec backend arrêté : 12 non exécutés, aucun succès artificiel.

Distinguer bloquants (régression, sécurité, perte de données, parcours cassé),
non bloquants à arbitrer et limitation VAL-007 déjà acceptée. Un nouveau défaut
ne devient pas automatiquement une limitation acceptée. Les contrôles Compose
ne remplacent pas la revue visuelle et la qualification métier.

## PO : promouvoir dev vers main

1. Stabiliser dev et ouvrir une PR **dev → main**, jamais de push direct.
2. Joindre le rapport QA avec le SHA qualifié, la CI et les limitations.
3. Attendre l'accord explicite de JuliusDoThings, Product Owner, enregistré
   sur la PR et portant sur le SHA exact de dev. Tout nouveau commit invalide
   cette qualification et nécessite une nouvelle vérification et validation.
4. Fusion humaine après CI verte et vérifications des contrôles ; jamais
   d'auto-merge vers main. Vérifier ensuite la CI push sur le SHA de main.
5. Aucun déploiement public n'est déclenché par ce processus.

Urgence : branche fix/* depuis dev, PR et mêmes contrôles. Si dev contient du
travail non qualifié, préparer une PR de correctif ciblée vers main seulement
avec accord PO explicite, puis reporter le correctif vers dev par PR.
Pour une régression, privilégier une PR de revert ; aucun reset ni force-push.

## Activer une autonomie garantie ultérieurement

Solution simple : conserver le dépôt privé et choisir un plan donnant accès aux
protections, avec configuration par le propriétaire. Sur dev et main : PR
obligatoire, contrôles backend-checks/frontend-checks/compose-checks requis,
branche à jour, interdiction force-push/suppression et aucun bypass pour agents.
Sur main, revue PO obligatoire et aucun automatisme de fusion ; vérifier que
les règles choisies imposent réellement cette identité (une approbation quelconque
ne suffit pas). Séparer les identités PO et agents et limiter leurs droits.

Avant d'activer l'auto-merge sur dev uniquement, faire appliquer une revue humaine
des changements sensibles par un mécanisme de confiance, réévaluer après chaque
commit et protéger ce mécanisme contre les modifications par les agents.
CODEOWNERS seul, un label posé par l'auteur et un workflow modifiable par la PR
ne suffisent pas. Tester drafts, conflits, CI échouée/annulée, nouveaux commits
et changements sensibles sur des PR sans risque. Ne pas installer de script
qui fusionne avec un jeton privilégié pour remplacer des protections absentes.

## Anciennes branches

Les 13 branches historiques ont été comparées à main : toutes sont derrière,
ahead_by=0. Aucune PR ouverte au début de l'audit.
La connexion GitHub disponible n'expose aucune opération de suppression de ref.
Aucune branche n'a donc été supprimée par cette mission. Une absence de commits
exclusifs ne prouve pas à elle seule l'absence de session Work active :
revérifier activité connue, refs et PR juste avant toute suppression.
Ne jamais supprimer main, dev ni la branche de cette mission tant que sa PR vit.

- feature/azure-cv-extraction : 23ea31dc2964061a4543cc41782c96cee33a9121
- feature/cv-extraction : 478d92f350f7224ea4d5e860419f40c59b8fdbb2
- feature/s1-003-cv-extraction-evaluation : 1d0d05ced44627142c55c8cb507ecd96a2095e0f
- feature/s2-001-skills-matching : 00d0abfe2b0fcc50b8dfd2ebd4b98dcfaab9438a
- feature/s2-002-job-requirements-extraction : d978e600fa876bdfcf2f4165a821f2a739b43c59
- feature/s2-003-job-extraction-evaluation : d4e7f517d97eccdd57d189e87aff4717c07c760e
- feature/s2-004-end-to-end-matching : f7527f1d709ced519e7864e9f63dff8377defd52
- feature/s3-001-backend-ci : 65b50f9b405ff9446e9c2c5b256ead0d1f4e0df7
- feature/s3-002-nextjs-mvp : e9ef806d15af87dab8e91f889ddbf0c353c8cfa8
- feature/s3-004-frontend-ci : 8b594057b31d6a24f1330510636ce5759cbff8f1
- feature/s4-001-cv-valorization : 280f133f5185c95a7749f11f590ad473f2ce1575
- feature/s4-val-001-functional-bench : cfbe7e63ac4f1ee4403695265fe33673d5d5d862
- fix/s3-003-skill-matching : 0559e89ca1c4e751c4d2c756940b0c8eb4010175
