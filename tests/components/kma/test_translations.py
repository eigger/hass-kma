"""Test KMA translations and key parity."""

from __future__ import annotations

import json
from pathlib import Path


def _flatten_keys(d: dict, prefix: str = "") -> set[str]:
    """Recursively collect flattened key paths."""
    keys = set()
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        keys.add(full_key)
        if isinstance(v, dict):
            keys.update(_flatten_keys(v, full_key))
    return keys


def test_translations_parity() -> None:
    """Test that strings.json, en.json, and ko.json exist and match keys."""
    kma_dir = Path(__file__).parents[3] / "custom_components" / "kma"
    strings_path = kma_dir / "strings.json"
    en_path = kma_dir / "translations" / "en.json"
    ko_path = kma_dir / "translations" / "ko.json"

    assert strings_path.is_file()
    assert en_path.is_file()
    assert ko_path.is_file()

    with open(strings_path, encoding="utf-8") as f:
        strings_data = json.load(f)
    with open(en_path, encoding="utf-8") as f:
        en_data = json.load(f)
    with open(ko_path, encoding="utf-8") as f:
        ko_data = json.load(f)

    strings_keys = _flatten_keys(strings_data)
    en_keys = _flatten_keys(en_data)
    ko_keys = _flatten_keys(ko_data)

    # All keys defined in strings.json should exist in en.json and ko.json
    assert strings_keys == en_keys
    assert strings_keys == ko_keys
