# Vibe Guard — Spécification produit et technique

**Version** : 1.0 — 2026-09-18
**Statut** : normative. Ce document **remplace** `plan-implementation-agent-vibe-coding.md` (conservé en annexe historique, statut `superseded`).
**Portée** : V1 (MVP publiable). Tout ce qui n'est pas exigé ici est hors périmètre — voir §10.

---

## 0. Comment ce document pilote le développement

Vibe Guard est développé en **spec-driven development** : la spécification est la source de vérité, le code en est une conséquence vérifiable.

### 0.1 Langage normatif

| Terme | Signification |
|---|---|
| **DOIT** / **DOIT NE PAS** | Exigence absolue. Une violation est un défaut bloquant, quelle que soit la phase. |
| **DEVRAIT** | Recommandation forte. Une dérogation DOIT être justifiée dans une ADR. |
| **PEUT** | Option laissée à l'implémentation. |

### 0.2 Règle de changement (non négociable)

1. Aucun comportement observable n'est implémenté sans exigence `SPEC-*` correspondante. Si le besoin n'est pas dans la spec, **on modifie la spec d'abord**, puis le code.
2. Toute exigence DOIT être **vérifiable par une commande** : un test automatisé, ou à défaut une procédure manuelle écrite dans la colonne *Vérification*.
3. Tout commit référence au moins un identifiant `SPEC-*` dans son message. Un commit sans exigence rattachée est un commit de tooling (`[CHORE]`) ou de documentation (`[DOC]`).
4. Une exigence marquée ⛔ ou ⚠️ en §11 ne PEUT pas être déclarée satisfaite sans la sortie de test qui le prouve, jointe à la PR.
5. Toute décision d'architecture non couverte par §9 DOIT faire l'objet d'une ADR `docs/adr/NNNN-*.md` soumise **avant** implémentation.

### 0.3 Identifiants d'exigences

`SPEC-<DOMAINE>-<n>` avec les domaines : `ING` (ingestion), `RUL` (référentiel de règles), `ENG` (moteur de détection), `REM` (remédiation), `REP` (rapport), `AUD` (audit), `AGT` (agent A2A), `OPS` (packaging, exécution, déploiement), `SEC` (invariants transverses).

### 0.4 Langue

Documentation produit, règles, remédiations et rendu Markdown : **français**. Code, identifiants, messages de log, commits, tests : **anglais**.

---

## 1. Produit

### 1.1 Problème

Les applications générées par assistant IA ("vibe codées") fonctionnent en démonstration mais franchissent rarement les prérequis d'une mise en production d'entreprise : authentification absente ou artisanale, secrets en clair, appels LLM directs sans passerelle ni garde-fou, exposition réseau par défaut. Elles arrivent en DSI sans revue d'architecture, souvent sans auteur technique identifié.

### 1.2 Proposition

Vibe Guard prend en entrée le **code source** d'une telle application et produit un **rapport de non-conformité priorisé, assorti d'un chemin de remédiation GCP-natif**, sans jamais exécuter ce code.

### 1.3 Acteurs

| Acteur | Attente |
|---|---|
| **Développeur / auteur de l'app** | Savoir ce qui bloque la mise en production et comment corriger. |
| **Architecte / RSSI / plateforme** | Décider *go / no-go* sur une base factuelle et traçable. |
| **Agent orchestrateur (A2A)** | Appeler Vibe Guard comme un outil dans une chaîne automatisée et consommer un rapport structuré. |

### 1.4 Cas d'usage V1

| ID | Cas d'usage | Sortie attendue |
|---|---|---|
| UC-1 | Scanner un dépôt Git distant (URL HTTPS) | Rapport JSON + Markdown |
| UC-2 | Scanner une archive `.zip` / `.tar.gz` fournie | Rapport JSON + Markdown |
| UC-3 | Interroger le rapport produit ("comment corriger SECRETS-001 ?") sans re-scanner | Réponse conversationnelle fondée sur le rapport en session |
| UC-4 | Exécuter le scan en CI ou hors ligne, sans LLM (`--no-llm`) | Rapport complet avec remédiations statiques |

### 1.5 Définition de « terminé » pour la V1

La V1 est terminée quand **toutes** les exigences `SPEC-*` marquées `V1` en §11 sont ✅, gates §8 comprises. Aucun autre critère (démo réussie, retour favorable, échéance) ne vaut acceptation.

---

## 2. Invariants (contraintes non négociables)

Ces invariants priment sur toute exigence fonctionnelle. En cas de conflit, l'invariant gagne et l'exigence est reformulée.

