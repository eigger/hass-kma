# User Guide

Detailed user documentation for the Korea Meteorological Administration (KMA) APIhub integration (`hass-kma`).

## Architecture Overview

Integrates official open data APIs from KMA APIhub (apihub.kma.go.kr) to provide real-time weather conditions, detailed observations, village forecasts (short/mid-term), living weather indices, radar/satellite imagery, and weather disaster warnings.

### Device Hierarchy

- **KMA APIhub (Hub)**: Manages API communication and sessions. Registers activation status entities (`binary_sensor.kma_activation_*`), error counters (`sensor.kma_error_count_*`), radar/satellite image entities, and earthquake/typhoon sensors.
- **Zone Device**: Configured per Home Assistant Zone (`zone.*`). Maps coordinates (nx, ny) and forecast regions to create the weather entity (`weather.<zone_slug>`), observation/forecast sensors (`sensor.<zone_slug>_*`), living index sensors, and warning sensors (`binary_sensor.<zone_slug>_warning`).
- **AWS Device**: Configured per AWS/ASOS station to monitor 1-minute real-time local ground observations (`sensor.aws_<station_id>_*`).

---

## KMA APIhub Application Guide

To utilize all integration features, create an account on the [KMA APIhub Website](https://apihub.kma.go.kr/) and apply for access to the following APIs.

### Required & Recommended APIs (~20 APIs)

1. **Village Forecast (Short-term Forecast)** (`getVilageFcst`) — Hourly/daily weather and core sensors
2. **Short-term Land Forecast** (`fct_afs_dl.php`) — Mid-term land weather
3. **Short-term Marine Forecast** (`fct_afs_do.php`) — Marine weather
4. **Special Weather Report Status** (`wrn_now_data.php`) — Weather warning safety binary sensor
5. **Forecast Region Information** (`fct_shrt_reg.php`) — API key validation
6. **PM10 Observation Data** (`kma_pm10.php`, Ground > PM10) — Fine dust observation
7. **PM10 Hourly Statistics** (`dst_pm10_hr.php`) — Fine dust stats
8. **Living Weather Index Service** (`LivingWthrIdxServiceV3` — `getUVIdxV3`, `getAirDiffusionIdxV3`) — UV index, air stagnation index
9. **Health Weather Index Service** (`HealthWthrIdxServiceV2` — `getOakPollenRiskIdxV2`, `getPinePollenRiskIdxV2`, `getWeedsPollenRiskndxV2`) — Pollen risk indices
10. **Weather Radar Service** (`WthrRadarInfoService/getCompCappiQcdArea`) — Radar precipitation rate
11. **Radar Composite Data Download** (`typ04/rdr_cmp_file.php`) — Radar image entity
12. **GK2A Satellite Imagery** (`typ03/nph-gk2a_img`) — Satellite infrared/visible/water vapor image entities
13. **Ultra Short-term QPF Graphic** (`typ03/nph-qpf_ana_img`) — 60-min precipitation forecast image
14. **High-resolution Surface Observation** (`sfc_nc_var.php`) — Observed apparent temperature
15. **Impact Forecast Status** (`ifs_fct_pstt.php`) — Heatwave / coldwave impact risk
16. **Snowfall Observation Data** (`kma_snow1.php`) — Observed snow depth
17. **Earthquake Information** (`typ09/eqk/urlNewNotiEqk.do`) — Recent earthquake alerts
18. **Typhoon Information** (`typ_now.php`) — Active typhoon status
19. **Yellow Dust Satellite Image** (`YdstInfoService/getYdstSatlitImg`) — Dust satellite imagery
20. **[Optional] Station 1-minute Observation** (`typ01/cgi-bin/url/nph-aws2_min`) — Required only when using AWS station subentries

*Special weather reports (`wrn_inf_rpt.php`) and weather commentaries (`wthr_cmt_rpt.php`) are accessible without separate application approval.*

---

## Detailed Entities

| Device | Entity ID (e.g. Home Zone) | Name | Underlying API | Example State | Interval |
| --- | --- | --- | --- | --- | --- |
| Weather | `weather.home` | Weather | Village Forecast (`getVilageFcst`) | `sunny` (HA condition) | 10 min |
| Zone | `sensor.home_temperature` | Temperature | Village Forecast | `22.5` °C | 10 min |
| Zone | `sensor.home_humidity` | Humidity | Village Forecast | `65` % | 10 min |
| Zone | `sensor.home_wind_speed` | Wind Speed | Village Forecast | `3.2` m/s | 10 min |
| Zone | `sensor.home_pop` | Precipitation Probability | Village Forecast | `30` % | 10 min |
| Zone | `sensor.home_precipitation` | 1h Precipitation | Village Forecast | `0.0` / `5.0` mm | 10 min |
| Zone | `sensor.home_snowfall` | 1h Snowfall | Village Forecast (SNO) | `0.0` / `2.0` cm | 10 min |
| Zone | `sensor.home_apparent_temperature` | Apparent Temperature | Steadman formula | `21.8` °C | 10 min |
| Zone | `sensor.home_dew_point` | Dew Point | Magnus-Tetens formula | `15.2` °C | 10 min |
| Zone | `sensor.home_discomfort_index` | Discomfort Index | Temp & Humidity | `72.3` | 10 min |
| Zone | `sensor.home_pm10` | PM10 (Fine Dust) | PM10 Observation | `28` µg/m³ | 10 min |
| Zone | `sensor.home_uv_index` | UV Index | `LivingWthrIdxServiceV3` | `6` | 10 min |
| Zone | `binary_sensor.home_warning` | Weather Warning | Special Weather Report | `off` / `on` | 10 min |
| Zone | `button.home_refresh` | Manual Refresh | Home Assistant action | Press to refresh | Manual |
| Hub | `image.kma_radar_image` | Radar Composite Image | `typ04/rdr_cmp_file.php` | State=Timestamp, Output=PNG | 10 min |
| Hub | `image.kma_satellite_image` | Satellite Infrared Image | `typ03/nph-gk2a_img` | State=Timestamp, Output=PNG | 10 min |
| AWS | `sensor.aws_108_temperature` | Temperature (1-min) | Station 1-min data | `23.1` °C | 5 min (301s) |
| AWS | `sensor.aws_108_humidity` | Humidity (1-min) | Station 1-min data | `71.0` % | 5 min (301s) |

---

## Configuration Options

Configure via **Settings → Devices & Services → KMA APIhub → Configure**:

- **Scan Interval**: Default 10 minutes (configurable between 5 and 180 minutes). AWS station observations use a fixed 5-minute (301s) throttle.
