"""기상청(KMA) 센서(Sensor) 플랫폼 구현."""
from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfSpeed,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import API_STATUS_HUB_KEYS, API_STATUS_IMAGE_KEYS, API_STATUS_ZONE_KEYS, DOMAIN
from .coordinator import CurrentWeather, KmaForecastCoordinator, KmaHubCoordinator, KmaImageCoordinator
from .api import VillageForecast
from .weather import get_ha_condition
from .helpers import (
    parse_pcp,
    get_pm10_grade,
    get_discomfort_grade,
    get_laundry_grade,
    get_car_wash_grade,
    get_freeze_risk_grade,
    get_food_poisoning_grade,
    get_uv_index_grade,
    get_air_stagnation_grade,
    get_pollen_risk_grade,
    get_impact_risk_grade,
)

_LOGGER = logging.getLogger(__name__)

# 빨래/세차/동파/식중독 지수의 등급(good/normal/...)은 helpers.get_*_grade()로 분류하고
# HA의 SensorDeviceClass.ENUM 상태 번역(translations/*.json의 state.*)으로 표시한다.
# 아래 사전들은 등급별 "추천 문구"(자유 텍스트, ENUM 상태로 표현 불가)만 보관한다.
LAUNDRY_RECS_KO = {
    "excellent": "야외 건조를 강력히 추천합니다.",
    "good": "빨래를 야외에 널기 좋습니다.",
    "normal": "빨래가 느리게 마릅니다. 실내 건조나 건조기 사용을 권장합니다.",
    "avoid": "빨래가 잘 마르지 않거나 냄새가 날 수 있습니다. 건조기 사용을 추천합니다.",
}
LAUNDRY_RECS_EN = {
    "excellent": "Hanging laundry outside is highly recommended.",
    "good": "Good day to dry laundry outside.",
    "normal": "Laundry will dry slowly. Indoor drying or dryer is recommended.",
    "avoid": "Laundry will dry very slowly. Using a dryer is highly recommended.",
}

CAR_WASH_RECS_KO = {
    "excellent": "향후 3일간 비 예보가 없어 세차하기 아주 좋은 날입니다!",
    "delay": "모레 비 소식이 있어 세차를 보류하는 것을 권장합니다.",
    "caution": "내일 비 소식이 있습니다. 오늘 세차는 피하세요.",
    "avoid": "24시간 이내 비 예보가 있어 세차를 금지합니다.",
}
CAR_WASH_RECS_EN = {
    "excellent": "No rain forecast for the next 3 days. Perfect time to wash your car!",
    "delay": "Rain is expected in 2 days. It is recommended to delay washing.",
    "caution": "Rain is expected tomorrow. Avoid washing today.",
    "avoid": "Rain is expected within 24 hours. Do not wash your car.",
}

FREEZE_RISK_RECS_KO = {
    "low": "동파 위험이 없습니다.",
    "normal": "동파 가능성이 있습니다. 노출된 계량기 등을 보온해 주세요.",
    "high": "동파 위험이 높습니다. 장시간 외출 시 온수 온도를 낮춰 물을 약간 흘려보내세요.",
    "very_high": "동파 위험이 매우 높습니다. 계량기 동파 방지를 위해 적극적인 예방이 필요합니다.",
}
FREEZE_RISK_RECS_EN = {
    "low": "No freeze risk.",
    "normal": "Freeze risk is moderate. Protect exposed water meters.",
    "high": "Freeze risk is high. Let faucets drip warm water during long outings.",
    "very_high": "Freeze risk is very high. Active pipe and meter protection is required.",
}

FOOD_POISON_RECS_KO = {
    "safe": "식중독 지수가 낮습니다. 일상적인 위생 관리를 유지해 주세요.",
    "caution": "식중독균이 발생하기 쉽습니다. 조리 음식을 실온에 오래 두지 마세요.",
    "warning": "식중독 발생 가능성이 높습니다. 조리 후 신속히 섭취하시고 주방 청결을 유지하세요.",
    "danger": "식중독 발생 위험이 매우 높습니다. 식품 취급 및 개인 위생에 각별히 유의하세요.",
}
FOOD_POISON_RECS_EN = {
    "safe": "Food poisoning risk is low. Maintain normal hygiene.",
    "caution": "Food poisoning bacteria can easily grow. Do not leave food at room temp for long.",
    "warning": "Food poisoning risk is high. Consume food quickly and keep kitchen clean.",
    "danger": "Food poisoning risk is very high. Pay extreme attention to food handling and hygiene.",
}

# 날씨 상태 다국어 표시용 사전
CONDITION_MAP_KO = {
    "sunny": "맑음",
    "clear-night": "맑음(밤)",
    "cloudy": "흐림",
    "partlycloudy": "구름많음",
    "rainy": "비",
    "pouring": "호우",
    "snowy": "눈",
    "snowy-rainy": "비/눈",
    "windy": "바람",
    "fog": "안개",
    "hail": "우박",
    "lightning": "번개",
    "lightning-rainy": "뇌우",
    "exceptional": "특이기상",
}

CONDITION_MAP_EN = {
    "sunny": "Sunny",
    "clear-night": "Clear",
    "cloudy": "Cloudy",
    "partlycloudy": "Partly Cloudy",
    "rainy": "Rainy",
    "pouring": "Heavy Rain",
    "snowy": "Snowy",
    "snowy-rainy": "Sleet",
    "windy": "Windy",
    "fog": "Foggy",
    "hail": "Hail",
    "lightning": "Lightning",
    "lightning-rainy": "Stormy",
    "exceptional": "Exceptional",
}



