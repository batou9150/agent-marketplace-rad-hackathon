# ADR-006 : Déploiement Cloud Run en conteneur durci non-root

* **Statut** : Proposé (proposed)
* **Date** : 2026-09-18
* **Auteur** : Vibe Guard Team

## Contexte
Vibe Guard doit être déployé sur Google Cloud comme service d'agent HTTP/A2A, avec une empreinte opérationnelle minimale et un niveau de sécurité exemplaire respectant ses propres règles de gouvernance réseau et sécurité.

## Décision
Déployer l'agent Vibe Guard sur **Google Cloud Run** en tant que service conteneurisé :
* Image minimale sans shell ou distroless, exécutée avec un utilisateur **non-root**.
* Binaires Semgrep et gitleaks embarqués directement dans l'image.
* Accès privé sécurisé (IAM ou Identity-Aware Proxy).
* Respect intrinsèque des règles `NET-ISO` définies dans le pack de règles Vibe Guard (l'agent scanné par lui-même ne doit produire aucune alerte).

## Justification
* Cloud Run offre un modèle serverless scalable à coût nul à l'arrêt, idéal pour un MVP et des charges de scans discontinues.
* Simplicité de gestion par rapport à un cluster GKE.
* Cohérence totale avec les remédiations et recommandations GCP-natives que l'agent fournit à ses utilisateurs.

## Alternatives écartées
* **Google Kubernetes Engine (GKE)** : Complexité et coûts d'infrastructure disproportionnés pour le MVP V1.
* **Cloud Functions** : Contraintes de packaging binaire (semgrep, gitleaks) et limites de timeout/mémoire moins flexibles que Cloud Run.

## Conséquences
* La construction du conteneur doit embarquer les binaires précompilés et vérifier les permissions de l'utilisateur non-root pour l'accès aux répertoires temporaires (`/tmp`).
* Définition d'un fichier de déploiement déclaratif `deploy/cloudrun.yaml`.
