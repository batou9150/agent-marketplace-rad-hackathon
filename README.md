# Vibe Guard

Agent d'industrialisation du vibe coding (MVP V1).

Vibe Guard prend en entrée le code source d'une application générée par IA ("vibe codée") et produit :
1. Un rapport de non-conformité priorisé (AUTH, SECRETS, LLM-GOV, NET-ISO).
2. Une proposition de remédiation textuelle contextualisée par non-conformité, ciblée GCP-natif.
3. Une exposition sous forme d'agent A2A (Agent-to-Agent) déployable sur Google Cloud.

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
uv run pytest tests/unit -v
```

## Linting et formatage

```bash
uv run ruff check .
uv run ruff format .
```

## Documentation

- [Stratégie Marketing & Commercialisation GCP Marketplace](docs/strategie-marketing-gcp-marketplace.md)
- [Kit de Communication & Go-To-Market](docs/communication/)
- [Format du pack de règles](docs/rule-pack-format.md)
- [Décisions d'architecture (ADR)](docs/adr/)
- [Plan d'implémentation](plan-implementation-agent-vibe-coding.md)

