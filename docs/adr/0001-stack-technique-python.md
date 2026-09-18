# ADR-001 : Stack technique Python 3.12, uv, ruff, pytest

* **Statut** : Proposé (proposed)
* **Date** : 2026-09-18
* **Auteur** : Vibe Guard Team

## Contexte
Le projet Vibe Guard nécessite un écosystème robuste, moderne et rapide pour orchestrer des analyses statiques, parser du YAML/JSON, interagir avec les SDKs Google Cloud / Vertex AI / Google ADK, et exécuter des tests de validation stricts.

## Décision
Adopter **Python 3.12** comme langage de référence du projet, avec l'outillage standardisé suivant :
* Gestionnaire d'environnement et de dépendances : `uv`
* Linter et formateur de code : `ruff`
* Framework de tests : `pytest`
* Gestion des hooks git : `pre-commit`

## Justification
* Alignement direct avec le SDK Python de Google ADK et les SDKs officiels Vertex AI / Google Cloud.
* Semgrep s'intègre nativement dans l'écosystème Python.
* `uv` apporte une vitesse d'exécution et de résolution de dépendances déterministe et reproductible.
* `ruff` unifie linting et formatage avec des performances optimales.

## Alternatives écartées
* **TypeScript / Node.js** : Bien que Google ADK JS existe, l'outillage de sécurité statique (wrapper Semgrep/gitleaks et manipulation AST) est nettement moins mûr et moins direct côté JS.

## Conséquences
* Toutes les dépendances doivent être compatibles avec Python 3.12.
* Les développeurs et l'environnement CI doivent disposer de `uv` pour synchroniser l'environnement.
