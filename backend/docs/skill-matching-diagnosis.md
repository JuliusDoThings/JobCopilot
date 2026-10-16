# S3-003 — Diagnostic du faux négatif de compétences

## Reproduction hors ligne et niveau de certitude

Le scénario signalé utilise exclusivement des textes fictifs :

- CV : « Développeuse backend. Compétences techniques : Python, FastAPI, Git.
  Développement d'API REST avec Python et FastAPI. »
- Offre : « Compétences obligatoires : maîtrise de Python ; expérience avec Docker.
  Compétences facultatives : Git et Kubernetes. »

Les réponses Azure de l'essai manuel ne sont pas disponibles dans le dépôt.
Aucun appel Azure n'a été effectué pour ce diagnostic. Les extractions ci-dessous
sont des profils synthétiques injectés pour isoler les couches, pas des sorties
réelles nouvellement observées.

Avec un `CVProfile.skills` simulé à `["Python", "FastAPI", "Git"]` :

| Exigences fournies directement au matcher | Score | Présentes | Manquantes |
| --- | --- | --- | --- |
| `maîtrise de Python`, `expérience avec Docker` | 0.0 | aucune | `expérience avec docker`, `maîtrise de python` |
| `Python`, `Docker` | 50.0 | `python` | `docker` |

La première ligne reproduit exactement le résultat signalé. La seconde vérifie
que le matcher fonctionne avec des noms de compétences de même granularité.
La reproduction est pérennisée dans
`test_reported_false_negative_is_a_label_mismatch`.

## Cause démontrée et incertitude résiduelle

`matching/service.py` applique uniquement `strip().casefold()`, une déduplication
et une intersection exacte. `python` et `maîtrise de python` sont donc deux
compétences différentes. Le score nul est conforme à ce contrat ; ce n'est pas
un défaut arithmétique du matcher.

Les schémas `CVProfile.skills` et `JobRequirements.required_skills` imposent
`list[str]`, sans définir la granularité des libellés. Pydantic accepte autant
`Python` que `maîtrise de Python`. La sortie structurée ne garantit donc pas
leur comparabilité métier.

Avant correction, les instructions offre demandaient de préserver les libellés
(`Preserve labels from the text`) sans préciser qu'il fallait isoler le nom de
la compétence. Cela autorisait une lecture trop littérale de la proposition
complète. L'orchestrateur transmet directement les listes au matcher et le
frontend affiche les éléments de `missing_skills` sans les reformuler.

**Le mécanisme du 0 % est démontré avec les libellés signalés ; l'explication
ciblée est un défaut de consigne sur la granularité d'extraction des exigences.**
Sans capture des deux sorties réelles, on ne peut pas affirmer quels libellés
exactement le CV avait produits, ni prouver le comportement du modèle Azure sur
l'essai d'origine. Le modèle peut aussi varier côté CV ; ce ticket ne prétend
pas éliminer tous les défauts possibles d'extraction.

## Correction minimale

Seules les instructions système de `jobs/azure.py` changent en production :

- Produire le nom explicite de la compétence, sans formulation de maîtrise ou
  d'expérience : `maîtrise de Python` → `Python`, `expérience avec Docker` → `Docker`.
- Effectuer cette sélection uniquement si le caractère obligatoire est établi.
- Exclure explicitement les exigences niées (`Python non requis`), les souhaits,
  les compétences facultatives, le contexte et les cas ambigus.
- Préserver les noms composés et les distinctions significatives : `gestion de
  projet`, `Docker Compose`, `C++`, `C#`, `JavaScript`. Aucun ajout de synonyme,
  expansion d'acronyme, rapprochement par sous-chaîne ou fuzzy matching.
- Conserver les règles sur les alternatives et les instructions parasites.

Le matcher, l'orchestrateur, les schémas publics, les erreurs HTTP, le client
Azure, le nombre d'appels et le frontend restent inchangés. Aucune dépendance
n'est ajoutée.

Le corpus unique de huit offres est enrichi sans changer ses attendus ni sa
cardinalité : le cas `explicit` comprend les formulations « maîtrise de Python »
et « expérience avec FastAPI » ; `preferred` comprend « Kubernetes non requis ».
La baseline couvre désormais ces formulations lors d'une éventuelle évaluation
réelle ultérieure explicitement autorisée, sans changer les métriques.

## Tests et portée de la validation

Les tests existants avec `httpx.MockTransport` et le vrai SDK sont réutilisés.
Les nouveaux scénarios inspectent séparément les réponses des endpoints CV et
jobs, le résultat direct du matcher, puis `/api/v1/matching/analyze` :

- Python/FastAPI/Git contre Python/Docker obligatoires : 50 %.
- SQL/Git contre Python/Docker : 0 %.
- Python/Docker contre Python/Docker : 100 %.
- Git/Kubernetes seulement facultatifs : `not_scorable`, `score: null`.
- Python non requis ou apprécié : liste vide et état non calculable.
- Docker obligatoire avec Python explicitement non requis : Python ne correspond pas.
- Alternative Python/Java avec Docker obligatoire : Docker seul.

Le test vérifie que les nouvelles consignes sont effectivement envoyées dans le
message système, séparément du texte non fiable, avec `store=False`. Les réponses
structurées sont **simulées explicitement** : ces tests valident les contrats,
le parsing et la composition, pas une compréhension de l'annonce par Azure.

Les tests déterministes négatifs vérifient l'absence de correspondance partielle
dans les deux sens : Python/CPython, Java/JavaScript, Docker/Docker Compose,
Git/GitLab, C/C++ et C++/C#. La reproduction avec les libellés phrastiques reste
volontairement à 0 %, pour interdire un correctif permissif dans le matcher.

La fixture globale retire la configuration Azure et bloque les transports HTTP
externes. Aucun secret ou document personnel réel n'est nécessaire. Seule une
évaluation réelle ultérieure pourrait mesurer le respect de la nouvelle consigne
par le modèle ; elle n'est ni lancée ni autorisée implicitement par ces tests.
