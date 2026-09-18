# Vibe Guard

Agent d'industrialisation du vibe coding (MVP V1).

Vibe Guard prend en entrée le code source d'une application générée par IA ("vibe codée") et produit :
1. Un rapport de non-conformité priorisé (AUTH, SECRETS, LLM-GOV, NET-ISO).
2. Une proposition de remédiation textuelle contextualisée par non-conformité, ciblée GCP-natif.
3. Une exposition sous forme d'agent A2A (Agent-to-Agent) déployable sur Google Cloud.

## Spécification

La référence normative du produit est [`docs/SPEC.md`](docs/SPEC.md) : invariants, modèle de domaine,
contrats d'interface, exigences testables `SPEC-*`, catalogue de règles et gates de vérification.
Le développement est piloté par cette spécification — le plan de phases initial est superseded.

## Stack technique

- Python 3.12 (`uv`)
- Moteur d'analyse statique : Semgrep OSS + gitleaks
- Framework agent : Google ADK (Python) + Gemini via Vertex AI
- Qualité & CI : Ruff, Pytest, GitHub Actions

## Installation locale

```bash
uv sync --all-extras --dev
```

## Lancer les tests

```bash
uv run pytest tests/ -v
```

## Utilisation CLI

```bash
# Lister les règles du pack
uv run vibe-guard rules list

# Valider l'intégrité du pack de règles
uv run vibe-guard rules validate

# Scanner un dépôt local ou distant
uv run vibe-guard scan fixtures/conform/clean_python_app --no-llm
uv run vibe-guard scan fixtures/nonconform/app_secrets_leak --no-llm
```

## Linting et formatage

```bash
uv run ruff check .
uv run ruff format .
```

## Documentation

- [Architecture & Workflows](docs/architecture.md)
- [Schéma du Rapport (JSON / Markdown)](docs/report-schema.md)
- [Format du pack de règles](docs/rule-pack-format.md)
- [Stratégie Marketing & Commercialisation GCP Marketplace](docs/strategie-marketing-gcp-marketplace.md)
- [Kit de Communication & Go-To-Market](docs/communication/)
- [Décisions d'architecture (ADR)](docs/adr/)
- [Plan d'implémentation](plan-implementation-agent-vibe-coding.md)

