"""한국관광공사 국문 관광정보 서비스 (TourAPI 4.0, KorService2, 공공데이터포털)."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any, Literal

from pydantic import Field

from ..errors import ApiError, Code
from ..providers import data_go_kr, items_of
from . import common

API = "한국관광공사 국문 관광정보"
BASE = "https://apis.data.go.kr/B551011/KorService2"
SOURCE = "한국관광공사 TourAPI (공공데이터포털)"
CONTENT_TYPES = {"attraction": "12", "culture": "14", "festival": "15", "course": "25",
                 "leports": "28", "lodging": "32", "shopping": "38", "restaurant": "39"}
CONTENT_LABEL = {"12": "관광지", "14": "문화시설", "15": "축제·공연·행사", "25": "여행코스",
                 "28": "레포츠", "32": "숙박", "38": "쇼핑", "39": "음식점"}
COMMON = {"MobileOS": "ETC", "MobileApp": "korea-opendata-mcp", "_type": "json"}


def _item(it: dict[str, Any]) -> dict[str, Any]:
    out = {
        "content_id": it.get("contentid"),
        "type": CONTENT_LABEL.get(str(it.get("contenttypeid")), it.get("contenttypeid")),
        "title": it.get("title"),
        "address": " ".join(x for x in (it.get("addr1"), it.get("addr2")) if x) or None,
        "tel": it.get("tel") or None,
        "image": it.get("firstimage") or None,
        "lat": common.num(it.get("mapy")), "lon": common.num(it.get("mapx")),
    }
    if it.get("eventstartdate"):
        out["event_start"] = common.iso(it.get("eventstartdate"))
        out["event_end"] = common.iso(it.get("eventenddate"))
    return out


def _page(body: dict[str, Any], page: int, per_page: int, key: str) -> dict[str, Any]:
    return {"total": common.num(body.get("totalCount")) or 0, "page": page, "per_page": per_page,
            key: [_item(it) for it in items_of(body)], "source": SOURCE}


async def search_tour_spots(
    keyword: Annotated[str, Field(min_length=1, max_length=50, description="검색어 (예: 경복궁, 해운대, 한옥마을)")],
    content_type: Annotated[Literal["all", "attraction", "culture", "festival", "course", "leports",
                                    "lodging", "shopping", "restaurant"],
                            Field(description="all 전체 / attraction 관광지 / culture 문화시설 / festival 축제·행사 / "
                                              "course 여행코스 / leports 레포츠 / lodging 숙박 / shopping 쇼핑 / restaurant 음식점")] = "all",
    page: Annotated[int, Field(ge=1, le=1000)] = 1,
    per_page: Annotated[int, Field(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    """키워드로 관광지·음식점·숙박·문화시설 등을 검색합니다 (주소, 전화, 좌표, 대표 이미지)."""
    body = await data_go_kr(API, f"{BASE}/searchKeyword2", {
        **COMMON, "keyword": keyword, "numOfRows": per_page, "pageNo": page,
        "contentTypeId": CONTENT_TYPES.get(content_type)}, ttl=3600)
    return _page(body, page, per_page, "places")


async def search_festivals(
    start_date: Annotated[str | None, Field(max_length=10, description="이 날짜 이후 시작/진행 중인 행사. 기본: 오늘")] = None,
    end_date: Annotated[str | None, Field(max_length=10, description="이 날짜까지 시작하는 행사. 기본: 시작일+30일")] = None,
    page: Annotated[int, Field(ge=1, le=1000)] = 1,
    per_page: Annotated[int, Field(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    """기간으로 전국 축제·공연·행사를 검색합니다."""
    s = common.parse_date(start_date, common.today_kst())
    e = common.parse_date(end_date, s + timedelta(days=30))
    if e < s:
        raise ApiError(Code.INVALID_PARAM, "end_date 가 start_date 보다 빠릅니다.")
    body = await data_go_kr(API, f"{BASE}/searchFestival2", {
        **COMMON, "eventStartDate": s.strftime("%Y%m%d"), "eventEndDate": e.strftime("%Y%m%d"),
        "numOfRows": per_page, "pageNo": page}, ttl=3600)
    out = _page(body, page, per_page, "festivals")
    out["period"] = {"start": s.isoformat(), "end": e.isoformat()}
    return out


TOOLS = [search_tour_spots, search_festivals]
