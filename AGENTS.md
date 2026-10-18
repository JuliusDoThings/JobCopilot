# Instructions de contribution

- Lire docs/development-workflow.md avant une intégration ou qualification QA.
- Base : dev à jour. Branches feature/* ou fix/* ; PR vers dev.
- Flux : PR vers dev → CI obligatoire → fusion par Codex si autorisée →
  QA indépendante sur le SHA de dev → rapport → validation PO → PR dev → main.
- Codex peut fusionner vers dev uniquement : dernier SHA intégralement examiné,
  contrôles obligatoires réussis sur ce SHA, PR ouverte non draft et fusionnable,
  rulesets respectés, aucun commit nouveau non examiné ni demande de modification
  non résolue, aucun bypass. Revérifier après tout changement de SHA ou de base.
- Authentification, autorisations, secrets, paiements, données personnelles,
  Azure, sécurité, permissions GitHub, CI, CODEOWNERS, AGENTS.md et politique
  de développement exigent une revue humaine explicite sur le SHA courant.
  L'autorisation générale de fusion vers dev ne vaut pas revue de ces changements.
- Les PR modifiant les instructions ou la politique restent ouvertes pour revue
  humaine ; aucune fusion automatique de ces PR.
- main reste sous contrôle exclusif du Product Owner : aucun push direct,
  aucune fusion par Codex ou automatique, aucune modification des protections
  pour contourner une règle. PR dev → main après QA indépendante, rapport et
  accord PO explicite sur le SHA exact qualifié ; fusion humaine uniquement.
- Une CI verte ne remplace pas la QA indépendante. Garder VAL-007 comme
  limitation MVP acceptée avec son attente métier inchangée.
- Avant chaque commit, vérifier les identités Git effectives auteur et committer :
  utiliser une adresse GitHub noreply, sans adresse personnelle.
- Après fusion réussie d'une PR vers dev, Codex doit supprimer la branche
  distante feature/* ou fix/* associée lorsque la CI post-fusion est verte,
  qu'aucune PR ouverte ni dépendance active ne la référence et que la suppression
  est autorisée par les protections GitHub. En cas d'incertitude, conserver la
  branche et signaler le motif. Appliquer les vérifications de cycle de vie
  décrites dans docs/development-workflow.md, dont SHA de dev et SHA distant.
- Ne jamais nettoyer automatiquement main ou dev, supprimer une branche avec PR
  ouverte, des branches locales, worktrees ou références de PR. Une suppression
  de branche ne nettoie pas les anciennes références de PR ni les objets Git.
- Ne pas appeler Azure en CI, modifier les secrets, déployer publiquement,
  désactiver des contrôles, réécrire l'historique ou utiliser un force-push.
  Seules les suppressions de branches distantes autorisées ci-dessus sont permises.
  Une réécriture historique et sa publication exigent une autorisation PO distincte.
