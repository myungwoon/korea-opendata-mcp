"""한국은행 경제통계시스템(ECOS) — 환율, 기준금리, 100대 통계지표, 통계 검색."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any, Literal

from pydantic import Field

from ..config import ECOS, is_sample
from ..errors import ApiError, Code
from ..providers import ecos
from . import common

SOURCE = "한국은행 경제통계시스템(ECOS)"
FX_ITEMS = {"USD": ("0000001", "원/미국달러"), "JPY": ("0000002", "원/일본엔(100엔)"),
            "EUR": ("0000003", "원/유로"), "GBP": ("0000012", "원/영국파운드"),
            "CNY": ("0000053", "원/위안")}


def _with_note(out: dict[str, Any]) -> dict[str, Any]:
    if is_sample(ECOS):
        out["note"] = "시험용 sample 키라 앞쪽 10건만 조회됐습니다. 전체 기간은 ECOS 인증키를 발급받아 쓰세요."
    return out


def _series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"time": r.get("TIME"), "value": common.num(r.get("DATA_VALUE"))} for r in rows]


async def get_exchange_rate_history(
    currency: Annotated[Literal["USD", "JPY", "EUR", "GBP", "CNY"],
                        Field(description="통화. JPY 는 100엔 기준")] = "USD",
    start_date: Annotated[str | None, Field(max_length=10, description="시작일. 기본: 30일 전")] = None,
    end_date: Annotated[str | None, Field(max_length=10, description="종료일. 기본: 오늘")] = None,
) -> dict[str, Any]:
    """한국은행 매매기준율(원화 환율) 일별 시계열을 조회합니다. 영업일 기준이라 주말·공휴일은 빠집니다."""
    e = common.parse_date(end_date, common.today_kst())
    s = common.parse_date(start_date, e - timedelta(days=30))
    if (e - s).days > 3660:
        raise ApiError(Code.INVALID_PARAM, "조회 기간은 10년 이내로 넣으세요.")
    item, label = FX_ITEMS[currency]
    data = await ecos("StatisticSearch", 1, 5000, "731Y001", "D",
                      s.strftime("%Y%m%d"), e.strftime("%Y%m%d"), item)
    series = _series(data.get("row", []))
    for p in series:
        p["time"] = common.iso(p["time"])
    vals = [p["value"] for p in series if p["value"] is not None]
    return _with_note({
        "currency": currency, "label": label, "unit": "원" + (" (100엔당)" if currency == "JPY" else ""),
        "period": {"start": s.isoformat(), "end": e.isoformat()},
        "latest": series[-1] if series else None,
        "stats": {"min": min(vals), "max": max(vals), "avg": round(sum(vals) / len(vals), 2),
                  "change": round(vals[-1] - vals[0], 2)} if vals else None,
        "series": series, "source": SOURCE,
    })


async def get_base_rate(
    months: Annotated[int, Field(ge=1, le=240, description="최근 몇 개월 (월말 기준)")] = 24,
) -> dict[str, Any]:
    """한국은행 기준금리의 월별 추이와 변경 시점을 조회합니다."""
    end = common.today_kst()
    y, m = end.year, end.month - months + 1
    while m <= 0:
        y, m = y - 1, m + 12
    data = await ecos("StatisticSearch", 1, 1000, "722Y001", "M", f"{y}{m:02d}", end.strftime("%Y%m"), "0101000")
    series = _series(data.get("row", []))
    changes = [{"month": cur["time"], "from": prev["value"], "to": cur["value"]}
               for prev, cur in zip(series, series[1:]) if prev["value"] != cur["value"]]
    return _with_note({"unit": "연%", "current": series[-1] if series else None, "changes": changes,
                       "series": series, "source": SOURCE})


async def get_key_statistics(
    category: Annotated[str | None, Field(max_length=30, description=(
        "분류명 일부로 필터 (예: 환율, 금리, 물가, 고용, 성장률, 주식). 생략하면 전체 100개"))] = None,
) -> dict[str, Any]:
    """한국은행 100대 통계지표(최신값)를 조회합니다. 환율·금리·물가·GDP·고용 등 주요 경제지표를 한 번에 볼 수 있습니다."""
    data = await ecos("KeyStatisticList", 1, 100)
    rows = data.get("row", [])
    if category:
        key = category.replace(" ", "")
        rows = [r for r in rows if key in (r.get("CLASS_NAME") or "").replace(" ", "")
                or key in (r.get("KEYSTAT_NAME") or "").replace(" ", "")]
    return _with_note({"count": len(rows), "statistics": [{
        "category": r.get("CLASS_NAME"), "name": r.get("KEYSTAT_NAME"),
        "value": common.num(r.get("DATA_VALUE")), "unit": r.get("UNIT_NAME"), "period": r.get("CYCLE"),
    } for r in rows], "source": SOURCE})


async def search_ecos_statistic(
    stat_code: Annotated[str, Field(min_length=3, max_length=20, description="통계표 코드 (예: 901Y009 소비자물가지수)")],
    cycle: Annotated[Literal["A", "S", "Q", "M", "SM", "D"],
                     Field(description="주기: A 연 / S 반년 / Q 분기 / M 월 / SM 반월 / D 일")],
    start: Annotated[str, Field(min_length=4, max_length=8, description="시작 시점 (A: 2020, Q: 2020Q1, M: 202001, D: 20200101)")],
    end: Annotated[str, Field(min_length=4, max_length=8, description="종료 시점 (start 와 같은 형식)")],
    item_code1: Annotated[str | None, Field(max_length=20, description="통계항목 코드1 (생략하면 전체)")] = None,
    item_code2: Annotated[str | None, Field(max_length=20, description="통계항목 코드2")] = None,
    max_rows: Annotated[int, Field(ge=1, le=1000)] = 100,
) -> dict[str, Any]:
    """ECOS 통계표를 코드로 직접 조회합니다 (고급). 통계표·항목 코드는 ECOS 개발 가이드에서 확인합니다."""
    segs: list[str | int] = [1, max_rows, stat_code, cycle, start, end]
    if item_code1 or item_code2:
        segs.append(item_code1 or "?")
    if item_code2:
        segs.append(item_code2)
    data = await ecos("StatisticSearch", *segs)
    rows = data.get("row", [])
    return _with_note({"total": common.num(data.get("list_total_count")) or 0,
            "stat_name": rows[0].get("STAT_NAME") if rows else None,
            "rows": [{"time": r.get("TIME"), "item1": r.get("ITEM_NAME1"), "item2": r.get("ITEM_NAME2"),
                      "value": common.num(r.get("DATA_VALUE")), "unit": r.get("UNIT_NAME")} for r in rows],
            "source": SOURCE})


TOOLS = [get_exchange_rate_history, get_base_rate, get_key_statistics, search_ecos_statistic]
