"""KmaAwsCoordinator 단위 테스트 — 스로틀/오류 격리/신선도."""
from __future__ import annotations

import asyncio
import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.kma.api import (
    AwsObservation,
    KmaActivationRequiredError,
    KmaApiError,
)
from conftest import CALL_LATER_CALLS, make_aws_observation as _obs
from custom_components.kma.const import (
    API_STATUS_HUB_KEYS,
    API_STATUS_IMAGE_KEYS,
    API_STATUS_ZONE_KEYS,
    AWS_ATTEMPT_INTERVAL_MINUTES,
    AWS_FUTURE_TOLERANCE_MINUTES,
    AWS_MAX_OBSERVATION_AGE_MINUTES,
    AWS_POLL_INTERVAL_SECONDS,
)
from custom_components.kma.coordinator import KmaAwsCoordinator

_KST = datetime.timezone(datetime.timedelta(hours=9))
T0 = datetime.datetime(2026, 7, 3, 14, 31, tzinfo=_KST)


class _Client:
    """AWS 클라이언트 대역 — 호출 횟수와 결과/오류를 조작할 수 있다."""

    def __init__(self) -> None:
        self.calls = 0
        self.result: AwsObservation | None = _obs()
        self.error: Exception | None = None

    async def async_get_aws_observation(self, *, stn: int, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _coordinator(client, station: int | None = 108) -> KmaAwsCoordinator:
    data = {} if station is None else {"aws_station_id": station}
    subentry = SimpleNamespace(subentry_id="sub-1", data=data)
    coordinator = KmaAwsCoordinator(MagicMock(), client, MagicMock(), subentry)
    coordinator._now = lambda: T0  # type: ignore[method-assign]
    return coordinator


def _update(coordinator: KmaAwsCoordinator) -> dict:
    """_async_update_data 실행 후 실제 HA DataUpdateCoordinator가 하듯 data 를 저장.

    (모의 코디네이터는 저장을 하지 않으므로 여기서 대신 수행한다.)
    """
    data = asyncio.run(coordinator._async_update_data())
    coordinator.data = data
    coordinator.last_update_success = True
    return data


def test_aws_coordinator_requires_an_opt_in_station_id() -> None:
    with pytest.raises(KeyError):
        _coordinator(_Client(), station=None)


def test_success_records_snapshot_and_status() -> None:
    client = _Client()
    coordinator = _coordinator(client)

    data = _update(coordinator)

    assert client.calls == 1
    assert data["status"] == "ok"
    assert data["station_id"] == 108
    assert data["observation"] is client.result
    assert data["last_attempt"] == T0
    assert data["last_success"] == T0
    assert data["error_count"] == 0
    assert data["last_error"] is None
    assert coordinator.aws_status == "ok"
    assert coordinator.aws_observation is client.result


def test_failure_is_swallowed_and_keeps_last_snapshot() -> None:
    client = _Client()
    coordinator = _coordinator(client)
    _update(coordinator)

    client.error = KmaApiError("500 server error")
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=6)  # type: ignore[method-assign]

    data = _update(coordinator)

    # 예외가 밖으로 새지 않는다(예보 코디네이터/셋업을 깨지 않기 위해).
    assert data["status"].startswith("error: ")
    assert "500 server error" in data["last_error"]
    assert data["error_count"] == 1
    assert data["last_error_time"] == T0 + datetime.timedelta(minutes=6)
    # 실패 시 이전 스냅샷은 유지한다.
    assert data["observation"] is client.result


def test_unexpected_success_payload_never_raises() -> None:
    """정상 응답이라도 잘못된 구조면 예외 대신 error 상태로 남긴다."""
    client = _Client()
    coordinator = _coordinator(client)
    _update(coordinator)

    client.result = object()  # observed_at 이 없는 값
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=6)  # type: ignore[method-assign]
    data = _update(coordinator)

    assert data["status"].startswith("error: ")
    assert data["error_count"] == 1
    # 이전 스냅샷은 그대로 남는다.
    assert data["observation"] is not None
    assert data["observation"] is not client.result


def test_activation_required_reports_not_applied() -> None:
    client = _Client()
    client.error = KmaActivationRequiredError("nph-aws2_min", "403 Forbidden")
    coordinator = _coordinator(client)

    data = _update(coordinator)

    assert data["status"] == "not_applied"
    assert data["error_count"] == 1
    assert data["observation"] is None


def test_auth_key_is_redacted_from_status_and_error() -> None:
    client = _Client()
    client.error = KmaApiError("403 authKey=TOPSECRET123 rejected")
    coordinator = _coordinator(client)

    data = _update(coordinator)

    assert "TOPSECRET123" not in data["status"]
    assert "TOPSECRET123" not in data["last_error"]
    assert "authKey=***" in data["status"]


