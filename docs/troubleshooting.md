# Troubleshooting Guide

This guide covers common issues and resolutions when using the Korea Meteorological Administration (KMA) integration (`hass-kma`).

## Common Issues

### 1. "Invalid Auth Key" Error During Setup

- Ensure you have registered on the [KMA APIhub](https://apihub.kma.go.kr/) portal.
- Verify that your API key is correctly copied without extra whitespace.
- Some endpoints require separate API activation on APIhub before they return data.

### 2. "API Activation Required" Diagnostic Sensor is Off

- Check `binary_sensor.kma_activation_*` diagnostic entities.
- If a specific service (e.g. UV index, radar, PM10) shows `off` (unregistered), log in to [KMA APIhub](https://apihub.kma.go.kr/) and request access for that specific API package.
- Once approved, the sensor will automatically transition to `on` on the next polling cycle.

### 3. Missing Pollen / Seasonal Indices

- Certain health indices (such as Oak pollen, Pine pollen, Weed pollen) are seasonal services provided only during designated calendar months:
  - Oak & Pine pollen: March through June.
  - Weed pollen: August through October.
- Outside of these active service months, the corresponding sensors will report `unavailable` or `unknown`.

### 4. Rate Limiting and Error Counts

- KMA APIhub applies hourly or daily rate limits depending on your API key type.
- The integration creates `sensor.kma_error_count_*` diagnostic sensors to monitor call failures.
- If error counts increase, consider increasing the update interval in **Settings → Devices & Services → KMA Weather → Configure**.