# KMA 센서 디스크립션 리스트
SENSOR_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="land_forecast_summary",
        translation_key="land_forecast_summary",
        icon="mdi:text-box-outline",
    ),
    SensorEntityDescription(
        key="marine_forecast_summary",
        translation_key="marine_forecast_summary",
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="wind_speed",
        translation_key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="precipitation_probability",
        translation_key="precipitation_probability",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="precipitation",
        translation_key="precipitation",
        icon="mdi:weather-rainy",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="snowfall",
        translation_key="snowfall",
        icon="mdi:weather-snowy",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="today_temp_low",
        translation_key="today_temp_low",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="today_temp_high",
        translation_key="today_temp_high",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="rain_snow_expected",
        translation_key="rain_snow_expected",
        icon="mdi:weather-snowy-rainy",
    ),
    SensorEntityDescription(
        key="precipitation_start",
        translation_key="precipitation_start",
        icon="mdi:weather-pouring",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="apparent_temperature",
        translation_key="apparent_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="dew_point",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="discomfort_index",
        translation_key="discomfort_index",
        icon="mdi:emoticon-neutral-outline",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="discomfort_grade",
        translation_key="discomfort_grade",
        device_class=SensorDeviceClass.ENUM,
        options=["low", "normal", "high", "very_high"],
        icon="mdi:emoticon-neutral-outline",
    ),
    SensorEntityDescription(
        key="laundry_index",
        translation_key="laundry_index",
        icon="mdi:tshirt-crew-outline",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="laundry_grade",
        translation_key="laundry_grade",
        device_class=SensorDeviceClass.ENUM,
        options=["excellent", "good", "normal", "avoid"],
        icon="mdi:tshirt-crew-outline",
    ),
    SensorEntityDescription(
        key="car_wash_index",
        translation_key="car_wash_index",
        icon="mdi:car-wash",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="car_wash_grade",
        translation_key="car_wash_grade",
        device_class=SensorDeviceClass.ENUM,
        options=["excellent", "delay", "caution", "avoid"],
        icon="mdi:car-wash",
    ),
    SensorEntityDescription(
        key="freeze_risk_index",
        translation_key="freeze_risk_index",
        icon="mdi:snowflake-alert",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="freeze_risk_grade",
        translation_key="freeze_risk_grade",
        device_class=SensorDeviceClass.ENUM,
        options=["low", "normal", "high", "very_high"],
        icon="mdi:snowflake-alert",
    ),
    SensorEntityDescription(
        key="food_poisoning_index",
        translation_key="food_poisoning_index",
        icon="mdi:food-off-outline",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="food_poisoning_grade",
        translation_key="food_poisoning_grade",
        device_class=SensorDeviceClass.ENUM,
        options=["safe", "caution", "warning", "danger"],
        icon="mdi:food-off-outline",
    ),
    SensorEntityDescription(
        key="one_line_summary",
        translation_key="one_line_summary",
        icon="mdi:card-text-outline",
    ),
    SensorEntityDescription(
        key="pm10",
        translation_key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm10_grade",
        translation_key="pm10_grade",
        device_class=SensorDeviceClass.ENUM,
        options=["good", "moderate", "unhealthy", "very_unhealthy"],
        icon="mdi:blur",
    ),
    SensorEntityDescription(
        key="uv_index",
        translation_key="uv_index",
        icon="mdi:weather-sunny-alert",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="uv_index_grade",
        translation_key="uv_index_grade",
        device_class=SensorDeviceClass.ENUM,
        options=["low", "moderate", "high", "very_high", "extreme"],
        icon="mdi:weather-sunny-alert",
    ),
    SensorEntityDescription(
        key="air_stagnation_index",
        translation_key="air_stagnation_index",
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="air_stagnation_grade",
        translation_key="air_stagnation_grade",
        device_class=SensorDeviceClass.ENUM,
        options=["low", "moderate", "high", "very_high"],
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="oak_pollen_risk",
        translation_key="oak_pollen_risk",
        icon="mdi:flower-pollen",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="oak_pollen_risk_grade",
        translation_key="oak_pollen_risk_grade",
        device_class=SensorDeviceClass.ENUM,
        options=["low", "moderate", "high", "very_high"],
        icon="mdi:flower-pollen",
    ),
    SensorEntityDescription(
        key="pine_pollen_risk",
        translation_key="pine_pollen_risk",
        icon="mdi:flower-pollen",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pine_pollen_risk_grade",
        translation_key="pine_pollen_risk_grade",
        device_class=SensorDeviceClass.ENUM,
        options=["low", "moderate", "high", "very_high"],
        icon="mdi:flower-pollen",
    ),
    SensorEntityDescription(
        key="weed_pollen_risk",
        translation_key="weed_pollen_risk",
        icon="mdi:flower-pollen-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="weed_pollen_risk_grade",
        translation_key="weed_pollen_risk_grade",
        device_class=SensorDeviceClass.ENUM,
        options=["low", "moderate", "high", "very_high"],
        icon="mdi:flower-pollen-outline",
    ),
    SensorEntityDescription(
        key="radar_precipitation",
        translation_key="radar_precipitation",
        icon="mdi:radar",
        native_unit_of_measurement="dBZ",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="apparent_temperature_observed",
        translation_key="apparent_temperature_observed",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="heat_wave_risk",
        translation_key="heat_wave_risk",
        device_class=SensorDeviceClass.ENUM,
        options=["none", "concern", "caution", "warning", "danger"],
        icon="mdi:sun-thermometer",
    ),
    SensorEntityDescription(
        key="cold_wave_risk",
        translation_key="cold_wave_risk",
        device_class=SensorDeviceClass.ENUM,
        options=["none", "concern", "caution", "warning", "danger"],
        icon="mdi:snowflake-thermometer",
    ),
    SensorEntityDescription(
        key="hazard_info",
        translation_key="hazard_info",
        icon="mdi:alert-outline",
    ),
    SensorEntityDescription(
        key="weather_commentary",
        translation_key="weather_commentary",
        icon="mdi:text-long",
    ),
    SensorEntityDescription(
        key="snow_depth_observed",
        translation_key="snow_depth_observed",
        icon="mdi:snowflake",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm10_hourly_avg",
        translation_key="pm10_hourly_avg",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Zone 서브엔트리별 센서 + 허브 단위 API 에러 카운트 센서 추가."""
    store = hass.data[DOMAIN][entry.entry_id]
    coordinators = store["coordinators"]
    hub_coordinator: KmaHubCoordinator | None = store.get("hub_coordinator")

    for subentry_id, coordinator in coordinators.items():
        subentry = entry.subentries[subentry_id]
        zone_name = subentry.title or subentry.data.get("zone_name") or "KMA"
        zone_device = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=zone_name,
            manufacturer="Korea Meteorological Administration",
            model="KMA APIhub Forecast",
            via_device=(DOMAIN, entry.entry_id),
        )
        zone_entities: list[SensorEntity] = [
            *[KmaSensor(coordinator, subentry, desc) for desc in SENSOR_DESCRIPTIONS],
            KmaCurrentDataSourceSensor(coordinator, subentry),
        ]
        # 지진/태풍은 Zone과 무관한 허브 데이터라 실제 페칭은 hub_coordinator
        # 하나뿐이지만, 이미지 엔티티와 같은 이유로 각 Zone 디바이스에 복제 배치한다
        # (허브 디바이스에는 진단성 엔티티만 남긴다).
        if hub_coordinator is not None:
            zone_entities += [
                KmaEarthquakeSensor(
                    hub_coordinator, unique_id=f"{subentry_id}_recent_earthquake", device_info=zone_device,
                ),
                KmaTyphoonSensor(
                    hub_coordinator, unique_id=f"{subentry_id}_typhoon_status", device_info=zone_device,
                ),
            ]
        async_add_entities(zone_entities, config_subentry_id=subentry_id)

    # 허브(통합) 기기: API별 에러 카운트 진단 센서.
    # Zone별 예·특보 API는 대표(첫) Zone 코디네이터, Zone 무관 이미지/허브 데이터
    # API는 각각 공유 image_coordinator/hub_coordinator에 연결한다. 새 API를
    # 추가할 때는 const.py의 API_STATUS_ZONE_KEYS/API_STATUS_IMAGE_KEYS/
    # API_STATUS_HUB_KEYS에 key만 추가하면 여기서 자동으로 에러 카운트 센서가 생성된다.
    entities: list[KmaApiErrorCountSensor] = []
    if coordinators:
        rep_coordinator = next(iter(coordinators.values()))
        entities += [
            KmaApiErrorCountSensor(rep_coordinator, entry, key)
            for key in API_STATUS_ZONE_KEYS
        ]
    image_coordinator: KmaImageCoordinator | None = store.get("image_coordinator")
    if image_coordinator is not None:
        entities += [
            KmaApiErrorCountSensor(image_coordinator, entry, key)
            for key in API_STATUS_IMAGE_KEYS
        ]
    if hub_coordinator is not None:
        entities += [
            KmaApiErrorCountSensor(hub_coordinator, entry, key)
            for key in API_STATUS_HUB_KEYS
        ]
    if entities:
        async_add_entities(entities)


class KmaSensor(CoordinatorEntity[KmaForecastCoordinator], SensorEntity):
    """기상청 센서 엔티티."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KmaForecastCoordinator,
        subentry: ConfigSubentry,
        description: SensorEntityDescription,
    ) -> None:
        """센서 구성원 초기화."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{subentry.subentry_id}_{description.key}"

        zone_name = subentry.title or subentry.data.get("zone_name") or "KMA"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=zone_name,
            manufacturer="Korea Meteorological Administration",
            model="KMA APIhub Forecast",
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
        )

    def _get_current_forecast(self) -> VillageForecast | None:
        """현재 시각에 가장 인접한 동네예보 레코드를 반환."""
        village: list[VillageForecast] = self.coordinator.data.get("village", [])
        if not village:
            return None

        now = datetime.datetime.now()
        closest = None
        min_diff = None

        for f in village:
            try:
                f_dt = datetime.datetime.strptime(f"{f.fcst_date}{f.fcst_time}", "%Y%m%d%H%M")
                diff = abs((f_dt - now).total_seconds())
                if min_diff is None or diff < min_diff:
                    min_diff = diff
                    closest = f
            except ValueError:
                continue

        return closest or village[0]

    def _compute_discomfort_index(self, curr: CurrentWeather) -> float | None:
        """불쾌지수 계산. `discomfort_index`/`discomfort_grade` 둘 다에서 재사용."""
        if curr.tmp is None or curr.reh is None:
            return None
        try:
            temp = float(curr.tmp)
            rh = float(curr.reh)
            di = 1.8 * temp - 0.55 * (1.0 - rh / 100.0) * (1.8 * temp - 26.0) + 32.0
            return round(di, 1)
        except (ValueError, TypeError):
            return None

    def _compute_laundry_index(
        self, curr: CurrentWeather, village: list[VillageForecast], now: datetime.datetime
    ) -> int | None:
        """빨래 건조 지수 계산. `laundry_index`/`laundry_grade` 둘 다에서 재사용."""
        if curr.tmp is None or curr.reh is None or curr.wsd is None:
            return None
        try:
            temp = float(curr.tmp)
            rh = float(curr.reh)
            ws = float(curr.wsd)
            sky = int(curr.sky) if curr.sky else 1

            # Scan next 12 hours for rain
            rain_expected = False
            for f in village:
                try:
                    f_dt = datetime.datetime.strptime(f"{f.fcst_date}{f.fcst_time}", "%Y%m%d%H%M")
                    if f_dt < now - datetime.timedelta(hours=1):
                        continue
                    diff_hours = (f_dt - now).total_seconds() / 3600.0
                    if 0.0 <= diff_hours <= 12.0:
                        if f.pty and f.pty != "0":
                            rain_expected = True
                            break
                except ValueError:
                    continue

            if rain_expected:
                return 10

            # Score calculation
            h_fact = 100.0 - rh
            w_fact = min(ws * 5.0, 20.0)
            s_fact = 30.0 if sky == 1 else 20.0 if sky == 3 else 10.0
            t_fact = max(0.0, temp * 0.5)
            score = min(100.0, h_fact + w_fact + s_fact + t_fact)
            return int(round(score))
        except (ValueError, TypeError):
            return None

    def _compute_car_wash_index(
        self, village: list[VillageForecast], now: datetime.datetime
    ) -> int:
        """세차 지수 계산. `car_wash_index`/`car_wash_grade` 둘 다에서 재사용."""
        rain_hours = None
        for f in village:
            try:
                f_dt = datetime.datetime.strptime(f"{f.fcst_date}{f.fcst_time}", "%Y%m%d%H%M")
                if f_dt < now - datetime.timedelta(hours=1):
                    continue
                diff_hours = (f_dt - now).total_seconds() / 3600.0
                if 0.0 <= diff_hours <= 72.0:
                    if f.pty and f.pty != "0":
                        rain_hours = diff_hours
                        break
            except ValueError:
                continue

        if rain_hours is not None:
            if rain_hours <= 24.0:
                return 10
            if rain_hours <= 48.0:
                return 40
            return 60
        return 90

    def _compute_freeze_risk_index(
        self, village: list[VillageForecast], now: datetime.datetime
    ) -> int | None:
        """동파 가능 지수 계산. `freeze_risk_index`/`freeze_risk_grade` 둘 다에서 재사용."""
        min_temp = None
        for f in village:
            try:
                f_dt = datetime.datetime.strptime(f"{f.fcst_date}{f.fcst_time}", "%Y%m%d%H%M")
                if f_dt < now - datetime.timedelta(hours=1):
                    continue
                diff_hours = (f_dt - now).total_seconds() / 3600.0
                if 0.0 <= diff_hours <= 48.0 and f.tmp is not None:
                    val = float(f.tmp)
                    if min_temp is None or val < min_temp:
                        min_temp = val
            except ValueError:
                continue

        if min_temp is None:
            return None
        if min_temp > -5.0:
            return 10
        if min_temp > -10.0:
            return 40
        if min_temp > -15.0:
            return 70
        return 100

    def _compute_food_poisoning_index(self, curr: CurrentWeather) -> int | None:
        """식중독 지수 계산. `food_poisoning_index`/`food_poisoning_grade` 둘 다에서 재사용."""
        if curr.tmp is None or curr.reh is None:
            return None
        try:
            temp = float(curr.tmp)
            rh = float(curr.reh)
            fpi = 0.000189 * temp * rh + 0.215 * temp + 0.161 * rh - 2.85
            score = max(0.0, min(100.0, fpi))
            return int(round(score))
        except (ValueError, TypeError):
            return None

    @property
    def native_value(self) -> Any:
        """센서의 상태값."""
        data = self.coordinator.data
        key = self.entity_description.key
        now = datetime.datetime.now()

        if key == "land_forecast_summary":
            land = data.get("land", [])
            return land[0].wf if land else None

        if key == "marine_forecast_summary":
            marine = data.get("marine", [])
            return marine[0].wf if marine else None

        if key == "pm10":
            pm10 = data.get("pm10")
            return pm10.pm10 if pm10 is not None else None

        if key == "pm10_grade":
            pm10 = data.get("pm10")
            return get_pm10_grade(pm10.pm10) if pm10 is not None else None

        if key == "uv_index":
            uv = data.get("uv_index")
            return uv.current if uv is not None else None

        if key == "uv_index_grade":
            uv = data.get("uv_index")
            return get_uv_index_grade(uv.current) if uv is not None else None

        if key == "air_stagnation_index":
            air = data.get("air_stagnation")
            return air.current if air is not None else None

        if key == "air_stagnation_grade":
            air = data.get("air_stagnation")
            return get_air_stagnation_grade(air.current) if air is not None else None

        if key in (
            "oak_pollen_risk", "oak_pollen_risk_grade",
            "pine_pollen_risk", "pine_pollen_risk_grade",
            "weed_pollen_risk", "weed_pollen_risk_grade",
        ):
            data_key = key.replace("_risk_grade", "").replace("_risk", "")
            pollen = data.get(data_key)
            if pollen is None:
                return None
            return (
                get_pollen_risk_grade(pollen.today) if key.endswith("_grade") else pollen.today
            )

        if key == "radar_precipitation":
            radar = data.get("radar_precipitation")
            return radar.value if radar is not None else None

        if key == "apparent_temperature_observed":
            sfc = data.get("sfc_observation")
            return sfc.apparent_temperature if sfc is not None else None

        if key in ("heat_wave_risk", "cold_wave_risk"):
            risk = data.get(key)
            return get_impact_risk_grade(risk.level) if risk is not None else None

        if key in ("hazard_info", "weather_commentary"):
            bulletin = data.get(key)
            return bulletin.title[:255] if bulletin is not None else None

        if key == "snow_depth_observed":
            snow = data.get("snow_depth")
            return snow.depth if snow is not None else None

        if key == "pm10_hourly_avg":
            hourly = data.get("pm10_hourly")
            return hourly.avg if hourly is not None else None

        if key == "precipitation_start":
            nxt = self.coordinator.next_precipitation()
            return dt_util.as_local(nxt.dt) if nxt is not None else None

        # 오늘 최고/최저 기온 및 비/눈 탐색용 데이터
        village = data.get("village", [])
        now = datetime.datetime.now()
        today_str = now.strftime("%Y%m%d")

        if key in ("today_temp_low", "today_temp_high"):
            today_temps = [f.tmp for f in village if f.fcst_date == today_str and f.tmp is not None]
            if key == "today_temp_low":
                return min(today_temps) if today_temps else None
            if key == "today_temp_high":
                return max(today_temps) if today_temps else None

        if key == "rain_snow_expected":
            rain_type = "none"
            for f in village:
                try:
                    f_dt = datetime.datetime.strptime(f"{f.fcst_date}{f.fcst_time}", "%Y%m%d%H%M")
                    if f_dt < now - datetime.timedelta(hours=1):
                        continue
                    if (f_dt - now).total_seconds() > 24 * 3600:
                        break
                    if f.pty and f.pty != "0":
                        if f.pty == "1":
                            rain_type = "rain"
                        elif f.pty == "2":
                            rain_type = "rain_snow"
                        elif f.pty == "3":
                            rain_type = "snow"
                        elif f.pty == "4":
                            rain_type = "shower"
                        break
                except ValueError:
                    continue
            return rain_type

        # 현재값 센서: 초단기실황(실측) 우선, 없으면 단기예보 폴백
        curr = self.coordinator.get_current()

        if key == "temperature":
            return curr.tmp
        if key == "humidity":
            return curr.reh
        if key == "wind_speed":
            return curr.wsd
        if key == "precipitation_probability":
            return curr.pop
        if key == "precipitation":
            return curr.pcp
        if key == "snowfall":
            return curr.sno

        if key == "apparent_temperature":
            import math
            if curr.tmp is not None and curr.reh is not None and curr.wsd is not None:
                try:
                    temp = float(curr.tmp)
                    rh = float(curr.reh)
                    ws = float(curr.wsd)
                    e = (rh / 100.0) * 6.105 * math.exp((17.27 * temp) / (237.7 + temp))
                    apparent = temp + 0.33 * e - 0.70 * ws - 4.00
                    return round(apparent, 1)
                except (ValueError, TypeError):
                    return None
            return None

        if key == "dew_point":
            import math
            if curr.tmp is not None and curr.reh is not None:
                try:
                    temp = float(curr.tmp)
                    rh = float(curr.reh)
                    if rh > 0:
                        gamma = (17.27 * temp) / (237.7 + temp) + math.log(rh / 100.0)
                        if 17.27 - gamma != 0:
                            dew_point = (237.7 * gamma) / (17.27 - gamma)
                            return round(dew_point, 1)
                except (ValueError, TypeError):
                    return None
            return None

        if key == "discomfort_index":
            return self._compute_discomfort_index(curr)
        if key == "discomfort_grade":
            return get_discomfort_grade(self._compute_discomfort_index(curr))

        if key == "laundry_index":
            return self._compute_laundry_index(curr, data.get("village", []), now)
        if key == "laundry_grade":
            return get_laundry_grade(
                self._compute_laundry_index(curr, data.get("village", []), now)
            )

        if key == "car_wash_index":
            return self._compute_car_wash_index(data.get("village", []), now)
        if key == "car_wash_grade":
            return get_car_wash_grade(
                self._compute_car_wash_index(data.get("village", []), now)
            )

        if key == "freeze_risk_index":
            return self._compute_freeze_risk_index(data.get("village", []), now)
        if key == "freeze_risk_grade":
            return get_freeze_risk_grade(
                self._compute_freeze_risk_index(data.get("village", []), now)
            )

        if key == "food_poisoning_index":
            return self._compute_food_poisoning_index(curr)
        if key == "food_poisoning_grade":
            return get_food_poisoning_grade(self._compute_food_poisoning_index(curr))

        if key == "one_line_summary":
            if curr.tmp is not None:
                try:
                    # Determine language
                    lang = "en"
                    if self.hass and hasattr(self.hass, "config") and self.hass.config.language == "ko":
                        lang = "ko"

                    is_night = False
                    if self.hass:
                        sun_state = self.hass.states.get("sun.sun")
                        if sun_state is not None:
                            is_night = (sun_state.state == "below_horizon")
                        else:
                            now_hour = now.hour
                            is_night = (now_hour < 6 or now_hour >= 18)
                    else:
                        now_hour = now.hour
                        is_night = (now_hour < 6 or now_hour >= 18)

                    cond = get_ha_condition(curr.sky, curr.pty, is_night)
                    
                    if lang == "ko":
                        cond_str = CONDITION_MAP_KO.get(cond, "흐림")
                    else:
                        cond_str = CONDITION_MAP_EN.get(cond, "Cloudy")

                    cur_temp = float(curr.tmp)
                    
                    # Today min/max temps
                    today_temps = [f.tmp for f in village if f.fcst_date == today_str and f.tmp is not None]
                    t_low = min(today_temps) if today_temps else cur_temp
                    t_high = max(today_temps) if today_temps else cur_temp

                    # Rain expected in 24 hours search
                    rain_time = None
                    rain_pty = None
                    for f in village:
                        try:
                            f_dt = datetime.datetime.strptime(f"{f.fcst_date}{f.fcst_time}", "%Y%m%d%H%M")
                            if f_dt < now - datetime.timedelta(hours=1):
                                continue
                            diff_hours = (f_dt - now).total_seconds() / 3600.0
                            if 0.0 <= diff_hours <= 24.0:
                                if f.pty and f.pty != "0":
                                    rain_time = f_dt
                                    rain_pty = f.pty
                                    break
                        except ValueError:
                            continue

                    rain_str = ""
                    if rain_time is not None:
                        # 0:없음, 1:비, 2:비/눈, 3:눈, 4:소나기
                        pty_names_ko = {"1": "비", "2": "비/눈", "3": "눈", "4": "소나기"}
                        pty_names_en = {"1": "Rain", "2": "Rain/Snow", "3": "Snow", "4": "Shower"}
                        
                        expected_hour = rain_time.hour
                        if lang == "ko":
                            pty_name = pty_names_ko.get(rain_pty, "비")
                            time_diff = (rain_time - now).total_seconds() / 3600.0
                            if time_diff <= 3.0:
                                rain_str = f" | 곧 {pty_name} 예보"
                            else:
                                rain_str = f" | {expected_hour}시경 {pty_name} 예보"
                        else:
                            pty_name = pty_names_en.get(rain_pty, "Rain")
                            time_diff = (rain_time - now).total_seconds() / 3600.0
                            if time_diff <= 3.0:
                                rain_str = f" | {pty_name} expected soon"
                            else:
                                rain_str = f" | {pty_name} expected around {expected_hour:02d}:00"

                    if lang == "ko":
                        summary = f"{cond_str} | 현재 {cur_temp}°C | 오늘 {t_low}°C ~ {t_high}°C{rain_str}"
                    else:
                        summary = f"{cond_str} | Cur: {cur_temp}°C | Min: {t_low}°C, Max: {t_high}°C{rain_str}"
                    return summary
                except Exception as err:
                    _LOGGER.error("한 줄 기상 요약 생성 오류: %s", err)
                    return None
            return None

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """센서 추가 속성 반환."""
        data = self.coordinator.data
        key = self.entity_description.key

        if key == "land_forecast_summary":
            land = data.get("land", [])
            if land:
                return {
                    "release_time": land[0].tm_fc,
                    "region_id": land[0].reg_id,
                    "forecast_time": land[0].tm_ef,
                }

        if key == "marine_forecast_summary":
            marine = data.get("marine", [])
            if marine:
                return {
                    "release_time": marine[0].tm_fc,
                    "region_id": marine[0].reg_id,
                    "forecast_time": marine[0].tm_ef,
                    "wave_height_min": marine[0].wh_min,
                    "wave_height_max": marine[0].wh_max,
                }

        if key in ("pm10", "pm10_grade"):
            pm10 = data.get("pm10")
            if pm10 is not None:
                return {
                    "station_id": pm10.stn,
                    "observed_time": pm10.tm,
                    "raw": pm10.raw,
                }
            return None

        if key in ("uv_index", "uv_index_grade"):
            uv = data.get("uv_index")
            if uv is not None:
                return {"area_no": uv.area_no, "announced": uv.date, "hourly": uv.hourly}
            return None

        if key in ("air_stagnation_index", "air_stagnation_grade"):
            air = data.get("air_stagnation")
            if air is not None:
                return {"area_no": air.area_no, "announced": air.date, "hourly": air.hourly}
            return None

        if key in (
            "oak_pollen_risk", "oak_pollen_risk_grade",
            "pine_pollen_risk", "pine_pollen_risk_grade",
            "weed_pollen_risk", "weed_pollen_risk_grade",
        ):
            data_key = key.replace("_risk_grade", "").replace("_risk", "")
            pollen = data.get(data_key)
            if pollen is not None:
                return {
                    "area_no": pollen.area_no,
                    "announced": pollen.date,
                    "tomorrow": pollen.tomorrow,
                    "day_after_tomorrow": pollen.day_after_tomorrow,
                }
            return None

        if key == "radar_precipitation":
            radar = data.get("radar_precipitation")
            if radar is not None:
                return {
                    "dong_code": radar.dong_code,
                    "observed_time": radar.date_time,
                    "lon": radar.lon,
                    "lat": radar.lat,
                }
            return None

        if key == "apparent_temperature_observed":
            sfc = data.get("sfc_observation")
            if sfc is not None:
                return {
                    "observed_time": sfc.tm,
                    "temperature": sfc.temperature,
                    "dew_point": sfc.dew_point,
                    "humidity": sfc.humidity,
                    "wind_speed": sfc.wind_speed,
                }
            return None

        if key in ("heat_wave_risk", "cold_wave_risk"):
            risk = data.get(key)
            if risk is not None:
                return {"level": risk.level, "announced": risk.tm_fc}
            return None

        if key in ("hazard_info", "weather_commentary"):
            bulletin = data.get(key)
            if bulletin is not None:
                return {"issued_at": bulletin.issued_at, "body": bulletin.body}
            return None

        if key == "snow_depth_observed":
            snow = data.get("snow_depth")
            if snow is not None:
                return {"observed_time": snow.tm}
            return None

        if key == "pm10_hourly_avg":
            hourly = data.get("pm10_hourly")
            if hourly is not None:
                return {"observed_time": hourly.tm, "min": hourly.min, "max": hourly.max}
            return None

        if key == "precipitation_start":
            nxt = self.coordinator.next_precipitation()
            if nxt is None:
                return {"expected": False}
            hours = round(
                (nxt.dt - datetime.datetime.now()).total_seconds() / 3600.0, 1
            )
            pty_names = {
                "1": "비", "2": "비/눈", "3": "눈", "4": "소나기",
                "5": "빗방울", "6": "빗방울/눈날림", "7": "눈날림",
            }
            return {
                "expected": True,
                "type": pty_names.get(nxt.pty, "강수"),
                "type_code": nxt.pty,
                "precipitation_probability": nxt.pop,
                "precipitation_amount": nxt.pcp,
                "snow_amount": nxt.sno,
                "hours_until": hours,
            }

        # 비/눈 예보 상세 속성
        if key == "rain_snow_expected":
            village = data.get("village", [])
            now = datetime.datetime.now()
            rain_start_dt = None
            pty_code = "0"
            pop = None
            pcp = None

            rain_3h = False
            rain_6h = False
            rain_12h = False

            for f in village:
                try:
                    f_dt = datetime.datetime.strptime(f"{f.fcst_date}{f.fcst_time}", "%Y%m%d%H%M")
                    if f_dt < now - datetime.timedelta(hours=1):
                        continue
                    diff_hours = (f_dt - now).total_seconds() / 3600.0
                    
                    if f.pty and f.pty != "0":
                        if -1.0 <= diff_hours <= 3.0:
                            rain_3h = True
                        if -1.0 <= diff_hours <= 6.0:
                            rain_6h = True
                        if -1.0 <= diff_hours <= 12.0:
                            rain_12h = True
                        
                        if rain_start_dt is None and diff_hours >= -1.0 and diff_hours <= 24.0:
                            rain_start_dt = f_dt
                            pty_code = f.pty
                            pop = f.pop
                            pcp = f.pcp
                except ValueError:
                    continue

            attrs = {
                "rain_expected_3h": rain_3h,
                "rain_expected_6h": rain_6h,
                "rain_expected_12h": rain_12h,
            }

            if rain_start_dt is not None:
                from homeassistant.util import dt as dt_util
                dt_localized = dt_util.as_utc(dt_util.as_local(rain_start_dt))
                iso_time = dt_localized.isoformat()

                attrs.update({
                    "expected_time": iso_time,
                    "pty_code": pty_code,
                    "precipitation_probability": pop,
                    "precipitation_amount": parse_pcp(pcp),
                })
            else:
                attrs.update({
                    "expected_time": None,
                    "pty_code": "0",
                    "precipitation_probability": None,
                    "precipitation_amount": 0.0,
                })
            return attrs

        # 동네예보 기반 속성
        if key in (
            "temperature",
            "humidity",
            "wind_speed",
            "precipitation_probability",
            "precipitation",
            "snowfall",
            "today_temp_low",
            "today_temp_high",
            "apparent_temperature",
            "dew_point",
            "discomfort_index",
            "discomfort_grade",
            "laundry_index",
            "laundry_grade",
            "car_wash_index",
            "car_wash_grade",
            "freeze_risk_index",
            "freeze_risk_grade",
            "food_poisoning_index",
            "food_poisoning_grade",
            "one_line_summary",
        ):
            curr = self._get_current_forecast()
            if curr:
                attrs = {
                    "fcst_date": curr.fcst_date,
                    "fcst_time": curr.fcst_time,
                }

                # Determine language
                lang = "en"
                if self.hass and hasattr(self.hass, "config") and self.hass.config.language == "ko":
                    lang = "ko"

                # 등급(grade) 표시는 각각의 전용 _grade ENUM 센서(HA 상태 번역)가 담당하므로
                # 여기서는 ENUM으로 표현할 수 없는 자유 텍스트 "recommendation"만 채운다.
                if key == "laundry_index":
                    grade_key = get_laundry_grade(self.native_value)
                    if grade_key is not None:
                        attrs["recommendation"] = (
                            LAUNDRY_RECS_KO[grade_key] if lang == "ko" else LAUNDRY_RECS_EN[grade_key]
                        )

                elif key == "car_wash_index":
                    grade_key = get_car_wash_grade(self.native_value)
                    if grade_key is not None:
                        attrs["recommendation"] = (
                            CAR_WASH_RECS_KO[grade_key] if lang == "ko" else CAR_WASH_RECS_EN[grade_key]
                        )

                elif key == "freeze_risk_index":
                    grade_key = get_freeze_risk_grade(self.native_value)
                    if grade_key is not None:
                        attrs["recommendation"] = (
                            FREEZE_RISK_RECS_KO[grade_key] if lang == "ko" else FREEZE_RISK_RECS_EN[grade_key]
                        )

                elif key == "food_poisoning_index":
                    grade_key = get_food_poisoning_grade(self.native_value)
                    if grade_key is not None:
                        attrs["recommendation"] = (
                            FOOD_POISON_RECS_KO[grade_key] if lang == "ko" else FOOD_POISON_RECS_EN[grade_key]
                        )

                return attrs

        return None


class KmaCurrentDataSourceSensor(CoordinatorEntity[KmaForecastCoordinator], SensorEntity):
    """현재값이 초단기실황/동네예보 중 어디서 왔는지 표시하는 진단 센서."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["ncst", "village", "none"]
    _attr_translation_key = "current_data_source"
    _attr_icon = "mdi:database-search"

    def __init__(
        self, coordinator: KmaForecastCoordinator, subentry: ConfigSubentry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{subentry.subentry_id}_current_data_source"
        zone_name = subentry.title or subentry.data.get("zone_name") or "KMA"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=zone_name,
            manufacturer="Korea Meteorological Administration",
            model="KMA APIhub Forecast",
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
        )

    @property
    def native_value(self) -> str:
        return self.coordinator.get_current().source

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "ncst_available": data.get("ncst") is not None,
            "ultra_fcst_records": len(data.get("ultra") or []),
            "village_forecast_records": len(data.get("village") or []),
            **self.coordinator.refresh_meta,
        }


