"""기상청 단기예보 조회서비스 (공공데이터포털)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Annotated, Any

from pydantic import Field

from .. import geo
from ..providers import data_go_kr, items_of
from . import common

API = "기상청 단기예보"
BASE = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
SOURCE = "기상청 단기예보 조회서비스 (공공데이터포털)"

SKY = {"1": "맑음", "3": "구름많음", "4": "흐림"}
PTY = {"0": "없음", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기",
       "5": "빗방울", "6": "빗방울눈날림", "7": "눈날림"}
VILAGE_HOURS = [2, 5, 8, 11, 14, 17, 20, 23]

Location = Annotated[str, Field(min_length=1, max_length=40, description=(
    "지명(서울, 부산, 강릉, 제주, 경기 등) 또는 '위도,경도' (예: 37.5665,126.9780)"))]


def ncst_base(now: datetime) -> tuple[str, str]:
    """초단기실황: 매시 정시 자료가 40분 이후 제공된다."""
    t = now - timedelta(minutes=40)
    return t.strftime("%Y%m%d"), t.strftime("%H00")


def vilage_base(now: datetime) -> tuple[str, str]:
    """단기예보: 02·05·…·23시 발표, 10분 이후 제공."""
    t = now - timedelta(minutes=10)
    hours = [h for h in VILAGE_HOURS if h <= t.hour]
    if not hours:
        t -= timedelta(days=1)
        return t.strftime("%Y%m%d"), "2300"
    return t.strftime("%Y%m%d"), f"{hours[-1]:02d}00"


def _place_info(p: geo.Place, nx: int, ny: int) -> dict[str, Any]:
    return {"name": p.name, "lat": p.lat, "lon": p.lon, "grid": {"nx": nx, "ny": ny}}


async def get_weather_now(location: Location) -> dict[str, Any]:
    """현재 날씨(초단기실황: 기온, 습도, 강수, 바람)를 조회합니다. 기상청 실측 자료입니다."""
    p = geo.resolve_place(location)
    nx, ny = geo.latlon_to_grid(p.lat, p.lon)
    bd, bt = ncst_base(common.now_kst())
    body = await data_go_kr(API, f"{BASE}/getUltraSrtNcst", {
        "dataType": "JSON", "numOfRows": 20, "pageNo": 1,
        "base_date": bd, "base_time": bt, "nx": nx, "ny": ny}, ttl=300)
    v = {it["category"]: it.get("obsrValue") for it in items_of(body)}
    pty = PTY.get(str(v.get("PTY", "0")).split(".")[0], v.get("PTY"))
    return {
        "location": _place_info(p, nx, ny),
        "observed_at": common.iso(bd + bt),
        "temperature_c": common.num(v.get("T1H")),
        "humidity_pct": common.num(v.get("REH")),
        "precipitation_type": pty,
        "precipitation_1h_mm": common.num(v.get("RN1")),
        "wind_speed_ms": common.num(v.get("WSD")),
        "wind_direction_deg": common.num(v.get("VEC")),
        "source": SOURCE,
    }


async def get_weather_forecast(
    location: Location,
    days: Annotated[int, Field(ge=1, le=3, description="예보 일수 (1~3, 오늘 포함)")] = 3,
    include_hourly: Annotated[bool, Field(description="시간별 예보 포함 여부")] = False,
) -> dict[str, Any]:
    """단기예보(최대 3일)를 날짜별 최저/최고기온, 강수확률, 하늘상태로 요약합니다."""
    p = geo.resolve_place(location)
    nx, ny = geo.latlon_to_grid(p.lat, p.lon)
    bd, bt = vilage_base(common.now_kst())
    body = await data_go_kr(API, f"{BASE}/getVilageFcst", {
        "dataType": "JSON", "numOfRows": 1000, "pageNo": 1,
        "base_date": bd, "base_time": bt, "nx": nx, "ny": ny}, ttl=1800)

    slots: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for it in items_of(body):
        slots[(it["fcstDate"], it["fcstTime"])][it["category"]] = str(it.get("fcstValue"))
    by_day: dict[str, list[tuple[str, dict[str, str]]]] = defaultdict(list)
    for (d, t), vals in sorted(slots.items()):
        by_day[d].append((t, vals))

    daily = []
    for d in sorted(by_day)[:days]:
        rows = by_day[d]
        temps = [common.num(v["TMP"]) for _, v in rows if "TMP" in v]
        temps = [t for t in temps if t is not None]
        tmn = next((common.num(v["TMN"]) for _, v in rows if "TMN" in v), None)
        tmx = next((common.num(v["TMX"]) for _, v in rows if "TMX" in v), None)
        pops = [common.num(v.get("POP")) or 0 for _, v in rows if "POP" in v]
        skies = [SKY.get(v.get("SKY", ""), "") for _, v in rows if "SKY" in v]
        ptys = sorted({PTY.get(v.get("PTY", "0"), "") for _, v in rows} - {"없음", ""})
        entry: dict[str, Any] = {
            "date": common.iso(d),
            "min_temp_c": tmn if tmn is not None else (min(temps) if temps else None),
            "max_temp_c": tmx if tmx is not None else (max(temps) if temps else None),
            "max_precip_prob_pct": max(pops) if pops else None,
            "sky": max(set(skies), key=skies.count) if skies else None,
            "precipitation_types": ptys,
        }
        if include_hourly:
            entry["hourly"] = [{
                "time": f"{t[:2]}:{t[2:]}", "temp_c": common.num(v.get("TMP")),
                "sky": SKY.get(v.get("SKY", "")), "precipitation": PTY.get(v.get("PTY", "0")),
                "precip_prob_pct": common.num(v.get("POP")), "precip_mm": v.get("PCP"),
                "humidity_pct": common.num(v.get("REH")), "wind_ms": common.num(v.get("WSD")),
            } for t, v in rows]
        daily.append(entry)
    return {"location": _place_info(p, nx, ny), "issued_at": common.iso(bd + bt),
            "days": daily, "source": SOURCE}


TOOLS = [get_weather_now, get_weather_forecast]
