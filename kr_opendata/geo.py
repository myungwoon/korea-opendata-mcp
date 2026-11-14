"""지명 → 좌표·기상청 격자·시도명 변환."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .errors import ApiError, Code


@dataclass(frozen=True)
class Place:
    name: str
    lat: float
    lon: float
    sido: str          # 에어코리아 sidoName


# 주요 도시 (위도, 경도, 에어코리아 시도명)
_PLACES: list[tuple[str, float, float, str]] = [
    ("서울", 37.5665, 126.9780, "서울"), ("부산", 35.1796, 129.0756, "부산"),
    ("대구", 35.8714, 128.6014, "대구"), ("인천", 37.4563, 126.7052, "인천"),
    ("광주", 35.1595, 126.8526, "광주"), ("대전", 36.3504, 127.3845, "대전"),
    ("울산", 35.5384, 129.3114, "울산"), ("세종", 36.4800, 127.2890, "세종"),
    ("수원", 37.2636, 127.0286, "경기"), ("성남", 37.4200, 127.1265, "경기"),
    ("고양", 37.6584, 126.8320, "경기"), ("용인", 37.2411, 127.1776, "경기"),
    ("부천", 37.5034, 126.7660, "경기"), ("안산", 37.3219, 126.8309, "경기"),
    ("파주", 37.7599, 126.7802, "경기"), ("평택", 36.9921, 127.1129, "경기"),
    ("가평", 37.8315, 127.5105, "경기"), ("춘천", 37.8813, 127.7298, "강원"),
    ("원주", 37.3422, 127.9202, "강원"), ("강릉", 37.7519, 128.8761, "강원"),
    ("속초", 38.2070, 128.5918, "강원"), ("평창", 37.3705, 128.3903, "강원"),
    ("청주", 36.6424, 127.4890, "충북"), ("충주", 36.9910, 127.9259, "충북"),
    ("천안", 36.8151, 127.1139, "충남"), ("공주", 36.4465, 127.1190, "충남"),
    ("태안", 36.7456, 126.2980, "충남"), ("전주", 35.8242, 127.1480, "전북"),
    ("군산", 35.9676, 126.7366, "전북"), ("목포", 34.8118, 126.3922, "전남"),
    ("여수", 34.7604, 127.6622, "전남"), ("순천", 34.9506, 127.4872, "전남"),
    ("포항", 36.0190, 129.3435, "경북"), ("경주", 35.8562, 129.2247, "경북"),
    ("안동", 36.5684, 128.7294, "경북"), ("구미", 36.1195, 128.3446, "경북"),
    ("창원", 35.2280, 128.6811, "경남"), ("진주", 35.1800, 128.1076, "경남"),
    ("김해", 35.2285, 128.8894, "경남"), ("통영", 34.8544, 128.4331, "경남"),
    ("거제", 34.8806, 128.6211, "경남"), ("제주", 33.4996, 126.5312, "제주"),
    ("서귀포", 33.2541, 126.5600, "제주"), ("울릉", 37.4844, 130.9057, "경북"),
]
PLACES: dict[str, Place] = {n: Place(n, la, lo, s) for n, la, lo, s in _PLACES}

# 시도 별칭 → 에어코리아 sidoName
SIDO_ALIASES = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기", "강원도": "강원", "강원특별자치도": "강원", "충청북도": "충북", "충청남도": "충남",
    "전라북도": "전북", "전북특별자치도": "전북", "전라남도": "전남", "경상북도": "경북",
    "경상남도": "경남", "제주도": "제주", "제주특별자치도": "제주",
}
SIDO_NAMES = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원",
              "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
# 시도 단위 대표 지점 (날씨용)
SIDO_CAPITAL = {"경기": "수원", "강원": "춘천", "충북": "청주", "충남": "천안", "전북": "전주",
                "전남": "목포", "경북": "안동", "경남": "창원", "제주": "제주"}


def _normalize(name: str) -> str:
    n = name.strip().replace(" ", "")
    if n in SIDO_ALIASES:
        return SIDO_ALIASES[n]
    return re.sub(r"(특별자치시|특별자치도|특별시|광역시|시|군)$", "", n) or n


def parse_latlon(text: str) -> tuple[float, float] | None:
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*", text)
    if not m:
        return None
    lat, lon = float(m[1]), float(m[2])
    if not (32 <= lat <= 39.5 and 124 <= lon <= 132):
        raise ApiError(Code.INVALID_PARAM, f"한국 범위를 벗어난 좌표입니다: {lat}, {lon}",
                       "위도 33~39, 경도 124~132 범위의 '위도,경도'를 넣으세요.")
    return lat, lon


def resolve_place(text: str) -> Place:
    """'서울', '부산광역시', '경기', '37.56,126.97' 등을 Place 로."""
    ll = parse_latlon(text)
    if ll:
        return Place(f"{ll[0]:.4f},{ll[1]:.4f}", ll[0], ll[1], "")
    n = _normalize(text)
    if n in PLACES:
        return PLACES[n]
    if n in SIDO_CAPITAL:
        base = PLACES[SIDO_CAPITAL[n]]
        return Place(f"{n}({base.name})", base.lat, base.lon, n)
    raise ApiError(Code.INVALID_PARAM, f"'{text}' 위치를 알 수 없습니다.",
                   "'위도,경도' 형식으로 넣으세요 (예: 37.5665,126.9780).",
                   "지원 지명 예: " + ", ".join(list(PLACES)[:20]) + " 등")


def resolve_sido(text: str) -> str:
    n = _normalize(text)
    if n in SIDO_NAMES or n == "전국":
        return n
    if n in PLACES:
        return PLACES[n].sido
    raise ApiError(Code.INVALID_PARAM, f"'{text}' 시도를 알 수 없습니다.",
                   "시도명을 넣으세요: " + ", ".join(SIDO_NAMES))


def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """기상청 동네예보 격자(LCC, 5km) 변환. 기상청 공개 변환식."""
    RE, GRID, SLAT1, SLAT2, OLON, OLAT, XO, YO = 6371.00877, 5.0, 30.0, 60.0, 126.0, 38.0, 43, 136
    d = math.pi / 180.0
    re_ = RE / GRID
    slat1, slat2, olon, olat = SLAT1 * d, SLAT2 * d, OLON * d, OLAT * d
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(
        math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5))
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5) ** sn * math.cos(slat1) / sn
    ro = re_ * sf / math.tan(math.pi * 0.25 + olat * 0.5) ** sn
    ra = re_ * sf / math.tan(math.pi * 0.25 + lat * d * 0.5) ** sn
    theta = lon * d - olon
    if theta > math.pi:
        theta -= 2 * math.pi
    if theta < -math.pi:
        theta += 2 * math.pi
    theta *= sn
    return int(math.floor(ra * math.sin(theta) + XO + 0.5)), int(math.floor(ro - ra * math.cos(theta) + YO + 0.5))