def test_network_attempts_are_throttled_for_five_minutes() -> None:
    client = _Client()
    coordinator = _coordinator(client)

    _update(coordinator)
    assert client.calls == 1

    # 4분 뒤 — 시도하지 않는다(성공했어도 마찬가지).
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=4)  # type: ignore[method-assign]
    data = _update(coordinator)
    assert client.calls == 1
    assert data["last_attempt"] == T0

    # 정확히 5분 뒤 — 시도한다.
    coordinator._now = lambda: T0 + datetime.timedelta(  # type: ignore[method-assign]
        minutes=AWS_ATTEMPT_INTERVAL_MINUTES
    )
    _update(coordinator)
    assert client.calls == 2


def test_throttle_applies_to_failures_and_manual_refreshes() -> None:
    client = _Client()
    client.error = KmaApiError("boom")
    coordinator = _coordinator(client)

    _update(coordinator)
    assert client.calls == 1

    # 실패 직후 수동 갱신/예약 갱신이 들어와도 5분 안에는 재시도하지 않는다.
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=4)  # type: ignore[method-assign]
    data = _update(coordinator)
    assert client.calls == 1
    assert data["error_count"] == 1


def test_last_success_is_tracked_separately_from_last_attempt() -> None:
    client = _Client()
    coordinator = _coordinator(client)
    _update(coordinator)

    client.error = KmaApiError("boom")
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=6)  # type: ignore[method-assign]
    data = _update(coordinator)

    assert data["last_attempt"] == T0 + datetime.timedelta(minutes=6)
    # 실패가 아니라 성공했을 때만 last_success 가 갱신된다.
    assert data["last_success"] == T0


@pytest.mark.parametrize(
    "delta_minutes,expected",
    [
        (-AWS_FUTURE_TOLERANCE_MINUTES - 1, False),
        (-AWS_FUTURE_TOLERANCE_MINUTES, True),
        (-3, True),
        (0, True),
        # 상한은 엄격히 미만 — 정확히 15분 경과는 신선하지 않다.
        (AWS_MAX_OBSERVATION_AGE_MINUTES, False),
        (AWS_MAX_OBSERVATION_AGE_MINUTES + 1, False),
        (20, False),
    ],
)
def test_freshness_is_evaluated_against_current_time(delta_minutes, expected) -> None:
    client = _Client()
    coordinator = _coordinator(client)
    coordinator.data = {"observation": _obs()}

    coordinator._now = lambda: T0 + datetime.timedelta(  # type: ignore[method-assign]
        minutes=delta_minutes
    )

    assert coordinator.aws_observation_fresh is expected


def test_stale_snapshot_is_retained_but_not_reported_fresh() -> None:
    client = _Client()
    coordinator = _coordinator(client)
    _update(coordinator)
    assert coordinator.aws_observation_fresh is True

    client.error = KmaApiError("network down")
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=25)  # type: ignore[method-assign]
    data = _update(coordinator)

    # 스냅샷 자체는 남아 있으나, 신선도 판정은 오류와 무관하게 매번 다시 계산된다.
    assert data["observation"] is not None
    assert coordinator.aws_observation_fresh is False


def test_older_observation_does_not_replace_newer_one() -> None:
    client = _Client()
    coordinator = _coordinator(client)
    client.result = _obs(observed_at=T0, tm="202607031431")
    _update(coordinator)

    client.result = _obs(
        observed_at=T0 - datetime.timedelta(minutes=5), tm="202607031426"
    )
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=6)  # type: ignore[method-assign]
    data = _update(coordinator)

    assert data["status"] == "ok"
    assert data["observation"].tm == "202607031431"
    # 조회 자체는 성공했으므로 성공 시각은 갱신된다.
    assert data["last_success"] == T0 + datetime.timedelta(minutes=6)


def test_newer_observation_replaces_older_one_and_fills_no_fields() -> None:
    client = _Client()
    coordinator = _coordinator(client)
    client.result = _obs(observed_at=T0, tm="202607031431")
    _update(coordinator)

    newer = _obs(observed_at=T0 + datetime.timedelta(minutes=1), tm="202607031432")
    newer = AwsObservation(**{**newer.__dict__, "temperature": None})
    client.result = newer
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=6)  # type: ignore[method-assign]
    data = _update(coordinator)

    assert data["observation"].tm == "202607031432"
    # 이전 스냅샷의 기온으로 채우지 않는다 — 스냅샷을 통째로 교체한다.
    assert data["observation"].temperature is None


