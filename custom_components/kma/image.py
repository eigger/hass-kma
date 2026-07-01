"""기상청(KMA) 레이더/위성/강수예측 이미지(Image) 플랫폼 구현.

위성은 적외(ir105) 외에 가시광선(vi006)/단파적외(sw038)/수증기(wv069) 채널도
제공한다. 같은 nph-gk2a_img 엔드포인트를 obs 파라미터만 바꿔 호출하며(실측
검증 2026-07-02), 반대로 obs=cld/fog/dst/rgb-* 등은 전부 1KB 안팎의 "미지원"
플레이스홀더 PNG만 돌아와 실데이터가 아님을 확인했다(구현하지 않음).

레이더/위성/강수예측 이미지는 특정 Zone과 무관한 전국(한반도) 단위 자료라, 실제 페칭은
`KmaImageCoordinator`(coordinator.py) 하나가 담당한다(중복 API 호출 없음). 다만
엔티티는 허브(API Hub) 디바이스가 아니라 각 Zone 디바이스에만 배치한다 —
사용자가 허브 디바이스에는 진단성 엔티티만 보이길 원해서, 같은 캐시 바이트를
가리키는 이미지 엔티티를 Zone 디바이스 화면에서만 볼 수 있게 한다. 내용은
모든 Zone에서 동일한 한반도 전체 이미지이고, Zone 개수와 무관하게 추가 API
호출은 발생하지 않는다.

처음에는 레이더 원시 반사도 격자(nph-rdr_cmp1_api)가 PNG가 아니라 수백만 셀짜리
데이터 덤프임을 확인하고 이미지 엔티티를 제거했었으나, 이후 실제 PNG를 반환하는
별도 엔드포인트(typ04/rdr_cmp_file.php, data=img)를 확인해(2026-07-01) 다시 추가함.
sensor.py의 행정구역별 강수강도 숫자 센서(radar_precipitation)는 그대로 유지한다
— 자동화용 숫자값과 대시보드용 이미지는 서로 다른 용도라 둘 다 필요하다.

HA 공식 문서에 따르면 `image_last_updated`는 코디네이터 갱신 시점에만 바꿔야 하며
(`async_image` 내부에서 바꾸면 순환 트리거가 됨), `async_image`는 캐시된 바이트만
반환해야 한다. 따라서 바이트 캐싱과 `image_last_updated` 갱신은
`_handle_coordinator_update`에서 수행한다.

주의: `CoordinatorEntity.async_added_to_hass()`는 `_handle_coordinator_update`를
"다음 갱신부터" 호출할 리스너로만 등록하고, 엔티티가 추가되는 시점에는 즉시
호출하지 않는다. 이 통합은 부모 엔트리 셋업 시 `KmaImageCoordinator`의 최초
갱신을 먼저 끝낸 뒤에 플랫폼(엔티티)을 생성하므로, 이 동기화를 안 해주면
코디네이터에는 이미 이미지가 있는데도 엔티티는 다음 10분 주기가 올 때까지
`unavailable`(이미지·아이콘 없음)로 보이는 문제가 생긴다(실측 확인됨).
그래서 `async_added_to_hass`를 오버라이드해 초기 상태를 즉시 동기화한다.
"""
from __future__ import annotations

