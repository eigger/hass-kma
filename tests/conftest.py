"""pytest 설정 — homeassistant/aiohttp 없이 단위 테스트 실행 가능하도록 mock.

CI는 `pip install pytest voluptuous`만 하므로(Home Assistant는 설치하지 않는다),
homeassistant 패키지는 전부 모의 모듈로 대체한다. 모의를 키워드 인자를 받는 "진짜 클래스"
수준으로 올려야 하는 이유:

* `class KmaSensor(CoordinatorEntity[...], RestoreEntity, SensorEntity)`처럼
  인자를 받으며 상속해야 한다(MagicMock 인스턴스는 상속할 수 없다).
* `SensorEntityDescription(key=...)`은 필수 키를 받아야 한다(HA dataclass는 필수 필드).
* `class KmaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN)`은
  `__init_subclass__`가 `domain` 키워드를 받아야 한다.
* `native_unit_of_measurement` 같은 상수를 실제 문자열로 두어야 센서 단위를 검증할 수 있다.
"""
import sys
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import pytest


class _MockBase:
    """제네릭 서브클래싱(예: DataUpdateCoordinator[T])을 지원하는 기본 Mock 클래스."""

    def __init__(self, *args, **kwargs):
        # super().__init__ 에 넘긴 키워드( update_interval, name 등)를 테스트가
        # 검증할 수 있도록 남겨 둔다. (실제 HA 코디네이터가 여기서 저장하는 값.)
        self._mock_init_kwargs = dict(kwargs)
        # 실제 HA 는 첫 위치인자로 hass 를 받는다 — 만료콜백 예약 등에서 참조하므로
        # 모의에서도 어트리뷰트가 존재해야 한다.
        if args and not hasattr(self, "hass"):
            self.hass = args[0]
        self._shutdown_requested = False
        self._listeners: dict = {}

    def __class_getitem__(cls, item):
        return cls

    async def async_shutdown(self) -> None:
        """실제 HA DataUpdateCoordinator.async_shutdown 과 동일한 효과."""
        self._shutdown_requested = True
        self._async_unsub_refresh()
        self._listeners.clear()

    def _async_unsub_refresh(self) -> None:
        if getattr(self, "_unsub_refresh", None):
            self._unsub_refresh()
            self._unsub_refresh = None

    def async_update_listeners(self) -> None:
        for _, listener in list(self._listeners.values()):
            listener()


class _MockCoordinatorEntity(_MockBase):
    """CoordinatorEntity — 실제 HA와 동일하게 coordinator 를 보관하고 available 을 노출."""

    def __init__(self, *args, **kwargs):
        coordinator = args[0] if args else kwargs.get("coordinator")
        super().__init__(*args, **kwargs)
        self.coordinator = coordinator

    @property
    def available(self) -> bool:
        return bool(getattr(self.coordinator, "last_update_success", True))


class _MockRestoreEntity(_MockBase):
    pass


class _MockSensorEntity(_MockBase):
    pass


class _MockBinarySensorEntity(_MockBase):
    pass


class _MockWeatherEntity(_MockBase):
    pass


class _MockImageEntity(_MockBase):
    pass


class _MockUpdateFailed(Exception):
    """UpdateFailed mock — raise UpdateFailed(...) 구문을 허용."""


class _MockFlowBase:
    """ConfigFlow/ConfigSubentryFlow/OptionsFlow 공통 기반.

    `class KmaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN)`처럼
    class-creation 키워드를 받도록 __init_subclass__를 허용한다.
    """

    def __init__(self, *args, **kwargs):
        pass

    def __class_getitem__(cls, item):
        return cls

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()


