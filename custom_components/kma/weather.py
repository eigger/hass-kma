"""기상청(KMA) 날씨(Weather) 플랫폼 구현."""
from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform, UnitOfTemperature, UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import KmaForecastCoordinator
from .api import VillageForecast, LandForecast
from .helpers import parse_pcp

_LOGGER = logging.getLogger(__name__)


# 하늘상태 및 강수형태 기반 날씨 상태 매핑 함수
def get_ha_condition(sky: str | None, pty: str | None, is_night: bool) -> str:
    """기상청 하늘상태 및 강수형태를 홈어시스턴트 날씨 상태로 변환.

    pty 단기예보(0없음,1비,2비/눈,3눈,4소나기) + 초단기(5빗방울,6빗방울눈날림,7눈날림)
    """
    if pty == "1":
        return ATTR_CONDITION_RAINY
    elif pty == "2":
        return ATTR_CONDITION_SNOWY_RAINY
    elif pty == "3":
        return ATTR_CONDITION_SNOWY
    elif pty == "4":
        return ATTR_CONDITION_POURING
    elif pty == "5":  # 빗방울
        return ATTR_CONDITION_RAINY
    elif pty == "6":  # 빗방울/눈날림
        return ATTR_CONDITION_SNOWY_RAINY
    elif pty == "7":  # 눈날림
        return ATTR_CONDITION_SNOWY

    # pty == "0" 또는 없음인 경우 하늘상태(sky)로 매핑
    # sky: 하늘상태 (1:맑음, 3:구름많음, 4:흐림)
    if sky == "1":
        return ATTR_CONDITION_CLEAR_NIGHT if is_night else ATTR_CONDITION_SUNNY
    elif sky == "3":
        return ATTR_CONDITION_PARTLYCLOUDY
    elif sky == "4":
        return ATTR_CONDITION_CLOUDY

    return ATTR_CONDITION_CLOUDY  # 기본 폴백