def test_aws_is_kept_out_of_shared_api_status_keys() -> None:
    """AWS 는 API_STATUS_* 목록에 없어야 한다.

    있으면 AWS 미설정 Zone에도 항상 꺼진 activation_*/error_count_* 진단 엔티티가
    생기기 때문이다(AWS 상태는 별도 코디네이터 data/status 로만 다룬다).
    """
    for keys in (API_STATUS_ZONE_KEYS, API_STATUS_IMAGE_KEYS, API_STATUS_HUB_KEYS):
        assert "aws" not in keys
        assert all("aws" not in str(key) for key in keys)


def test_poll_interval_is_301s_and_attempt_guard_stays_300s() -> None:
    client = _Client()
    coordinator = _coordinator(client)

    kwargs = coordinator._mock_init_kwargs
    assert kwargs["update_interval"] == datetime.timedelta(
        seconds=AWS_POLL_INTERVAL_SECONDS
    )
    # 자동 폴링은 1초 여유(301s)를 두되 요청 가드는 300s 를 유지한다.
    assert AWS_POLL_INTERVAL_SECONDS == 301
    assert AWS_ATTEMPT_INTERVAL_MINUTES == 5


def test_poll_margin_covers_ha_scheduling_rounding() -> None:
    """HA 예약식의 int() 절삭 때문에 300s 주기는 가드를 비껴가 폴링을 건너뛴다.

    검증된 반례: 시도 1000.2504, 완료 1000.4504, microsecond 0.2500 →
    다음 자동 갱신은 int(loop.time())+microsecond+interval 에서 발화한다.
    """
    loop_attempt = 1000.2504
    loop_finish = 1000.4504
    microsecond = 0.2500

    def next_refresh(interval: float) -> float:
        return int(loop_finish) + microsecond + interval

    # 300s 주기면 경과가 300s 미만이라 가드에 걸려 스킵된다(원래 결함).
    assert next_refresh(300) - loop_attempt < 300
    # 301s 주기면 같은 반례에서도 경과가 300s 를 넘어 가드가 통과한다.
    assert next_refresh(AWS_POLL_INTERVAL_SECONDS) - loop_attempt > 300

    # 실제 가드도 그 자동 갱신 시각에서 호출을 허용한다.
    client = _Client()
    coordinator = _coordinator(client)
    _update(coordinator)
    elapsed = next_refresh(AWS_POLL_INTERVAL_SECONDS) - loop_attempt
    coordinator._now = lambda: T0 + datetime.timedelta(  # type: ignore[method-assign]
        seconds=elapsed
    )
    _update(coordinator)
    assert client.calls == 2


def test_manual_refresh_boundary_is_strict_at_300_seconds() -> None:
    client = _Client()
    coordinator = _coordinator(client)
    _update(coordinator)
    assert client.calls == 1

    # 299.999초 — 아직 스로틀.
    coordinator._now = lambda: T0 + datetime.timedelta(  # type: ignore[method-assign]
        seconds=299.999
    )
    _update(coordinator)
    assert client.calls == 1

    # 정확히 300초 — 허용.
    coordinator._now = lambda: T0 + datetime.timedelta(  # type: ignore[method-assign]
        seconds=300
    )
    _update(coordinator)
    assert client.calls == 2


def test_forecast_update_path_has_no_aws_dependency() -> None:
    """예보 갱신 경로는 AWS 를 참조하지 않는다 — AWS 실패가 예보를 깨지 않도록."""
    import inspect

    from custom_components.kma.coordinator import KmaForecastCoordinator

    source = inspect.getsource(KmaForecastCoordinator._async_update_data)
    assert "aws" not in source.lower()


def test_expiry_callback_is_scheduled_at_observation_end() -> None:
    """관측시각+15분 정각에 정확히 한 번 상태를 다시 쓰도록 예약한다.

    폴링(5분)에만 기대면 만료 이후 최대 5분간 오래된 값이 게시 상태로 남는다.
    신선도 상한이 엄격히 15분 미만이므로 인위적 여유 없이 정각에 맞춘다.
    """
    coordinator = _coordinator(_Client())

    _update(coordinator)

    assert coordinator._expiry_unsub is not None
    assert coordinator._expiry_at == T0 + datetime.timedelta(
        minutes=AWS_MAX_OBSERVATION_AGE_MINUTES
    )
    record = CALL_LATER_CALLS[-1]
    # 남은 시간 기준 지연 — 관측 직후면 정확히 15분.
    assert record["delay"] == pytest.approx(AWS_MAX_OBSERVATION_AGE_MINUTES * 60)
    assert record["cancelled"] is False
    assert record["action"].__self__ is coordinator


