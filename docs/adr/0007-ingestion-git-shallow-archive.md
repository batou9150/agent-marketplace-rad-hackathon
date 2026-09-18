# ADR-007 : Ingestion V1 par URL Git shallow ou archive bornée

* **Statut** : Proposé (proposed)
* **Date** : 2026-09-18
* **Auteur** : Vibe Guard Team

## Contexte
L'agent doit accepter en entrée le code source d'applications vibe-codées provenant de différentes sources sans risque de saturation des ressources locales ni compromission de la confidentialité (Contraintes C1, C2).

## Décision
Pour le MVP V1, limiter les modes d'ingestion à deux mécanismes strictement contrôlés :
1. **URL de dépôt Git** : Cloner le dépôt avec `git clone --depth 1` (shallow clone) via HTTPS (avec token optionnel pour dépôts privés).
2. **Archive compressée** : Téléversement ou téléchargement d'archives `.zip` ou `.tar.gz` avec validation stricte (taille maximale décompressée bornée, vérification anti "zip slip").

Dans tous les cas :
* Extraction/clone dans un répertoire temporaire éphémère (`tempfile.TemporaryDirectory`).
* Purge inconditionnelle garantie par un bloc `finally` ou un context manager Python.
* Aucune persistance des fichiers du dépôt après le scan.

## Justification
* Mécanisme universel et simple pour les utilisateurs en phase MVP (§PRD-4.1).
* Garantit l'absence d'empreinte mémoire ou disque résiduelle sur les machines hôtes.
* Le clone shallow limite le volume de données transféré au commit le plus récent.

## Alternatives écartées
* **Intégration GitHub App / Webhooks / GitLab App** : Trop complexe pour un MVP V1, repoussé en V2.
* **Synchronisation de bucket Cloud Storage permanente** : Risque de stockage prolongé de code sensible non purgé (contraire à C2).

## Conséquences
* Le module `src/vibe_guard/ingest` doit être rigoureusement testé pour garantir la suppression du dossier temporaire même en cas de crash, d'annulation ou d'exception non gérée.
