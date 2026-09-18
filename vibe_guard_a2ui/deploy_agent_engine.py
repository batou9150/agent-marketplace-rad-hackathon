"""Deploy or update Vibe Guard A2UI on Vertex AI Agent Engine.

Packaging model
---------------
Agent Engine tars `extra_packages` **relative to the current working directory**
and extracts the archive at the root of the remote working directory, which is on
`sys.path`. The deployer therefore assembles a clean staging tree:

    vibe_guard_a2ui/            the ADK agent, A2UI presentation, A2A executor
    vibe_guard/                 the scan engine (from src/vibe_guard)
    rules/                      the rule pack
    installation_scripts/       git + gitleaks, installed as root at build time

then chdirs into it so the remote layout matches `import vibe_guard_a2ui...` and
`import vibe_guard...` exactly.

Usage:
    python vibe_guard_a2ui/deploy_agent_engine.py --project PROJECT --dry-run
    python vibe_guard_a2ui/deploy_agent_engine.py --project PROJECT \
        --staging-bucket gs://BUCKET [--existing-id RESOURCE_ID]
"""

import argparse
import importlib.metadata
import json
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent

# The whole `vibe_guard_a2ui` package ships, minus what only serves local
# development or deployment itself. An allowlist of modules was tried first and
# silently dropped `schemas/`, so Agent Engine and Cloud Run (which copies the
# package wholesale) diverged; excluding is safer than enumerating here.
AGENT_EXCLUDES = shutil.ignore_patterns(
    "__pycache__",
    "*.pyc",
    "*.db",
    ".adk",
    "local_tester",
    "deploy_agent_engine.py",
    "register_gemini_enterprise.py",
    "create_ge_authorization.py",
)

INSTALLATION_SCRIPT = "installation_scripts/install.sh"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agent_engine_deployer")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy Vibe Guard A2UI to Vertex AI Agent Engine")
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
        "--model",
        default=os.environ.get("ADK_MODEL", "gemini-2.5-flash"),
        help="Gemini model served by the deployed agent (exported as ADK_MODEL)",
    )
    parser.add_argument(
        "--env",
        default="production",
        choices=["production", "development"],
        help="VIBE_GUARD_ENV of the deployment. Production rejects local paths "
        "and unauthenticated callers (SPEC-AGT-4, SPEC-AGT-5).",
    )
    parser.add_argument(
        "--caller-id",
        help="Static caller identity fallback (CALLER_ID) used when the platform "
        "does not forward an authenticated principal. Weakens SPEC-AGT-5.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and packaging without calling Google Cloud APIs",
    )
    return parser.parse_args()


def get_agent_card_definition() -> dict:
    """Read agent card metadata from .well-known/agent-card.json."""
    card_path = CURRENT_DIR / ".well-known" / "agent-card.json"
    if not card_path.is_file():
        raise FileNotFoundError(f"Agent card missing: {card_path}")
    with open(card_path, encoding="utf-8") as f:
        return json.load(f)


def build_staging_tree(staging_dir: Path) -> list[str]:
    """Assemble the deployment tree and return the relative extra_packages paths."""
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".adk", "*.db")

    shutil.copytree(CURRENT_DIR, staging_dir / "vibe_guard_a2ui", ignore=AGENT_EXCLUDES)
    shutil.copytree(PROJECT_DIR / "src" / "vibe_guard", staging_dir / "vibe_guard", ignore=ignore)
    shutil.copytree(PROJECT_DIR / "rules", staging_dir / "rules", ignore=ignore)

    script_source = PROJECT_DIR / "deploy" / "agent_engine" / INSTALLATION_SCRIPT
    if not script_source.is_file():
        raise FileNotFoundError(f"Installation script missing: {script_source}")
    script_target = staging_dir / INSTALLATION_SCRIPT
    script_target.parent.mkdir(parents=True)
    shutil.copy2(script_source, script_target)
    script_target.chmod(0o755)

    return ["vibe_guard_a2ui", "vibe_guard", "rules", INSTALLATION_SCRIPT]


def build_requirements() -> list[str]:
    """Pin the runtime dependencies, matching the local versions used to pickle."""
    try:
        cloudpickle_version = importlib.metadata.version("cloudpickle")
    except importlib.metadata.PackageNotFoundError:
        # Only reachable on a dry run: cloudpickle is required to actually deploy.
        cloudpickle_version = "3.1.2"
    return [
        "google-cloud-aiplatform[agent_engines,adk]>=2.1.3,<3",
        "google-adk>=2.9.1,<3",
        # The Vertex A2aAgent template imports a2a.types.TransportProtocol, which
        # a2a-sdk 1.x (protobuf types) dropped, so the A2A server side stays on 0.3.x.
        "a2a-sdk[http-server]>=0.3.4,<1",
        f"cloudpickle=={cloudpickle_version}",
        "pydantic>=2.7.0,<3",
        # Pinned to the version deploy/Dockerfile and SPEC.md fix, so a repository
        # scanned on Cloud Run and on Agent Engine yields the same findings.
        "semgrep==1.70.0",
        "pyyaml>=6.0",
    ]


def build_env_vars(args: argparse.Namespace) -> dict[str, str]:
    env_vars = {
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "true",
        "VIBE_GUARD_ENV": args.env,
        "ADK_MODEL": args.model,
        # Scanners run in a container whose only writable location is /tmp.
        # Mirrors deploy/Dockerfile: git, semgrep and the interpreter all write
        # under $HOME by default, which is not writable here.
        "HOME": "/tmp",
        "TMPDIR": "/tmp",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": "/tmp/pycache",
        "SEMGREP_SETTINGS_FILE": "/tmp/semgrep_settings.yml",
        "SEMGREP_ENABLE_VERSION_CHECK": "0",
        "SEMGREP_SEND_METRICS": "off",
        "VIBE_GUARD_GITLEAKS_BIN": "/usr/local/bin/gitleaks",
    }
    if args.caller_id:
        env_vars["CALLER_ID"] = args.caller_id
    return env_vars


