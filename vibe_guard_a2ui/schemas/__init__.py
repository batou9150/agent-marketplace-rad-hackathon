"""Vendored A2UI v0.9 schemas and the A2UI message validator.

The three JSON files in this package are verbatim copies of the public A2UI v0.9
specification and of the Gemini Enterprise composite catalog:

- `server_to_client.json`
  https://raw.githubusercontent.com/google/A2UI/main/specification/v0_9/json/server_to_client.json
- `common_types.json`
  https://a2ui.org/specification/v0_9/common_types.json
- `gemini_enterprise_composite_catalog.json`
  https://www.gstatic.com/vertexaisearch/a2ui/v0_9/gemini_enterprise_composite_catalog.json

They are vendored (rather than fetched at runtime) so conformance checks stay
hermetic in CI, following the same convention as Google's own Gemini Enterprise
ADK sample. Refresh them whenever the published catalog changes.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMA_DIR = Path(__file__).resolve().parent

COMMON_TYPES_ID = "https://a2ui.org/specification/v0_9/common_types.json"
_COMMON_TYPES_REF_PREFIX = f"{COMMON_TYPES_ID}#/$defs/"
_CATALOG_REF_PREFIX = "catalog.json#/$defs/"
_COMMON_TYPES_DEF_PREFIX = "ct_"


def load_schema(name: str) -> dict[str, Any]:
    """Load one vendored schema file by stem (e.g. 'common_types')."""
    return json.loads((SCHEMA_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _rewrite_refs(node: Any, internal_prefix: str = "") -> Any:
    """Rewrite cross-document `$ref`s into pointers inside the bundled schema."""
    if isinstance(node, dict):
        rewritten: dict[str, Any] = {}
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                if value.startswith(_COMMON_TYPES_REF_PREFIX):
                    name = value[len(_COMMON_TYPES_REF_PREFIX) :]
                    rewritten[key] = f"#/$defs/{_COMMON_TYPES_DEF_PREFIX}{name}"
                elif value.startswith(_CATALOG_REF_PREFIX):
                    rewritten[key] = f"#/$defs/{value[len(_CATALOG_REF_PREFIX) :]}"
                elif internal_prefix and value.startswith("#/$defs/"):
                    rewritten[key] = f"#/$defs/{internal_prefix}{value[len('#/$defs/') :]}"
                else:
                    rewritten[key] = value
            else:
                rewritten[key] = _rewrite_refs(value, internal_prefix)
        return rewritten
    if isinstance(node, list):
        return [_rewrite_refs(item, internal_prefix) for item in node]
    return node


@lru_cache(maxsize=1)
def build_message_schema() -> dict[str, Any]:
    """Bundle the vendored schemas into one self-contained A2UI message schema.

    `jsonschema` would otherwise have to fetch `common_types.json` and
    `catalog.json` over the network, so every cross-document `$ref` is rewritten
    into a local `#/$defs/...` pointer (common-type definitions are namespaced
    with a `ct_` prefix to avoid colliding with catalog definitions).
    """
    common = load_schema("common_types")
    catalog = load_schema("gemini_enterprise_composite_catalog")
    server_to_client = load_schema("server_to_client")

    defs: dict[str, Any] = {}
    defs.update(_rewrite_refs(server_to_client["$defs"]))
    defs.update(_rewrite_refs(catalog["$defs"]))
    for name, definition in common["$defs"].items():
        defs[f"{_COMMON_TYPES_DEF_PREFIX}{name}"] = _rewrite_refs(
            definition, internal_prefix=_COMMON_TYPES_DEF_PREFIX
        )

    # The published Gemini Enterprise catalog carries two dangling refs of its
    # own: MaterialTabs.children and MaterialTab.children point at a local
    # `#/$defs/ChildList` the catalog never defines. Alias it to the common type
    # they clearly mean so the bundle resolves.
    defs.setdefault("ChildList", defs[f"{_COMMON_TYPES_DEF_PREFIX}ChildList"])

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "oneOf": _rewrite_refs(server_to_client["oneOf"]),
        "$defs": defs,
        "components": _rewrite_refs(catalog["components"]),
    }


def iter_message_errors(message: dict[str, Any]) -> list[str]:
    """Return human-readable A2UI v0.9 violations for a single message envelope.

    Component-level errors are reported against the concrete catalog component
    (rather than the `anyComponent` union) so the message names the offending
    property instead of dumping every branch of the union.
    """
    from jsonschema import Draft202012Validator

    schema = build_message_schema()
    errors: list[str] = []

    if not Draft202012Validator(schema).is_valid(message):
        errors.append("message envelope does not match the A2UI v0.9 schema")

    components = message.get("updateComponents", {}).get("components", [])
    for component in components:
        component_id = component.get("id", "<no id>")
        name = component.get("component")
        if name not in schema["components"]:
            errors.append(f"{component_id}: unknown component {name!r}")
            continue
        validator = Draft202012Validator(
            {
                "$ref": f"#/components/{name}",
                "$defs": schema["$defs"],
                "components": schema["components"],
            }
        )
        for error in sorted(validator.iter_errors(component), key=lambda e: list(e.path)):
            location = "/".join(str(part) for part in error.absolute_path) or "<component>"
            errors.append(f"{component_id} ({name}) @ {location}: {error.message}")

    return errors