def aggregate_daily_forecasts(
    village_forecasts: list[VillageForecast],
    land_forecasts: list[LandForecast]
) -> list[Forecast]:
    """시간별 단기예보 및 중기 육상예보를 병합하여 일별 예보 리스트를 생성합니다."""
    daily_forecasts: dict[str, dict[str, Any]] = {}

    # 1. 동네예보(VillageForecast) 집계 (최대 3일)
    for vf in village_forecasts:
        date_str = vf.fcst_date  # YYYYMMDD
        if date_str not in daily_forecasts:
            daily_forecasts[date_str] = {
                "temps": [],
                "pops": [],
                "pty_sky": [],
                "wind_speeds": [],
                "wind_bearings": [],
                "precips": [],
            }

        d = daily_forecasts[date_str]
        if vf.tmp is not None:
            d["temps"].append(vf.tmp)
        if vf.pop is not None:
            d["pops"].append(vf.pop)
        if vf.wsd is not None:
            d["wind_speeds"].append(vf.wsd)
        if vf.vec is not None:
            d["wind_bearings"].append(vf.vec)

        pcp_val = parse_pcp(vf.pcp)
        if pcp_val is not None:
            d["precips"].append(pcp_val)

        if vf.sky or vf.pty:
            d["pty_sky"].append((vf.fcst_time, vf.sky, vf.pty))

    # 2. 집계 결과로 Forecast 생성
    result: list[Forecast] = []

    for date_str, d in sorted(daily_forecasts.items()):
        if not d["temps"]:
            continue

        try:
            dt = datetime.datetime.strptime(date_str, "%Y%m%d")
            dt_localized = dt_util.as_utc(dt_util.as_local(dt))
            datetime_str = dt_localized.isoformat()
        except ValueError:
            continue

        t_max = max(d["temps"])
        t_min = min(d["temps"])
        pop_max = max(d["pops"]) if d["pops"] else 0.0
        precip_sum = sum(d["precips"]) if d["precips"] else 0.0
        wsd_avg = sum(d["wind_speeds"]) / len(d["wind_speeds"]) if d["wind_speeds"] else 0.0
        vec_avg = d["wind_bearings"][0] if d["wind_bearings"] else 0.0

        # 낮 시간대(0600~1800) 중 가장 빈번하거나 악천후인 상태 우선 선택
        day_pty_sky = [item for item in d["pty_sky"] if "0600" <= item[0] <= "1800"]
        if not day_pty_sky:
            day_pty_sky = d["pty_sky"]

        rep_pty = "0"
        rep_sky = "1"

        rain_snow_items = [item for item in day_pty_sky if item[2] and item[2] != "0"]
        if rain_snow_items:
            rep_pty = max(rain_snow_items, key=lambda x: int(x[2] or 0))[2]
        else:
            sky_items = [item[1] for item in day_pty_sky if item[1]]
            if sky_items:
                if "4" in sky_items:
                    rep_sky = "4"
                elif "3" in sky_items:
                    rep_sky = "3"
                else:
                    rep_sky = "1"

        cond = get_ha_condition(rep_sky, rep_pty, is_night=False)

        result.append(
            Forecast(
                datetime=datetime_str,
                condition=cond,
                native_temperature=t_max,
                native_templow=t_min,
                precipitation_probability=int(pop_max),
                native_precipitation=round(precip_sum, 1),
                native_wind_speed=round(wsd_avg, 1),
                wind_bearing=int(vec_avg),
            )
        )

    # 3. 육상예보(LandForecast) 병합 (4일차~10일차)
    existing_dates = set(daily_forecasts.keys())
    land_by_date: dict[str, list[LandForecast]] = {}
    for lf in land_forecasts:
        try:
            date_str = lf.tm_ef[:8]
            if date_str in existing_dates:
                continue
            land_by_date.setdefault(date_str, []).append(lf)
        except Exception:
            continue

    for date_str, lfs in sorted(land_by_date.items()):
        try:
            dt = datetime.datetime.strptime(date_str, "%Y%m%d")
            dt_localized = dt_util.as_utc(dt_util.as_local(dt))
            datetime_str = dt_localized.isoformat()
        except ValueError:
            continue

        temps = [lf.ta for lf in lfs if lf.ta is not None]
        t_max = max(temps) if temps else None
        t_min = min(temps) if temps else None

        pops = [lf.pop for lf in lfs if lf.pop is not None]
        pop_max = max(pops) if pops else 0

        # 대표 상태 결정 (눈/비 우선)
        rep_sky = "DB01"
        rep_prep = "0"

        for lf in lfs:
            if lf.prep and lf.prep != "0":
                rep_prep = lf.prep
                break
        else:
            skies = [lf.sky for lf in lfs if lf.sky]
            if skies:
                if "DB04" in skies:
                    rep_sky = "DB04"
                elif "DB03" in skies:
                    rep_sky = "DB03"
                else:
                    rep_sky = "DB01"

        sky_map = {"DB01": "1", "DB02": "1", "DB03": "3", "DB04": "4"}
        sky_val = sky_map.get(rep_sky, "1")

        cond = get_ha_condition(sky_val, rep_prep, is_night=False)

        result.append(
            Forecast(
                datetime=datetime_str,
                condition=cond,
                native_temperature=t_max,
                native_templow=t_min,
                precipitation_probability=int(pop_max),
            )
        )

    return result


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Zone 서브엔트리별 날씨 엔티티 추가."""
    store = hass.data[DOMAIN][entry.entry_id]
    for subentry_id, coordinator in store["coordinators"].items():
        subentry = entry.subentries[subentry_id]
        async_add_entities(
            [KmaWeather(coordinator, subentry)],
            config_subentry_id=subentry_id,
        )


class KmaWeather(CoordinatorEntity[KmaForecastCoordinator], WeatherEntity):
    """기상청 날씨 엔티티."""

    _attr_has_entity_name = False
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self, coordinator: KmaForecastCoordinator, subentry: ConfigSubentry
    ) -> None:
        """날씨 구성원 초기화."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{subentry.subentry_id}_weather"

        # 웨더 엔티티는 Zone 이름을 그대로 표시한다.
        zone_name = subentry.title or subentry.data.get("zone_name") or "KMA"
        self._attr_name = zone_name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=zone_name,
            manufacturer="Korea Meteorological Administration",
            model="KMA APIhub Forecast",
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
        )

    def _is_night(self) -> bool:
        """낮/밤 판단."""
        sun_state = self.hass.states.get("sun.sun")
        if sun_state is not None:
            return sun_state.state == "below_horizon"
        
        # sun 엔티티가 없는 경우 현재 시간 기준으로 판단 (오후 6시 ~ 오전 6시)
        now_hour = datetime.datetime.now().hour
        return now_hour < 6 or now_hour >= 18

    def _is_night_at_hour(self, hour: int) -> bool:
        """특정 시간대가 밤인지 판단 (시간별 예보용)."""
        return hour < 6 or hour >= 18

    @property
    def condition(self) -> str | None:
        """현재 기상 상태 (실황 기반)."""
        cur = self.coordinator.get_current()
        if cur.tmp is None and cur.sky is None and cur.pty is None:
            return None
        return get_ha_condition(cur.sky, cur.pty, self._is_night())

    @property
    def native_temperature(self) -> float | None:
        """현재 온도 (실황)."""
        return self.coordinator.get_current().tmp

    @property
    def humidity(self) -> float | None:
        """현재 습도 (실황)."""
        return self.coordinator.get_current().reh

    @property
    def native_wind_speed(self) -> float | None:
        """현재 풍속 (실황)."""
        return self.coordinator.get_current().wsd

    @property
    def wind_bearing(self) -> float | None:
        """현재 풍향 (실황)."""
        return self.coordinator.get_current().vec

    def _get_hourly_forecasts(self) -> list[Forecast] | None:
        """시간별 예보 생성.

        근시간(앞 6시간)은 초단기예보, 이후는 단기예보를 병합(coordinator.forecast_points).
        """
        points = self.coordinator.forecast_points()
        if not points:
            return None

        out: list[Forecast] = []
        for p in points:
            dt_localized = dt_util.as_utc(dt_util.as_local(p.dt))
            out.append(
                Forecast(
                    datetime=dt_localized.isoformat(),
                    condition=get_ha_condition(p.sky, p.pty, self._is_night_at_hour(p.dt.hour)),
                    native_temperature=p.tmp,
                    humidity=p.reh,
                    native_wind_speed=p.wsd,
                    wind_bearing=int(p.vec) if p.vec is not None else None,
                    native_precipitation=p.pcp,
                    precipitation_probability=int(p.pop) if p.pop is not None else None,
                )
            )
        return out

    def _get_daily_forecasts(self) -> list[Forecast] | None:
        """일별 예보 생성."""
        village: list[VillageForecast] = self.coordinator.data.get("village", [])
        land: list[LandForecast] = self.coordinator.data.get("land", [])
        return aggregate_daily_forecasts(village, land)

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """일별 예보 반환."""
        return self._get_daily_forecasts()

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """시간별 예보 반환."""
        return self._get_hourly_forecasts()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """추가 속성 반환 (예보요약, 특보목록)."""
        attrs = {}

        # 1. 육상예보 요약
        land = self.coordinator.data.get("land", [])
        if land:
            attrs["land_forecast_summary"] = land[0].wf
            attrs["land_forecast_release_time"] = land[0].tm_fc

        # 2. 해상예보 요약
        marine = self.coordinator.data.get("marine", [])
        if marine:
            attrs["marine_forecast_summary"] = marine[0].wf
            attrs["marine_forecast_release_time"] = marine[0].tm_fc

        # 3. 현재 지역 특보 리스트
        warnings = self.coordinator.data.get("warnings", [])
        if warnings:
            attrs["active_warnings"] = [
                {
                    "region": w.get("REG_KO"),
                    "warning": w.get("WRN"),
                    "level": w.get("LVL"),
                    "time": w.get("TM_EF"),
                }
                for w in warnings
            ]
        else:
            attrs["active_warnings"] = []

        return attrs