| ID | Invariant | Mécanisme d'application | Vérification |
|---|---|---|---|
| **SEC-1** | Le code scanné est de la **donnée**, jamais un exécutable. Aucun build, aucune installation de dépendances, aucun `import` dynamique, aucune exécution de script issu du dépôt scanné. | Analyse statique uniquement ; les seuls sous-processus autorisés sont les binaires d'outillage listés en `SPEC-OPS-1`. | Revue + `SPEC-ENG-7` |
| **SEC-2** | Le code scanné est **éphémère**. Il est extrait dans un répertoire temporaire dédié, purgé systématiquement, y compris sur exception. | `EphemeralWorkspace` (context manager, purge en `finally`). | `tests/eval/test_corpus.py::test_gate2_ephemeral_workspace_purged_on_normal_and_exception` ✅ |
| **SEC-3** | **Aucun fichier entier ne quitte le périmètre.** Seuls des extraits bornés autour d'un finding transitent vers un modèle. | `extract_bounded_snippet` + troncature explicite côté remédiation. | `SPEC-REM-3` ✅ |
| **SEC-4** | La **détection est déterministe**. Aucun LLM ne décide d'un finding en V1. | Semgrep + gitleaks pilotés par le pack de règles. | `SPEC-ENG-6` ✅ |
| **SEC-5** | Le **référentiel de règles est déclaratif**. Ajouter une règle DOIT NE PAS nécessiter de modification du code Python. | Pack YAML validé par schéma. | `SPEC-RUL-4` |
| **SEC-6** | **Traçabilité sans fuite** : chaque scan produit un enregistrement d'audit qui DOIT NE PAS contenir de code source, de secret détecté, ni de chemin absolu hôte. | `ScanAuditRecord`. | `SPEC-AUD-2` |
| **SEC-7** | **Aucun chiffre non mesuré.** Aucune métrique de performance, de précision ou de rappel ne figure dans le code, le README, la fiche produit ou l'agent card tant qu'elle n'est pas issue de `tests/eval/`. | Revue + CI. | `SPEC-OPS-6` |

> **SEC-3 précision** : « bornée » signifie ici ±4 lignes autour de la ligne du finding et ≤ 1 500 caractères, valeurs normatives fixées en `SPEC-ENG-5`. `docs/architecture.md` mentionne ±5 lignes : c'est une dérive documentaire, à corriger (`SPEC-OPS-7`).

---

## 3. Modèle de domaine

Les entités ci-dessous sont normatives. Les noms de champs sont ceux du contrat : les renommer est un changement cassant, soumis à §0.2.

### 3.1 `IngestSource` — description de la source à scanner

| Champ | Type | Oblig. | Règle |
|---|---|---|---|
| `type` | `"git_url" \| "archive" \| "directory"` | oui | `directory` réservé à l'usage local et aux tests ; refusé côté agent déployé (`SPEC-AGT-4`). |
| `location` | `string` | oui | URL HTTPS, chemin d'archive, ou chemin de répertoire. |
| `branch` | `string \| null` | non | `git_url` uniquement. |
| `credential_ref` | `string \| null` | non | **Référence** Secret Manager, jamais un token en clair (`SPEC-ING-7`). |

### 3.2 `IngestLimits` — bornes d'ingestion (valeurs normatives V1)

| Champ | Valeur V1 | Comportement au dépassement |
|---|---|---|
| `max_files` | 5 000 | `IngestionError`, scan non démarré |
| `max_total_bytes` | 50 Mio | `IngestionError`, scan non démarré |
| `max_file_bytes` | 5 Mio | `IngestionError`, scan non démarré |

Ces valeurs sont **configurables** mais leurs défauts sont normatifs : les modifier dans le code sans mettre à jour ce tableau est une violation de §0.2.

### 3.3 `RulePack` / `RuleDef`

Format complet : `docs/rule-pack-format.md`. Champs obligatoires d'une règle : `id`, `family`, `severity`, `title`, `rationale`, `example`, `remediation{summary, gcp_service, steps[], reference_url?}`, `engine{type, semgrep_rule|gitleaks_rule}`.

- `family` ∈ `AUTH`, `SECRETS`, `LLM-GOV`, `NET-ISO`.
- `severity` ∈ `critical`, `high`, `medium`, `low`.
- `id` unique à l'échelle du pack, motif `^[A-Z0-9_-]+$`, convention `<FAMILLE>-<NNN>`.

### 3.4 `Finding` (interne) et `ReportFinding` (contrat)

`Finding` est le modèle interne normalisé produit par le moteur. `ReportFinding` est la projection publiée. Distinction normative : un `Finding` PEUT porter `is_tool_error=True` ; un `ReportFinding` DOIT NE PAS en porter — les erreurs d'outil sont remontées dans `report.engine_status` (`SPEC-REP-6`), jamais confondues avec une non-conformité applicative.

### 3.5 `Report`

Structure racine : `$schema`, `version`, `metadata`, `summary`, `engine_status`, `findings[]`. Détail des champs : `docs/report-schema.md`, qui DOIT être tenu synchrone du modèle Pydantic (`SPEC-REP-1`).

### 3.6 `ScanAuditRecord`

`scan_id`, `timestamp`, `caller_id`, `pack_version`, `rules_evaluated[]`, `rules_count`, `duration_seconds`, `target_type`, `total_findings`, `findings_by_severity`, `findings_by_family`. Aucun autre champ ne PEUT être ajouté sans revue au titre de SEC-6.

---

## 4. Contrats d'interface

### 4.1 API Python (surface stable)

