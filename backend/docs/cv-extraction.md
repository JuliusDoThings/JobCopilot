# Architecture de l'extraction de CV

La route `cv/routes.py` gère uniquement le contrat HTTP : validation via les
schémas, injection du service et traduction de l'absence de fournisseur en 503.
`cv/schemas.py` définit l'entrée normalisée et le profil structuré.

`cv/service.py` expose le contrat `CVExtractor` (`typing.Protocol`), sa dépendance
FastAPI et l'adaptateur non configuré. Le contrat représente directement le
service métier : aucune couche supplémentaire ne se contente de transmettre
l'appel. Il accepte du texte déjà validé et renvoie un `CVProfile`.

`cv/azure.py` implémente `extract(cv_text) -> CVProfile` avec le client synchrone
OpenAI 2.54.0 et Responses sur l'API Azure v1 GA. `config.py` lit uniquement les
variables du processus ; une configuration absente, partielle ou invalide
conserve l'adaptateur non configuré, sans empêcher le démarrage. L'endpoint doit
être celui de la ressource Azure, pas l'URL du projet Foundry.

La dépendance construit le client à la demande et le ferme après la requête.
La route synchrone `def` est exécutée dans le pool de threads de FastAPI : l'appel
SDK occupe un thread pendant l'attente sans bloquer la boucle asynchrone.
Cela conserve le contrat S1-001 ; un passage à l'asynchrone pourra être étudié
avec les besoins de concurrence.

`responses.parse(text_format=CVProfile)` génère un schéma JSON strict et valide
la sortie. Le profil refuse aussi les champs inconnus et les types incorrects.
L'adaptateur contrôle le statut, les refus et la présence du profil, puis valide
à nouveau avec Pydantic. Les instructions sont séparées du CV, transmis uniquement
comme donnée utilisateur. Aucune mémoire de conversation, aucun outil et aucune
réponse factice ne sont utilisés. `store=False` désactive le stockage de la réponse
par Responses ; ce paramètre ne constitue pas une garantie de rétention nulle
pour tous les mécanismes Azure.

Le timeout SDK vaut 30 secondes par opération réseau, pas une échéance globale.
`max_retries=1` signifie au maximum deux tentatives : la première et un retry.
Dans le SDK installé, les erreurs de connexion, timeouts, HTTP 408/409/429 et 5xx
sont éligibles. Le SDK respecte aussi les indications serveur ; une réponse
non réessayable ne consomme pas de seconde tentative. Aucun retry applicatif.
L'attente serveur et les deux tentatives peuvent dépasser 60 secondes au total.
La sortie est limitée à 2 000 tokens ; une sortie tronquée est un échec 502.

`cv/errors.py` expose uniquement des erreurs métier à messages fixes. La route
les traduit en HTTP sans transmettre les exceptions SDK ou les refus bruts.
HTTP 503 distingue configuration absente et fournisseur indisponible par le
message ; 504 signale un timeout ; 502 signale un refus, une réponse invalide
ou une autre erreur fournisseur. HTTP 422 reste la validation de l'entrée.

Les tests remplacent cette dépendance par un `FakeExtractor` à réponse fixe et
restaurent les overrides après chaque test. Cela vérifie le contrat sans réseau,
sans secret et sans vrais CV. Les tests Azure utilisent le vrai SDK avec
`httpx.MockTransport` pour vérifier sérialisation, parsing et nombre de tentatives.
Une fixture retire la configuration locale et bloque le transport HTTP externe.
Le texte des CV et les réponses brutes ne sont pas journalisés par notre code.

Références vérifiées :

- [Azure v1 GA et client OpenAI](https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle)
- [Responses et modèles compatibles](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses)
- [Sorties structurées Azure](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs)
- [SDK Python](https://developers.openai.com/api/reference/python)

Microsoft liste `gpt-4.1-mini` version `2025-04-14` comme compatible. La région,
l'endpoint, les droits et la version du déploiement réel doivent être vérifiés
par l'essai manuel : les tests logiciels ne prouvent pas cet accès.