class _StrNameEnum:
    """StrEnum 비슷한 모의체. 멤버 접근 시 멤버명 소문자 문자열을 돌려준다.

    HA는 SensorDeviceClass.WIND_DIRECTION -> "wind_direction" 형태라서
    소문자 변환이 실제 값과 일치한다. UNIT 처럼 값이 다른 상수는 따로 고정한다.
    """

    def __init__(self, prefix: str = ""):
        self._prefix = prefix
        self._cache: dict[str, str] = {}

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(name)
        cache = object.__getattribute__(self, "_cache")
        if name not in cache:
            cache[name] = name.lower()
        return cache[name]


class _StrNamespace:
    """키워드로 넘긴 값은 그대로, 그 외에는 멤버명 소문자 문자열을 돌려준다."""

    def __init__(self, **values: str):
        self.__dict__.update(values)

    def __getattr__(self, name: str) -> str:
        if name.startswith("__"):
            raise AttributeError(name)
        value = name.lower()
        self.__dict__[name] = value
        return value


class _IntFlag:
    """bit-flag 상수 모의체. 멤버는 서로 다른 비트, `|` 연산이 동작해야 한다.

    weather.py는 `WeatherEntityFeature.FORECAST_DAILY | ..._HOURLY`처럼
    상수를 비트 연산하므로 문자열을 돌려주면 TypeError가 난다.
    """

    def __init__(self) -> None:
        self._cache: dict[str, int] = {}

    def __getattr__(self, name: str) -> int:
        if name.startswith("__"):
            raise AttributeError(name)
        cache = object.__getattribute__(self, "_cache")
        if name not in cache:
            cache[name] = 1 << len(cache)
        return cache[name]


class _MockEntityDescription:
    """SensorEntityDescription 대체 — key는 필수, 나머지는 HA와 동일하게 기본 None."""

    def __init__(self, key: str, **kwargs: Any) -> None:
        self.key = key
        self.translation_key = kwargs.pop("translation_key", key)
        self.device_class = kwargs.pop("device_class", None)
        self.native_unit_of_measurement = kwargs.pop("native_unit_of_measurement", None)
        self.state_class = kwargs.pop("state_class", None)
        self.icon = kwargs.pop("icon", None)
        self.entity_category = kwargs.pop("entity_category", None)
        self.entity_registry_enabled_default = kwargs.pop(
            "entity_registry_enabled_default", True
        )
        self.__dict__.update(kwargs)

    def __class_getitem__(cls, item):
        return cls