Les signatures suivantes constituent le contrat interne. Les modifier est un changement cassant.

```python
# ingestion
with EphemeralWorkspace(limits: IngestLimits = ...) as ws:
    path: Path = ws.clone_git(git_url: str, branch: str | None = None, token: str | None = None)
    path: Path = ws.extract_archive(archive_path: Path | str)
# règles
pack: RulePack = load_rule_pack(rules_dir: Path | str)          # lève RuleValidationError
# détection
findings: list[Finding] = ScanEngine(pack).scan(target_dir: Path)
# remédiation
advices: dict[str, str] = RemediationGenerator(...).enrich_findings(findings, rule_pack=pack)
# rapport
report: Report = build_report(findings, scan_id, timestamp, duration_seconds,
                              caller_id, pack_version, target,
                              llm_remediation_enabled=False, contextual_advices=None)
report.to_json(); report.to_markdown()
# audit
AuditRecorder(...).record(record: ScanAuditRecord)
```

### 4.2 Outil agent `scan` (contrat A2A)

Entrée :

```json
{
  "source": {"type": "git_url", "location": "https://...", "branch": null, "credential_ref": null},
  "options": {"no_llm": false, "families": ["AUTH", "SECRETS", "LLM-GOV", "NET-ISO"], "format": "both"}
}
```

Sortie : objet `Report` (§3.5) sérialisé. `format` ∈ `json`, `markdown`, `both`.

L'agent DOIT exposer exactement deux capacités en V1 : `scan` (ci-dessus) et `explain_finding(finding_id | rule_id)` qui répond **depuis le rapport en session**, sans re-scanner (`SPEC-AGT-3`).

### 4.3 CLI

```
vibe-guard scan <source> [--branch B] [--rules DIR] [--no-llm] [--format json|markdown|both] [--out FILE]
vibe-guard rules validate [--rules DIR]
vibe-guard rules list [--family F]
```

Codes de sortie : `0` aucun finding ; `1` au moins un finding ; `2` erreur d'ingestion ou de configuration ; `3` dégradation de couverture (`SPEC-ENG-4`).

### 4.4 Taxonomie d'erreurs

| Code | Classe | Sens | Effet sur le scan |
|---|---|---|---|
| `E-ING-*` | `IngestionError` | source illisible, limite dépassée, traversée de chemin, clone en échec | arrêt avant scan |
| `E-RUL-*` | `RuleValidationError` | pack invalide — DOIT citer fichier + chemin du champ fautif | arrêt avant scan |
| `E-ENG-*` | erreur outil | binaire absent, timeout, sortie illisible | scan continue, couverture dégradée (`SPEC-ENG-4`) |
| `E-REM-*` | erreur LLM | Vertex AI indisponible, quota, réponse vide | repli silencieux sur remédiation statique |

Règle normative : une erreur `E-ING-*` ou `E-RUL-*` DOIT NE PAS produire de rapport. Un rapport n'existe que si le scan a effectivement eu lieu.

---

## 5. Exigences fonctionnelles

Colonne *Statut* : ✅ implémenté et couvert par un test vert au 2026-09-18 · ⚠️ implémenté partiellement ou non couvert · ⛔ non implémenté. L'état constaté est détaillé en §11.

### 5.1 Ingestion (`ING`)

| ID | Exigence | Critère d'acceptation | Statut |
|---|---|---|---|
| SPEC-ING-1 | Le système DOIT accepter trois types de source : dépôt Git HTTPS (clone `--depth 1`), archive `.zip`/`.tar.gz`/`.tgz`/`.tar`, répertoire local. | Un scan aboutit pour chacun des trois types. | ⚠️ |
| SPEC-ING-2 | Le répertoire de travail DOIT être unique par scan et purgé en sortie, y compris sur exception. | Test dédié vérifiant l'absence du chemin après sortie normale **et** après exception. | ✅ |
| SPEC-ING-3 | Les limites §3.2 DOIVENT être appliquées **avant** le lancement des scanners, et lors de l'extraction pour les archives. | Une archive de 6 000 fichiers échoue en `IngestionError` sans qu'aucun scanner ne démarre. | ⚠️ |
| SPEC-ING-4 | L'extraction DOIT rejeter toute entrée sortant du répertoire de travail (traversée de chemin), en utilisant une comparaison de chemins (`Path.is_relative_to`) et non une comparaison de préfixe de chaîne. | Fixture d'archive malveillante (`../../etc/passwd`) rejetée ; test de non-régression sur le cas frère (`/tmp/ws` vs `/tmp/ws-evil`). | ✅ |
| SPEC-ING-5 | L'extraction DOIT refuser les membres qui ne sont pas des fichiers réguliers ou des répertoires : liens symboliques, liens durs, périphériques, FIFO. L'extraction tar DOIT utiliser `filter="data"`. | Fixture d'archive contenant un symlink : rejet explicite, aucun lien créé. | ✅ |
| SPEC-ING-6 | Le clone Git DOIT être non interactif et non récursif : `GIT_TERMINAL_PROMPT=0`, `--no-recurse-submodules`, `core.hooksPath` neutralisé, protocoles limités à `https`. | Un dépôt avec sous-module ne déclenche aucun fetch supplémentaire ; un dépôt demandant des identifiants échoue en `IngestionError` sans blocage. | ✅ |
| SPEC-ING-7 | Un jeton d'accès DOIT NE PAS apparaître dans `argv`, dans l'URL du remote, ni dans un message d'erreur ou de log. Il est transmis par en-tête ou credential helper, depuis une **référence** Secret Manager. | `ps` pendant un clone authentifié ne révèle aucun secret ; les messages d'erreur sont masqués (test). | ✅ |
| SPEC-ING-8 | Le répertoire `.git` du dépôt cloné DOIT être exclu de l'analyse Semgrep ; il PEUT rester disponible pour l'analyse d'historique par gitleaks. | Aucun finding Semgrep dont le chemin commence par `.git/`. | ⚠️ |