def main() -> None:
    args = parse_args()

    if not args.dry_run and not args.project:
        logger.error(
            "Project ID must be specified via --project or PROJECT_ID environment variable."
        )
        sys.exit(1)
    if not args.dry_run and not args.staging_bucket:
        logger.error("A staging bucket is required: pass --staging-bucket gs://BUCKET")
        sys.exit(1)

    card_data = get_agent_card_definition()

    logger.info("======================================================================")
    logger.info("🚀 VIBE GUARD A2UI — VERTEX AI AGENT ENGINE DEPLOYER")
    logger.info("======================================================================")
    logger.info(f"Project ID     : {args.project or 'DRY-RUN'}")
    logger.info(f"Location       : {args.location}")
    logger.info(f"Staging Bucket : {args.staging_bucket or 'None'}")
    logger.info(f"Model          : {args.model}")
    logger.info(f"VIBE_GUARD_ENV : {args.env}")
    action_str = "UPDATE" if args.existing_id else "CREATE"
    dry_str = " (DRY RUN)" if args.dry_run else ""
    logger.info(f"Action         : {action_str}{dry_str}")
    logger.info("======================================================================")
    logger.info(f"Loaded Agent Card: {card_data.get('name')} v{card_data.get('version')}")

    requirements = build_requirements()
    env_vars = build_env_vars(args)

    with tempfile.TemporaryDirectory(prefix="vibeguard_agent_engine_") as tmp_dir:
        staging_dir = Path(tmp_dir)
        extra_packages = build_staging_tree(staging_dir)

        # extra_packages are tarred relative to the working directory, and the
        # staging tree must shadow the repository layout for cloudpickle to
        # reference modules under the exact names the container will import.
        os.chdir(staging_dir)
        sys.path.insert(0, str(staging_dir))

        config = {
            "display_name": card_data.get("name", "VibeGuardAgent"),
            "description": card_data.get("description", "Vibe Guard Security Auditor"),
            "agent_framework": "google-adk",
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "staging_bucket": args.staging_bucket,
            "requirements": requirements,
            "extra_packages": extra_packages,
            "build_options": {"installation_scripts": [INSTALLATION_SCRIPT]},
            "env_vars": env_vars,
        }

        if args.dry_run:
            logger.info("✓ [DRY RUN] Packaging validation successful.")
            logger.info("Staging tree:")
            for path in sorted(staging_dir.rglob("*")):
                if path.is_file():
                    logger.info(f"  - {path.relative_to(staging_dir)}")
            logger.info("Requirements:")
            for req in requirements:
                logger.info(f"  - {req}")
            logger.info("Environment:")
            for key, value in env_vars.items():
                logger.info(f"  - {key}={value}")
            logger.info("✓ Configuration ready for Vertex AI Agent Engine deployment.")
            return

        try:
            import vertexai
            from a2a.types import AgentCapabilities, AgentExtension, AgentSkill
            from google.genai import types
            from vertexai.preview.reasoning_engines import A2aAgent
            from vertexai.preview.reasoning_engines.templates.a2a import create_agent_card

            from vibe_guard_a2ui.agent_executor import (
                A2UI_EXTENSION_URI,
                VibeGuardAgentExecutor,
            )
        except ImportError as e:
            logger.error(f"Agent Engine dependencies are not installed: {e}")
            logger.error("Run: pip install 'google-cloud-aiplatform[agent_engines,adk]' a2a-sdk")
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

        # The card declares tags, examples and A2UI modes per skill; pass them
        # through rather than rebuilding a reduced skill definition.
        skills = [AgentSkill(**skill) for skill in card_data.get("skills", [])]

        agent_card_obj = create_agent_card(
            agent_name=card_data.get("name", "VibeGuardAgent"),
            description=card_data.get("description", "Vibe Guard Security Auditor"),
            skills=skills,
            default_input_modes=card_data.get("defaultInputModes"),
            default_output_modes=card_data.get("defaultOutputModes"),
        )
        # Advertise A2UI so Gemini Enterprise renders the DataParts as surfaces,
        # carrying over the catalog params declared on the card.
        card_extensions = card_data.get("capabilities", {}).get("extensions", [])
        extensions = [AgentExtension(**extension) for extension in card_extensions] or [
            AgentExtension(uri=A2UI_EXTENSION_URI, required=False)
        ]
        capabilities = AgentCapabilities(streaming=False, extensions=extensions)
        if hasattr(agent_card_obj.capabilities, "CopyFrom"):  # a2a-sdk 1.x protobuf
            agent_card_obj.capabilities.CopyFrom(capabilities)
        else:
            agent_card_obj.capabilities = capabilities

        a2a_agent = A2aAgent(
            agent_card=agent_card_obj,
            agent_executor_builder=VibeGuardAgentExecutor,
        )

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
            logger.info(f"✓ Reasoning Engine updated: {remote_agent.api_resource.name}")
        else:
            logger.info("Creating new Vertex AI Agent Engine instance...")
            remote_agent = client.agent_engines.create(
                agent=a2a_agent,
                config=config,
            )
            logger.info(f"✓ Reasoning Engine created: {remote_agent.api_resource.name}")

        print("\n" + "=" * 70)
        print("REASONING ENGINE RESOURCE NAME:")
        print(remote_agent.api_resource.name)
        print("=" * 70)


if __name__ == "__main__":
    main()
