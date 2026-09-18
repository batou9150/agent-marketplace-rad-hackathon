# ADR-008 : Périmètre des langages et frameworks cibles pour le MVP V1

* **Statut** : Proposé (proposed)
* **Date** : 2026-09-18
* **Auteur** : Vibe Guard Team

## Contexte
Les applications générées par IA ("vibe coding") utilisent massivement certains écosystèmes bien identifiés pour le prototypage rapide (frameworks web légers en Python et JavaScript/TypeScript, conteneurisation Docker, infrastructure cloud as code). Il est essentiel de délimiter précisément le périmètre du MVP V1 afin d'éviter la dispersion d'effort.

## Décision
Restreindre le périmètre de détection V1 aux stacks et fichiers de configuration suivants :
1. **Python** : FastAPI, Flask, Streamlit.
2. **JavaScript / TypeScript** : Node.js (Express), Next.js.
3. **Infrastructure & Déploiement** : `Dockerfile`, manifests `Terraform` (fichiers `.tf` ciblés pour Cloud Run / GCP IAM / Networking).

Les langages ou frameworks hors de cette liste ne sont pas couverts en V1 et ne doivent faire l'objet d'aucune règle avant validation en V2.

## Justification
* Ces stacks représentent la très grande majorité des applications vibe-codées générées par des outils grand public (Cursor, Claude Artifacts, v0, Lovable, Bolt, etc.).
* Semgrep supporte nativement et avec une grande maturité ces syntaxes et langages.
* Les risques majeurs (secrets exposés, absence d'authentification sur les routes, appels LLM directs sans passerelle, exposition sur `0.0.0.0`) y sont fréquents et immédiatement remédiables.

## Alternatives écartées
* **Java, C#, Go, Rust** : Très peu représentés dans les prototypes vibe-codés rapides, complexité de règles disproportionnée pour un MVP.
* **Manifestes Kubernetes (K8s) bruts** : GKE étant hors du scope initial Cloud Run (ADR-006), Terraform et Dockerfile couvrent le besoin V1.

## Conséquences
* Le pack de règles initial `rules/` doit concentrer ses motifs et tests sur ces frameworks cibles.
* La documentation et les messages d'erreur doivent indiquer clairement les langages supportés.
