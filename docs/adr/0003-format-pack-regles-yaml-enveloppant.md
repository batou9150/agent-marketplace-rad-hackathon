# ADR-003 : Format de pack de règles YAML propriétaire enveloppant

* **Statut** : Proposé (proposed)
* **Date** : 2026-09-18
* **Auteur** : Vibe Guard Team

## Contexte
L'agent a besoin d'un référentiel de règles déclaratif et extensible (Contrainte C4) pouvant être enrichi sans modifier le code source Python. Chaque règle doit porter non seulement le mécanisme de détection, mais également des métadonnées riches destinées au rapport et à la remédiation GCP-native (Contrainte C5).

## Décision
Adopter un format de **pack de règles en YAML propriétaire léger** qui *enveloppe* la définition de détection Semgrep ou gitleaks sous-jacente et y adjoint 6 champs de métadonnées obligatoires :
1. `id` : identifiant unique de la règle (ex. `AUTH-001`, `SECRETS-001`)
2. `family` : famille (`AUTH`, `SECRETS`, `LLM-GOV`, `NET-ISO`)
3. `severity` : niveau de criticité (`critical`, `high`, `medium`, `low`)
4. `title` : titre synthétique explicatif
5. `rationale` : justification du risque pour l'application vibe-codée
6. `example` : exemple de code non conforme
7. `remediation` : remédiation GCP-native statique (recommandation d'architecture sécurisée)
8. `engine` : configuration du détecteur sous-jacent (motif Semgrep ou règle gitleaks)

## Justification
* Sépare nettement "comment détecter" (délégué à l'outillage OSS standard) de "pourquoi c'est un problème et comment corriger" (valeur ajoutée spécifique du produit Vibe Guard).
* Permet à un utilisateur ou à une équipe sécurité d'ajouter des règles personnalisées via un simple fichier YAML documenté.
* Facilite la génération d'un rapport complet même en mode hors-ligne sans appel LLM (`--no-llm`).

## Alternatives écartées
* **Métadonnées Semgrep brutes uniquement** : Le schéma de métadonnées natif de Semgrep est insuffisant pour porter la structuration des remédiations GCP-natives et le typage strict requis par notre schéma de rapport.

## Conséquences
* Nécessite un chargeur et un validateur de schéma strict (Pydantic / Cerberus) dans `vibe_guard.rules`.
* Tout pack invalide doit échouer de manière explicite dès le démarrage du scan en indiquant le chemin précis de l'erreur.