def test_expiry_callback_reschedules_on_new_observation() -> None:
    """새 관측을 수용하면 만료 시각이 새 관측시각+15분으로 옮겨진다."""
    client = _Client()
    coordinator = _coordinator(client)
    _update(coordinator)
    assert coordinator._expiry_at == T0 + datetime.timedelta(
        minutes=AWS_MAX_OBSERVATION_AGE_MINUTES
    )

    newer = _obs(observed_at=T0 + datetime.timedelta(minutes=2), tm="202607031433")
    client.result = newer
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=6)  # type: ignore[method-assign]
    _update(coordinator)

    assert coordinator._expiry_at == T0 + datetime.timedelta(
        minutes=2 + AWS_MAX_OBSERVATION_AGE_MINUTES
    )
    # 이전 콜백은 취소되고 하나만 남는다.
    assert len(CALL_LATER_CALLS) == 2
    assert CALL_LATER_CALLS[0]["cancelled"] is True
    assert CALL_LATER_CALLS[1]["cancelled"] is False


def test_throttled_refresh_does_not_reschedule_expiry() -> None:
    """스로틀 갱신은 관측을 바꾸지 않으므로 만료 시각을 늘릴 수 없다."""
    coordinator = _coordinator(_Client())
    _update(coordinator)
    armed_at = coordinator._expiry_at
    assert armed_at is not None

    # 5분 미만 재갱신 — 네트워크 시도 없이 이전 데이터 반환.
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=3)  # type: ignore[method-assign]
    _update(coordinator)

    assert coordinator._expiry_at == armed_at
    assert len(CALL_LATER_CALLS) == 1  # 추가 예약 없음


def test_error_refresh_does_not_reschedule_expiry() -> None:
    """오류 갱신도 관측을 바꾸지 않으므로 만료 시각이 그대로 유지된다."""
    coordinator = _coordinator(_Client())
    _update(coordinator)
    armed_at = coordinator._expiry_at
    assert armed_at is not None

    client = coordinator.client
    client.error = KmaApiError("boom")
    coordinator._now = lambda: T0 + datetime.timedelta(minutes=6)  # type: ignore[method-assign]
    _update(coordinator)

    assert coordinator._expiry_at == armed_at
    assert len(CALL_LATER_CALLS) == 1  # 추가 예약 없음


def test_expiry_callback_is_cancelled_on_shutdown() -> None:
    """언로드/비활성화 시 만료콜백과 폴링이 함께 정리된다."""
    coordinator = _coordinator(_Client())
    _update(coordinator)

    asyncio.run(coordinator.async_shutdown())

    assert coordinator._expiry_unsub is None
    assert coordinator._expiry_at is None
    assert CALL_LATER_CALLS[-1]["cancelled"] is True
    assert coordinator._shutdown_requested is True


def test_shutdown_during_inflight_request_does_not_rearm_expiry() -> None:
    """요청이 진행 중일 때 셧다운되면 늦게 도착한 응답이 만료콜백을 되살리지 않는다.

    비동기 경합: HTTP 요청 보류 → async_shutdown → 요청 완료. 완료된 응답이
    스냅샷을 저장하거나 async_call_later 로 타이머를 다시 걸면 언로드 후에도
    타이머/리스너가 남는다.
    """

    class _BlockingClient(_Client):
        def __init__(self) -> None:
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def async_get_aws_observation(self, *, stn: int, **kwargs):
            self.calls += 1
            self.started.set()
            await self.release.wait()
            assert self.result is not None
            return self.result

    holder: dict = {}

    async def _scenario() -> None:
        client = _BlockingClient()
        coordinator = _coordinator(client)
        holder["coordinator"] = coordinator
        task = asyncio.create_task(coordinator._async_update_data())
        await client.started.wait()
        await coordinator.async_shutdown()
        client.release.set()
        holder["data"] = await task

    asyncio.run(_scenario())

    coordinator = holder["coordinator"]
    assert holder["data"]["observation"] is None
    assert coordinator._shutdown is True
    assert coordinator._expiry_unsub is None
    assert coordinator._expiry_at is None
    # 늦게 완료된 응답이 만료 타이머를 다시 걸지 않는다.
    assert CALL_LATER_CALLS == []


def test_no_expiry_callback_without_observation() -> None:
    """관측이 없으면(미신청/오류) 만료콜백을 예약하지 않는다."""
    client = _Client()
    client.error = KmaApiError("boom")
    coordinator = _coordinator(client)

    _update(coordinator)

    assert coordinator.aws_observation is None
    assert coordinator._expiry_unsub is None
    assert coordinator._expiry_at is None
    assert CALL_LATER_CALLS == []


def test_malformed_observation_is_never_stored_or_scheduled() -> None:
    """관측시각 없는 성공 페이로드는 스냅샷에 넣지도, 만료콜백도 만들지 않는다."""
    client = _Client()
    client.result = object()  # observed_at 이 없는 값 (첫 응답)
    coordinator = _coordinator(client)

    data = _update(coordinator)

    assert data["status"].startswith("error: ")
    assert data["observation"] is None
    assert coordinator._expiry_unsub is None
    assert CALL_LATER_CALLS == []
