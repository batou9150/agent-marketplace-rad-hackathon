"""Register Vibe Guard A2UI agent into Gemini Enterprise.

Supports registering both:
1. Cloud Run A2A HTTP endpoint (e.g. https://<service-url>/a2a/vibe_guard_a2ui)
2. Vertex AI Agent Engine endpoint (projects/<PID>/locations/<LOC>/reasoningEngines/<ID>)

Follows gemini-enterprise-agent-registrar skill and DiscoveryEngine v1alpha API.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

current_dir = Path(__file__).resolve().parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ge_registrar")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register Vibe Guard A2UI in Gemini Enterprise"
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("PROJECT_ID") or os.environ.get("GCP_PROJECT_ID"),
        help="Google Cloud Project ID",
    )
    parser.add_argument(
        "--project-number",
        default=os.environ.get("PROJECT_NUMBER"),
        help="Google Cloud Project Number (numeric ID)",
    )
    parser.add_argument(
        "--app-id",
        default=os.environ.get("GEMINI_ENTERPRISE_APP_ID") or "default",
        help="Gemini Enterprise Application ID (Discovery Engine engine ID)",
    )
    parser.add_argument(
        "--endpoint-location",
        default="global",
        choices=["global", "us", "eu"],
        help="Discovery Engine endpoint location (global, us, eu)",
    )
    parser.add_argument(
        "--cloud-run-url",
        help="Base A2A URL of deployed Cloud Run service (e.g., https://<service>.run.app/a2a/vibe_guard_a2ui)",
    )
    parser.add_argument(
        "--agent-engine-id",
        help="Reasoning Engine resource ID or full path (e.g. projects/.../locations/.../reasoningEngines/...)",
    )
    parser.add_argument(
        "--auth-id",
        help="Optional Gemini Enterprise Authorization ID for OAuth (projects/<PNUM>/locations/global/authorizations/<AUTH_ID>)",
    )
    parser.add_argument(
        "--display-name",
        default="Vibe Guard",
        help="Display name in Gemini Enterprise UI",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and print registration JSON and curl command without executing",
    )
    return parser.parse_args()


def load_agent_card() -> dict:
    card_path = current_dir / ".well-known" / "agent-card.json"
    if not card_path.is_file():
        raise FileNotFoundError(f"Agent card not found at {card_path}")
    with open(card_path, encoding="utf-8") as f:
        return json.load(f)


def build_registration_payload(
    card: dict,
    target_url: str,
    display_name: str,
    description: str,
    project_number: str | None = None,
    auth_id: str | None = None,
) -> dict:
    """Build the DiscoveryEngine agent registration payload with escaped jsonAgentCard."""
    # Update target URL in agent card
    card_copy = dict(card)
    card_copy["url"] = target_url

    # A2A definition with jsonAgentCard string
    payload = {
        "displayName": display_name,
        "description": description,
        "a2aAgentDefinition": {
            "jsonAgentCard": json.dumps(card_copy, separators=(",", ":"))
        },
    }

    if auth_id and project_number:
        payload["authorizationConfig"] = {
            "agentAuthorization": f"projects/{project_number}/locations/global/authorizations/{auth_id}"
        }

    return payload


def get_gcloud_token() -> str:
    """Retrieve OAuth access token from gcloud."""
    res = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def main() -> None:
    args = parse_args()

    if not args.cloud_run_url and not args.agent_engine_id and not args.dry_run:
        logger.error("Either --cloud-run-url or --agent-engine-id must be provided.")
        sys.exit(1)

    card = load_agent_card()

    # Determine target A2A URL
    if args.cloud_run_url:
        target_url = args.cloud_run_url.rstrip("/")
    elif args.agent_engine_id:
        engine_id = args.agent_engine_id
        if "reasoningEngines/" in engine_id:
            engine_id = engine_id.split("reasoningEngines/")[-1]
        loc = os.environ.get("LOCATION") or "us-central1"
        target_url = f"https://{loc}-aiplatform.googleapis.com/v1beta1/projects/{args.project}/locations/{loc}/reasoningEngines/{engine_id}/a2a"
    else:
        target_url = "https://vibe-guard-a2ui.a.run.app/a2a/vibe_guard_a2ui"

    payload = build_registration_payload(
        card=card,
        target_url=target_url,
        display_name=args.display_name,
        description=card.get("description", "Vibe Guard Security Auditor"),
        project_number=args.project_number,
        auth_id=args.auth_id,
    )

    api_endpoint = (
        f"https://{args.endpoint_location}-discoveryengine.googleapis.com/v1alpha/"
        f"projects/{args.project or 'PROJECT_ID'}/locations/{args.endpoint_location}/"
        f"collections/default_collection/engines/{args.app_id}/assistants/default_assistant/agents"
    )

    logger.info("======================================================================")
    logger.info("📋 GEMINI ENTERPRISE REGISTRATION PAYLOAD")
    logger.info("======================================================================")
    logger.info(f"Target URL   : {target_url}")
    logger.info(f"Discovery API: {api_endpoint}")
    logger.info("======================================================================")

    curl_command = (
        f"curl -X POST \\\n"
        f"  -H \"Authorization: Bearer $(gcloud auth print-access-token)\" \\\n"
        f"  -H \"Content-Type: application/json\" \\\n"
        f"  -H \"X-Goog-User-Project: {args.project or '$PROJECT_ID'}\" \\\n"
        f"  \"{api_endpoint}\" \\\n"
        f"  -d '{json.dumps(payload, indent=2)}'"
    )

    if args.dry_run:
        print("\nGenerated curl command for Gemini Enterprise registration:\n")
        print(curl_command)
        print("\n✓ Dry-run completed successfully.")
        return

    # Execute registration if not dry-run
    try:
        token = get_gcloud_token()
        import urllib.request

        req = urllib.request.Request(
            api_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Goog-User-Project": args.project,
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            logger.info("✓ Registration succeeded!")
            print(body)
    except Exception as e:
        logger.error(f"Registration request failed: {e}")
        print("\nYou can execute the registration manually using curl:\n")
        print(curl_command)
        sys.exit(1)


if __name__ == "__main__":
    main()
