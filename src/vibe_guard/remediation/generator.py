"""Contextual remediation generation using Gemini on Vertex AI (ADR-005, Constraint C2)."""

import logging
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from vibe_guard.engine.models import Finding

logger = logging.getLogger("vibe_guard.remediation")

PROMPTS_DIR = Path(__file__).parent / "prompts"
DEFAULT_PROMPT_FILE = PROMPTS_DIR / "remediation_v1.txt"
DEFAULT_MAX_SNIPPET_CHARS = 1500


class RemediationGenerator:
    """Generates GCP-native contextual remediation using Gemini via Vertex AI."""

    def __init__(
        self,
        client: Any = None,
        model: str | None = None,
        max_snippet_chars: int = DEFAULT_MAX_SNIPPET_CHARS,
        enabled: bool = True,
        prompt_file: Path | str | None = None,
    ) -> None:
        self._client = client
        self.model = model or os.getenv("VG_LLM_MODEL", "gemini-3.8-flash")
        self.max_snippet_chars = max_snippet_chars
        self.enabled = enabled
        prompt_path = Path(prompt_file or DEFAULT_PROMPT_FILE)
        self.prompt_version = prompt_path.stem.replace("remediation_", "")
        self.prompt_template = self._load_prompt_template(prompt_path)

    def _load_prompt_template(self, prompt_path: Path | str) -> str:
        path = Path(prompt_path)
        if not path.is_file():
            raise FileNotFoundError(f"Remediation prompt template not found: {path}")
        return path.read_text(encoding="utf-8")

    def _get_client(self) -> Any:
        """Lazy initialization of Google GenAI client if not passed in."""
        if self._client is None and self.enabled:
            try:
                from google import genai

                self._client = genai.Client()
            except Exception as exc:
                logger.warning(
                    "Google GenAI Client init failed: %s. Using static fallback.",
                    exc,
                )
                self.enabled = False
        return self._client

    def generate_advice(self, finding: Finding, rule_pack: Any = None) -> str | None:
        """Generate tailored GCP-native remediation advice for a single finding."""
        if not self.enabled or finding.is_tool_error:
            return None

        snippet_content = ""
        if finding.snippet and finding.snippet.content:
            raw = finding.snippet.content
            if len(raw) > self.max_snippet_chars:
                snippet_content = raw[: self.max_snippet_chars] + "\n... [tronqué C2]"
            else:
                snippet_content = raw

        rule_def = rule_pack.get_rule(finding.rule_id) if rule_pack else None
        default_summary = (
            rule_def.remediation.summary if rule_def else None
        ) or "Consulter la documentation de sécurité GCP"
        prompt = self.prompt_template.format(
            rule_id=finding.rule_id,
            title=finding.title,
            family=finding.family,
            severity=finding.severity,
            file_path=finding.file_path,
            line_number=finding.line_number,
            remediation_summary=finding.remediation_summary or default_summary,
            gcp_service=finding.remediation_gcp_service or "Google Cloud Platform",
            snippet_content=snippet_content,
        )

        client = self._get_client()
        if not client:
            return None

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            if response and response.text:
                return response.text.strip()
        except Exception as exc:
            logger.warning(
                "Gemini API call failed for finding %s (%s). Falling back to static remediation.",
                finding.rule_id,
                exc,
            )
            return None

        return None

    def generate_contextual_advice(self, finding: Finding, **kwargs: Any) -> str | None:
        """Alias for generate_advice."""
        return self.generate_advice(finding, **kwargs)

    def enrich_findings(self, findings: Sequence[Finding], rule_pack: Any = None) -> dict[str, str]:
        """Generate contextual advice for a sequence of findings, keyed by finding identifier."""
        if not self.enabled:
            return {}

        advices: dict[str, str] = {}
        for finding in findings:
            if finding.is_tool_error:
                continue
            advice = self.generate_advice(finding, rule_pack=rule_pack)
            if advice:
                key = f"{finding.rule_id}:{finding.file_path}:{finding.line_number}"
                advices[key] = advice
        return advices
