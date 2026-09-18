# Vibe Guard — Context & Instructions

## Project Overview
Vibe Guard is an autonomous AI agent designed to scan vibe-coded application repositories, detect non-conformities (AUTH, SECRETS, LLM-GOV, NET-ISO), and provide actionable, GCP-native remediation reports.

**Source of truth: [`docs/SPEC.md`](docs/SPEC.md)** — normative specification driving development.
Every behavior change MUST map to a `SPEC-*` requirement; if the requirement does not exist, update the spec first, then implement.
Every commit message MUST reference at least one `SPEC-*` id (or `[CHORE]` / `[DOC]`).
Historical plan (superseded): `plan-implementation-agent-vibe-coding.md`.

## Architectural Principles & Non-Negotiable Constraints
- **C1: Static analysis only** — Never run the scanned code, never install its dependencies, never execute builds.
- **C2: Ephemeral & Bounded** — Ephemeral scan directory purged in `finally`. Never send raw full files to LLMs; send only bounded context snippets around findings.
- **C3: Leverage OSS** — Semgrep OSS for AST/code rules, gitleaks for secrets detection.
- **C4: Declarative Rules** — YAML rule packs containing metadata, rationale, and GCP-native remediation.
- **C5: GCP-Native target** — Remediations target Cloud Run/GKE, Secret Manager, IAP, Vertex AI.
- **C6: Audit & Traceability** — Maintain audit records for every scan (rules evaluated, pack version, timestamp, caller ID).
- **C7: No fabricated metrics** — Benchmark metrics must come strictly from fixtures in `tests/eval/`.

## Working Conventions
- **Git auto-updates**: Automatically commit and push changes with atomic commits per checked task.
- Commit messages: task identifier + verb in imperative in English (e.g. `[PHASE-0] Initialize project structure and CI`).
- Code, identifiers, tests in English.
- Product documentation (`docs/`, `rules/*/remediation`) in French.
- Tests before code for `engine/`, `rules/`, and `ingest/`.

## Skills Auto-Activation & Domain Routing
The agent MUST proactively consult and activate (`view_file` on `SKILL.md`) the following specialized skills when working on corresponding project domains and phases:

### 1. Python Tooling & Environment
- **`uv`** (`/Users/antoinelefetz/.gemini/config/plugins/science/skills/uv/SKILL.md`)
  - *Trigger*: Managing Python dependencies, virtual environments, tool installations (`semgrep`, `ruff`, `pytest`), or updating `pyproject.toml`.
- **`google-antigravity-sdk`** (`/Users/antoinelefetz/.gemini/config/plugins/google-antigravity-sdk/skills/google-antigravity-sdk/SKILL.md`)
  - *Trigger*: Implementing, instrumenting, or debugging Antigravity autonomous agent workflows and CLI behaviors.

### 2. Rule Authoring & GCP-Native Remediations (Phase 1 & Phase 3)
- **`google-cloud-waf-security`** (`/Users/antoinelefetz/.gemini/config/skills/google-cloud-waf-security/SKILL.md`)
  - *Trigger*: Defining rules and drafting GCP-native remediations for `AUTH`, `SECRETS`, and `NET-ISO` (IAM best practices, secret storage, service isolation).
- **`google-cloud-recipe-auth`** (`/Users/antoinelefetz/.gemini/config/skills/google-cloud-recipe-auth/SKILL.md`)
  - *Trigger*: Writing detection rules and remediations for missing authentication, insecure credentials, ADC patterns, Service Accounts, and IAP integration.
- **`google-cloud-solution-multi-agent-security`** (`/Users/antoinelefetz/.gemini/config/skills/google-cloud-solution-multi-agent-security/SKILL.md`)
  - *Trigger*: Formulating A2A security policies, LLM gateway isolation (`LLM-GOV`), Model Armor, and network ingress/egress boundaries.
- **`agent-platform-prompt-management`** (`/Users/antoinelefetz/.gemini/config/skills/agent-platform-prompt-management/SKILL.md`)
  - *Trigger*: Writing, versioning, and organizing prompt templates for Phase 3 contextual remediation drafting.

### 3. LLM Orchestration & Remediation Engine (Phase 3)
- **`gemini-api`** (`/Users/antoinelefetz/.gemini/config/skills/gemini-api/SKILL.md`)
  - *Trigger*: Implementing Vertex AI / Gemini SDK calls for contextual remediation generation, schema enforcement, and finding deduplication.

### 4. Agent Architecture, A2A & Marketplace Packaging (Phase 4 & Phase 5)
- **`google-agents-cli-onboarding`** (`/Users/antoinelefetz/.gemini/config/skills/google-agents-cli-onboarding/SKILL.md`)
  - *Trigger*: Scaffolding, testing, and lifecycle management of the Google ADK agent.
- **`gemini-agents-api`** (`/Users/antoinelefetz/.gemini/config/skills/gemini-agents-api/SKILL.md`)
  - *Trigger*: Programmatically creating, configuring, and publishing stateful agent resources and tool definitions.
- **`gemini-interactions-api`** (`/Users/antoinelefetz/.gemini/config/skills/gemini-interactions-api/SKILL.md`)
  - *Trigger*: Structuring A2A multi-turn conversations and background tool execution for scan reporting.
- **`agent-platform-skill-registry`** (`/Users/antoinelefetz/.gemini/config/skills/agent-platform-skill-registry/SKILL.md`)
  - *Trigger*: Registering Vibe Guard capabilities and skills into Agent Platform.

### 5. Deployment, Audit & Cloud Operations (Phase 2 & Phase 4)
- **`cloud-run-basics`** (`/Users/antoinelefetz/.gemini/config/skills/cloud-run-basics/SKILL.md`)
  - *Trigger*: Writing `deploy/Dockerfile`, `deploy/cloudrun.yaml`, setting up non-root containers, and configuring Cloud Run service parameters.
- **`gcloud`** (`/Users/antoinelefetz/.gemini/config/skills/gcloud/SKILL.md`)
  - *Trigger*: Proposing, validating, or running any `gcloud` CLI commands (deployment, IAM grants, Secret Manager).
- **`cloud-logging-configuration-basics`** (`/Users/antoinelefetz/.gemini/config/skills/cloud-logging-configuration-basics/SKILL.md`)
  - *Trigger*: Implementing `audit/` scan logs (C6 constraint: audit traceability, log sinks, view access without leaking scanned code).
- **`google-cloud-waf-operational-excellence`** (`/Users/antoinelefetz/.gemini/config/skills/google-cloud-waf-operational-excellence/SKILL.md`)
  - *Trigger*: Designing observability, health probes, incident traceability, and production readiness checks.

