# Development & Testing Guide

This document describes how to develop and test `hass-kma` locally using the shared repository standards.

## Prerequisites

- Python 3.14 (HA 2026.9.0 and 2026.10.2 baseline)
- `uv` (recommended) or `pip`

## Virtual Environments

### Current Environment (Python 3.14 / HA 2026.10.2)

```bash
uv venv .venv --python 3.14
source .venv/bin/activate
uv pip install -r requirements_test.txt -r requirements_lint.txt
pytest tests/components/kma/ -v
uv pip check
```

### Minimum HA Environment (Python 3.14 / HA 2026.9.0)

```bash
uv venv .venv-min --python 3.14
source .venv-min/bin/activate
uv pip install -r requirements_test_min.txt -r requirements_lint.txt
pytest tests/components/kma/ -v
uv pip check
```

### Linting and Formatting

```bash
uv pip install -r requirements_lint.txt
ruff check .
ruff format --check .
```

## Test Structure

Tests are organized under `tests/components/kma/` following Home Assistant Core architectural standards:

- `conftest.py`: Authentic fixtures, sample KMA APIhub payloads, and mock clients.
- `test_init.py`: Entry setup, unload, options reload, and subentry loading.
- `test_config_flow.py`: User flow (auth key validation), Zone subentry flow, and AWS station subentry flow.
- `test_weather.py`: Weather entity, state calculations, and forecast methods.
- `test_sensor.py`: Weather observations, indices, and error count sensors.
- `test_binary_sensor.py`: Weather warning binary sensors and API activation diagnostics.
- `test_button.py`: Refresh action button entities.
- `test_image.py`: Radar and satellite image entities and stream fetching.
- `test_coordinator.py`: Data update coordinator lifecycles and fallback handling.
- `test_diagnostics.py`: Diagnostics redaction and dump format.
- `test_manifest.py`: `manifest.json` schema validation.
- `test_translations.py`: Localization key parity between `strings.json` and translations.
