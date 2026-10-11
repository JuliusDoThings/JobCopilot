# Architecture de l'extraction de CV

La route `cv/routes.py` gère uniquement le contrat HTTP : validation via les
schémas, injection du service et traduction de l'absence de fournisseur en 503.
`cv/schemas.py` définit l'entrée normalisée et le profil structuré.

`cv/service.py` expose le contrat `CVExtractor` (`typing.Protocol`), sa dépendance
FastAPI et l'adaptateur non configuré. Le contrat représente directement le
service métier : aucune couche supplémentaire ne se contente de transmettre
l'appel. Il accepte du texte déjà validé et renvoie un `CVProfile`.

Un futur adaptateur Azure OpenAI implémentera `extract(cv_text) -> CVProfile` et
sera sélectionné dans `get_cv_extractor`. Les appels fournisseur, la configuration
et la validation de sa réponse resteront isolés de la route HTTP. Aucun SDK ni
appel LLM n'est présent à cette étape.

Les tests remplacent cette dépendance par un `FakeExtractor` à réponse fixe et
restaurent les overrides après chaque test. Cela vérifie le contrat sans réseau,
sans secret et sans vrais CV. Le texte des CV n'est pas journalisé par notre code.
