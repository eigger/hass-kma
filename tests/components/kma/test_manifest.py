"""Test KMA manifest."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.kma.const import DOMAIN


def test_manifest() -> None:
    """Test that manifest is valid and matches domain."""
    manifest_path = (
        Path(__file__).parents[3] / "custom_components" / "kma" / "manifest.json"
    )
    assert manifest_path.is_file()

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["domain"] == DOMAIN
    assert manifest["config_flow"] is True
    assert "name" in manifest
    assert "version" in manifest
    assert "documentation" in manifest
    assert "issue_tracker" in manifest
    assert "codeowners" in manifest
    assert "@eigger" in manifest["codeowners"]
