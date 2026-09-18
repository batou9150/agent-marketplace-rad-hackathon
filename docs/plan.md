# Plan d'implémentation — Agent d'industrialisation du vibe coding (V1)

> Ce document **séquence** l'implémentation de `spec.md`. Il ne redéfinit aucune exigence : chaque tâche référence des identifiants de la spec (`FR-`, `NF-`, `SEC-`, `CT-`, `T-`). En cas de contradiction entre ce plan et la spec, la spec gagne et le plan se corrige.
>
> Ordre de lecture pour l'agent de développement : `spec.md` §0 → `spec.md` en entier → ce plan → `schemas/` et `examples/`.

Version : 0.2.0 — 2026-09-18 (aligné sur `spec.md` 0.1.0)

---

## 1. Décisions d'architecture (ADR-lite)

Statut : **proposées**. À confirmer par le porteur produit avant Phase 1 ; à formaliser chacune dans `docs/adr/` en Phase 0. Une ADR ne peut pas contredire la spec (spec §10).

| ADR | Décision | Justification | Écarté |
|---|---|---|---|
| ADR-001 | Python 3.12, `uv`, `ruff`, `pytest` | Écosystème natif d'ADK et de Semgrep | TypeScript |
| ADR-002 | Détection = Semgrep OSS + gitleaks orchestrés (FR-05, NF-02) | Règles Semgrep en YAML → CT-01 ; gitleaks référence OSS secrets ; licences compatibles usage commercial | Détecteurs maison ; CodeQL (licence) |
| ADR-003 | Pack YAML produit enveloppant la règle OSS (CT-01) | Sépare détection (OSS) et valeur produit (rationale, remédiation) | Métadonnées Semgrep brutes |
| ADR-004 | Google ADK (Python) + Gemini via Vertex AI (FR-10, FR-14) | Critère d'éligibilité Marketplace ; exposition A2A native | LangGraph, CrewAI |
| ADR-005 | LLM limité à la remédiation contextualisée et au regroupement sémantique ; **aucune détection par LLM** (FR-10, spec §2) | Détection déterministe et testable (NF-01) | Détection "zero-rule" |
| ADR-006 | Cloud Run, image non-root sans shell, outils épinglés (NF-07, SEC-05) | Cible GCP-natif ; le service respecte son propre pack (SEC-07) | GKE |
| ADR-007 | Ingestion V1 = Git HTTPS shallow ou archive (FR-01, FR-02) | Spec | GitHub App (V2) |
| ADR-008 | Périmètre langages = FR-15 | Stacks dominantes du vibe coding | Java/Go/.NET (V2) |
| ADR-009 | Canonicalisation JSON = clés triées, séparateurs `(",", ":")`, UTF-8, `\n` final (NF-01) | Comparaison octet à octet en T-11 | — |
| ADR-010 | Masquage secrets = 4 premiers caractères + `…`, appliqué par remplacement de sous-chaîne sur le snippet (NF-04) | Simple, testable (T-10b) | Hachage (non lisible) |

---

## 2. Structure du dépôt

```
vibe-guard/                          # OQ-02 : à renommer
├── README.md
├── pyproject.toml                   # [tool.vibe-guard.tools] : versions semgrep/gitleaks (NF-08)
├── uv.lock
├── spec/                            # copie versionnée de spec.md, schemas/, examples/
├── docs/adr/
├── rules/                           # RulePack (CT-01)
│   ├── pack.yaml
│   ├── auth/  secrets/  llm-gov/  net-iso/
├── src/vibe_guard/
│   ├── config.py                    # CT-07
│   ├── errors.py                    # codes d'erreur SOURCE_*, PACK_INVALID
│   ├── ingest/                      # FR-01, FR-02, FR-03, SEC-01..04
│   ├── rules/                       # FR-04, CT-01
│   ├── engine/                      # FR-05, FR-06, NF-02
│   ├── report/                      # FR-07, FR-08, FR-11, CT-02, CT-03
│   ├── remediation/                 # FR-09, FR-10  (prompts/<version>.md)
│   ├── audit/                       # FR-12, CT-04
│   ├── cli.py                       # FR-13, CT-05
│   └── agent/                       # FR-14, CT-06
├── fixtures/{nonconform,conform}/   # spec §7.1
├── tests/{unit,integration,eval}/   # spec §7.2
├── deploy/{Dockerfile,cloudrun.yaml}
└── .github/workflows/ci.yaml
```

---

## 3. Phases

Chaque phase se termine par un **gate**. Ne pas entamer la phase suivante tant que le gate n'est pas vert. Un gate = un sous-ensemble de tests de la spec §7.2 qui passent en CI.

### Phase 0 — Bootstrap

