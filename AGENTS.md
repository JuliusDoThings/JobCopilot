# Instructions de contribution

- Base de développement : dev. Branches feature/* ou fix/* ; PR vers dev.
- main reçoit uniquement une promotion qualifiée, normalement une PR dev → main.
- Aucune fusion vers main sans accord explicite du Product Owner sur le SHA.
- Lire docs/development-workflow.md avant une intégration ou qualification QA.
- Aucun auto-merge tant que les protections réelles ne garantissent pas la politique.
- Authentification, autorisations, secrets, paiements, données personnelles,
  infrastructure Azure, sécurité et permissions GitHub nécessitent revue humaine.
  Les changements de CI et de ces instructions sont également sensibles.
- Garder VAL-007 comme limitation MVP acceptée avec son attente métier inchangée.
- Ne pas appeler Azure en CI, modifier les secrets, déployer publiquement,
  désactiver des contrôles ou réécrire l'historique.