class _KmaHubSensorBase(CoordinatorEntity[KmaHubCoordinator], SensorEntity):
    """지진/태풍처럼 Zone과 무관한 허브 데이터를 Zone 디바이스에 복제 표시하는 공통 베이스.

    image.py의 _KmaBaseImage와 동일한 이유(허브 디바이스에는 진단성 엔티티만
    두고 싶다는 사용자 요청)로 Zone 디바이스에만 배치한다. 실제 페칭은
    KmaHubCoordinator 하나뿐이며 여기서는 같은 데이터를 가리키는 엔티티를
    Zone마다 나눠 배치할 뿐이다.
    """

    _attr_has_entity_name = True
    _data_key = ""  # 서브클래스에서 "earthquake"/"typhoon"으로 지정

    def __init__(
        self,
        coordinator: KmaHubCoordinator,
        *,
        unique_id: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info


class KmaEarthquakeSensor(_KmaHubSensorBase):
    """최근 지진정보. [실측 검증 2026-07-02]

    state는 규모(매그니튜드)이며, 위치/발생시각 등은 속성으로 제공한다.
    """

    _attr_translation_key = "recent_earthquake"
    _attr_icon = "mdi:pulse"
    _data_key = "earthquake"

    @property
    def native_value(self) -> float | None:
        eq = (self.coordinator.data or {}).get(self._data_key)
        return eq.magnitude if eq is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        eq = (self.coordinator.data or {}).get(self._data_key)
        if eq is None:
            return {}
        return {
            "location": eq.location,
            "occurred_at": eq.occurred_at,
            "issued_at": eq.issued_at,
            "domestic": eq.domestic,
            "depth_km": eq.depth,
            "msg_code": eq.msg_code,
            "reference": eq.reference,
        }


class KmaTyphoonSensor(_KmaHubSensorBase):
    """태풍정보(현재 상태). [실측 검증 2026-07-02]

    state는 태풍번호(활성 태풍 없으면 0)이며, 위치/기압/풍속 등은 속성으로 제공한다.
    """

    _attr_translation_key = "typhoon_status"
    _attr_icon = "mdi:weather-hurricane"
    _data_key = "typhoon"

    @property
    def native_value(self) -> int:
        typhoon = (self.coordinator.data or {}).get(self._data_key)
        return typhoon.typ_no if typhoon is not None else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        typhoon = (self.coordinator.data or {}).get(self._data_key)
        if typhoon is None:
            return {}
        return {
            "year": typhoon.year,
            "lat": typhoon.lat,
            "lon": typhoon.lon,
            "direction": typhoon.direction,
            "speed_kmh": typhoon.speed,
            "pressure_hpa": typhoon.pressure,
            "wind_speed_ms": typhoon.wind_speed,
            "location": typhoon.location,
            "analyzed_at": typhoon.typ_tm,
        }


class KmaApiErrorCountSensor(
    CoordinatorEntity[KmaForecastCoordinator | KmaImageCoordinator | KmaHubCoordinator], SensorEntity
):
    """허브 단위 API별 누적 에러 카운트 진단 센서.

    UpdateFailed 상태에서도 카운터를 표시해야 하므로 available 를 항상 True로 유지.
    Zone별 예·특보/이미지/허브 코디네이터 모두 api_error_counts를 제공하므로
    (coordinator.py의 _ApiStatusMixin) 어느 쪽이든 그대로 연결할 수 있다.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(
        self,
        coordinator: KmaForecastCoordinator | KmaImageCoordinator | KmaHubCoordinator,
        entry: ConfigEntry,
        api_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._api_key = api_key
        self._attr_translation_key = f"error_count_{api_key}"
        self._attr_unique_id = f"{entry.entry_id}_error_count_{api_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="기상청 APIhub",
            manufacturer="Korea Meteorological Administration",
            model="API Hub",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """에러 카운터는 코디네이터 상태와 무관하게 항상 표시."""
        return True

    @property
    def native_value(self) -> int:
        return self.coordinator.api_error_counts.get(self._api_key, 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        last_time = self.coordinator.api_last_error_times.get(self._api_key)
        return {
            "last_error_time": (
                dt_util.as_local(last_time).isoformat() if last_time is not None else None
            ),
            "current_status": self.coordinator.api_status.get(self._api_key, "unknown"),
        }