class _MockDeviceInfo(dict):
    """DeviceInfo — Keyword init + dict 접근을 모두 지원."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


def _callback(func):
    """@callback 이 메서드를 MagicMock으로 바꾸지 않도록 그대로 둔다."""
    return func


def _module(name: str) -> ModuleType:
    """모의 모듈 생성 — 없는 속성은 자동으로 만들어 주는 PEP 562 __getattr__ 포함.

    MagicMock 모듈 대신 진짜 ModuleType을 쓰는 이유는 `from module import X`가
    속성 조회로 끝나게 하기 위함이다(MagicMock은 상속/인스턴스화가 불가능하다).
    """
    mod = ModuleType(name)

    def __getattr__(attr: str) -> Any:
        if attr.startswith("__"):
            raise AttributeError(attr)
        value = MagicMock(name=f"{name}.{attr}")
        setattr(mod, attr, value)
        return value

    mod.__getattr__ = __getattr__
    sys.modules[name] = mod
    return mod


# --- homeassistant.helpers.update_coordinator --------------------------------
_mock_ha_coordinator = _module("homeassistant.helpers.update_coordinator")
_mock_ha_coordinator.DataUpdateCoordinator = _MockBase
_mock_ha_coordinator.CoordinatorEntity = _MockCoordinatorEntity
_mock_ha_coordinator.UpdateFailed = _MockUpdateFailed

# --- homeassistant.helpers.event --------------------------------------------
# AWS 코디네이터의 만료 타이머를 단위 테스트에서 관찰하기 위한 mock입니다.
# 실제 타이머 대신 지연 시간·동작·취소 여부를 기록합니다.
_mock_ha_event = _module("homeassistant.helpers.event")
CALL_LATER_CALLS: list[dict[str, Any]] = []


def _async_call_later(hass: Any, delay: Any, action: Any):
    seconds = delay.total_seconds() if hasattr(delay, "total_seconds") else float(delay)
    record: dict[str, Any] = {
        "delay": seconds,
        "action": action,
        "cancelled": False,
        "hass": hass,
    }
    CALL_LATER_CALLS.append(record)

    def _cancel() -> None:
        record["cancelled"] = True

    return _cancel


_mock_ha_event.async_call_later = _async_call_later


@pytest.fixture(autouse=True)
def _reset_call_later():
    """각 테스트마다 만료콜백 예약 기록을 비운다."""
    CALL_LATER_CALLS.clear()
    yield
    CALL_LATER_CALLS.clear()


# --- homeassistant.components.image -----------------------------------------
_mock_ha_image = _module("homeassistant.components.image")
_mock_ha_image.ImageEntity = _MockImageEntity

# --- homeassistant.components.sensor ----------------------------------------
_mock_ha_sensor = _module("homeassistant.components.sensor")
_mock_ha_sensor.SensorDeviceClass = _StrNameEnum()
_mock_ha_sensor.SensorStateClass = _StrNameEnum()
_mock_ha_sensor.SensorEntity = _MockSensorEntity
_mock_ha_sensor.SensorEntityDescription = _MockEntityDescription

# --- homeassistant.components.binary_sensor / weather -----------------------
_mock_ha_binary_sensor = _module("homeassistant.components.binary_sensor")
_mock_ha_binary_sensor.BinarySensorDeviceClass = _StrNameEnum()
_mock_ha_binary_sensor.BinarySensorEntity = _MockBinarySensorEntity

_mock_ha_weather = _module("homeassistant.components.weather")
_mock_ha_weather.WeatherEntity = _MockWeatherEntity
_mock_ha_weather.WeatherEntityFeature = _IntFlag()
for _condition in (
    "ATTR_CONDITION_CLEAR_NIGHT",
    "ATTR_CONDITION_CLOUDY",
    "ATTR_CONDITION_FOG",
    "ATTR_CONDITION_HAIL",
    "ATTR_CONDITION_LIGHTNING",
    "ATTR_CONDITION_LIGHTNING_RAINY",
    "ATTR_CONDITION_PARTLYCLOUDY",
    "ATTR_CONDITION_POURING",
    "ATTR_CONDITION_RAINY",
    "ATTR_CONDITION_SNOWY",
    "ATTR_CONDITION_SNOWY_RAINY",
    "ATTR_CONDITION_SUNNY",
    "ATTR_CONDITION_WINDY",
    "ATTR_CONDITION_WINDY_VARIANT",
    "ATTR_CONDITION_EXCEPTIONAL",
):
    setattr(_mock_ha_weather, _condition, _condition.lower().removeprefix("attr_condition_"))

# --- homeassistant.config_entries -------------------------------------------
_mock_ha_config_entries = _module("homeassistant.config_entries")


class _MockConfigFlow(_MockFlowBase):
    pass


class _MockConfigSubentryFlow(_MockFlowBase):
    pass


class _MockOptionsFlow(_MockFlowBase):
    pass


_mock_ha_config_entries.ConfigFlow = _MockConfigFlow
_mock_ha_config_entries.ConfigSubentryFlow = _MockConfigSubentryFlow
_mock_ha_config_entries.OptionsFlow = _MockOptionsFlow
# 타입 힌트/실행 중 참조용 — 실제 클래스일 필요는 없다.
_mock_ha_config_entries.ConfigEntry = type("ConfigEntry", (), {})
_mock_ha_config_entries.ConfigSubentry = type("ConfigSubentry", (), {})
_mock_ha_config_entries.ConfigFlowResult = dict
_mock_ha_config_entries.SubentryFlowResult = dict

# --- homeassistant.const (실제와 같은 문자열 단위 값) -------------------------
_mock_ha_const = _module("homeassistant.const")
_mock_ha_const.PERCENTAGE = "%"
_mock_ha_const.DEGREE = "°"
_mock_ha_const.EntityCategory = _StrNamespace(DIAGNOSTIC="diagnostic")
_mock_ha_const.UnitOfTemperature = _StrNamespace(CELSIUS="°C", KELVIN="K", FAHRENHEIT="°F")
_mock_ha_const.UnitOfSpeed = _StrNamespace(
    METERS_PER_SECOND="m/s", KILOMETERS_PER_HOUR="km/h", KNOTS="kn"
)
_mock_ha_const.UnitOfLength = _StrNamespace(
    MILLIMETERS="mm", CENTIMETERS="cm", METERS="m"
)
_mock_ha_const.UnitOfPressure = _StrNamespace(
    HPA="hPa", PA="Pa", INHG="inHg", MMHG="mmHg"
)
_mock_ha_const.UnitOfDensity = _StrNamespace(
    MICROGRAMS_PER_CUBIC_METER="µg/m³", GRAMS_PER_CUBIC_METER="g/m³"
)
_mock_ha_const.UnitOfPrecipitationDepth = _StrNamespace(MILLIMETERS="mm", INCHES="in")


def _const_getattr(name: str) -> Any:
    """homeassistant.const의 그 외 상수는 값처럼 보이는 네임스페이스로 모의한다.

    `Platform.WEATHER` 처럼 잠금 인용(locked-attribute)으로 접근하는 상수가 있어
    순수 문자열을 돌려주면 AttributeError가 난다. 네임스페이스면 멤버 접근이
    "소문자 멤버명" 문자열로 풀려 실제 HA 값(Platform.WEATHER == "weather")과 같다.
    """
    if name.startswith("__"):
        raise AttributeError(name)
    value = _StrNamespace()
    _mock_ha_const.__dict__[name] = value
    return value


_mock_ha_const.__getattr__ = _const_getattr

# --- homeassistant.helpers.entity -------------------------------------------
_mock_ha_entity = _module("homeassistant.helpers.entity")
_mock_ha_entity.DeviceInfo = _MockDeviceInfo

# --- homeassistant.helpers.restore_state ------------------------------------
_mock_ha_restore_state = _module("homeassistant.helpers.restore_state")
_mock_ha_restore_state.RestoreEntity = _MockRestoreEntity

# --- homeassistant.components.diagnostics -----------------------------------
def _async_redact_data(data, keys):
    """HA async_redact_data 단순 재현 — 지정한 키의 값을 *** 로 마스킹."""
    keys = tuple(keys)

    def _walk(value):
        if isinstance(value, dict):
            return {
                k: "***" if k in keys else _walk(v) for k, v in value.items()
            }
        if isinstance(value, list):
            return [_walk(item) for item in value]
        return value

    return _walk(data)


_mock_ha_diagnostics = _module("homeassistant.components.diagnostics")
_mock_ha_diagnostics.async_redact_data = _async_redact_data

# --- 나머지 모듈 (MagicMock으로 충분) ----------------------------------------
for _mod in [
    "homeassistant",
    "homeassistant.core",
    "homeassistant.data_entry_flow",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.selector",
    "homeassistant.components",
    "homeassistant.components.button",
    "homeassistant.util",
    "homeassistant.util.dt",
    # aiohttp — kma has no pip requirements, HA bundles it at runtime
    "aiohttp",
]:
    sys.modules[_mod] = MagicMock()

sys.modules["homeassistant"].config_entries = _mock_ha_config_entries
# `from homeassistant import config_entries` 는 속성 조회로 풀리므로 명시적으로 연결한다.
sys.modules["homeassistant"].core = sys.modules["homeassistant.core"]
sys.modules["homeassistant.core"].callback = _callback
