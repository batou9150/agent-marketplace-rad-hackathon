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
        f"> **Scan ID** : `{report.metadata.scan_id}`  ",
        f"> **Date** : {report.metadata.timestamp}  ",
        f"> **Cible** : `{report.metadata.target}`  ",
        f"> **Pack de règles** : v{report.metadata.pack_version}  ",
        f"> **Durée** : {report.metadata.duration_seconds}s  ",
        f"> **Enrichissement IA (Gemini)** : {llm_status}",
        "",
        "---",
        "",
        "## 1. Synthèse globale",
        "",
        f"Total de non-conformités identifiées : **{report.summary.total_findings}**",
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

    if not report.findings:
        lines.append(
            "✅ **Aucune non-conformité détectée.** L'application respecte les règles Vibe Guard."
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
