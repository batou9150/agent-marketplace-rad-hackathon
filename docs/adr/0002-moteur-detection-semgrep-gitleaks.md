# ADR-002 : Moteur de détection basé sur Semgrep OSS et gitleaks

* **Statut** : Proposé (proposed)
* **Date** : 2026-09-18
* **Auteur** : Vibe Guard Team

## Contexte
Vibe Guard doit analyser statiquement le code source d'applications vibe-codées sans jamais exécuter le code cible (Contrainte C1) et en réutilisant l'open source existant (Contrainte C3).

## Décision
Utiliser **Semgrep OSS** pour les règles de détection sur le code source (AST et motifs syntaxiques) et **gitleaks** pour la détection des secrets et tokens sensibles, tous deux orchestrés directement depuis le moteur Python.

## Justification
* Semgrep OSS supporte nativement des règles déclaratives en YAML (aligné avec C4) et couvre les langages cibles (Python, JavaScript/TypeScript, Dockerfile, Terraform).
* Semgrep permet de cibler la structure du code avec précision sans dépendances d'exécution.
* Gitleaks est le standard open source reconnu pour la recherche rapide et éprouvée de secrets, clés API et jetons dans les dépôts.
* Les sorties JSON structurées des deux outils permettent une normalisation aisée en objets `Finding`.

## Alternatives écartées
* **Détecteurs regex maison** : Trop fragiles, complexes à maintenir, réinvention de la roue (violation de C3).
* **CodeQL** : Licence propriétaire GitHub incompatible avec un usage commercial SaaS / Marketplace tiers sans accord spécifique.
* **SonarQube / Bandit / ESLint** : Éparpillement d'outils hétérogènes nécessitant plusieurs configurations et runtimes complexes.

## Conséquences
* Les binaires `semgrep` et `gitleaks` doivent être présents dans l'environnement d'exécution (CLI local, CI et conteneur de déploiement).
* L'orchestrateur Python doit gérer proprement les erreurs d'exécution des outils sous forme de findings typés `tool_error`.
