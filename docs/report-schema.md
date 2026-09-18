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
    "target": "/workspace/repo",
    "llm_remediation_enabled": true
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
  "findings": [ ... ]
}
```

### 2.2 Modèle d'une constatation (`Finding`)

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `finding_id` | `string` | Oui | UUID unique de l'occurrence trouvée |
| `rule_id` | `string` | Oui | ID de la règle déclenchée (ex: `AUTH-001`, `SECRETS-001`) |
| `family` | `string` | Oui | `AUTH`, `SECRETS`, `LLM-GOV`, `NET-ISO` |
| `severity` | `string` | Oui | `critical`, `high`, `medium`, `low` |
| `title` | `string` | Oui | Intitulé clair de la non-conformité |
| `message` | `string` | Oui | Message contextualisé sur le motif détecté |
| `file_path` | `string` | Oui | Chemin relatif du fichier analysé |
| `line_number` | `integer` | Oui | Numéro de la ligne de détection principale |
| `snippet` | `object` | Non | Extrait de code borné autour du finding (C2) |
| `snippet.start_line` | `integer` | Non | Première ligne du snippet |
| `snippet.end_line` | `integer` | Non | Dernière ligne du snippet |
| `snippet.highlight_line` | `integer` | Non | Ligne ciblée |
| `snippet.content` | `string` | Non | Lignes de code (taille bornée, max 1500 car.) |
| `remediation` | `object` | Oui | Recommandation de remédiation GCP-native |
| `remediation.summary` | `string` | Oui | Synthèse de l'action corrective |
| `remediation.gcp_service` | `string` | Oui | Composant ou service Google Cloud cible |
| `remediation.steps` | `list[string]` | Oui | Étapes ordonnées pour remédier à la vulnérabilité |
| `remediation.reference_url` | `string` | Non | Lien officiel vers la documentation GCP ou WAF |
| `remediation.contextual_advice` | `string` | Non | Conseil généré par Gemini (ADR-005) à partir du snippet |

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
