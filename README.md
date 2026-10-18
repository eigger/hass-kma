# KMA Weather (기상청 APIhub)

<!-- hass-standards:badges:start -->
[![Release](https://img.shields.io/github/v/release/eigger/hass-kma?style=flat)](https://github.com/eigger/hass-kma/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat)](#installation)
[![Home Assistant minimum](https://img.shields.io/badge/HA-%E2%89%A5%202026.9.0-41BDF5?style=flat)](hacs.json)
[![Tests](https://img.shields.io/github/actions/workflow/status/eigger/hass-kma/tests.yml?branch=main&style=flat&label=Tests)](https://github.com/eigger/hass-kma/actions/workflows/tests.yml)
[![Validate](https://img.shields.io/github/actions/workflow/status/eigger/hass-kma/validate.yml?branch=main&style=flat&label=Validate)](https://github.com/eigger/hass-kma/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/eigger/hass-kma?style=flat)](LICENSE)
[![Analytics reporting installs](https://img.shields.io/badge/dynamic/json?style=flat&color=41BDF5&label=Usage&query=%24.kma.total&url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json)](https://analytics.home-assistant.io/)
<!-- hass-standards:badges:end -->

English | [한국어 (Korean)](README.ko.md)

Home Assistant custom component for integrating Korea Meteorological Administration (KMA) APIhub services (`apihub.kma.go.kr`). Provides real-time observations, village forecasts, life weather indices, safety warnings, and satellite/radar imagery.

## Features

- **Standard Weather Platform**: Hourly forecasts (up to 3 days) and daily forecasts (up to 10 days).
- **Comprehensive Sensors**: Temperature, humidity, wind, rainfall probability, PM10, UV index, and discomfort index.
- **Safety Warnings**: Instant `binary_sensor` activation upon regional weather advisories (heavy rain, typhoons, heatwaves, etc.).
- **Radar & Satellite Imagery**: Composite radar reflectance and GK2A satellite infrared images exposed as `image` entities.
- **Diagnostics**: Built-in API authorization tracking and error rate counters.

## Quick start

Add your API Key from [KMA APIhub](https://apihub.kma.go.kr/) and select your Home Assistant zone:

1. Obtain an API key (authKey) from [KMA APIhub](https://apihub.kma.go.kr/) and apply for necessary APIs (~20 APIs; see [User Guide](docs/user-guide.md#kma-apihub-application-guide)).
2. In Home Assistant, go to **Settings → Devices & Services → Add Integration**.
3. Search for **KMA Weather (기상청 APIhub)**.
4. Enter your API key and configure your location zones and optional AWS stations.

## Installation

### HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed.
2. Add this repository as a Custom Repository under HACS with category `Integration`.
3. Search for `KMA Weather` and click **Download**.
4. Restart Home Assistant.

### Manual Installation

1. Download the latest release archive.
2. Copy `custom_components/kma` into your Home Assistant `<config_dir>/custom_components/`.
3. Restart Home Assistant.

## Documentation

- [User Guide](docs/user-guide.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Development & Testing](docs/development.md)

## Support & Contributing

- Report issues and request features on [GitHub Issues](https://github.com/eigger/hass-kma/issues).
- Licensed under the [MIT License](LICENSE).
