"""기상청 연동을 위한 좌표 변환 및 지역 매핑 헬퍼 함수."""

from __future__ import annotations

import math
from .const import REPRESENTATIVE_LAND_ZONES, REPRESENTATIVE_MARINE_ZONES


def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """기상청 Lambert Conformal Conic (LCC) 격자좌표 변환.

    공식 기상청 알고리즘을 준수하여 (lat, lon) -> (nx, ny)를 반환합니다.
    """
    RE = 6371.00877  # 지구 반경(km)
    GRID = 5.0       # 격자 간격(km)
    SLAT1 = 30.0     # 투영 위도1(degree)
    SLAT2 = 60.0     # 투영 위도2(degree)
    OLON = 126.0     # 기준점 경도(degree)
    OLAT = 38.0      # 기준점 위도(degree)
    XO = 43          # 기준점 X좌표(GRID)
    YO = 136         # 기준점 Y좌표(GRID)

    DEGRAD = math.pi / 180.0

    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = math.floor(ra * math.sin(theta) + XO + 0.5)
    ny = math.floor(ro - ra * math.cos(theta) + YO + 0.5)

    return int(nx), int(ny)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 위경도 사이의 Haversine 거리 계산 (km)."""
    R = 6371.00877  # 지구 평균 반경 (km)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def get_nearest_land_zone(lat: float, lon: float) -> str:
    """주어진 위경도 좌표에서 가장 가까운 대표 육상예보구역(reg_id) 반환."""
    min_dist = float("inf")
    nearest_code = "11B10101"  # 서울 기본값

    for code, coords in REPRESENTATIVE_LAND_ZONES.items():
        dist = haversine_distance(lat, lon, coords[0], coords[1])
        if dist < min_dist:
            min_dist = dist
            nearest_code = code

    return nearest_code


def get_nearest_marine_zone(lat: float, lon: float) -> str:
    """주어진 위경도 좌표에서 가장 가까운 대표 해상예보구역(reg_id) 반환."""
    min_dist = float("inf")
    nearest_code = "12A10100"  # 서해북부 기본값

    for code, coords in REPRESENTATIVE_MARINE_ZONES.items():
        dist = haversine_distance(lat, lon, coords[0], coords[1])
        if dist < min_dist:
            min_dist = dist
            nearest_code = code

    return nearest_code


if __name__ == "__main__":
    # 테스트 드라이버: 다양한 한국 도시의 변환 결과 확인
    test_cases = [
        ("서울 (Jongno)", 37.57, 126.97),
        ("부산", 35.18, 129.08),
        ("제주", 33.50, 126.53),
        ("인천", 37.45, 126.70),
        ("독도", 37.24, 131.86),
    ]

    print("== 기상청 좌표 변환 및 대표 구역 테스트 ==")
    for name, lat, lon in test_cases:
        nx, ny = latlon_to_grid(lat, lon)
        land_reg = get_nearest_land_zone(lat, lon)
        marine_reg = get_nearest_marine_zone(lat, lon)
        print(f"{name} ({lat}, {lon})")
        print(f"  -> nx: {nx}, ny: {ny}")
        print(f"  -> 육상구역: {land_reg}")
        print(f"  -> 해상구역: {marine_reg}")
        print()
