"""부모 엔트리 셋업의 Zone/AWS 관측소 서브엔트리 라우팅 테스트.

`__init__.async_setup_entry`가 서브엔트리 유형별로 올바른 코디네이터를 만드는지,
레거시 Zone AWS 필드를 무시하는지, Zone 없이도 AWS가 독립 동작하는지 검증한다.
코디네이터/전송은 가벼운 대역으로 대체하고 라우팅 로직만 실제로 태운다.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import custom_components.kma as kma_init
from custom_components.kma import async_setup_entry
from custom_components.kma.const import (
    CONF_AWS_STATION_ID,
    DOMAIN,
    SUBENTRY_TYPE_AWS_STATION,
    SUBENTRY_TYPE_ZONE,
)


class _FakeCoordinator:
    def __init__(self, *args, **kwargs):
        self.hub_device_id = None
        self.data = None
        self.last_update_success = True
        self.shutdown = False

    async def async_config_entry_first_refresh(self):
        return None

    async def async_shutdown(self):
        self.shutdown = True


def _install_fakes(monkeypatch):
    created = {"aws": [], "zone": []}

    class _FakeForecast(_FakeCoordinator):
        def __init__(self, hass, client, entry, subentry):
            super().__init__()
            created["zone"].append(subentry)

    class _FakeAws(_FakeCoordinator):
        def __init__(self, hass, client, entry, subentry):
            super().__init__()
            created["aws"].append(subentry)

    class _FakePlain(_FakeCoordinator):
        def __init__(self, hass, client, entry):
            super().__init__()

    monkeypatch.setattr(kma_init, "KmaForecastCoordinator", _FakeForecast)
    monkeypatch.setattr(kma_init, "KmaAwsCoordinator", _FakeAws)
    monkeypatch.setattr(kma_init, "KmaImageCoordinator", _FakePlain)
    monkeypatch.setattr(kma_init, "KmaHubCoordinator", _FakePlain)
    monkeypatch.setattr(kma_init, "async_get_clientsession", lambda hass: MagicMock())
    return created


def _entry(subentries):
    entry = SimpleNamespace(
        data={"auth_key": "TESTKEY"},
        entry_id="entry-1",
        subentries={sub.subentry_id: sub for sub in subentries},
        title="KMA",
    )
    entry.add_update_listener = lambda callback: None
    entry.async_on_unload = lambda callback: None
    return entry


def _hass():
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    return hass


def _zone(sub_id, *, aws_station_id=None):
    data = {"zone_id": "zone.home", "zone_name": "Home"}
    if aws_station_id is not None:
        data[CONF_AWS_STATION_ID] = aws_station_id
    return SimpleNamespace(
        subentry_id=sub_id, subentry_type=SUBENTRY_TYPE_ZONE, data=data
    )


def _aws(sub_id, station):
    return SimpleNamespace(
        subentry_id=sub_id,
        subentry_type=SUBENTRY_TYPE_AWS_STATION,
        data={CONF_AWS_STATION_ID: station},
    )


def test_setup_creates_aws_coordinator_from_aws_station_subentry(monkeypatch):
    created = _install_fakes(monkeypatch)
    hass = _hass()
    entry = _entry([_zone("sub-zone"), _aws("sub-aws", 108)])

    assert asyncio.run(async_setup_entry(hass, entry)) is True

    store = hass.data[DOMAIN][entry.entry_id]
    assert set(store["coordinators"]) == {"sub-zone"}
    assert set(store["aws_coordinators"]) == {"sub-aws"}
    assert [sub.subentry_id for sub in created["aws"]] == ["sub-aws"]


def test_setup_ignores_legacy_zone_aws_field(monkeypatch):
    """레거시 Zone 서브엔트리의 AWS 필드는 더 이상 코디네이터를 만들지 않는다."""
    created = _install_fakes(monkeypatch)
    hass = _hass()
    entry = _entry([_zone("sub-zone", aws_station_id=108)])

    asyncio.run(async_setup_entry(hass, entry))

    store = hass.data[DOMAIN][entry.entry_id]
    assert store["aws_coordinators"] == {}
    assert created["aws"] == []


def test_setup_creates_aws_coordinator_without_any_zone(monkeypatch):
    """AWS 관측소는 Zone이 없어도 독립적으로 셋업된다(Zone 관리와 무관)."""
    _install_fakes(monkeypatch)
    hass = _hass()
    entry = _entry([_aws("sub-aws", 400)])

    asyncio.run(async_setup_entry(hass, entry))

    store = hass.data[DOMAIN][entry.entry_id]
    assert store["coordinators"] == {}
    assert set(store["aws_coordinators"]) == {"sub-aws"}


def test_setup_creates_one_coordinator_per_aws_station(monkeypatch):
    created = _install_fakes(monkeypatch)
    hass = _hass()
    entry = _entry([_aws("sub-108", 108), _aws("sub-400", 400)])

    asyncio.run(async_setup_entry(hass, entry))

    store = hass.data[DOMAIN][entry.entry_id]
    assert set(store["aws_coordinators"]) == {"sub-108", "sub-400"}
    assert {sub.data[CONF_AWS_STATION_ID] for sub in created["aws"]} == {108, 400}


def test_setup_wires_aws_coordinators_to_hub(monkeypatch):
    """AWS 코디네이터가 허브 집계 코디네이터에 연결된다(실제 시도 결과 보고용)."""
    _install_fakes(monkeypatch)
    hass = _hass()
    entry = _entry([_aws("sub-aws", 108)])

    asyncio.run(async_setup_entry(hass, entry))

    store = hass.data[DOMAIN][entry.entry_id]
    assert store["aws_coordinators"]["sub-aws"].hub_coordinator is store["hub_coordinator"]


def test_setup_loads_saved_station_absent_from_catalog(monkeypatch):
    """카탈로그에 없는 지점번호로 저장된 서브엔트리도 그대로 로드된다."""
    created = _install_fakes(monkeypatch)
    hass = _hass()
    entry = _entry([_aws("sub-saved", 999999)])

    asyncio.run(async_setup_entry(hass, entry))

    store = hass.data[DOMAIN][entry.entry_id]
    assert set(store["aws_coordinators"]) == {"sub-saved"}
    assert created["aws"][0].data[CONF_AWS_STATION_ID] == 999999


def test_setup_skips_aws_station_subentry_with_invalid_number(monkeypatch):
    created = _install_fakes(monkeypatch)
    hass = _hass()
    bad = SimpleNamespace(
        subentry_id="sub-bad",
        subentry_type=SUBENTRY_TYPE_AWS_STATION,
        data={CONF_AWS_STATION_ID: 0},
    )
    entry = _entry([bad])

    asyncio.run(async_setup_entry(hass, entry))

    store = hass.data[DOMAIN][entry.entry_id]
    assert store["aws_coordinators"] == {}
    assert created["aws"] == []