### 5.2 Référentiel de règles (`RUL`)

| ID | Exigence | Critère d'acceptation | Statut |
|---|---|---|---|
| SPEC-RUL-1 | Le pack DOIT être chargé et validé par schéma ; toute règle invalide DOIT provoquer un échec explicite citant le fichier et le champ. | Fixture de règle invalide → `RuleValidationError` mentionnant chemin + champ. | ✅ |
| SPEC-RUL-2 | Les identifiants de règles DOIVENT être uniques dans le pack. | Deux règles de même `id` → échec au chargement. | ✅ |
| SPEC-RUL-3 | Chaque règle DOIT porter les 7 champs produit (`id`, `family`, `severity`, `title`, `rationale`, `example`, `remediation`) et une configuration `engine` cohérente avec son `type`. | Validation Pydantic `extra="forbid"` + test sur le pack livré. | ✅ |
| SPEC-RUL-4 | Ajouter, modifier ou désactiver une règle DOIT NE PAS nécessiter de modification du code Python. | Une règle ajoutée par simple dépôt d'un fichier YAML est évaluée au scan suivant. | ⚠️ |
| SPEC-RUL-5 | Le pack DOIT être versionné (`pack.yaml:version`, semver) et cette version DOIT figurer dans le rapport et l'audit. | `report.metadata.pack_version == pack.yaml:version`. | ✅ |
| SPEC-RUL-6 | Chaque famille DOIT compter au moins 3 règles en V1. | `len(pack.by_family(f)) >= 3` pour les 4 familles. | ✅ (12 règles) |
| SPEC-RUL-7 | Toute règle DOIT être accompagnée d'au moins une fixture non conforme la déclenchant et ne DOIT déclencher sur aucune fixture conforme. | Gate G2 (§8). | ⚠️ |

### 5.3 Moteur de détection (`ENG`)

| ID | Exigence | Critère d'acceptation | Statut |
|---|---|---|---|
| SPEC-ENG-1 | Le moteur DOIT exécuter Semgrep OSS avec les règles `type: semgrep` du pack et gitleaks pour les règles `type: gitleaks`, puis normaliser les sorties en `Finding`. | Scan d'une fixture mixte : findings des deux moteurs présents et normalisés. | ✅ |
| SPEC-ENG-2 | Chaque `Finding` DOIT hériter du pack : `severity`, `family`, `title`, remédiation statique. Aucune sévérité ne PEUT provenir de l'outil sous-jacent. | Sévérité du finding == sévérité de la règle, pour toutes les fixtures. | ✅ |
| SPEC-ENG-3 | L'échec d'un scanner (binaire absent, timeout, sortie illisible) DOIT NE PAS interrompre le scan. | Simulation d'absence de binaire : le scan aboutit. | ✅ |
| SPEC-ENG-4 | L'échec d'un scanner DOIT être remonté dans `report.engine_status` avec la ou les familles dont la couverture est dégradée, et le rapport DOIT NE PAS pouvoir être interprété comme « conforme ». | gitleaks absent → `engine_status.gitleaks.status == "error"`, `coverage_degraded == ["SECRETS"]`, code de sortie CLI `3`. | ✅ |
| SPEC-ENG-5 | L'extrait attaché à un finding DOIT être borné : ±4 lignes autour de la ligne détectée, ≤ 1 500 caractères, troncature explicitement marquée. | Aucun `snippet.content` > 1 500 caractères hors marqueur ; borne testée. | ✅ |
| SPEC-ENG-6 | La détection DOIT être déterministe : deux scans du même code produisent des findings identiques hors champs générés par LLM. | Test de déterminisme sur fixtures. | ✅ |
| SPEC-ENG-7 | Les seuls sous-processus autorisés sont `semgrep`, `gitleaks` et `git`, invoqués avec timeout et sans shell. Leur chemin DOIT provenir d'une variable de configuration (`VIBE_GUARD_<TOOL>_BIN`) ou du `PATH` ; il DOIT NE PAS être codé en dur sur un chemin de poste de développement. | Revue + absence de `shell=True` et de chemin absolu littéral dans le code (contrôle CI). | ✅ |
| SPEC-ENG-8 | Les timeouts DOIVENT être explicites : Semgrep 180 s, gitleaks 120 s, clone Git 120 s (valeurs V1, configurables). | Valeurs présentes et testées par simulation de dépassement. | ⚠️ |

