"""helpers.py 단위 테스트 — parse_pcp, parse_sno, 좌표 변환."""
import pytest

from custom_components.kma.helpers import (
    haversine_distance,
    latlon_to_grid,
    parse_pcp,
    parse_sno,
)


# ---------------------------------------------------------------------------
# parse_pcp
# ---------------------------------------------------------------------------
class TestParsePcp:
    def test_none_returns_zero(self):
        assert parse_pcp(None) == 0.0

    def test_no_rain_string(self):
        assert parse_pcp("강수없음") == 0.0

    def test_zero_string(self):
        assert parse_pcp("0") == 0.0

    def test_float_passthrough(self):
        assert parse_pcp(3.5) == pytest.approx(3.5)

    def test_int_passthrough(self):
        assert parse_pcp(10) == pytest.approx(10.0)

    def test_less_than_1mm(self):
        # "1.0mm 미만" → 0.5 (절반)
        assert parse_pcp("1.0mm 미만") == pytest.approx(0.5)

    def test_range_avg(self):
        # "30.0~50.0mm" → 40.0 (평균)
        assert parse_pcp("30.0~50.0mm") == pytest.approx(40.0)

    def test_at_least(self):
        # "50.0mm 이상" → 50.0
        assert parse_pcp("50.0mm 이상") == pytest.approx(50.0)

    def test_simple_numeric_string(self):
        assert parse_pcp("5.0mm") == pytest.approx(5.0)

    def test_empty_string_returns_zero(self):
        assert parse_pcp("") == 0.0


# ---------------------------------------------------------------------------
# parse_sno
# ---------------------------------------------------------------------------
class TestParseSno:
    def test_none_returns_zero(self):
        assert parse_sno(None) == 0.0

    def test_no_snow_string(self):
        assert parse_sno("적설없음") == 0.0

    def test_zero_string(self):
        assert parse_sno("0") == 0.0

    def test_float_passthrough(self):
        assert parse_sno(2.5) == pytest.approx(2.5)

    def test_less_than_1cm(self):
        # "1.0cm 미만" → 0.5 (절반)
        assert parse_sno("1.0cm 미만") == pytest.approx(0.5)

    def test_range_avg(self):
        # "1.0~3.0cm" → 2.0 (평균)
        assert parse_sno("1.0~3.0cm") == pytest.approx(2.0)

    def test_at_least(self):
        # "5.0cm 이상" → 5.0
        assert parse_sno("5.0cm 이상") == pytest.approx(5.0)

    def test_empty_string_returns_zero(self):
        assert parse_sno("") == 0.0


# ---------------------------------------------------------------------------
# latlon_to_grid
# ---------------------------------------------------------------------------
class TestLatLonToGrid:
    """기상청 LCC 격자 변환 — 결과는 정수 (nx, ny) 튜플."""

    def test_returns_int_tuple(self):
        nx, ny = latlon_to_grid(37.5665, 126.9780)
        assert isinstance(nx, int)
        assert isinstance(ny, int)

    def test_seoul_range(self):
        # 서울 중심부: nx ≈ 60, ny ≈ 127
        nx, ny = latlon_to_grid(37.5665, 126.9780)
        assert 58 <= nx <= 62
        assert 125 <= ny <= 129

    def test_busan_range(self):
        # 부산: nx ≈ 98, ny ≈ 76
        nx, ny = latlon_to_grid(35.18, 129.08)
        assert 95 <= nx <= 101
        assert 73 <= ny <= 79

    def test_jeju_range(self):
        # 제주: nx ≈ 52, ny ≈ 38
        nx, ny = latlon_to_grid(33.50, 126.53)
        assert 50 <= nx <= 55
        assert 36 <= ny <= 41

    def test_seoul_north_of_busan(self):
        # 서울이 부산보다 북쪽 → ny 더 큼
        _, ny_seoul = latlon_to_grid(37.5665, 126.9780)
        _, ny_busan = latlon_to_grid(35.18, 129.08)
        assert ny_seoul > ny_busan

    def test_busan_east_of_seoul(self):
        # 부산이 서울보다 동쪽 → nx 더 큼
        nx_seoul, _ = latlon_to_grid(37.5665, 126.9780)
        nx_busan, _ = latlon_to_grid(35.18, 129.08)
        assert nx_busan > nx_seoul

    def test_positive_coords(self):
        # 한국 영토 내 좌표는 항상 양수
        nx, ny = latlon_to_grid(36.0, 128.0)
        assert nx > 0
        assert ny > 0


# ---------------------------------------------------------------------------
# haversine_distance
# ---------------------------------------------------------------------------
class TestHaversineDistance:
    def test_same_point_is_zero(self):
        d = haversine_distance(37.5665, 126.9780, 37.5665, 126.9780)
        assert d == pytest.approx(0.0, abs=1e-6)

    def test_seoul_to_busan_approx_325km(self):
        # 서울~부산 직선거리 ≈ 320~340km
        d = haversine_distance(37.5665, 126.9780, 35.18, 129.08)
        assert 300.0 <= d <= 360.0

    def test_symmetric(self):
        d1 = haversine_distance(37.5665, 126.9780, 35.18, 129.08)
        d2 = haversine_distance(35.18, 129.08, 37.5665, 126.9780)
        assert d1 == pytest.approx(d2, rel=1e-6)
