# User Guide

Detailed documentation for the Korea Meteorological Administration (KMA) Home Assistant Integration.

## Features & Entity Architecture

The integration connects Home Assistant with the official KMA APIhub services (`apihub.kma.go.kr`) to provide real-time weather observations, short/mid-term village forecasts, safety warnings, and radar/satellite image products.

### Hub & Zone Structure

- **API Hub Device**: Represents the API connection and client credentials. Houses diagnostic activation sensors (`binary_sensor.kma_activation_*`) and error counters (`sensor.kma_error_count_*`).
- **Zone Subentry Devices**: Created for each configured Home Assistant Zone (e.g. `zone.home`). Maps coordinates to KMA grid (nx, ny) and forecast regions.
- **AWS Station Devices**: Automatically discovers or manually configures automated weather stations (AWS) for localized hyper-local observations.

## Entities Summary

| Platform | Entity Name | Description | Update Interval |
|----------|-------------|-------------|-----------------|
| `weather` | `weather.kma_<zone>` | Standard Home Assistant Weather entity with hourly & 10-day forecasts | 10 min |
| `sensor` | `sensor.kma_<zone>_temperature` | Current observed/forecast temperature (°C) | 10 min |
| `sensor` | `sensor.kma_<zone>_humidity` | Relative humidity (%) | 10 min |
| `sensor` | `sensor.kma_<zone>_wind_speed` | Wind speed (m/s) | 10 min |
| `sensor` | `sensor.kma_<zone>_pop` | Probability of precipitation (%) | 10 min |
| `sensor` | `sensor.kma_<zone>_pcp` | 1-hour precipitation amount (mm) | 10 min |
| `sensor` | `sensor.kma_<zone>_pm10` | Particulate matter PM10 concentration (µg/m³) | 10 min |
| `sensor` | `sensor.kma_<zone>_uv_index` | UV index score and rating | 10 min |
| `binary_sensor` | `binary_sensor.kma_<zone>_warning` | Active weather advisories/warnings | 10 min |
| `button` | `button.kma_<zone>_refresh` | Manual data refresh action | On demand |
| `image` | `image.kma_radar_image` | Composite radar precipitation reflectance image | 10 min |
| `image` | `image.kma_satellite_image` | GK2A weather satellite infrared image | 10 min |

## Actions & Services

### `homeassistant.update_entity` or Refresh Button

Pressing `button.kma_<zone>_refresh` triggers an immediate data fetch bypassing the regular update interval.
