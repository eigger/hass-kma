"""AWS API 상태의 허브 집계 + 실제 시도만 기록 검증."""
from __future__ import annotations

import asyncio
import datetime
from unittest.mock import MagicMock

from conftest import make_aws_observation as _obs
from custom_components.kma.api import KmaActivationRequiredError, KmaApiError
from custom_components.kma.const import CONF_AWS_STATION_ID
from custom_components.kma.coordinator import KmaAwsCoordinator, KmaHubCoordinator

_KST = datetime.timezone(datetime.timedelta(hours=9))
T0 = datetime.datetime(2026, 7, 3, 14, 31, tzinfo=_KST)


class _HubClient:
    async def async_get_earthquake_recent(self):
        return None

    async def async_get_typhoon_now(self, *, tm=None):
        return None


def _hub() -> KmaHubCoordinator:
    return KmaHubCoordinator(MagicMock(), _HubClient(), MagicMock())


class _HubRecorder:
    def __init__(self) -> None:
        self.attempts: list[tuple[int, str]] = []
        self.forgotten: list[int] = []

    def record_aws_attempt(self, station: int, status: str) -> None:
        self.attempts.append((station, status))

    def forget_aws_station(self, station: int) -> None:
        self.forgotten.append(station)


class _AwsClient:
    def __init__(self, *, result=None, error=None) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    async def async_get_aws_observation(self, *, stn: int):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def _aws_coordinator(client, *, station: int = 108) -> KmaAwsCoordinator:
    subentry = MagicMock()
    subentry.data = {CONF_AWS_STATION_ID: station}
    coordinator = KmaAwsCoordinator(MagicMock(), client, MagicMock(), subentry)
    coordinator._now = lambda: T0
    return coordinator


def _update(coordinator: KmaAwsCoordinator) -> dict:
    data = asyncio.run(coordinator._async_update_data())
    coordinator.data = data
    return data


# --- 허브 집계 -------------------------------------------------------------


def test_hub_aggregates_worst_status_across_stations() -> None:
    hub = _hub()
    hub.record_aws_attempt(108, "ok")
    hub.record_aws_attempt(400, "error: boom")

    # B 실패는 A 성공으로 지워지지 않는다(최악값 집계).
    assert hub.api_status["aws"] == "error: boom"
    assert hub.api_error_counts["aws"] == 1
    assert hub.api_last_error_times["aws"] is not None


def test_hub_activation_not_applied_aggregation() -> None:
    hub = _hub()
    hub.record_aws_attempt(108, "ok")
    hub.record_aws_attempt(400, "not_applied")

    assert hub.api_status["aws"] == "not_applied"
    # not_applied 는 에러 카운트를 올리지 않는다(기존 진단 의미와 동일).
    assert hub.api_error_counts["aws"] == 0


def test_hub_recovers_only_when_all_stations_recover() -> None:
    hub = _hub()
    hub.record_aws_attempt(108, "ok")
    hub.record_aws_attempt(400, "error: boom")
    assert hub.api_status["aws"] == "error: boom"

    hub.record_aws_attempt(400, "ok")
    assert hub.api_status["aws"] == "ok"

    hub.record_aws_attempt(108, "error: x")
    assert hub.api_status["aws"] == "error: x"


def test_hub_refresh_preserves_aws_and_does_not_double_count() -> None:
    hub = _hub()
    hub.record_aws_attempt(400, "error: boom")
    assert hub.api_error_counts["aws"] == 1

    # 허브 자체 갱신(지진/태풍)은 AWS 상태를 덮어쓰거나 다시 세지 않는다.
    asyncio.run(hub._async_update_data())

    assert hub.api_status["aws"] == "error: boom"
    assert hub.api_error_counts["aws"] == 1


def test_hub_forget_station_removes_it_from_aggregate() -> None:
    hub = _hub()
    hub.record_aws_attempt(108, "ok")
    hub.record_aws_attempt(400, "error: boom")
    hub.forget_aws_station(400)

    assert hub.api_status["aws"] == "ok"
    # 누적 카운트는 유지된다(집계 상태만 바뀐다).
    assert hub.api_error_counts["aws"] == 1


