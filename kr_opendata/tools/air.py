"""에어코리아 대기오염정보 (공공데이터포털)."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from .. import geo
from ..errors import ApiError, Code
from ..providers import data_go_kr, items_of
from . import common

API = "에어코리아 대기오염정보"
URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
SOURCE = "한국환경공단 에어코리아 대기오염정보 (공공데이터포털)"
GRADE = {"1": "좋음", "2": "보통", "3": "나쁨", "4": "매우나쁨"}


def pm10_grade(v: float | None) -> str | None:
    if v is None:
        return None
    return "좋음" if v <= 30 else "보통" if v <= 80 else "나쁨" if v <= 150 else "매우나쁨"


def pm25_grade(v: float | None) -> str | None:
    if v is None:
        return None
    return "좋음" if v <= 15 else "보통" if v <= 35 else "나쁨" if v <= 75 else "매우나쁨"


def _station(it: dict[str, Any]) -> dict[str, Any]:
    return {
        "station": it.get("stationName"), "sido": it.get("sidoName"), "measured_at": it.get("dataTime"),
        "pm10": common.num(it.get("pm10Value")), "pm10_grade_24h": GRADE.get(str(it.get("pm10Grade") or "")),
        "pm25": common.num(it.get("pm25Value")), "pm25_grade_24h": GRADE.get(str(it.get("pm25Grade") or "")),
        "o3_ppm": common.num(it.get("o3Value")), "no2_ppm": common.num(it.get("no2Value")),
        "co_ppm": common.num(it.get("coValue")), "so2_ppm": common.num(it.get("so2Value")),
        "khai": common.num(it.get("khaiValue")), "khai_grade": GRADE.get(str(it.get("khaiGrade") or "")),
    }


async def get_air_quality(
    region: Annotated[str, Field(min_length=1, max_length=20, description=(
        "시도명(서울, 경기, 부산 …) 또는 도시명(수원, 강릉 …, 해당 시도로 조회)"))],
    station: Annotated[str | None, Field(max_length=20, description=(
        "측정소명 일부 (예: 종로구, 중구). 생략하면 시도 전체 요약"))] = None,
) -> dict[str, Any]:
    """미세먼지(PM10·PM2.5)와 대기질을 시도별 실시간 측정값으로 조회합니다. 시도 평균과 등급을 함께 돌려줍니다."""
    sido = geo.resolve_sido(region)
    body = await data_go_kr(API, URL, {"returnType": "json", "numOfRows": 300, "pageNo": 1,
                                       "sidoName": sido, "ver": "1.0"}, ttl=600)
    stations = [_station(it) for it in items_of(body)]
    if station:
        key = station.replace(" ", "")
        matched = [s for s in stations if key in str(s["station"]).replace(" ", "")]
        if not matched:
            raise ApiError(Code.NOT_FOUND, f"{sido} 지역에 '{station}' 측정소가 없습니다.",
                           "측정소 이름 일부만 넣거나 station 을 비워 시도 전체를 조회하세요.",
                           "측정소 예: " + ", ".join(str(s["station"]) for s in stations[:10]))
        stations = matched
    pm10s = [s["pm10"] for s in stations if isinstance(s["pm10"], (int, float))]
    pm25s = [s["pm25"] for s in stations if isinstance(s["pm25"], (int, float))]
    avg10 = round(sum(pm10s) / len(pm10s), 1) if pm10s else None
    avg25 = round(sum(pm25s) / len(pm25s), 1) if pm25s else None
    return {
        "sido": sido,
        "measured_at": next((s["measured_at"] for s in stations if s["measured_at"]), None),
        "summary": {"pm10_avg": avg10, "pm10_grade_1h": pm10_grade(avg10),
                    "pm25_avg": avg25, "pm25_grade_1h": pm25_grade(avg25),
                    "stations_reporting": len(pm10s)},
        "stations": stations if station or len(stations) <= 40 else stations[:40],
        "note": None if station or len(stations) <= 40 else f"측정소 {len(stations)}곳 중 40곳만 표시. station 으로 좁히세요.",
        "grade_basis": ("pm10/pm25 는 1시간 측정값(㎍/㎥). summary 의 *_grade_1h 는 그 평균을 환경부 기준"
                        "(PM10 좋음≤30·보통≤80·나쁨≤150, PM2.5 좋음≤15·보통≤35·나쁨≤75)으로 매긴 참고 등급이고, "
                        "stations 의 *_grade_24h 는 에어코리아가 24시간 이동평균으로 매긴 공식 등급이라 서로 다를 수 있습니다."),
        "source": SOURCE,
    }


TOOLS = [get_air_quality]
