# Développement, QA et promotion — S4-OPS-002

## Politique autorisée et état vérifié le 18 octobre 2026

Dépôt canonique : JuliusDoThings/JobCopilot. Le PO autorise Codex à fusionner
les changements éligibles vers dev. Cette autorisation ne s'applique jamais
à main et ne dispense pas de revue humaine des changements sensibles.

Flux : feature/* ou fix/* → PR vers dev → CI obligatoire → fusion par Codex
si toutes les conditions sont satisfaites → QA indépendante sur dev → rapport
→ validation PO du SHA qualifié → PR dev → main → fusion humaine.

Vérifications API GitHub (sans modification des règles) :

- [protect-dev](https://github.com/JuliusDoThings/JobCopilot/rules/25336749) :
  actif sur refs/heads/dev ; PR obligatoire, suppression et force-push interdits,
  backend-checks/frontend-checks/compose-checks obligatoires (GitHub Actions,
  integration_id=15368), zéro approbation exigée, branche à jour non imposée.
- [defaultRules](https://github.com/JuliusDoThings/JobCopilot/rules/25336723) :
  actif sur la branche par défaut main ; mêmes contrôles, branche à jour requise,
  PR et une approbation obligatoires, suppression et force-push interdits.
- Les deux rulesets déclarent bypass_actors=[] et current_user_can_bypass=never.
- Ces règles n'imposent ni l'identité du PO sur main ni la revue des changements
  sensibles sur dev ; elles n'empêchent pas à elles seules un agent de fusionner
  main. Les obligations ci-dessous restent impératives pour Codex. Ne pas
  présenter l'exclusivité PO ou la revue sensible comme garanties techniques.
- L'endpoint des règles effectives par branche n'est pas accessible via le
  connecteur actuel ; les conditions et contenus des deux rulesets ont été lus.
- PR #16 déjà fusionnée par JuliusDoThings à 08:57:23 UTC : dev à
  36a222531edcc4e0148a728ac76e34327dd7e494 ;
  [CI push réussie](https://github.com/JuliusDoThings/JobCopilot/actions/runs/39113443225).
  Aucun nouvel acte de fusion n'a été effectué pour cette PR par S4-OPS-002.

Les constats S4-OPS-001 du 16 octobre (dépôt privé et règles non accessibles)
sont historiques et ne décrivent plus l'état observé ci-dessus.

## Work : développer et intégrer vers dev

1. Vérifier dev distante et partir de son dernier SHA sur feature/<mission>
   ou fix/<mission>. Avant chaque commit, vérifier git var GIT_AUTHOR_IDENT
   et git var GIT_COMMITTER_IDENT : adresses GitHub noreply effectives.
2. Développer une mission limitée et conserver les tests. Aucun secret ni appel
   Azure payant dans les tests. Ouvrir une PR vers dev avec critères, validation,
   risques, sensibilité et limitations.
3. Examiner tous les commits et le diff final. Sont sensibles : authentification,
   autorisations, secrets, paiements, données personnelles (CV et journaux), Azure,
   sécurité, permissions GitHub, CI, CODEOWNERS, AGENTS.md et cette politique.
   Ils nécessitent une revue humaine explicite du SHA courant. Une autorisation
   générale, un label ou une liste de chemins ne remplace pas cette revue.
   Les PR des instructions et de la politique sont laissées ouvertes pour revue
   humaine, sans fusion automatique.
4. Juste avant une fusion autorisée par Codex : confirmer PR ouverte non draft,
   cible dev, aucun conflit, fusionnabilité et rulesets respectés ; vérifier les
   trois contrôles obligatoires et tout contrôle supplémentaire requis, tous
   réussis sur le SHA à intégrer, sans contrôle requis ignoré. Examiner aussi
   les reviews et discussions : aucune demande de modification non résolue.
   Aucun commit supplémentaire non examiné ne doit être présent. Si le SHA,
   la base ou le diff change, interrompre et refaire examen et contrôles ; une
   revue humaine sensible doit porter sur le nouveau SHA. Un échec ou une
   incertitude suspend la fusion et impose une nouvelle revue.
5. Fusionner via l'API standard avec le SHA source attendu, uniquement vers dev,
   sans bypass, jeton privilégié de contournement ni modification des protections.
   Ne pas activer de fusion différée qui éviterait cette dernière vérification.
6. Relever le SHA exact de dev après fusion et vérifier sa CI push. CI rouge :
   suspendre les intégrations, préparer correctif ou PR de revert vers dev.
   Ne pas supprimer la branche source sans nécessité et vérification d'activité.
7. Faire qualifier dev par une QA indépendante de l'implémentation : testeur
   humain ou session distincte, résultats et preuves liés au SHA exact. La CI
   verte autorise l'intégration éligible ; elle ne vaut pas qualification produit.

## Protections et limites d'autonomie

Ne jamais modifier rulesets, permissions ou contrôles pour permettre une fusion.
Si GitHub refuse, arrêter et transmettre le motif au PO. Les changements
sensibles restent soumis à revue humaine même si GitHub accepterait la fusion.
Toute évolution de CI, CODEOWNERS ou de cette politique suit une PR distincte
revue humainement. Aucun agent ne fusionne vers main, même après CI verte et
accord PO : la fusion est effectuée par un humain.

Le nettoyage historique S4-SEC-004 est à ce stade une étude en lecture seule.
Aucune réécriture, aucun force-push ni suppression de référence n'est autorisé.
Une opération future exige un accord PO distinct couvrant sauvegarde, périmètre,
publication, protections, restauration et impact sur main.

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

Urgence : branche fix/* depuis dev, PR et mêmes contrôles. Toute intervention
vers main reste une opération humaine sous contrôle exclusif du PO.
Pour une régression, privilégier une PR de revert ; aucun reset ni force-push.

## Anciennes branches — constat historique S4-OPS-001

Lors de S4-OPS-001, les 13 branches historiques ont été comparées à main :
toutes étaient derrière,
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