import logging

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import KmaImageCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Zone별 복제 레이더/위성 이미지 엔티티 추가 (허브 디바이스에는 배치하지 않음).

    페칭은 공유 KmaImageCoordinator 하나뿐이며, 여기서는 같은 캐시 바이트를
    가리키는 엔티티를 각 Zone 디바이스에 나눠 배치할 뿐이다.
    """
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator: KmaImageCoordinator = store["image_coordinator"]

    for subentry_id in store.get("coordinators", {}):
        subentry = entry.subentries[subentry_id]
        zone_name = subentry.title or subentry.data.get("zone_name") or "KMA"
        zone_device = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=zone_name,
            manufacturer="Korea Meteorological Administration",
            model="KMA APIhub Forecast",
            via_device=(DOMAIN, entry.entry_id),
        )
        async_add_entities(
            [
                entity_cls(
                    hass, coordinator,
                    unique_id=f"{subentry_id}_{entity_cls._attr_translation_key}",
                    device_info=zone_device,
                )
                for entity_cls in _IMAGE_ENTITY_CLASSES
            ],
            config_subentry_id=subentry_id,
        )


class _KmaBaseImage(CoordinatorEntity[KmaImageCoordinator], ImageEntity):
    """레이더/위성/강수예측 공통 베이스: 지정된 디바이스 + coordinator.data[_data_key]에서 바이트 캐싱."""

    _attr_has_entity_name = True
    _data_key = ""  # 서브클래스에서 "radar"/"satellite"/"precipitation_forecast"로 지정

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: KmaImageCoordinator,
        *,
        unique_id: str,
        device_info: DeviceInfo,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._last_bytes: bytes | None = None
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        return super().available and self._last_bytes is not None

    async def async_added_to_hass(self) -> None:
        """엔티티 추가 시점에 코디네이터가 이미 들고 있는 데이터로 즉시 동기화.

        CoordinatorEntity는 _handle_coordinator_update를 향후 갱신에 대한
        리스너로만 등록하고 즉시 호출하지 않으므로, 여기서 한 번 직접 호출해
        최초 갱신 결과를 곧바로 반영한다.
        """
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        """코디네이터 갱신 시점에만 바이트/갱신시각을 반영 (async_image에서는 반영 금지)."""
        img = (self.coordinator.data or {}).get(self._data_key)
        if img is not None and img.data != self._last_bytes:
            self._last_bytes = img.data
            self.content_type = img.content_type
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """캐시된 최신 이미지 바이트를 반환."""
        return self._last_bytes


class KmaRadarImage(_KmaBaseImage):
    """레이더 합성영상(강수강도) 최신 이미지. [실측 검증 2026-07-01]"""

    _attr_translation_key = "radar_image"
    _data_key = "radar"


class KmaSatelliteImage(_KmaBaseImage):
    """위성(GK2A) 적외 최신 이미지. [실측 검증 2026-07-01]"""

    _attr_translation_key = "satellite_image"
    _data_key = "satellite"


class KmaPrecipitationForecastImage(_KmaBaseImage):
    """초단기 강수예측(QPF, 60분 뒤) 이미지. [실측 검증 2026-07-02]"""

    _attr_translation_key = "precipitation_forecast_image"
    _data_key = "precipitation_forecast"


class KmaSatelliteVisibleImage(_KmaBaseImage):
    """위성(GK2A) 가시광선(vi006) 최신 이미지, 야간에는 관측되지 않음. [실측 검증 2026-07-02]"""

    _attr_translation_key = "satellite_visible_image"
    _data_key = "satellite_visible"


class KmaSatelliteShortwaveIrImage(_KmaBaseImage):
    """위성(GK2A) 단파적외(sw038) 최신 이미지, 야간 안개/하층운 탐지에 사용. [실측 검증 2026-07-02]"""

    _attr_translation_key = "satellite_shortwave_ir_image"
    _data_key = "satellite_shortwave_ir"


class KmaSatelliteWaterVaporImage(_KmaBaseImage):
    """위성(GK2A) 수증기(wv069) 최신 이미지. [실측 검증 2026-07-02]"""

    _attr_translation_key = "satellite_water_vapor_image"
    _data_key = "satellite_water_vapor"


_IMAGE_ENTITY_CLASSES = (
    KmaRadarImage,
    KmaSatelliteImage,
    KmaPrecipitationForecastImage,
    KmaSatelliteVisibleImage,
    KmaSatelliteShortwaveIrImage,
    KmaSatelliteWaterVaporImage,
)
