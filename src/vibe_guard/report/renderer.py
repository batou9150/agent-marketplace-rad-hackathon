"""Report rendering in JSON and Markdown formats (Phase 3)."""

from vibe_guard.report.models import Report


def render_json(report: Report, indent: int = 2) -> str:
    """Serialize Report to strictly validated JSON string matching API contract."""
    return report.model_dump_json(by_alias=True, indent=indent)


def render_markdown(report: Report) -> str:
    """Render a comprehensive, human-readable Markdown security report in French."""
    llm_status = "Activé" if report.metadata.llm_remediation_enabled else "Désactivé (--no-llm)"
    lines: list[str] = [
        "# 🛡️ Rapport de non-conformité — Vibe Guard",
        "",
    ]

    if report.engine_status.coverage_degraded:
        degraded_str = ", ".join(report.engine_status.coverage_degraded)
        lines.extend(
            [
                "> ⚠️ **ATTENTION : Couverture de détection dégradée**  ",
                f"> Les familles non analysées pour cause d'indisponibilité scanner : "
                f"**{degraded_str}**.  ",
                "> Ce rapport **ne peut pas être interprété comme conforme** (SPEC-ENG-4).",
                "",
            ]
        )

    lines.extend(
        [
            f"> **Scan ID** : `{report.metadata.scan_id}`  ",
            f"> **Date** : {report.metadata.timestamp}  ",
            f"> **Cible** : `{report.metadata.target}`  ",
            f"> **Appelant** : `{report.metadata.caller_id}`  ",
            f"> **Pack de règles** : v{report.metadata.pack_version}  ",
            f"> **Durée** : {report.metadata.duration_seconds}s  ",
            f"> **Enrichissement IA (Gemini)** : {llm_status}",
        ]
    )
    if report.metadata.prompt_version:
        lines.append(f"> **Version du prompt** : `{report.metadata.prompt_version}`  ")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 1. Synthèse globale",
            "",
            f"Total de non-conformités identifiées : **{report.summary.total_findings}**",
            "",
            "### État des scanners d'analyse (SPEC-REP-6)",
            "| Scanner | Statut | Version | Familles couvertes | Couverture dégradée |",
            "|---|---|---|---|---|",
        ]
    )

    sem = report.engine_status.semgrep
    sem_icon = "✅ Opérationnel" if sem.status == "ok" else "❌ Erreur"
    sem_cov = ", ".join(sem.covered_families) if sem.covered_families else "-"
    sem_deg = ", ".join(sem.degraded_families) if sem.degraded_families else "-"
    lines.append(
        f"| **Semgrep OSS** | {sem_icon} | `{sem.version or 'N/A'}` | {sem_cov} | {sem_deg} |"
    )

    gitl = report.engine_status.gitleaks
    gitl_icon = "✅ Opérationnel" if gitl.status == "ok" else "❌ Erreur"
    gitl_cov = ", ".join(gitl.covered_families) if gitl.covered_families else "-"
    gitl_deg = ", ".join(gitl.degraded_families) if gitl.degraded_families else "-"
    lines.append(
        f"| **Gitleaks** | {gitl_icon} | `{gitl.version or 'N/A'}` | {gitl_cov} | {gitl_deg} |"
    )

    lines.extend(
        [
            "",
            "### Répartition par sévérité",
            "| Sévérité | Nombre |",
            "|---|---|",
            f"| 🔴 **Critique** | {report.summary.by_severity.get('critical', 0)} |",
            f"| 🟠 **Élevée** | {report.summary.by_severity.get('high', 0)} |",
            f"| 🟡 **Moyenne** | {report.summary.by_severity.get('medium', 0)} |",
            f"| 🔵 **Faible** | {report.summary.by_severity.get('low', 0)} |",
            "",
            "### Répartition par famille",
            "| Famille | Description | Constatations |",
            "|---|---|---|",
            f"| **AUTH** | Authentification | {report.summary.by_family.get('AUTH', 0)} |",
            f"| **SECRETS** | Secrets & clés | {report.summary.by_family.get('SECRETS', 0)} |",
            f"| **LLM-GOV** | Gouvernance LLM | {report.summary.by_family.get('LLM-GOV', 0)} |",
            f"| **NET-ISO** | Isolation réseau | {report.summary.by_family.get('NET-ISO', 0)} |",
            "",
            "---",
            "",
            "## 2. Détail des constatations et remédiations GCP-natives",
            "",
        ]
    )

    if not report.findings:
        if report.engine_status.coverage_degraded:
            lines.append(
                "⚠️ **Aucune non-conformité détectée sur les familles actives, "
                "mais la couverture de détection est dégradée.**"
            )
        else:
            lines.append(
                "✅ **Aucune non-conformité détectée.** "
                "L'application respecte les règles Vibe Guard."
            )
        return "\n".join(lines)

    for idx, finding in enumerate(report.findings, start=1):
        sev_icon = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🔵",
        }.get(finding.severity.lower(), "⚪")

        lines.extend(
            [
                f"### {idx}. [{finding.rule_id}] {finding.title}",
                "",
                f"- **ID constatation** : `{finding.finding_id}`",
                f"- **Sévérité** : {sev_icon} `{finding.severity.upper()}`",
                f"- **Famille** : `{finding.family}`",
                f"- **Emplacement** : `{finding.file_path}:{finding.line_number}`",
                f"- **Constat** : {finding.message}",
                "",
            ]
        )

        if finding.snippet and finding.snippet.content:
            lines.extend(
                [
                    "**Extrait de code détecté :**",
                    "```",
                    finding.snippet.content.strip(),
                    "```",
                    "",
                ]
            )

        lines.extend(
            [
                "#### 💡 Remédiation GCP recommandée",
                f"**Service cible** : `{finding.remediation.gcp_service}`  ",
                f"**Action** : {finding.remediation.summary}",
                "",
                "**Étapes de correction :**",
            ]
        )
        for step in finding.remediation.steps:
            lines.append(f"1. {step}")

        if finding.remediation.reference_url:
            ref = finding.remediation.reference_url
            lines.append(f"\nDocumentation : [{ref}]({ref})")

        if finding.remediation.contextual_advice:
            lines.extend(
                [
                    "",
                    "**Conseil d'architecture IA (Gemini) :**",
                    f"> {finding.remediation.contextual_advice}",
                ]
            )

        lines.extend(["", "---", ""])

    return "\n".join(lines)
