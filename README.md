# KMA Weather (기상청 APIhub)

**English** | [한국어 (Korean)](README.ko.md)

<!-- hass-standards:badges:start -->
[![Release](https://img.shields.io/github/v/release/eigger/hass-kma?style=flat)](https://github.com/eigger/hass-kma/releases)
[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5?style=flat)](#installation)
[![Home Assistant minimum](https://img.shields.io/badge/HA-%E2%89%A5%202026.9.0-41BDF5?style=flat)](hacs.json)
[![Tests](https://img.shields.io/github/actions/workflow/status/eigger/hass-kma/tests.yml?branch=main&style=flat&label=Tests)](https://github.com/eigger/hass-kma/actions/workflows/tests.yml)
[![Validate](https://img.shields.io/github/actions/workflow/status/eigger/hass-kma/validate.yml?branch=main&style=flat&label=Validate)](https://github.com/eigger/hass-kma/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/eigger/hass-kma?style=flat)](LICENSE)
[![Downloads](https://img.shields.io/github/downloads/eigger/hass-kma/total?style=flat&color=41BDF5&label=Downloads)](https://github.com/eigger/hass-kma/releases)
<!-- hass-standards:badges:end -->

The Downloads badge counts GitHub release asset downloads across all releases, not active installations.

Home Assistant custom integration for Korea Meteorological Administration (KMA) APIhub services (`apihub.kma.go.kr`). Delivers real-time weather observations, detailed station measurements, short- and mid-term forecasts, life weather indices (PM10, UV, atmospheric stagnation, pollen risk), severe weather advisories, and radar/satellite imagery.

---

## 🌟 Key Features

* **Standard Weather Entity (`weather.kma_*`)**
  * Current conditions: temperature, humidity, wind direction, wind speed, pressure, and visibility.
  * **Hourly Forecast**: Up to 3 days of hourly village forecasts.
  * **Daily Forecast**: Aggregates the 3-day village forecast daily, merged with mid-term land forecasts (`fct_afs_dl`) for days 4 to 10, providing up to 10 days of continuous daily forecasts.
  * Provides forecast summary texts (`land_forecast_summary`, `marine_forecast_summary`) and active weather warnings as attributes.
* **Detailed Weather Sensors (`sensor.kma_*`)**
  * Temperature, humidity, wind speed, precipitation probability, and 1-hour rainfall.
  * **Land / Marine Forecast Summaries**: Dashboard-ready Korean forecast statements.
  * **Daily Min/Max Temperatures**: Extracted from village forecast extreme values.
  * **Rain/Snow Forecast Window**: Monitors precipitation within 24 hours, exposing 3/6/12-hour flags.
  * **One-Line Weather Summary**: Concise single-string summary combining condition, temperature, daily range, and upcoming rain (ideal for ESL / E-Paper displays).
  * **Apparent Temperature / Dew Point / Discomfort Index**: Real-time calculations based on Steadman and Magnus-Tetens formulas. Discomfort index includes an enum grade sensor (`discomfort_grade`).
* **4 Life Weather Indices**
  * Laundry drying index, car wash index, freeze risk index, food poisoning index — each provided as a 0–100 numerical sensor paired with an ENUM grade sensor (`*_grade`) that auto-translates according to HA system language.
* **Fine Dust (PM10)**
  * Real-time 5-minute ground PM10 observations from the nearest station (`pm10`) with Ministry of Environment standard grade (`pm10_grade`). Hourly average/min/max statistics (`pm10_hourly_avg`) are also provided.
* **UV Index / Atmospheric Stagnation / Pollen Risk Indices**
  * Fetched via KMA living and health weather index APIs with the same authKey.
  * UV and air stagnation update every 3 hours. Pollen risk (oak, pine, weeds) updates twice daily during seasonal periods; reports unavailable outside active seasons.
* **Radar Precipitation Intensity & Radar / Satellite Images**
  * Zone-based radar reflectivity (dBZ) numeric sensor.
  * Provides composite radar images, GK2A satellite images (IR, visible, shortwave IR, water vapor), 60-minute precipitation forecast (QPF), and satellite Asian dust images directly as Home Assistant `image` entities for Picture Entity cards.
* **High-Resolution Surface Observation / Impact Forecast / Snow Depth**
  * Lat/lon coordinate-based observed apparent temperature (`apparent_temperature_observed`).
  * Official KMA heatwave and coldwave impact forecast risk levels (`heat_wave_risk` / `cold_wave_risk`, ENUM).
  * Station-observed snow depth (`snow_depth_observed`).
* **Hazard Information & Weather Commentary**
  * Real-time weather hazard bulletins (`hazard_info`) and daily meteorologist weather commentaries (`weather_commentary`) split into discrete sub-section sensors.
* **Earthquake & Typhoon Tracking**
  * Latest domestic/international earthquake reports and active typhoon positions, pressure, max wind speeds, and movement direction.
* **Severe Weather Safety Sensor (`binary_sensor.kma_*_warning`)**
  * Instantly turns `on` when severe weather warnings (heavy rain, heavy snow, gale, heatwave, coldwave, typhoon, yellow dust, etc.) are issued for the registered region, exposing details and count as attributes.
* **API Authorization & Health Diagnostics**
  * Automatically creates diagnostic sensors for every configured API tracking approval status (`binary_sensor.kma_activation_*`) and cumulative error counts (`sensor.kma_error_count_*`).
* **Seamless Multi-Zone & AWS Station Setup**
  * Select any Home Assistant Zone (`zone.*`) to automatically calculate grid coordinates (nx, ny) and match the optimal forecast region.
  * Search and add any of 720 built-in KMA ASOS/AWS/Gyeonggi-do (SG) automated weather observation stations for 1-minute real-time telemetry.

---

## 📋 Provided Entities & Sensors

| Device | Entity ID | Entity Name | Source API | Sample Value | Update Interval |
| --- | --- | --- | --- | --- | --- |
| KMA Weather | `weather.kma_<zone>` | Weather | Village forecast (`getVilageFcst`) | `sunny`, `rainy`, etc. | 10 min |
| KMA Weather | `sensor.kma_<zone>_temperature` | Temperature | Village forecast | `19.5` ℃ | 10 min |
| KMA Weather | `sensor.kma_<zone>_humidity` | Humidity | Village forecast | `65` % | 10 min |
| KMA Weather | `sensor.kma_<zone>_wind_speed` | Wind Speed | Village forecast | `3.2` m/s | 10 min |
| KMA Weather | `sensor.kma_<zone>_wind_direction` | Wind Direction | Village forecast | `WNW` (16-point cardinal) | 10 min |
| KMA Weather | `sensor.kma_<zone>_precipitation_probability` | Precipitation Probability | Village forecast | `20` % | 10 min |
| KMA Weather | `sensor.kma_<zone>_precipitation` | Hourly Precipitation | Village forecast | `0.0` mm | 10 min |
| KMA Weather | `sensor.kma_<zone>_daily_min_temp` | Today Min Temp | Village forecast extreme scan | `11.0` ℃ | 10 min |
| KMA Weather | `sensor.kma_<zone>_daily_max_temp` | Today Max Temp | Village forecast extreme scan | `26.0` ℃ | 10 min |
| KMA Weather | `sensor.kma_<zone>_precipitation_expected_time` | Expected Rain Time | Forecast merge | `2026-07-03T16:00:00+09:00` | 10 min |
| KMA Weather | `binary_sensor.kma_<zone>_precipitation_expected` | Rain Expected Soon | Rain within 6 hours | `on` / `off` | 10 min |
| KMA Weather | `sensor.kma_<zone>_apparent_temperature` | Apparent Temperature | Steadman formula | `21.8` ℃ | 10 min |
| KMA Weather | `sensor.kma_<zone>_dew_point` | Dew Point | Magnus-Tetens formula | `15.2` ℃ | 10 min |
| KMA Weather | `sensor.kma_<zone>_discomfort_index` / `_grade` | Discomfort Index / Grade | Temperature & humidity | `72.3` / `normal` | 10 min |
| KMA Weather | `sensor.kma_<zone>_laundry_index` / `_grade` | Laundry Index / Grade | Temperature, humidity, wind | `85` / `good` | 10 min |
| KMA Weather | `sensor.kma_<zone>_car_wash_index` / `_grade` | Car Wash Index / Grade | 72h rain outlook | `90` / `excellent` | 10 min |
| KMA Weather | `sensor.kma_<zone>_freeze_risk_index` / `_grade` | Freeze Risk Index / Grade | 48h min temp | `10` / `low` | 10 min |
| KMA Weather | `sensor.kma_<zone>_food_poisoning_index` / `_grade` | Food Poisoning Index / Grade | Temp & humidity model | `42` / `attention` | 10 min |
| KMA Weather | `sensor.kma_<zone>_one_line_summary` | One-Line Weather Summary | Comprehensive condition string | `Sunny, 19.5°C (11.0°C/26.0°C)` | 10 min |
| KMA Weather | `sensor.kma_<zone>_land_forecast_summary` | Land Forecast Summary | Short-term land forecast (`fct_afs_dl`) | `Partly cloudy` | Daily 05:00, 17:00 |
| KMA Weather | `sensor.kma_<zone>_marine_forecast_summary` | Marine Forecast Summary | Short-term marine forecast (`fct_afs_do`) | `Waves 0.5–1.0m` | Daily 05:00, 17:00 |
| KMA Weather | `sensor.kma_<zone>_pm10` / `_grade` | PM10 Fine Dust / Grade | PM10 observations (`kma_pm10.php`) | `28` ㎍/㎥ / `good` | 10 min |
| KMA Weather | `sensor.kma_<zone>_pm10_hourly_avg` | PM10 Hourly Average | Hourly stats (`dst_pm10_hr.php`) | `31.5` ㎍/㎥ | 10 min |
| KMA Weather | `sensor.kma_<zone>_uv_index` / `_grade` | UV Index / Grade | Living index (`getUVIdxV3`) | `6` / `high` | 10 min |
| KMA Weather | `sensor.kma_<zone>_air_stagnation_index` / `_grade` | Air Stagnation Index / Grade | Diffusion index (`getAirDiffusionIdxV3`) | `50` / `moderate` | 10 min |
| KMA Weather | `sensor.kma_<zone>_oak_pollen_risk` / `_grade` | Pollen Risk (Oak) / Grade | Pollen index (`getOakPollenRiskIdxV2`) | `1` / `moderate` | 10 min |
| KMA Weather | `sensor.kma_<zone>_pine_pollen_risk` / `_grade` | Pollen Risk (Pine) / Grade | Pollen index (`getPinePollenRiskIdxV2`) | `1` / `moderate` | 10 min |
| KMA Weather | `sensor.kma_<zone>_weed_pollen_risk` / `_grade` | Pollen Risk (Weeds) / Grade | Pollen index (`getWeedsPollenRiskndxV2`) | `1` / `moderate` | 10 min |
| KMA Weather | `sensor.kma_<zone>_radar_precipitation` | Radar Intensity (dBZ) | Radar CAPPI (`getCompCappiQcdArea`) | `32.5` dBZ | 10 min |
| KMA Weather | `sensor.kma_<zone>_radar_precipitation_grade` | Radar Intensity Grade | Classified from dBZ | `Light Rain` | 10 min |
| KMA Weather | `sensor.kma_<zone>_apparent_temperature_observed` | Observed Apparent Temp | Surface observation (`sfc_nc_var.php`) | `27.0` ℃ | 10 min |
| KMA Weather | `sensor.kma_<zone>_heat_wave_risk` / `_cold_wave_risk` | Heatwave / Coldwave Risk | Impact forecast (`ifs_fct_pstt.php`) | `None` / `Caution` | 10 min |
| KMA Weather | `sensor.kma_<zone>_snow_depth_observed` | Observed Snow Depth | Snow observation (`kma_snow1.php`) | `0.0` cm | 10 min |
| KMA Weather | `sensor.kma_<zone>_hazard_info` (+ `_section_1`~`_3`) | Hazard Information | Weather warning reports (`wrn_inf_rpt.php`) | Title (sections in attributes) | 10 min |
| KMA Weather | `sensor.kma_<zone>_weather_commentary` (+ `_section_1`~`_8`) | Weather Commentary | Weather commentary (`wthr_cmt_rpt.php`) | Title (sections in attributes) | 10 min |
| KMA Weather | `binary_sensor.kma_<zone>_warning` | Weather Warning Safety Sensor | Warning bulletins (`wrn_now_data.php`) | `on` / `off` | 10 min |
| Each Zone | `sensor.kma_recent_earthquake` | Recent Earthquake | Earthquake alerts (`urlNewNotiEqk.do`) | `4.3` (mag; loc/time in attrs) | 10 min |
| Each Zone | `sensor.kma_typhoon_number` | Typhoon Number | Typhoon alerts (`typ_now.php`) | `0` (none) / `5` (Typhoon #5) | 10 min |
| Each Zone | `image.kma_radar_image` | Radar Composite Image | Radar composite (`rdr_cmp_file.php`) | State=Timestamp, Output=PNG | 10 min |
| Each Zone | `image.kma_satellite_image` | Satellite (GK2A) IR Image | GK2A IR (`nph-gk2a_img`) | State=Timestamp, Output=PNG | 10 min |
| Each Zone | `image.kma_precipitation_forecast_image` | QPF Forecast Image (+60m) | QPF analysis (`nph-qpf_ana_img`) | State=Timestamp, Output=PNG | 10 min |
| Each Zone | `image.kma_satellite_visible_image` | Satellite Visible Image | GK2A visible (`nph-gk2a_img?obs=vi006`) | State=Timestamp, Output=PNG | 10 min |
| Each Zone | `image.kma_satellite_shortwave_ir_image` | Satellite Shortwave IR Image | GK2A SWIR (`nph-gk2a_img?obs=sw038`) | State=Timestamp, Output=PNG | 10 min |
| Each Zone | `image.kma_satellite_water_vapor_image` | Satellite Water Vapor Image | GK2A WV (`nph-gk2a_img?obs=wv069`) | State=Timestamp, Output=PNG | 10 min |
| Each Zone | `image.kma_dust_satellite_image` | Dust Satellite Image (IDI) | Yellow dust imagery (`getYdstSatlitImg`) | State=Timestamp, Output=PNG | 10 min |
| Each AWS Station | `sensor.aws_<station>_observation_time` | Observation Time | AWS 1-min data (`nph-aws2_min`) | `2026-07-03T14:31:00+09:00` | ~5 min |
| Each AWS Station | `sensor.aws_<station>_temperature` | Temperature | AWS 1-min data (TA) | `23.1` ℃ | ~5 min |
| Each AWS Station | `sensor.aws_<station>_humidity` | Humidity | AWS 1-min data (HM) | `71` % | ~5 min |
| Each AWS Station | `sensor.aws_<station>_dew_point` | Dew Point | AWS 1-min data (TD) | `17.7` ℃ | ~5 min |
| Each AWS Station | `sensor.aws_<station>_wind_direction_1_min` | 1-Min Avg Wind Direction | AWS 1-min data (WD1) | `225` ° (Calm 360 = `unknown`) | ~5 min |
| Each AWS Station | `sensor.aws_<station>_wind_speed_1_min` | 1-Min Avg Wind Speed | AWS 1-min data (WS1) | `1.8` m/s | ~5 min |
| Each AWS Station | `sensor.aws_<station>_gust_direction` | Gust Direction | AWS 1-min data (WDS) | `180` ° | ~5 min |
| Each AWS Station | `sensor.aws_<station>_gust_speed` | Gust Speed | AWS 1-min data (WSS) | `6.2` m/s | ~5 min |
| Each AWS Station | `sensor.aws_<station>_wind_direction_10_min` | 10-Min Avg Wind Direction | AWS 1-min data (WD10) | `190` ° | ~5 min |
| Each AWS Station | `sensor.aws_<station>_wind_speed_10_min` | 10-Min Avg Wind Speed | AWS 1-min data (WS10) | `2.4` m/s | ~5 min |
| Each AWS Station | `sensor.aws_<station>_rain_15_min` | 15-Min Rain | AWS 1-min data (RN-15m) | `0.5` mm | ~5 min |
| Each AWS Station | `sensor.aws_<station>_rain_60_min` | 60-Min Rain | AWS 1-min data (RN-60m) | `2.0` mm | ~5 min |
| Each AWS Station | `sensor.aws_<station>_rain_12_h` | 12-Hour Rain | AWS 1-min data (RN-12H) | `8.5` mm | ~5 min |
| Each AWS Station | `sensor.aws_<station>_rain_today` | Today Rain | AWS 1-min data (RN-DAY) | `14.0` mm | ~5 min |
| Each AWS Station | `sensor.aws_<station>_station_pressure` | Station Pressure | AWS 1-min data (PA) | `1013.4` hPa | ~5 min |
| Each AWS Station | `sensor.aws_<station>_sea_level_pressure` | Sea Level Pressure | AWS 1-min data (PS) | `1015.8` hPa | ~5 min |

> Nationwide feeds (earthquake, typhoon, radar/satellite images) are fetched once centrally, then mapped per Zone device for dashboard convenience. Hub device contains system diagnostics.
>
> **Note on Image Entities**: The entity state represents the last update timestamp, while the camera/image stream delivers PNG image data. Use Home Assistant Picture Entity cards to display them on your dashboard.

---

## 🔍 Detailed Sensor Information

### One-Line Weather Summary (`one_line_summary`)
A unified text sensor formatted specifically for ESL (Electronic Shelf Labels), E-Paper displays, and dashboard subtitle badges. Formats automatically according to your Home Assistant language setting:
* English: `Clear, 19.5°C (11.0°C/26.0°C)`, `Overcast, 15.0°C (12.0°C/18.0°C), Rain expected around 16:00`
* Korean: `맑음, 19.5°C (11.0°C/26.0°C)`, `흐림, 15.0°C (12.0°C/18.0°C), 16시경 비 예보`

### 4 Life Weather Indices
Each index provides a 0–100 numerical value (`_index`) and an ENUM grade (`_grade`) with advice guidelines in attributes:
* **Laundry Drying Index**: Very Good / Good / Normal / Not Recommended
* **Car Wash Index**: Very Good / Recommend Delay / Not Recommended / Avoid
* **Freeze Risk Index**: Low / Moderate / High / Very High
* **Food Poisoning Index**: Attention / Caution / Warning / Danger

### Fine Dust (PM10)
Uses real-time 5-minute ground observations from the nearest active station.
* `pm10`: Concentration (㎍/㎥).
* `pm10_grade`: Ministry of Environment grade (Good 0–30 / Normal 31–80 / Bad 81–150 / Very Bad 151+).
* `pm10_hourly_avg`: Hourly average, minimum, and maximum statistics.
* Exposes `station_id` and `station_name` attributes so you can verify the exact monitoring location.

### Radar Precipitation Intensity & Imagery Gallery
* **Radar Intensity (dBZ)**: Reflectivity value queried by administrative zone. Categorized into 6 human-friendly levels via `radar_precipitation_grade`: None, Drizzle, Light Rain, Moderate Rain, Heavy Rain, Torrential Rain.
* **Image Entities**: 7 live PNG channels updating every ~10 minutes.

**Sample Images** (Live samples retrieved via APIhub authKey):

| `image.kma_radar_image` (Radar Composite) | `image.kma_satellite_image` (Satellite IR) |
| --- | --- |
| ![Radar Composite Sample](https://raw.githubusercontent.com/eigger/hass-kma/main/docs/images/radar_composite_sample.png) | ![Satellite IR Sample](https://raw.githubusercontent.com/eigger/hass-kma/main/docs/images/satellite_ir105_sample.png) |

| `image.kma_precipitation_forecast_image` (QPF +60min Forecast) | `image.kma_satellite_visible_image` (Satellite Visible) |
| --- | --- |
| ![Precipitation Forecast Sample](https://raw.githubusercontent.com/eigger/hass-kma/main/docs/images/precipitation_forecast_qpf_sample.png) | ![Satellite Visible Sample](https://raw.githubusercontent.com/eigger/hass-kma/main/docs/images/satellite_visible_sample.png) |

| `image.kma_satellite_shortwave_ir_image` (Satellite Shortwave IR) | `image.kma_satellite_water_vapor_image` (Satellite Water Vapor) |
| --- | --- |
| ![Satellite SWIR Sample](https://raw.githubusercontent.com/eigger/hass-kma/main/docs/images/satellite_shortwave_ir_sample.png) | ![Satellite WV Sample](https://raw.githubusercontent.com/eigger/hass-kma/main/docs/images/satellite_water_vapor_sample.png) |

### UV Index / Atmospheric Stagnation / Pollen Risk
* `uv_index` (3-hour interval) + `uv_index_grade` (Low / Moderate / High / Very High / Extreme according to WHO standards).
* `air_stagnation_index` + `air_stagnation_grade` (Numerical scale mapped to diffusion quality).
* `oak_pollen_risk` / `pine_pollen_risk` / `weed_pollen_risk`: Seasonal health indices (Oak/Pine in March–June, Weeds in August–October). Includes tomorrow and day-after-tomorrow outlooks in attributes.

### Surface Observations / Impact Forecasts / Snow Depth
* **Observed Apparent Temp** (`apparent_temperature_observed`): High-resolution multi-variable surface observation (`sfc_nc_var.php`) calculated at the exact latitude/longitude of your zone.
* **Impact Forecasts** (`heat_wave_risk` / `cold_wave_risk`): Official KMA heatwave and coldwave risk classifications.
* **Observed Snow Depth** (`snow_depth_observed`): Ground station snow measurements in cm.

### Weather Hazard Bulletins & Commentary
Official meteorological bulletins published by regional weather offices:
* **Hazard Information** (`hazard_info`): Flash bulletins for fog, thunderstorms, downpours, etc.
* **Weather Commentary** (`weather_commentary`): Comprehensive daily briefings. Dedicated fixed slots (`_section_1` to `_section_8`) allow deterministic card and automation binding.

### Earthquake & Typhoon
* **Earthquake Information** (`sensor.kma_recent_earthquake`): Details of recent domestic and major global earthquakes (magnitude, epicenter, timestamp).
* **Typhoon Tracking** (`sensor.kma_typhoon_number`): Active typhoon identifier, location coordinates, pressure, and trajectory.

### Asian Dust Satellite Imagery
GK2A satellite Asian Dust (IDI) imagery (`image.kma_dust_satellite_image`).

![Dust Satellite Sample](https://raw.githubusercontent.com/eigger/hass-kma/main/docs/images/dust_satellite_sample.png)

### AWS 1-Minute Station Telemetry (Optional)
Supports real-time 1-minute telemetry from 720 built-in ASOS/AWS/SG stations across South Korea:
* **Isolated Subentry**: Add or remove weather stations independently from your location zones.
* **Fixed 5-minute Polling**: Throttled to ~301 seconds to protect rate limits and prevent duplicate calls.
* **Resilience**: Cached observations persist across network disruptions and Home Assistant reboots until fresh data arrives (`observation_fresh` flag indicates data timeliness).

---

## 🔑 Prerequisites (KMA APIhub Registration)

To use this integration, obtain an authentication key (**authKey**) from **KMA APIhub**:

1. Register and sign in at the [KMA APIhub Portal](https://apihub.kma.go.kr/).
2. Navigate to API Search or My Page, search for the following APIs, and click **Apply for Use (활용신청)**:
    * Village Forecast (`getVilageFcst`)
    * Short-Term Land Forecast (`fct_afs_dl.php`)
    * Short-Term Marine Forecast (`fct_afs_do.php`)
    * Weather Warnings Status (`wrn_now_data.php`)
    * Forecast Region Info (`fct_shrt_reg.php`) — used for key validation
    * PM10 Observations (`kma_pm10.php`, Surface > Asian Dust PM10)
    * PM10 Hourly Statistics (`dst_pm10_hr.php`)
    * Living Weather Index Service (`LivingWthrIdxServiceV3` — `getUVIdxV3`, `getAirDiffusionIdxV3`)
    * Health Weather Index Service (`HealthWthrIdxServiceV2` — `getOakPollenRiskIdxV2`, `getPinePollenRiskIdxV2`, `getWeedsPollenRiskndxV2`)
    * Weather Radar Info Service (`WthrRadarInfoService/getCompCappiQcdArea`)
    * Radar Composite Download (`typ04/rdr_cmp_file.php`)
    * GK2A Satellite Imagery (`typ03/nph-gk2a_img`) — IR, visible, SWIR, water vapor
    * Ultra-Short-Term Precipitation Graphic (`typ03/nph-qpf_ana_img`)
    * High-Resolution Surface Observation (`sfc_nc_var.php`)
    * Impact Forecast Status (`ifs_fct_pstt.php`)
    * Snow Observation Data (`kma_snow1.php`)
    * Earthquake Notification (`typ09/eqk/urlNewNotiEqk.do`)
    * Typhoon Information (`typ_now.php`)
    * Asian Dust Satellite Imagery (`YdstInfoService/getYdstSatlitImg`)
    * **[Optional]** AWS 1-Minute Observations (`typ01/cgi-bin/url/nph-aws2_min`) — only needed if adding AWS stations.
    * Weather hazard reports (`wrn_inf_rpt.php`) and commentary (`wthr_cmt_rpt.php`) work immediately without separate application.
3. Once approved, copy your **authKey**.

### Diagnostic Sensors
The integration automatically creates diagnostic entities under the KMA APIhub device:
* `binary_sensor.kma_activation_<api>`: `on` when application is approved and responding normally; `off` if not applied (403) or errored.
* `sensor.kma_error_count_<api>`: Cumulative error count with `last_error_time` attribute.

---

<a id="installation"></a>
## ⚙️ Installation

<!-- hass-standards:installation:start -->
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=eigger&repository=hass-kma)
<!-- hass-standards:installation:end -->

### Method 1: HACS (Recommended)
1. In Home Assistant, open **HACS**.
2. Search for **KMA Weather (기상청 APIhub)** and click **Download**.
3. Restart Home Assistant.

### Method 2: Manual Installation
1. Download the latest release from the [Releases](https://github.com/eigger/hass-kma/releases) page.
2. Copy the `custom_components/kma` folder into your Home Assistant directory under `config/custom_components/`.
3. Restart Home Assistant.

---

## 🛠️ Configuration & Usage

1. In Home Assistant, go to **Settings → Devices & Services → Add Integration**.
2. Search for **KMA** or **기상청** and select it.
3. Enter your **authKey**.
4. In the integration card, click **Add Zone** to register your location. The integration automatically converts zone coordinates into KMA grid values and binds forecast areas.
5. **Add AWS Station (Optional)**: Click **Add Station** to search the built-in catalog of 720 observation stations by name, region, or station ID.
6. **Configure Options**: Click **Configure** on the integration card to adjust scan intervals (5 to 180 minutes; default: 10 minutes).

---

## 🤖 Automation Example

Send a smartphone alert whenever a severe weather warning is issued for your area:

```yaml
alias: "[Weather] KMA Severe Weather Warning Alert"
description: "Send push notification when a weather warning is issued"
trigger:
  - platform: state
    entity_id: binary_sensor.home_weather_warning  # Adjust to match your entity ID
    from: "off"
    to: "on"
condition: []
action:
  - service: notify.notify
    data:
      title: "⚠️ KMA Weather Warning Issued"
      message: >-
        {{ state_attr('binary_sensor.home_weather_warning', 'warnings_count') }} warning(s) currently active.

        Details:
        {% for w in state_attr('binary_sensor.home_weather_warning', 'active_warnings') %}
        - {{ w.region }} {{ w.warning_name }}{{ w.level_name }} (Effective: {{ w.effective_time }})
        {% endfor %}
mode: single
```

---

## 🛠️ Future Roadmap

1. **Marine Buoy Observations**: Fetch real-time wave height, water temperature, and pressure via `kma_buoy2.php` / `sea_obs.php`.
2. **Marine Sector Forecasts**: +75h sea forecasts via `marine_small_zone.php` / `marine_large_zone.php`.
3. **Impact Forecast Heat/Cold Maps**: Map graphics via `ifs_ilvl_dmap.php`.

---

## 📚 Documentation

- [User Guide](docs/user-guide.md) ([한국어](docs/ko/user-guide.md))
- [Troubleshooting](docs/troubleshooting.md) ([한국어](docs/ko/troubleshooting.md))
- [Development Guide](docs/development.md)

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
