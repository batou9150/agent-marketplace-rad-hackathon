"""Unit tests for Cloud Run and Vertex AI Agent Engine deployment artifacts."""

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from vibe_guard_a2ui.local_tester.server import app

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

    template_spec = manifest["spec"]["template"]["spec"]
    container = template_spec["containers"][0]
    assert container["ports"][0]["containerPort"] == 8080
    assert container["securityContext"]["runAsNonRoot"] is True
    assert container["securityContext"]["runAsUser"] == 10001
    assert container["securityContext"]["readOnlyRootFilesystem"] is True

    # SPEC-OPS-3: Ingress restricted, dedicated service account, Secret Manager integration
    assert (
        manifest["metadata"]["annotations"]["run.googleapis.com/ingress"]
        == "internal-and-cloud-load-balancing"
    )
    assert "vibe-guard-agent-sa@" in template_spec["serviceAccountName"]
    secret_envs = [
        e for e in container["env"] if "valueFrom" in e and "secretKeyRef" in e["valueFrom"]
    ]
    assert len(secret_envs) >= 1

    # Verify memory volume mounted on /tmp for ephemeral scans
    volume_mounts = {vm["name"]: vm["mountPath"] for vm in container["volumeMounts"]}
    assert "/tmp" in volume_mounts.values()


def test_deploy_cloudrun_script_security_flags() -> None:
    """SPEC-OPS-3: deploy_cloudrun.sh enforces private IAM/IAP and minimal SA."""
    script_path = PROJECT_ROOT / "deploy" / "deploy_cloudrun.sh"
    assert script_path.is_file(), "deploy/deploy_cloudrun.sh must exist"

    content = script_path.read_text(encoding="utf-8")
    assert "--no-allow-unauthenticated" in content
    assert "--ingress=internal-and-cloud-load-balancing" in content
    assert "--service-account" in content
    assert "vibe-guard-agent-sa@" in content


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


def test_a2ui_server_routes_and_jsonrpc() -> None:
    client = TestClient(app)

    # 1. Health check endpoint
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["agent"] == "VibeGuardAgent"

    # 2. Agent Card root and namespaced endpoints
    card_resp = client.get("/.well-known/agent-card.json")
    assert card_resp.status_code == 200
    card_data = card_resp.json()
    assert card_data["name"] == "VibeGuardAgent"
    assert "capabilities" in card_data

    ns_card_resp = client.get("/a2a/vibe_guard_a2ui/.well-known/agent-card.json")
    assert ns_card_resp.status_code == 200
    assert ns_card_resp.json()["name"] == "VibeGuardAgent"

    # 3. JSON-RPC protocol error on invalid version
    err_resp = client.post("/jsonrpc", json={"jsonrpc": "1.0", "id": "1"})
    assert err_resp.status_code == 200
    assert err_resp.json()["error"]["code"] == -32600

    # 4. JSON-RPC unsupported method
    unsupp_resp = client.post(
        "/jsonrpc", json={"jsonrpc": "2.0", "method": "unknown/op", "id": "2"}
    )
    assert unsupp_resp.status_code == 200
    assert unsupp_resp.json()["error"]["code"] == -32601

    # 5. Namespaced JSON-RPC endpoint
    ns_err_resp = client.post("/a2a/vibe_guard_a2ui", json={"jsonrpc": "1.0", "id": "3"})
    assert ns_err_resp.status_code == 200
    assert ns_err_resp.json()["error"]["code"] == -32600

    # 6. JSON-RPC message/send rendering scan form
    form_resp = client.post(
        "/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {"message": {"text": "help"}},
            "id": "4",
        },
    )
    assert form_resp.status_code == 200
    form_data = form_resp.json()
    assert "result" in form_data
    parts = form_data["result"]["message"]["parts"]
    assert any("application/json+a2ui" in str(p.get("metadata", {})) for p in parts)

    # 7. JSON-RPC message/send executing scan
    scan_resp = client.post(
        "/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "text": "scan",
                    "parts": [
                        {
                            "data": {
                                "action": "submit_scan",
                                "repo_url": "fixtures/conform/clean_python_app",
                            }
                        }
                    ],
                }
            },
            "id": "5",
        },
    )
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert "result" in scan_data
    scan_parts = scan_data["result"]["message"]["parts"]
    assert any("application/json+a2ui" in str(p.get("metadata", {})) for p in scan_parts)


def test_a2ui_server_head_probes() -> None:
    """Verify HEAD requests for Cloud Run health checking."""
    client = TestClient(app)
    assert client.head("/healthz").status_code == 200
    assert client.head("/").status_code == 200


def test_a2ui_server_deployed_mode_authenticated_scan(monkeypatch, tmp_path) -> None:
    """Verify deployed mode resolves authenticated caller from headers and avoids 401/403."""
    app_file = tmp_path / "app.py"
    app_file.write_text("print('clean application')\n", encoding="utf-8")
    archive_path = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.write(app_file, arcname="app.py")

    monkeypatch.setenv("VIBE_GUARD_ENV", "production")
    client = TestClient(app)

    scan_resp = client.post(
        "/jsonrpc",
        headers={"X-Caller-ID": "auditor@gcp.sfeir.com"},
        json={
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "text": "scan",
                    "parts": [
                        {
                            "data": {
                                "action": "submit_scan",
                                "repo_url": str(archive_path),
                            }
                        }
                    ],
                }
            },
            "id": "6",
        },
    )
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert "result" in scan_data
    result_text = scan_data["result"]["message"]["parts"][0].get("text", "")
    assert "Error 401/403" not in result_text
    assert "Vibe Guard Security Audit Completed" in result_text


def test_a2ui_server_raw_git_url_detected_as_scan() -> None:
    """Verify that pasting a repository path or git URL automatically triggers scan intent."""
    client = TestClient(app)
    resp = client.post(
        "/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "text": "fixtures/conform/clean_python_app",
                }
            },
            "id": "7",
        },
    )
    assert resp.status_code == 200
    resp_data = resp.json()
    assert "result" in resp_data
    result_text = resp_data["result"]["message"]["parts"][0].get("text", "")
    assert "Vibe Guard Security Audit Completed" in result_text
