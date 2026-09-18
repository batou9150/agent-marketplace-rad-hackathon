"""Prompt definitions and versions for contextual remediation."""

from pathlib import Path

PROMPT_VERSION = "1.0.0"

_PROMPT_FILE = Path(__file__).parent / "remediation_v1.txt"
if _PROMPT_FILE.is_file():
    REMEDIATION_USER_PROMPT_TEMPLATE = _PROMPT_FILE.read_text(encoding="utf-8")
else:
    REMEDIATION_USER_PROMPT_TEMPLATE = "Remediation prompt template"

REMEDIATION_SYSTEM_INSTRUCTION = (
    "Tu es Vibe Guard, un expert en sécurité cloud et en gouvernance d'applications "
    "développées avec l'aide d'IA générative ('vibe-codées'). Ton rôle est d'analyser une "
    "non-conformité de sécurité et de proposer une remédiation concise, concrète et "
    "GCP-native (Cloud Run, Secret Manager, IAP, Vertex AI, Model Armor) adaptée à l'extrait "
    "de code fourni sans jamais divulguer de données sensibles."
)

__all__ = [
    "PROMPT_VERSION",
    "REMEDIATION_SYSTEM_INSTRUCTION",
    "REMEDIATION_USER_PROMPT_TEMPLATE",
]
