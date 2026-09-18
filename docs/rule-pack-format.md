# Spécification du format des packs de règles (Rule Pack Format)

Ce document définit la spécification formelle du format déclaratif des règles de détection de Vibe Guard (conformément aux contraintes C4 et C5, et à l'ADR-003).

## 1. Vue d'ensemble

Un pack de règles Vibe Guard est un ensemble de fichiers YAML versionné. Il se compose :
1. D'un manifeste principal : `rules/pack.yaml`
2. De définitions de règles classées par famille :
   - `rules/auth/*.yaml` : Authentification et contrôle d'accès
   - `rules/secrets/*.yaml` : Secrets, clés et tokens sensibles
   - `rules/llm-gov/*.yaml` : Gouvernance, résilience et sécurité des appels LLM
   - `rules/net-iso/*.yaml` : Isolation réseau, ports et durcissement d'infrastructure

Chaque règle est une enveloppe déclarant les métadonnées produit et la remédiation GCP-native statique, tout en encapsulant ou référençant la configuration du moteur d'analyse statique sous-jacent (Semgrep OSS ou gitleaks).

---

## 2. Manifeste du pack (`pack.yaml`)

Le fichier `pack.yaml` décrit la version du pack et les familles activées :

```yaml
version: "0.1.0"
name: "vibe-guard-core"
description: "Pack de règles standard pour applications vibe-codées"
families:
  - id: AUTH
    name: "Authentication & Access Control"
    description: "Détection des failles d'authentification, credentials en clair et absence d'IAP"
  - id: SECRETS
    name: "Secret & Credential Leakage"
    description: "Détection de clés d'API et secrets exposés dans le code et les configurations"
  - id: LLM-GOV
    name: "LLM Governance & Guardrails"
    description: "Encadrement des appels directs aux LLMs, gestion des timeouts et injection de prompts"
  - id: NET-ISO
    name: "Network Isolation & Hardening"
    description: "Exposition réseau excessive, bindings dangereux et conteneurs non durcis"
```

---

## 3. Schéma d'une règle

Chaque fichier de règle YAML contient un objet racine avec les champs suivants :

### 3.1 Métadonnées produit obligatoires (6 champs)

| Champ | Type | Valeurs autorisées / Description |
|---|---|---|
| `id` | `string` | Identifiant unique (ex. `AUTH-001`, `LLM-002`, `NET-003`) |
| `family` | `string` | `AUTH`, `SECRETS`, `LLM-GOV`, `NET-ISO` |
| `severity` | `string` | `critical`, `high`, `medium`, `low` |
| `title` | `string` | Titre clair et concis de la non-conformité |
| `rationale` | `string` | Explication du risque sécurité / opérationnel pour une application vibe-codée |
| `remediation` | `object` | Objet structurant la remédiation GCP-native statique (voir §3.2) |

### 3.2 Structure de l'objet `remediation`

L'objet de remédiation GCP-native comporte obligatoirement :
- `summary` (`string`) : Résumé de l'action corrective recommandée.
- `gcp_service` (`string`) : Service GCP cible (ex. `Google Cloud Armor`, `Secret Manager`, `Identity-Aware Proxy (IAP)`, `Vertex AI`, `Cloud Run`).
- `steps` (`list[string]`) : Étapes concrètes pour corriger le problème dans l'architecture.
- `reference_url` (`string`, optionnel) : Lien vers la documentation officielle GCP ou WAF.

### 3.3 Configuration du moteur (`engine`)

Spécifie l'outil OSS chargé de détecter la règle :
- `type` (`string`) : `semgrep` ou `gitleaks`
- `semgrep_rule` (`object`, requis si `type == "semgrep"`) : Définition YAML standard d'une règle Semgrep valide (contenant `id`, `message`, `languages`, `severity`, et au moins un motif `pattern`, `patterns`, ou `pattern-either`).
- `gitleaks_rule` (`object`, requis si `type == "gitleaks"`) : Identifiant ou regex ciblé pour le moteur gitleaks.

### 3.4 Exemple complet

```yaml
id: AUTH-001
family: AUTH
severity: high
title: "Route HTTP FastAPI non protégée sans middleware d'authentification"
rationale: "Les applications vibe-codées exposent fréquemment des endpoints de modification de données sans mécanisme de contrôle d'accès ou dépendance d'authentification, les rendant accessibles à tout utilisateur non authentifié."
example: |
  @app.post("/api/admin/update")
  def update_data(payload: dict):
      return db.update(payload)
remediation:
  summary: "Protéger les routes sensibles via Cloud IAP ou un middleware d'authentification OAuth2/JWT"
  gcp_service: "Identity-Aware Proxy (IAP)"
  steps:
    - "Activer Identity-Aware Proxy (IAP) devant le service Cloud Run ou la passerelle API"
    - "Exiger l'en-tête de validation 'X-Goog-Authenticated-User-Email' dans le middleware d'application"
    - "Ou injecter un Security Dependency FastAPI (ex. HTTPBearer ou OAuth2PasswordBearer)"
  reference_url: "https://cloud.google.com/iap/docs/concepts-overview"
engine:
  type: semgrep
  semgrep_rule:
    id: fastapi-unprotected-admin-route
    languages: [python]
    severity: WARNING
    message: "Route administrative FastAPI exposée sans dépendance de sécurité"
    patterns:
      - pattern: |
          @$APP.post("/admin/$...", ...)
          def $FUNC(...):
              ...
      - pattern-not: |
          @$APP.post("/admin/$...", ..., dependencies=$DEPS, ...)
          def $FUNC(...):
              ...
```

---

## 4. Validation et gestion des erreurs

Le chargeur de règles (`src/vibe_guard/rules/loader.py`) valide rigoureusement chaque règle lors du chargement :
- Tout champ obligatoire manquant ou non conforme au type attendu lève une exception explicite `RuleValidationError` précisant le fichier et le chemin JSON/YAML du champ invalide.
- L'ID d'une règle doit être unique à l'échelle du pack complet.