def test_hub_omits_aws_key_without_stations() -> None:
    """AWS 관측소 상태가 없으면 'aws' 키를 넣지 않는다(미사용 API를 ok로 표시 금지)."""
    hub = _hub()
    assert "aws" not in hub.api_status

    # 허브 자체 갱신(지진/태풍) 뒤에도 여전히 없다.
    asyncio.run(hub._async_update_data())
    assert "aws" not in hub.api_status


def test_hub_forget_last_station_omits_key_and_keeps_count() -> None:
    hub = _hub()
    hub.record_aws_attempt(108, "error: AWS 관측 자료 조회 실패")
    assert hub.api_status["aws"].startswith("error:")
    assert hub.api_error_counts["aws"] == 1

    hub.forget_aws_station(108)

    assert "aws" not in hub.api_status  # 마지막 관측소 제거 → 키 생략
    assert hub.api_error_counts["aws"] == 1  # 누적 카운트는 유지


# --- AWS 코디네이터의 실제 시도만 보고 -------------------------------------


def test_aws_coordinator_publishes_only_actual_attempts() -> None:
    coordinator = _aws_coordinator(_AwsClient(result=_obs()))
    hub = _HubRecorder()
    coordinator.hub_coordinator = hub

    _update(coordinator)
    assert hub.attempts == [(108, "ok")]

    # 5분 이내 스로틀(캐시) 갱신 → 보고 없음.
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=1)
    _update(coordinator)
    assert hub.attempts == [(108, "ok")]



def test_aws_coordinator_publishes_failure_and_recovery() -> None:
    client = _AwsClient(result=_obs())
    coordinator = _aws_coordinator(client)
    hub = _HubRecorder()
    coordinator.hub_coordinator = hub

    _update(coordinator)
    assert hub.attempts == [(108, "ok")]

    client.error = KmaApiError("boom")
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=6)
    _update(coordinator)
    assert hub.attempts[-1][0] == 108 and hub.attempts[-1][1].startswith("error:")

    client.error = None
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=12)
    _update(coordinator)
    assert hub.attempts[-1] == (108, "ok")


def test_aws_coordinator_publishes_brief_error_summary_only() -> None:
    """허브에는 URL/토큰 없는 짧은 요약만, 관측소 자체 상태는 상세(redacted) 유지."""
    coordinator = _aws_coordinator(
        _AwsClient(
            error=KmaApiError(
                "https://apihub.kma.go.kr/x?authKey=SECRET boom"
            )
        )
    )
    hub = _HubRecorder()
    coordinator.hub_coordinator = hub

    data = _update(coordinator)

    assert hub.attempts == [(108, "error: AWS 관측 자료 조회 실패")]
    summary = hub.attempts[0][1]
    assert "http" not in summary and "authKey" not in summary
    assert "nph-aws2_min" not in summary

    # 관측소 자체 상태는 상세(문제 해결용)하게 유지하고 토큰은 마스킹한다.
    assert data["status"].startswith("error:")
    assert "boom" in data["status"] and "apihub" in data["status"]
    assert "SECRET" not in data["status"]


def test_aws_coordinator_publishes_activation_not_applied() -> None:
    coordinator = _aws_coordinator(
        _AwsClient(error=KmaActivationRequiredError("ep", "msg"))
    )
    hub = _HubRecorder()
    coordinator.hub_coordinator = hub

    _update(coordinator)
    assert hub.attempts == [(108, "not_applied")]


def test_aws_coordinator_does_not_publish_after_shutdown() -> None:
    coordinator = _aws_coordinator(_AwsClient(result=_obs()))
    hub = _HubRecorder()
    coordinator.hub_coordinator = hub
    coordinator._shutdown = True
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=6)

    _update(coordinator)
    assert hub.attempts == []


def test_aws_coordinator_forgets_station_on_shutdown() -> None:
    coordinator = _aws_coordinator(_AwsClient(result=_obs()))
    hub = _HubRecorder()
    coordinator.hub_coordinator = hub

    asyncio.run(coordinator.async_shutdown())
    assert hub.forgotten == [108]
