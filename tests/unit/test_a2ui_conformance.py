"""A2UI v0.9 conformance tests for every surface Vibe Guard emits.

These validate the real builder output against the vendored official schemas
(the A2UI v0.9 server-to-client message schema plus the Gemini Enterprise
composite catalog the agent declares as its `catalogId`), rather than against
the shape the builders happen to produce.
"""

import pytest

from tests.unit.test_a2ui_presentation import _make_dummy_report
from vibe_guard_a2ui.a2ui_presentation import (
    GE_CATALOG_ID,
    build_dashboard_canvas_surface,
    build_finding_detail_surface,
    build_scan_form_surface,
)
from vibe_guard_a2ui.schemas import iter_message_errors, load_schema


def _surfaces():
    report = _make_dummy_report()
    return {
        "scan_form": build_scan_form_surface(),
        "dashboard": build_dashboard_canvas_surface(report),
        "finding_detail": build_finding_detail_surface(report.findings[0]),
    }


@pytest.mark.parametrize("name", ["scan_form", "dashboard", "finding_detail"])
def test_surface_validates_against_a2ui_v0_9(name: str) -> None:
    """Every message of every surface must satisfy the A2UI v0.9 schema."""
    envelope = _surfaces()[name]
    failures: list[str] = []
    for index, message in enumerate(envelope["messages"]):
        for error in iter_message_errors(message):
            failures.append(f"{name} msg[{index}]: {error}")
    assert not failures, "A2UI v0.9 violations:\n" + "\n".join(failures)


def test_declared_catalog_matches_vendored_catalog() -> None:
    """The catalogId the agent advertises must be the catalog we validate against."""
    catalog = load_schema("gemini_enterprise_composite_catalog")
    assert catalog["catalogId"] == GE_CATALOG_ID


@pytest.mark.parametrize("name", ["scan_form", "dashboard", "finding_detail"])
def test_component_tree_is_connected(name: str) -> None:
    """Every component must be reachable from `root`, and every child must exist.

    Schema validation cannot catch an orphan: a component that no parent lists in
    its `children` is silently dropped by the renderer.
    """
    envelope = _surfaces()[name]
    components = envelope["messages"][1]["updateComponents"]["components"]
    by_id = {component["id"]: component for component in components}
    assert "root" in by_id, "updateComponents must define a component with id 'root'"

    reachable: set[str] = set()
    stack = ["root"]
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        children = by_id[current].get("children", [])
        assert isinstance(children, list), f"{current}: dynamic child templates are not used here"
        for child in children:
            assert child in by_id, f"{current} references missing component {child!r}"
            stack.append(child)

    orphans = sorted(set(by_id) - reachable)
    assert not orphans, f"components unreachable from root: {orphans}"


@pytest.mark.parametrize("name", ["scan_form", "dashboard", "finding_detail"])
def test_actions_carry_a_prompt(name: str) -> None:
    """Gemini Enterprise replays `context.prompt` as the user's chat message."""
    envelope = _surfaces()[name]
    components = envelope["messages"][1]["updateComponents"]["components"]
    actions = [c["action"] for c in components if "action" in c]
    assert actions, f"{name} should expose at least one action"
    for action in actions:
        event = action["event"]
        assert isinstance(event, dict) and event.get("name"), "event must be an object with a name"
        assert isinstance(event.get("context"), dict), "event context must be an object"
        assert event["context"].get("prompt"), "event context must carry a human-readable prompt"


def test_surface_ids_are_unique_per_response() -> None:
    """Re-using a surfaceId across responses is a spec error and breaks the renderer."""
    first = build_scan_form_surface()["messages"][0]["createSurface"]["surfaceId"]
    second = build_scan_form_surface()["messages"][0]["createSurface"]["surfaceId"]
    assert first != second

    report = _make_dummy_report()

    def dashboard_surface_id() -> str:
        return build_dashboard_canvas_surface(report)["messages"][0]["createSurface"]["surfaceId"]

    assert dashboard_surface_id() != dashboard_surface_id()


@pytest.mark.parametrize("name", ["scan_form", "dashboard", "finding_detail"])
def test_all_messages_share_one_surface_id(name: str) -> None:
    """createSurface / updateComponents / updateDataModel must address one surface."""
    envelope = _surfaces()[name]
    surface_ids = {
        payload["surfaceId"]
        for message in envelope["messages"]
        for key, payload in message.items()
        if key != "version"
    }
    assert len(surface_ids) == 1, f"{name} spreads across surfaces {surface_ids}"
