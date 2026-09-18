"""Unit tests for Cloud Run and Vertex AI Agent Engine deployment artifacts."""

import json
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_dockerfile_security_and_a2a_compliance() -> None:
    dockerfile_path = PROJECT_ROOT / "deploy" / "Dockerfile"
    assert dockerfile_path.is_file(), "deploy/Dockerfile must exist"

    content = dockerfile_path.read_text(encoding="utf-8")

    # SPEC-DEP-1: Non-root user with UID >= 10000
    assert "USER_UID=10001" in content or "10001" in content
    assert "USER ${USERNAME}" in content or "USER vibeguard" in content

    # SPEC-DEP-2: Minimal base image
    assert "FROM python:3.12-slim" in content

    # SPEC-DEP-3: Pinned tool versions
    assert "semgrep==1.70.0" in content
    assert "gitleaks" in content

    # A2UI Cloud Run Deployer wiring:
    assert "PYTHONPATH" in content and "vibe_guard_a2ui" in content
    assert "ENTRYPOINT" in content
    assert "8080" in content


def test_cloudrun_yaml_manifest() -> None:
    yaml_path = PROJECT_ROOT / "deploy" / "cloudrun.yaml"
    assert yaml_path.is_file(), "deploy/cloudrun.yaml must exist"

    manifest = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "Service"
    assert manifest["metadata"]["name"] == "vibe-guard-a2ui"

    container = manifest["spec"]["template"]["spec"]["containers"][0]
    assert container["ports"][0]["containerPort"] == 8080
    assert container["securityContext"]["runAsNonRoot"] is True
    assert container["securityContext"]["runAsUser"] == 10001

    # Verify memory volume mounted on /tmp for ephemeral scans
    volume_mounts = {vm["name"]: vm["mountPath"] for vm in container["volumeMounts"]}
    assert "/tmp" in volume_mounts.values()


def test_agent_engine_dry_run() -> None:
    deployer_path = PROJECT_ROOT / "vibe_guard_a2ui" / "deploy_agent_engine.py"
    assert deployer_path.is_file()

    res = subprocess.run(
        [sys.executable, str(deployer_path), "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    success_msg = "Packaging validation successful"
    assert success_msg in res.stderr or success_msg in res.stdout


def test_register_gemini_enterprise_payload_generation() -> None:
    from vibe_guard_a2ui.register_gemini_enterprise import (
        build_registration_payload,
        load_agent_card,
    )

    card = load_agent_card()
    payload = build_registration_payload(
        card=card,
        target_url="https://test.run.app/a2a/vibe_guard_a2ui",
        display_name="Vibe Guard Security",
        description="Test description",
        project_number="123456789",
        auth_id="auth-profile-v1",
    )

    assert payload["displayName"] == "Vibe Guard Security"
    assert "a2aAgentDefinition" in payload
    agent_card_str = payload["a2aAgentDefinition"]["jsonAgentCard"]
    parsed_card = json.loads(agent_card_str)
    assert parsed_card["url"] == "https://test.run.app/a2a/vibe_guard_a2ui"
    assert payload["authorizationConfig"]["agentAuthorization"] == (
        "projects/123456789/locations/global/authorizations/auth-profile-v1"
    )
