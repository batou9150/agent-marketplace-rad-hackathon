# Spécification du schéma de rapport Vibe Guard (Report Schema)

Ce document spécifie le format des rapports de sécurité et de conformité générés par Vibe Guard (Phase 3, ADR-005).

---

## 1. Vue d'ensemble

Le rapport Vibe Guard est généré sous deux formats :
1. **JSON (`application/json`)** : Contrat d'API strict, typé et validé via un modèle Pydantic (`Report`). C'est le format consommé par les agents A2A et les pipelines CI/CD.
2. **Markdown (`text/markdown`)** : Synthèse structurée lisible par un humain (développeur, RSSI, tech lead).

---

## 2. Schéma JSON (`Report`)

### 2.1 Structure racine

```json
{
  "$schema": "https://vibe-guard.dev/schemas/v1/report.json",
  "version": "1.0.0",
  "metadata": {
    "scan_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "timestamp": "2026-09-18T10:00:00Z",
    "duration_seconds": 1.42,
    "caller_id": "anonymous",
    "pack_version": "0.1.0",
    "target": "src/my_app",
    "llm_remediation_enabled": true,
    "prompt_version": "v1"
  },
  "summary": {
    "total_findings": 3,
    "by_severity": {
      "critical": 1,
      "high": 1,
      "medium": 1,
      "low": 0
    },
    "by_family": {
      "AUTH": 1,
      "SECRETS": 1,
      "LLM-GOV": 1,
      "NET-ISO": 0
    }
  },
  "engine_status": {
    "semgrep": {
      "status": "ok",
      "version": "1.70.0",
      "error_message": null,
      "covered_families": ["AUTH", "LLM-GOV", "NET-ISO"],
      "degraded_families": []
    },
    "gitleaks": {
      "status": "ok",
      "version": "8.18.2",
      "error_message": null,
      "covered_families": ["SECRETS"],
      "degraded_families": []
    },
    "coverage_degraded": []
  },
  "findings": [ ... ]
}
```

### 2.2 Champs racines (`Report` - SPEC-REP-1)

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `$schema` | `string` | Oui | URI canonique du schéma (`https://vibe-guard.dev/schemas/v1/report.json`) |
| `version` | `string` | Oui | Version du schéma de rapport (`1.0.0`) |
| `metadata` | `object` | Oui | Métadonnées d'exécution et de contexte du scan |
| `summary` | `object` | Oui | Synthèse statistique globale des non-conformités |
| `engine_status` | `object` | Oui | Statut d'exécution et couverture des scanners |
| `findings` | `list[object]` | Oui | Liste détaillée et ordonnée des constatations |

### 2.3 Métadonnées d'exécution (`metadata` - ReportMetadata)

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `scan_id` | `string` | Oui | Identifiant unique du scan (UUID) |
| `timestamp` | `string` | Oui | Date et heure ISO 8601 UTC de début d'analyse |
| `duration_seconds` | `number` | Oui | Durée totale d'analyse en secondes |
| `caller_id` | `string` | Oui | Identité authentifiée de l'appelant (ou `anonymous` en local) |
| `pack_version` | `string` | Oui | Version sémantique du pack de règles évalué |
| `target` | `string` | Oui | Cible ou dépôt analysé (chemin relatif hôte proscrit) |
| `llm_remediation_enabled` | `boolean` | Oui | `true` si l'enrichissement Gemini a été activé |
| `prompt_version` | `string` | Non | Version du template de prompt LLM utilisé (ex: `v1`) |

### 2.4 Synthèse des constatations (`summary` - ReportSummary)

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `total_findings` | `integer` | Oui | Nombre total de non-conformités (égal à `len(findings)`) |
| `by_severity` | `dict[string, int]` | Oui | Compteurs par sévérité (`critical`, `high`, `medium`, `low`) |
| `by_family` | `dict[string, int]` | Oui | Compteurs par famille (`AUTH`, `SECRETS`, `LLM-GOV`, `NET-ISO`) |

### 2.5 Modèle du statut des moteurs (`engine_status` - SPEC-REP-6)

