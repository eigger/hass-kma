"""pytest 설정 — homeassistant/aiohttp 없이 단위 테스트 실행 가능하도록 mock."""
import sys
from unittest.mock import MagicMock


class _MockBase:
    """제네릭 서브클래싱(예: DataUpdateCoordinator[T])을 지원하는 기본 Mock 클래스."""

    def __init__(self, *args, **kwargs):
        pass

    def __class_getitem__(cls, item):
        return cls


class _MockUpdateFailed(Exception):
    """UpdateFailed mock — raise UpdateFailed(...) 구문을 허용."""


# homeassistant.helpers.update_coordinator
# DataUpdateCoordinator / CoordinatorEntity 는 실제로 서브클래싱되므로 _MockBase 사용
_mock_ha_coordinator = MagicMock()
_mock_ha_coordinator.DataUpdateCoordinator = _MockBase
_mock_ha_coordinator.CoordinatorEntity = _MockBase
_mock_ha_coordinator.UpdateFailed = _MockUpdateFailed
sys.modules["homeassistant.helpers.update_coordinator"] = _mock_ha_coordinator

# homeassistant 나머지 모듈 (MagicMock으로 충분)
for _mod in [
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.data_entry_flow",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.entity",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.selector",
    "homeassistant.components",
    "homeassistant.components.binary_sensor",
    "homeassistant.components.button",
    "homeassistant.components.sensor",
    "homeassistant.components.weather",
    "homeassistant.util",
    "homeassistant.util.dt",
    # aiohttp — kma has no pip requirements, HA bundles it at runtime
    "aiohttp",
]:
    sys.modules[_mod] = MagicMock()
