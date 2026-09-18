# ADR-005 : Rôle ciblé de Gemini (Remédiation contextualisée & déduplication)

* **Statut** : Proposé (proposed)
* **Date** : 2026-09-18
* **Auteur** : Vibe Guard Team

## Contexte
L'usage de modèles d'IA générative dans un outil de sécurité doit garantir un haut niveau de déterminisme, de reproductibilité et de sécurité des données analysées (Contrainte C1, C2, C7).

## Décision
Restreindre strictement le rôle de Gemini (via Vertex AI) dans le MVP V1 à deux tâches précises :
1. **Rédaction de remédiations contextualisées** : Transformer un finding brut (métadonnées de la règle + extrait de code borné) en conseils et étapes d'architecture GCP personnalisés pour l'utilisateur.
2. **Déduplication et regroupement sémantique** : Regrouper des findings similaires ou contigus pour alléger le rapport final sans masquer de vulnérabilité distincte.

**Aucune détection de vulnérabilité par LLM "zero-rule" n'est réalisée en V1.**

## Justification
* **Déterminisme et auditabilité** : La phase de détection est 100 % reproductible et vérifiable par tests unitaires et d'intégration sur des fixtures.
* **Sécurité du code (C2)** : Aucun fichier entier ou projet complet n'est envoyé au modèle. Seul un extrait strict et borné (fenêtre de quelques lignes autour du finding) transite vers l'API.
* **Résilience** : En cas d'indisponibilité ou d'erreur de l'API Vertex AI, le moteur bascule automatiquement sur la remédiation statique présente dans le pack de règles (mode dégradé robuste / flag `--no-llm`).

## Alternatives écartées
* **Détection par LLM sans règles (Zero-shot vulnerability detection)** : Non déterministe, sujette aux hallucinations, impossible à tester avec un rappel/précision garanti (violation de C7).

## Conséquences
* La détection repose intégralement sur la qualité du pack de règles Semgrep/gitleaks.
* Les prompts envoyés à Gemini doivent être versionnés et testés pour garantir le respect de la taille maximale des extraits.