#### Structure globale (`EngineStatus`)

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `semgrep` | `object` | Oui | Statut d'exécution et version du scanner Semgrep OSS (`ScannerStatus`) |
| `gitleaks` | `object` | Oui | Statut d'exécution et version du scanner Gitleaks (`ScannerStatus`) |
| `coverage_degraded` | `list[string]` | Oui | Liste agrégée des familles non couvertes suite à un échec d'outil |

#### Détail d'un scanner (`ScannerStatus`)

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `status` | `string` | Oui | `ok`, `error`, ou `skipped` |
| `version` | `string` | Non | Version du binaire utilisé |
| `error_message` | `string` | Non | Message d'erreur si échec |
| `covered_families` | `list[string]` | Oui | Familles de sécurité couvertes par ce scanner |
| `degraded_families` | `list[string]` | Oui | Familles dont l'évaluation a échoué pour ce scanner |

### 2.6 Modèle d'une constatation (`Finding` - ReportFinding)

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `finding_id` | `string` | Oui | UUID unique de l'occurrence trouvée |
| `rule_id` | `string` | Oui | ID de la règle déclenchée (ex: `AUTH-001`, `SECRETS-001`) |
| `family` | `string` | Oui | Famille de sécurité (`AUTH`, `SECRETS`, `LLM-GOV`, `NET-ISO`) |
| `severity` | `string` | Oui | Niveau de gravité (`critical`, `high`, `medium`, `low`) |
| `title` | `string` | Oui | Intitulé clair de la non-conformité |
| `message` | `string` | Oui | Message contextualisé sur le motif détecté |
| `file_path` | `string` | Oui | Chemin relatif du fichier analysé (sans préfixe hôte) |
| `line_number` | `integer` | Oui | Numéro de la ligne de détection principale |
| `snippet` | `object` | Non | Extrait de code borné autour du finding (`ReportSnippet`, C2) |
| `remediation` | `object` | Oui | Recommandation de remédiation GCP-native (`ReportRemediation`) |

### 2.7 Extrait borné de code (`snippet` - ReportSnippet - C2)

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `start_line` | `integer` | Oui | Première ligne de l'extrait de code |
| `end_line` | `integer` | Oui | Dernière ligne de l'extrait de code |
| `highlight_line` | `integer` | Oui | Ligne précise déclenchant la règle |
| `content` | `string` | Oui | Lignes de code (taille bornée, max 1500 car. hors marqueur C2) |

### 2.8 Remédiation GCP (`remediation` - ReportRemediation)

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `summary` | `string` | Oui | Synthèse claire de l'action corrective |
| `gcp_service` | `string` | Oui | Composant ou service Google Cloud cible |
| `steps` | `list[string]` | Oui | Étapes ordonnées pour remédier à la vulnérabilité |
| `reference_url` | `string` | Non | Lien officiel vers la documentation GCP ou WAF |
| `contextual_advice` | `string` | Non | Conseil contextuel généré par Gemini (ADR-005) à partir du snippet |

---

## 3. Rendu Markdown

Le rendu Markdown génère un rapport lisible contenant :
- Un bandeau récapitulatif avec le statut global du scan et la sévérité maximale observée.
- Un tableau de bord des constatations par sévérité et par famille de sécurité.
- Le détail chronologique ordonné par sévérité décroissante (`critical` -> `high` -> `medium` -> `low`).
- Pour chaque finding :
  - Métadonnées (règle, fichier, ligne)
  - Bloc de code avec l'extrait borné
  - Remédiation GCP statique (services, étapes, lien)
  - Remédiation contextualisée Gemini si activée.

---

## 4. Règles de conformité et déterminisme

1. **Déterminisme (ADR-005)** : À l'exception du champ `contextual_advice` (qui provient de l'inférence LLM), l'ensemble des champs du rapport est 100 % déterministe et reproductible d'un scan à l'autre sur un code source identique.
2. **Mode `--no-llm`** : Lorsque le drapeau `--no-llm` est activé ou en l'absence de connectivité Vertex AI, le champ `contextual_advice` est positionné à `null` et les remédiations statiques garantissent un rapport complet et directement actionnable.
3. **Borne des extraits (C2)** : Aucun snippet ne dépasse 1500 caractères, assurant la protection du code source et limitant le coût en tokens lors de l'appel LLM.