### 5.4 Remédiation (`REM`)

| ID | Exigence | Critère d'acceptation | Statut |
|---|---|---|---|
| SPEC-REM-1 | Chaque finding DOIT porter une remédiation **statique** GCP-native issue du pack, indépendamment de toute disponibilité LLM. | Scan avec `--no-llm` : 100 % des findings ont `remediation.summary`, `gcp_service`, `steps` non vides. | ✅ |
| SPEC-REM-2 | Le LLM (Gemini via Vertex AI) DOIT être utilisé uniquement pour (a) contextualiser la remédiation, (b) regrouper les findings redondants. Il DOIT NE PAS créer, supprimer ni requalifier un finding. | Revue + test de déterminisme (`SPEC-ENG-6`). | ✅ |
| SPEC-REM-3 | Le prompt de remédiation DOIT NE PAS contenir plus que la règle, ses métadonnées et l'extrait borné. Aucun fichier entier, aucun chemin absolu hôte. | Test vérifiant la borne de l'extrait transmis. | ✅ |
| SPEC-REM-4 | Toute indisponibilité LLM DOIT provoquer un repli silencieux sur la remédiation statique, sans échec du scan. | Client LLM en erreur : rapport complet, `contextual_advice == null`. | ✅ |
| SPEC-REM-5 | Les prompts DOIVENT être versionnés dans le dépôt et référencés par version dans le rapport. | `report.metadata.prompt_version` présent quand `llm_remediation_enabled == true`. | ⚠️ (prompt versionné en fichier, non exposé dans le rapport) |
| SPEC-REM-6 | Le regroupement de findings DOIT être déterministe et DOIT NE PAS masquer une occurrence dans un autre fichier ou une autre règle. | Findings contigus (≤ 2 lignes, même règle, même fichier) fusionnés ; test dédié. | ✅ |

### 5.5 Rapport (`REP`)

| ID | Exigence | Critère d'acceptation | Statut |
|---|---|---|---|
| SPEC-REP-1 | Le rapport JSON DOIT valider contre le modèle publié, et `docs/report-schema.md` DOIT décrire exactement ce modèle. | Test de validation sur toutes les fixtures + contrôle de cohérence doc/modèle. | ⚠️ |
| SPEC-REP-2 | Les findings DOIVENT être triés par sévérité décroissante, puis famille, fichier, ligne. | Test d'ordre sur fixture multi-familles. | ✅ |
| SPEC-REP-3 | Le résumé DOIT compter les findings par sévérité et par famille, et ces totaux DOIVENT être cohérents avec la liste. | `sum(by_severity.values()) == total_findings == len(findings)`. | ⚠️ |
| SPEC-REP-4 | Le rendu Markdown DOIT être produit à partir du même objet `Report` que le JSON — aucune donnée présente dans l'un et absente de l'autre. | Test comparant les deux rendus sur une fixture. | ⚠️ |
| SPEC-REP-5 | Le rapport DOIT NE PAS contenir la valeur d'un secret détecté : seule sa localisation, son type et une empreinte tronquée sont publiés. | Test : fixture `app_secrets_leak` scannée, aucune valeur de clé présente dans le JSON ni dans le Markdown. | ✅ |
| SPEC-REP-6 | Le rapport DOIT porter un bloc `engine_status` déclarant, pour chaque scanner, son statut, sa version et les familles couvertes ou dégradées. | Voir `SPEC-ENG-4`. | ✅ |
| SPEC-REP-7 | Le rapport DOIT NE PAS contenir de chemin absolu de l'hôte : tous les chemins sont relatifs à la racine scannée. | Aucun `file_path` commençant par `/` ni contenant le préfixe du workspace. | ⚠️ |

### 5.6 Audit (`AUD`)

| ID | Exigence | Critère d'acceptation | Statut |
|---|---|---|---|
| SPEC-AUD-1 | Chaque scan DOIT produire un `ScanAuditRecord` (§3.6), qu'il ait ou non produit des findings. | Un scan sans finding produit tout de même un enregistrement. | ✅ |
| SPEC-AUD-2 | L'enregistrement DOIT NE PAS contenir de code, d'extrait, de secret ni de chemin absolu hôte. | Test d'absence de ces champs sur l'objet sérialisé. | ⚠️ |
| SPEC-AUD-3 | L'enregistrement DOIT être émis en log structuré exploitable par Cloud Logging. | Payload JSON une ligne, champs plats, `severity` normalisée. | ⚠️ |
| SPEC-AUD-4 | `caller_id` DOIT provenir de l'identité authentifiée de l'appelant en déploiement, et valoir `anonymous` uniquement en exécution locale. | Scan via agent déployé : `caller_id` == identité IAM/IAP. | ⛔ |

### 5.7 Agent A2A (`AGT`)

