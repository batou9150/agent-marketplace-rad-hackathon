"""Secret masking and redaction utilities (SPEC-REP-5)."""

import re

# Regex patterns for well-known secrets and token signatures
SECRET_PATTERNS = [
    # OpenAI API keys (sk-..., sk-proj-...)
    re.compile(r"\b(sk-(?:proj-)?[A-Za-z0-9_-]{10,})\b"),
    # GitHub personal access tokens
    re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{16,})\b"),
    # Google Cloud / Google API keys
    re.compile(r"\b(AIza[0-9A-Za-z_-]{30,})\b"),
    # AWS access key IDs
    re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
    # Slack tokens
    re.compile(r"\b(xox[baprs]-[0-9a-zA-Z-]{20,})\b"),
]

# Pattern for assignment of secrets in code/env files
# e.g. SECRET_TOKEN="super-secret-token-12345", API_KEY = 'secret', ENV TOKEN=secret
ASSIGNMENT_PATTERN = re.compile(
    r"""(?i)\b(api[_-]?key|secret[_-]?token|secret|password|token|bearer|auth[_-]?token)\s*(?:=|:)\s*(["']?)([^"'\s\r\n]{6,})\2"""
)

ENV_ASSIGNMENT_PATTERN = re.compile(
    r"""(?i)(ENV\s+[^=\n\r]*?(?:API_KEY|SECRET|PASSWORD|TOKEN|AUTH)\s*=\s*)(["']?)([^"'\s\r\n]+)\2"""
)


def mask_secret_value(value: str) -> str:
    """Format a secret value into a safe truncated fingerprint (SPEC-REP-5)."""
    clean_val = value.strip("\"'")
    if len(clean_val) <= 6:
        return "***[MASQUÉ]***"
    prefix = clean_val[:4]
    return f"{prefix}...[MASQUÉ]"


def mask_secrets_in_text(text: str, explicit_secrets: list[str] | None = None) -> str:
    """Replace plain text secrets in code snippets and messages with truncated fingerprints."""
    if not text:
        return text

    masked = text

    # 1. Mask any explicitly reported secret strings
    if explicit_secrets:
        for secret in explicit_secrets:
            if secret and len(secret) >= 4 and secret in masked:
                masked = masked.replace(secret, mask_secret_value(secret))

    # 2. Mask known token patterns
    for pattern in SECRET_PATTERNS:
        masked = pattern.sub(lambda m: mask_secret_value(m.group(1)), masked)

    # 3. Mask assignments (KEY = "secret_val")
    def _replace_assignment(m: re.Match) -> str:
        var_name = m.group(1)
        quote = m.group(2)
        val = m.group(3)
        return f"{var_name}={quote}{mask_secret_value(val)}{quote}"

    masked = ASSIGNMENT_PATTERN.sub(_replace_assignment, masked)

    # 4. Mask Dockerfile ENV assignments
    def _replace_env(m: re.Match) -> str:
        env_prefix = m.group(1)
        quote = m.group(2)
        val = m.group(3)
        return f"{env_prefix}{quote}{mask_secret_value(val)}{quote}"

    masked = ENV_ASSIGNMENT_PATTERN.sub(_replace_env, masked)

    return masked
