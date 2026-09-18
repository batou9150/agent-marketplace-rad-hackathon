"""Contextual remediation engine module (alias to RemediationGenerator)."""

from vibe_guard.remediation.generator import RemediationGenerator

# Alias for backwards compatibility
RemediationEngine = RemediationGenerator

__all__ = ["RemediationEngine", "RemediationGenerator"]