| ID | Exigence | Critère d'acceptation | Statut |
|---|---|---|---|
| SPEC-AGT-1 | L'agent DOIT être un agent ADK exposant l'outil `scan` conforme à §4.2. | Appel local de l'agent → rapport identique à l'appel direct de l'API Python. | ⛔ |
| SPEC-AGT-2 | L'agent DOIT publier une agent card A2A déclarant capacités, schémas d'entrée/sortie et mode d'authentification. | Card servie et validée contre la spec A2A. | ⛔ |
| SPEC-AGT-3 | `explain_finding` DOIT répondre uniquement à partir du rapport en session ; il DOIT NE PAS déclencher de nouveau scan. | Trace d'exécution sans invocation d'outil de scan. | ⛔ |
| SPEC-AGT-4 | En déploiement, la source `directory` DOIT être refusée. | Requête `type: directory` → erreur explicite. | ⛔ |
| SPEC-AGT-5 | Un scan DOIT NE PAS pouvoir être déclenché sans appelant authentifié. | Requête non authentifiée → 401/403, aucun scan, aucune trace d'audit de scan. | ⛔ |

### 5.8 Exécution, packaging, déploiement (`OPS`)

| ID | Exigence | Critère d'acceptation | Statut |
|---|---|---|---|
| SPEC-OPS-1 | L'image d'exécution DOIT embarquer `semgrep`, `gitleaks` et `git` à des versions épinglées, et le démarrage DOIT échouer si l'un manque. | `docker run` sans réseau : les trois binaires répondent `--version` ; suppression de l'un → démarrage en échec explicite. | ⛔ **écart connu** : `gitleaks` n'est aujourd'hui ni une dépendance déclarée ni packagée ; il est résolu via `PATH` (présent sur le poste, absent en CI/conteneur). |
| SPEC-OPS-2 | Le conteneur DOIT tourner en utilisateur non-root, sans shell, système de fichiers racine en lecture seule hormis le répertoire de travail éphémère. | Inspection de l'image + exécution. | ⛔ |
| SPEC-OPS-3 | Le service DOIT être privé (IAM/IAP), sa configuration issue de Secret Manager, avec un compte de service dédié à droits minimaux. | Déploiement inspecté ; accès anonyme refusé. | ⛔ |
| SPEC-OPS-4 | Vibe Guard scanné par lui-même DOIT NE remonter aucun finding `NET-ISO` ni `SECRETS`. | Auto-scan en CI. | ⛔ |
| SPEC-OPS-5 | La CI DOIT exécuter lint, tests unitaires, intégration et eval sur chaque PR, et échouer si une gate §8 régresse. | Pipeline vert exigé avant merge. | ⚠️ |
| SPEC-OPS-6 | Aucune métrique non mesurée ne DOIT figurer dans le dépôt (README, docstrings, agent card, fiche Marketplace). | Revue systématique + contrôle CI sur motifs chiffrés dans le README. | ⚠️ |
| SPEC-OPS-7 | La documentation (`docs/architecture.md`, `docs/report-schema.md`, `docs/rule-pack-format.md`) DOIT être cohérente avec le code ; toute divergence est un défaut. | Contrôle à chaque PR touchant un modèle. | ⚠️ (dérive connue : ±5 vs ±4 lignes d'extrait) |

---

## 6. Catalogue de règles

### 6.1 Familles

| Famille | Question à laquelle elle répond | Moteur dominant |
|---|---|---|
| `AUTH` | Qui peut appeler cette application, et comment est-ce vérifié ? | Semgrep |
| `SECRETS` | Des identifiants sont-ils présents dans le code ou la configuration ? | gitleaks |
| `LLM-GOV` | Les appels aux modèles sont-ils encadrés (passerelle, timeout, injection) ? | Semgrep |
| `NET-ISO` | Quelle est la surface d'exposition réseau et le durcissement du conteneur ? | Semgrep (Dockerfile, Terraform) |

### 6.2 Pack livré `vibe-guard-core` v0.1.0

12 règles, 3 par famille : `AUTH-001..003`, `SECRETS-001..003`, `LLM-GOV-001..003`, `NET-ISO-001..003`. Le contenu normatif de chaque règle est le fichier YAML lui-même ; ce document ne le duplique pas (règle anti-dérive).

### 6.3 Procédure d'ajout d'une règle (normative)

1. Relever le **maximum d'identifiant utilisé dans la famille, dans `rules/`** — pas dans ce document — et incrémenter.
2. Écrire la fixture non conforme **avant** la règle, avec son `findings.expected.yaml`.
3. Écrire la règle YAML (7 champs produit + `engine`).
4. Vérifier qu'elle ne déclenche sur aucune fixture conforme.
5. Rejouer la gate G2 : rappel et précision restent à 1 sur le corpus.
6. Incrémenter `pack.yaml:version` (mineure pour un ajout, majeure pour un changement de sévérité ou une suppression).

### 6.4 Politique de sévérité

| Sévérité | Critère |
|---|---|
| `critical` | Exploitable à distance sans authentification, ou secret exploitable exposé. |
| `high` | Contournement d'un contrôle d'accès, ou exposition d'une surface sensible. |
| `medium` | Absence de garde-fou opérationnel (timeout, isolation) sans exploitation directe. |
| `low` | Écart aux bonnes pratiques sans impact direct démontrable. |

Une sévérité est une **décision produit**, jamais une reprise de la sévérité de l'outil sous-jacent (`SPEC-ENG-2`).

---

## 7. Exigences non fonctionnelles

| Domaine | Exigence |
|---|---|
| **Sécurité** | Invariants SEC-1 à SEC-7. Le service traite du code client : toute fonctionnalité nouvelle est évaluée d'abord contre ces invariants. |
| **Déterminisme** | Hors `contextual_advice`, deux scans du même code produisent des rapports identiques champ à champ, `scan_id`, horodatage et durée exceptés. |
| **Performance** | Aucune cible chiffrée en V1 (SEC-7). Les timeouts `SPEC-ENG-8` sont des garde-fous, pas des objectifs. Une cible ne sera écrite ici qu'après mesure sur corpus. |
| **Observabilité** | Un scan émet : un enregistrement d'audit (`SPEC-AUD-1`), un log de démarrage et un log de fin avec durée et statut des scanners. Aucun log ne contient de code. |
| **Portabilité** | Exécution locale (poste développeur), CI, et Cloud Run avec le même code et le même pack. Toute divergence de comportement entre ces trois environnements est un défaut. |
| **Extensibilité** | Le pack de règles est versionné indépendamment du code et PEUT être remplacé par un pack client (SEC-5). |

---

## 8. Vérification et gates

### 8.1 Niveaux de test

| Niveau | Répertoire | Objet |
|---|---|---|
| Unitaire | `tests/unit/` | Modèles, chargeur, bornes, purge |
| Intégration | `tests/integration/` | Scan complet d'une fixture, rapport, rendus |
| Eval | `tests/eval/` | Gates mesurables sur le corpus de fixtures |
| Cloud (`@cloud`) | `tests/integration/test_e2e.py` | Parité local / déployé |

### 8.2 Gates

| Gate | Condition de passage | Exigences couvertes |
|---|---|---|
| **G1 — Référentiel** | Pack chargé sans erreur ; 7 champs produit présents sur toutes les règles ; ≥ 3 règles par famille ; chaque `findings.expected.yaml` relu par le porteur produit. | RUL-1..7 |
| **G2 — Détection** | Sur le corpus de fixtures : rappel = 1, précision = 1 ; workspace purgé en sortie normale et sur exception. | ENG-1..3, ENG-5..6, ING-2 |
| **G3 — Rapport** | Rapport valide pour toutes les fixtures ; mode `--no-llm` complet ; extraits bornés ; `engine_status` renseigné ; aucune valeur de secret publiée. | REP-1..7, REM-1..6 |
| **G4 — Agent & déploiement** | Scan de bout en bout via l'agent déployé identique au scan local sur la même fixture ; auto-scan sans finding `NET-ISO`/`SECRETS` ; accès anonyme refusé. | AGT-1..5, OPS-1..4 |

> **Portée des chiffres de G2** : rappel et précision valent 1 **sur le corpus interne de fixtures**. Ce n'est pas une mesure de performance produit et cela DOIT NE PAS être présenté comme telle (SEC-7).

### 8.3 Traçabilité

Chaque exigence §5 DOIT être rattachée à au moins un test. La matrice est maintenue dans le tableau §5 lui-même (colonne *Critère d'acceptation* + §11). Une exigence sans test est ⛔ par définition, quel que soit l'état du code.

---

## 9. Décisions d'architecture

Les huit décisions fondatrices sont formalisées dans `docs/adr/0001` à `0008` : Python 3.12/uv/ruff/pytest · Semgrep OSS + gitleaks · format de pack YAML enveloppant · Google ADK + Gemini sur Vertex AI · rôle du LLM limité à la remédiation et au regroupement · déploiement Cloud Run · ingestion git shallow / archive · périmètre langages V1 (Python, JS/TS, Dockerfile, Terraform).

**Points ouverts** (ne rien implémenter avant tranchage) :

| Point | Bloque | Décideur |
|---|---|---|
| Critère Marketplace « usage de Vertex AI au-delà du simple appel LLM » — candidats : Vertex AI Evaluation sur la qualité des remédiations, ou Vertex AI Search sur la base de règles | G4 / éligibilité | Porteur produit + Google |
| Nom commercial du produit (impacte agent card, image, fiche) | G4 | Porteur produit |
| Modèle de pricing et revenue share Marketplace | Publication | Porteur produit + Google |
| Périmètre langages au-delà de l'ADR-008 | V2 | Porteur produit |

---

## 10. Hors périmètre V1

Ne pas implémenter, même si le coût paraît faible :

- génération ou application automatique de correctifs ;
- détection par LLM sans règle ;
- exécution dynamique, DAST, test d'intrusion ;
- intégration CI côté client (GitHub App, webhooks) ;
- langages hors ADR-008 ;
- interface web — JSON et Markdown suffisent ;
- gestion d'un workflow d'approbation IT ou d'un registre d'applications ;
- multi-tenant, quotas, facturation à l'usage.

---

## 11. État constaté au 2026-09-18 (mesuré, non déclaratif)

Base : dépôt `antigravity`, commit `1cd2e04`, exécution locale.

**Preuve d'exécution** : `uv run pytest -q` → `30 passed in 25.83s` (12 fonctions de test, paramétrées).

| Module | Présent | Remarque |
|---|---|---|
| `ingest/workspace.py` | oui | limites, traversée via `is_relative_to`, rejet symlinks/devices, clone sécurisé sans fuite de token |
| `rules/` (loader + modèles) | oui | validation Pydantic `extra="forbid"`, 12 règles chargées |
| `engine/` (semgrep, gitleaks, snippet, scanner) | oui | timeouts 180 s / 120 s, extrait ±4 lignes / 1 500 car., binaires via env/PATH |
| `report/` (modèles, builder, renderer, masking) | oui | JSON + Markdown, déduplication contiguë, masquage secrets, engine_status complet |
| `remediation/` (generator + prompt v1) | oui | repli statique sur échec LLM |
| `audit/` (record + recorder) | oui | pas encore de `caller_id` authentifié |
| `agent/` | **non** | uniquement un `__init__.py` documentaire |
| CLI | **non** | aucun point d'entrée `vibe-guard` |
| `deploy/` (Dockerfile, Cloud Run) | **non** | absent du dépôt |

**Statut des 7 écarts prioritaires au 2026-09-18** :

1. **`SPEC-ENG-4` / `SPEC-REP-6`** : ✅ **Résolu**. Modèles `ScannerStatus` et `EngineStatus` implémentés dans `report.engine_status`. Tout échec de scanner (ex. `TOOL-ERR-GITLEAKS`) bascule le scanner en statut `error`, renseigne `degraded_families`, peuple `coverage_degraded`, et génère un bandeau d'avertissement explicite en tête de rapport Markdown empêchant toute déclaration de conformité. Couvert par `test_engine_status_and_tool_error_degradation` et `test_spec_eng_4_and_rep_6_tool_error_engine_status`.
2. **`SPEC-REP-5`** : ✅ **Résolu**. Module `src/vibe_guard/report/masking.py` implémenté. Tous les secrets détectés (OpenAI `sk-...`, clés GCP `AIza...`, tokens GitHub `ghp_...`, assignations `.env` et `ENV` Dockerfile) sont systématiquement masqués en empreintes tronquées (`sk-pr...[MASQUÉ]`) dans les messages et snippets de code du rapport JSON et Markdown. Couvert par `test_spec_rep_5_secrets_redacted_in_json_and_markdown` sur la fixture `app_secrets_leak`.
3. **`SPEC-OPS-1` / `SPEC-ENG-7`** : ✅ **Résolu**. Chemins codés en dur `/opt/homebrew` et `/usr/local` supprimés. Résolution configurable via `VIBE_GUARD_GITLEAKS_BIN` et `VIBE_GUARD_SEMGREP_BIN`, avec repli propre sur `PATH`. Couvert par `test_spec_eng_7_binary_env_override`.
4. **`SPEC-ING-7`** : ✅ **Résolu**. `clone_git` n'injecte plus le token dans l'URL ni dans `argv`. Authentification déléguée à un credential helper / script éphémère `GIT_ASKPASS` supprimé dès la fin du clone, `GIT_TERMINAL_PROMPT=0`, et masquage strict des tokens en cas d'erreur de `stderr`. Couvert par `test_spec_ing_7_git_clone_token_not_in_argv_or_url` et `test_spec_ing_7_git_clone_error_masks_token`.
5. **`SPEC-ING-5`** : ✅ **Résolu**. Rejet explicite en `IngestionError` des symlinks, hardlinks, fifos et devices dans les archives `.zip` et `.tar.gz`, et utilisation du filtre `filter="data"` sur `tarfile.extractall`. Couvert par `test_spec_ing_5_zip_symlink_rejected`, `test_spec_ing_5_tar_symlink_rejected` et `test_spec_ing_5_tar_hardlink_rejected`.
6. **`SPEC-ING-4`** : ✅ **Résolu**. Contrôle de traversée de chemin systématiquement effectué via `Path.is_relative_to(self.path)` sur `.resolve()`, immunisant contre les attaques de type préfixe sibling (`/tmp/ws-evil`). Couvert par `test_spec_ing_4_path_traversal_sibling_rejected`.
7. **`SPEC-OPS-7`** : ✅ **Résolu**. Cohérence documentaire rétablie dans `docs/architecture.md` à ±4 lignes (conforme au code et à C2). Couvert par commit `7061f9f`.

---

## Annexe — Historique

`plan-implementation-agent-vibe-coding.md` (v0.1, 2026-09-18) a servi de plan de démarrage et reste consultable pour le découpage en phases. Il est **remplacé** par ce document : en cas de contradiction, la présente spécification prime.
