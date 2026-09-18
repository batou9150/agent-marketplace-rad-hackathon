"""Deploy or update Vibe Guard A2UI on Vertex AI Agent Engine using the Python SDK.

Follows Agent Engine Python Deployer skill patterns.
Supports client.agent_engines.create and client.agent_engines.update (in-place).
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add project root and vibe_guard_a2ui to path
current_dir = Path(__file__).resolve().parent
project_dir = current_dir.parent
sys.path.extend([str(current_dir), str(project_dir), str(project_dir / "src")])

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agent_engine_deployer")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deploy Vibe Guard A2UI to Vertex AI Agent Engine"
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("PROJECT_ID") or os.environ.get("GCP_PROJECT_ID"),
        help="Google Cloud Project ID",
    )
    parser.add_argument(
        "--location",
        default=os.environ.get("LOCATION") or os.environ.get("GCP_REGION") or "us-central1",
        help="Google Cloud Region",
    )
    parser.add_argument(
        "--staging-bucket",
        default=os.environ.get("STORAGE_BUCKET") or os.environ.get("GCS_BUCKET"),
        help="GCS bucket for deployment staging (e.g., gs://my-bucket)",
    )
    parser.add_argument(
        "--existing-id",
        help="Optional Reasoning Engine resource ID to update in-place",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and packaging without calling Google Cloud APIs",
    )
    return parser.parse_args()


def get_agent_card_definition() -> dict:
    """Read agent card metadata from .well-known/agent-card.json."""
    card_path = current_dir / ".well-known" / "agent-card.json"
    if not card_path.is_file():
        raise FileNotFoundError(f"Agent card missing: {card_path}")
    with open(card_path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    args = parse_args()

    if not args.dry_run and not args.project:
        logger.error(
            "Project ID must be specified via --project or PROJECT_ID environment variable."
        )
        sys.exit(1)

    logger.info("======================================================================")
    logger.info("🚀 VIBE GUARD A2UI — VERTEX AI AGENT ENGINE DEPLOYER")
    logger.info("======================================================================")
    logger.info(f"Project ID     : {args.project or 'DRY-RUN'}")
    logger.info(f"Location       : {args.location}")
    logger.info(f"Staging Bucket : {args.staging_bucket or 'None'}")
    action_str = "UPDATE" if args.existing_id else "CREATE"
    dry_str = " (DRY RUN)" if args.dry_run else ""
    logger.info(f"Action         : {action_str}{dry_str}")
    logger.info("======================================================================")

    # 1. Load agent card and verify components
    card_data = get_agent_card_definition()
    logger.info(f"Loaded Agent Card: {card_data.get('name')} v{card_data.get('version')}")

    # 2. Package configuration
    requirements = [
        "google-cloud-aiplatform[agent_engines,adk]>=1.65.0",
        "a2a-sdk>=0.3.4",
        "cloudpickle>=3.1.2",
        "pydantic>=2.7.0",
        "semgrep>=1.70.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
    ]

    extra_packages = [
        str(current_dir / "a2ui_presentation.py"),
        str(current_dir / "agent.py"),
        str(current_dir / "agent_executor.py"),
        str(current_dir / "sitecustomize.py"),
        str(project_dir / "rules"),
        str(project_dir / "src" / "vibe_guard"),
    ]

    for p in extra_packages:
        if not Path(p).exists():
            logger.error(f"Required package/file does not exist: {p}")
            sys.exit(1)

    config = {
        "agent_framework": "google-adk",
        "requirements": requirements,
        "env_vars": {
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "true",
            "VIBE_GUARD_ENV": "production",
        },
        "extra_packages": extra_packages,
    }

    if args.dry_run:
        logger.info("✓ [DRY RUN] Packaging validation successful.")
        logger.info("Requirements:")
        for req in requirements:
            logger.info(f"  - {req}")
        logger.info("Extra Packages:")
        for pkg in extra_packages:
            logger.info(f"  - {pkg}")
        logger.info("✓ Configuration ready for Vertex AI Agent Engine deployment.")
        return

    # 3. Dynamic import of vertexai SDK
    try:
        import agent_executor
        import vertexai
        from a2a.types import AgentSkill
        from google.genai import types
        from vertexai.preview.reasoning_engines import A2aAgent
        from vertexai.preview.reasoning_engines.templates.a2a import create_agent_card
    except ImportError as e:
        logger.error(
            f"Vertex AI Agent Engine dependencies not installed in current environment: {e}"
        )
        logger.error("Run: pip install google-cloud-aiplatform[agent_engines,adk] a2a-sdk")
        sys.exit(1)

    vertexai.init(
        project=args.project,
        location=args.location,
        staging_bucket=args.staging_bucket,
    )

    client = vertexai.Client(
        project=args.project,
        location=args.location,
        http_options=types.HttpOptions(api_version="v1beta1"),
    )

    # 4. Construct A2aAgent wrapper
    skills = [
        AgentSkill(
            id=s["id"],
            name=s["name"],
            description=s["description"],
        )
        for s in card_data.get("skills", [])
    ]

    agent_card_obj = create_agent_card(
        agent_name=card_data.get("name", "VibeGuardAgent"),
        description=card_data.get("description", "Vibe Guard Security Auditor"),
        skills=skills,
    )

    a2a_agent = A2aAgent(
        agent_card=agent_card_obj,
        agent_executor_builder=agent_executor.AdkAgentToA2AExecutor,
    )

    # 5. Execute Create or Update
    if args.existing_id:
        engine_name = (
            f"projects/{args.project}/locations/{args.location}"
            f"/reasoningEngines/{args.existing_id}"
        )
        logger.info(f"Updating Reasoning Engine in-place: {engine_name}...")
        remote_agent = client.agent_engines.update(
            name=engine_name,
            agent=a2a_agent,
            config=config,
        )
        logger.info(f"✓ Reasoning Engine updated: {remote_agent.name}")
    else:
        logger.info("Creating new Vertex AI Agent Engine instance...")
        remote_agent = client.agent_engines.create(
            agent=a2a_agent,
            config=config,
        )
        logger.info(f"✓ Reasoning Engine created: {remote_agent.name}")

    print("\n" + "=" * 70)
    print("REASONING ENGINE RESOURCE ID:")
    print(remote_agent.name)
    print("=" * 70)


if __name__ == "__main__":
    main()
