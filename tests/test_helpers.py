"""helpers.py 단위 테스트 — parse_pcp, parse_sno, 좌표 변환, 등급 분류 함수."""
import pytest

from custom_components.kma.helpers import (
    get_air_stagnation_grade,
    get_car_wash_grade,
    get_discomfort_grade,
    get_food_poisoning_grade,
    get_freeze_risk_grade,
    get_laundry_grade,
    get_pm10_grade,
    get_pollen_risk_grade,
    get_uv_index_grade,
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


# ---------------------------------------------------------------------------
# get_pm10_grade
# ---------------------------------------------------------------------------
class TestGetPm10Grade:
    def test_none_returns_none(self):
        assert get_pm10_grade(None) is None

    def test_good_boundary(self):
        assert get_pm10_grade(30) == "good"

    def test_moderate_lower_boundary(self):
        assert get_pm10_grade(31) == "moderate"

    def test_moderate_upper_boundary(self):
        assert get_pm10_grade(80) == "moderate"

    def test_unhealthy_boundary(self):
        assert get_pm10_grade(150) == "unhealthy"

    def test_very_unhealthy_above_threshold(self):
        assert get_pm10_grade(151) == "very_unhealthy"

    def test_very_unhealthy_far_above(self):
        assert get_pm10_grade(500) == "very_unhealthy"

    def test_zero(self):
        assert get_pm10_grade(0) == "good"


# ---------------------------------------------------------------------------
# get_uv_index_grade
# ---------------------------------------------------------------------------
class TestGetUvIndexGrade:
    def test_none_returns_none(self):
        assert get_uv_index_grade(None) is None

    def test_low_boundary(self):
        assert get_uv_index_grade(2) == "low"

    def test_moderate_boundary(self):
        assert get_uv_index_grade(5) == "moderate"

    def test_high_boundary(self):
        assert get_uv_index_grade(7) == "high"

    def test_very_high_boundary(self):
        assert get_uv_index_grade(10) == "very_high"

    def test_extreme_above_threshold(self):
        assert get_uv_index_grade(11) == "extreme"

    def test_extreme_far_above(self):
        assert get_uv_index_grade(15) == "extreme"


# ---------------------------------------------------------------------------
# get_air_stagnation_grade
# ---------------------------------------------------------------------------
class TestGetAirStagnationGrade:
    def test_none_returns_none(self):
        assert get_air_stagnation_grade(None) is None

    def test_25_is_low(self):
        assert get_air_stagnation_grade(25) == "low"

    def test_50_is_moderate(self):
        assert get_air_stagnation_grade(50) == "moderate"

    def test_75_is_high(self):
        assert get_air_stagnation_grade(75) == "high"

    def test_100_is_very_high(self):
        assert get_air_stagnation_grade(100) == "very_high"

    def test_unmapped_value_returns_none(self):
        # 지수값은 25/50/75/100 넷 중 하나만 오는 것으로 실측 확인됨 — 그 외 값은 미매핑.
        assert get_air_stagnation_grade(60) is None

    def test_negative_sentinel_returns_none(self):
        assert get_air_stagnation_grade(-250) is None


# ---------------------------------------------------------------------------
# get_pollen_risk_grade
# ---------------------------------------------------------------------------
class TestGetPollenRiskGrade:
    def test_none_returns_none(self):
        assert get_pollen_risk_grade(None) is None

    def test_0_is_low(self):
        assert get_pollen_risk_grade(0) == "low"

    def test_1_is_moderate(self):
        assert get_pollen_risk_grade(1) == "moderate"

    def test_2_is_high(self):
        assert get_pollen_risk_grade(2) == "high"

    def test_3_is_very_high(self):
        assert get_pollen_risk_grade(3) == "very_high"

    def test_unmapped_value_returns_none(self):
        assert get_pollen_risk_grade(4) is None


# ---------------------------------------------------------------------------
# get_discomfort_grade
# ---------------------------------------------------------------------------
class TestGetDiscomfortGrade:
    def test_none_returns_none(self):
        assert get_discomfort_grade(None) is None

    def test_low(self):
        assert get_discomfort_grade(67.9) == "low"

    def test_normal_boundary(self):
        assert get_discomfort_grade(68) == "normal"

    def test_high_boundary(self):
        assert get_discomfort_grade(75) == "high"

    def test_very_high_boundary(self):
        assert get_discomfort_grade(80) == "very_high"


# ---------------------------------------------------------------------------
# get_laundry_grade
# ---------------------------------------------------------------------------
class TestGetLaundryGrade:
    def test_none_returns_none(self):
        assert get_laundry_grade(None) is None

    def test_excellent_boundary(self):
        assert get_laundry_grade(90) == "excellent"

    def test_good_boundary(self):
        assert get_laundry_grade(70) == "good"

    def test_normal_boundary(self):
        assert get_laundry_grade(40) == "normal"

    def test_avoid_below_threshold(self):
        assert get_laundry_grade(39) == "avoid"

    def test_avoid_zero(self):
        assert get_laundry_grade(0) == "avoid"


# ---------------------------------------------------------------------------
# get_car_wash_grade
# ---------------------------------------------------------------------------
class TestGetCarWashGrade:
    def test_none_returns_none(self):
        assert get_car_wash_grade(None) is None

    def test_excellent_boundary(self):
        assert get_car_wash_grade(90) == "excellent"

    def test_delay_boundary(self):
        assert get_car_wash_grade(60) == "delay"

    def test_caution_boundary(self):
        assert get_car_wash_grade(40) == "caution"

    def test_avoid_below_threshold(self):
        assert get_car_wash_grade(10) == "avoid"

    def test_actual_native_values(self):
        # car_wash_index의 실제 native_value는 10/40/60/90 넷 중 하나만 나온다.
        assert get_car_wash_grade(10) == "avoid"
        assert get_car_wash_grade(40) == "caution"
        assert get_car_wash_grade(60) == "delay"
        assert get_car_wash_grade(90) == "excellent"


# ---------------------------------------------------------------------------
# get_freeze_risk_grade
# ---------------------------------------------------------------------------
class TestGetFreezeRiskGrade:
    def test_none_returns_none(self):
        assert get_freeze_risk_grade(None) is None

    def test_low_below_threshold(self):
        assert get_freeze_risk_grade(0) == "low"

    def test_normal_boundary(self):
        assert get_freeze_risk_grade(30) == "normal"

    def test_high_boundary(self):
        assert get_freeze_risk_grade(60) == "high"

    def test_very_high_boundary(self):
        assert get_freeze_risk_grade(90) == "very_high"


# ---------------------------------------------------------------------------
# get_food_poisoning_grade
# ---------------------------------------------------------------------------
class TestGetFoodPoisoningGrade:
    def test_none_returns_none(self):
        assert get_food_poisoning_grade(None) is None

    def test_safe_below_threshold(self):
        assert get_food_poisoning_grade(54.9) == "safe"

    def test_caution_boundary(self):
        assert get_food_poisoning_grade(55) == "caution"

    def test_warning_boundary(self):
        assert get_food_poisoning_grade(71) == "warning"

    def test_danger_boundary(self):
        assert get_food_poisoning_grade(86) == "danger"
