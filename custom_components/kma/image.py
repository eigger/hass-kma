"""기상청(KMA) 레이더/위성 이미지(Image) 플랫폼 구현.

레이더/위성 이미지는 Zone과 무관한 전국 단위 자료이므로 허브(부모 엔트리) 디바이스에
배정하고, `KmaImageCoordinator`(coordinator.py)를 사용한다.

처음에는 레이더 원시 반사도 격자(nph-rdr_cmp1_api)가 PNG가 아니라 수백만 셀짜리
데이터 덤프임을 확인하고 이미지 엔티티를 제거했었으나, 이후 실제 PNG를 반환하는
별도 엔드포인트(typ04/rdr_cmp_file.php, data=img)를 확인해(2026-07-01) 다시 추가함.
sensor.py의 행정구역별 강수강도 숫자 센서(radar_precipitation)는 그대로 유지한다
— 자동화용 숫자값과 대시보드용 이미지는 서로 다른 용도라 둘 다 필요하다.

HA 공식 문서에 따르면 `image_last_updated`는 코디네이터 갱신 시점에만 바꿔야 하며
(`async_image` 내부에서 바꾸면 순환 트리거가 됨), `async_image`는 캐시된 바이트만
반환해야 한다. 따라서 바이트 캐싱과 `image_last_updated` 갱신은
`_handle_coordinator_update`에서 수행한다.
"""
from __future__ import annotations

import logging

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
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
    """허브 단위 레이더/위성 이미지 엔티티 추가 (Zone 무관)."""
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator: KmaImageCoordinator = store["image_coordinator"]
    async_add_entities(
        [
            KmaRadarImage(hass, coordinator, entry),
            KmaSatelliteImage(hass, coordinator, entry),
        ]
    )


class _KmaBaseImage(CoordinatorEntity[KmaImageCoordinator], ImageEntity):
    """레이더/위성 공통 베이스: 허브 디바이스 + coordinator.data[_data_key]에서 바이트 캐싱."""

    _attr_has_entity_name = True
    _data_key = ""  # 서브클래스에서 "radar"/"satellite"로 지정

    def __init__(
        self, hass: HomeAssistant, coordinator: KmaImageCoordinator, entry: ConfigEntry
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._entry = entry
        self._last_bytes: bytes | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="기상청 APIhub",
            manufacturer="Korea Meteorological Administration",
            model="API Hub",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        return super().available and self._last_bytes is not None

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

    def __init__(
        self, hass: HomeAssistant, coordinator: KmaImageCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(hass, coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_radar_image"


class KmaSatelliteImage(_KmaBaseImage):
    """위성(GK2A) 적외 최신 이미지. [실측 검증 2026-07-01]"""

    _attr_translation_key = "satellite_image"
    _data_key = "satellite"

    def __init__(
        self, hass: HomeAssistant, coordinator: KmaImageCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(hass, coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_satellite_image"
