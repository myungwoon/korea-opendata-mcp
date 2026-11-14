"""한국천문연구원 특일 정보 (공공데이터포털)."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import Field

from ..providers import data_go_kr, items_of
from . import common

API = "한국천문연구원 특일정보"
BASE = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService"
SOURCE = "한국천문연구원 특일 정보 (공공데이터포털)"
KIND = {"holidays": ("getRestDeInfo", "공휴일"), "anniversaries": ("getAnniversaryInfo", "기념일"),
        "solar_terms": ("get24DivisionsInfo", "24절기")}
WEEKDAY = "월화수목금토일"


async def get_holidays(
    year: Annotated[int | None, Field(ge=2000, le=2100, description="연도. 생략하면 올해")] = None,
    month: Annotated[int | None, Field(ge=1, le=12, description="월. 생략하면 연간 전체")] = None,
    kind: Annotated[Literal["holidays", "anniversaries", "solar_terms"],
                    Field(description="holidays 공휴일(대체공휴일 포함) / anniversaries 기념일 / solar_terms 24절기")] = "holidays",
) -> dict[str, Any]:
    """공휴일·대체공휴일, 기념일, 24절기 날짜를 조회합니다."""
    y = year or common.today_kst().year
    op, label = KIND[kind]
    months = [month] if month else list(range(1, 13))
    bodies = await asyncio.gather(*(data_go_kr(API, f"{BASE}/{op}", {
        "_type": "json", "numOfRows": 50, "pageNo": 1, "solYear": y, "solMonth": f"{m:02d}"}, ttl=86400)
        for m in months))
    entries: list[dict[str, Any]] = []
    for body in bodies:
        for it in items_of(body):
            iso = common.iso(it.get("locdate"))
            wd = WEEKDAY[date.fromisoformat(iso).weekday()] if iso and len(iso) == 10 else None
            entries.append({"date": iso, "weekday": wd, "name": it.get("dateName"),
                            "is_holiday": it.get("isHoliday") == "Y"})
    entries.sort(key=lambda e: e["date"] or "")
    return {"year": y, "month": month, "kind": label, "count": len(entries),
            "dates": entries, "source": SOURCE}


TOOLS = [get_holidays]