- [ ] Dépôt selon §2 ; `uv`, `ruff`, `pytest`, pre-commit ; CI lint + unit sur PR
- [ ] Copier `spec.md`, `schemas/`, `examples/` dans `spec/` ; test qui valide `schemas/*.json` comme JSON Schema 2020-12 et `examples/**` contre leur schéma
- [ ] ADR-001 à ADR-010 dans `docs/adr/`, statut `proposed`
- [ ] `config.py` : toutes les variables CT-07 avec défauts, typées, validées au démarrage
- [ ] `errors.py` : codes de FR-01/FR-02/FR-04 et mapping vers codes de sortie CT-05
- [ ] Vérifier `semgrep`/`gitleaks` disponibles dans l'environnement de dev aux versions de `pyproject.toml`

**Gate 0** : CI verte ; schémas et exemples validés ; 10 ADR présentes.

### Phase 1 — RulePack v0

- [ ] `rules/` : chargeur + validation CT-01 (schéma **et** contraintes inter-fichiers de CT-01) — FR-04
- [ ] 13 règles de FR-16 : un fichier produit + un fichier Semgrep (ou config gitleaks) par règle, tous les champs CT-01 renseignés, `remediation.gcp` complet (FR-09)
- [ ] Corpus §7.1 : 4 fixtures `nonconform` + 2 `conform` avec `fixture.yaml` et `findings.expected.yaml` ; **chaque `findings.expected.yaml` est relu et approuvé par le porteur produit** avant le gate
- [ ] `vibe-guard validate-pack` (CT-05)

**Gate 1** : T-04 vert ; `validate-pack` vert sur `rules/` ; 13 règles ; 6 fixtures approuvées.

### Phase 2 — Ingestion et détection

- [ ] `ingest/` : FR-01, FR-02, FR-03 ; archives adverses de T-02 ; jeton via `http.extraHeader` en variable d'environnement (SEC-04)
- [ ] `engine/` : FR-05 (un appel Semgrep, un appel gitleaks, arguments fixes, sans shell, timeouts), FR-06 (normalisation, `unmapped`)
- [ ] `report/` : FR-07 (regroupement), FR-08 (ordre total)
- [ ] `audit/` : FR-12 en succès et en échec
- [ ] Tests : T-01, T-02, T-03, T-05, T-06, T-07, T-08, T-12 ; **T-09 et T-10** sur le corpus

**Gate 2** : T-01..T-08, T-12 verts ; **T-09 rappel = 1 et T-10 précision = 1 sur le corpus** ; T-05 confirme processus enfants ⊆ {git, semgrep, gitleaks}.

### Phase 3 — Rapport, remédiation, CLI

- [ ] `report/` : sérialisation CT-03 validée contre `report.schema.json` ; canonicalisation ADR-009 ; rendu Markdown dérivé du JSON (FR-11)
- [ ] `remediation/` : FR-10 — prompt versionné + SHA-256 dans le rapport, contrat d'entrée, borne et masquage du snippet (NF-04, ADR-010), validation de sortie, fallback ; client Vertex AI derrière une interface pour le mock de T-10a
- [ ] `cli.py` : CT-05 complet, codes de sortie, stderr JSON
- [ ] Tests : T-10a, T-10b, T-11, T-13

**Gate 3** : T-10a, T-10b, T-11, T-13 verts ; `vibe-guard scan --no-llm` sur chaque fixture produit un JSON valide et un Markdown lisible.

### Phase 4 — Agent A2A et déploiement

- [ ] **Trancher OQ-01** (spec A2A en vigueur) avant d'écrire l'agent card
- [ ] `agent/` : agent ADK, compétence `scan` (CT-06), validation d'entrée SEC-08, réponses conversationnelles bornées au rapport de session (FR-14)
- [ ] `deploy/Dockerfile` : NF-07, SEC-05 ; `cloudrun.yaml` : service privé, SA minimal (SEC-06)
- [ ] Tests : T-14, T-15, T-16 (`@cloud`)
- [ ] **OQ-04** (Vertex AI au-delà du LLM) : documenter la réponse de Google ; n'implémenter que ce qui est confirmé

**Gate 4** : T-14 parité agent/CLI ; T-15 ; T-16 auto-scan sans finding `net-iso` ni `secrets`.

### Phase 5 — Préparation Marketplace (hors MVP)

Conditionnée aux réponses de Google (PRD §6, OQ-04). Pub/Sub, liaison de comptes, Producer Portal. Non planifiée tant que les inconnues ne sont pas levées.

---

## 4. Conventions

- Une ADR par décision non couverte par la spec ; une ADR qui contredit la spec est refusée — la spec change d'abord (spec §10)
- Toute PR référence les identifiants de spec qu'elle implémente et la version de spec qui l'autorise
- Tests avant code pour `ingest/`, `rules/`, `engine/`, `report/` ; les fixtures sont la source de vérité de la détection
- Aucune nouvelle dépendance sans justification d'une ligne dans la PR
- Code, identifiants, commits en anglais ; `rules/`, `docs/`, prompts et messages utilisateur en français
- Aucun chiffre de performance ou de qualité dans le README tant qu'il n'est pas issu de `tests/eval/`
- En cas de doute : relire spec §2 (hors périmètre), puis poser la question — ne pas interpréter
