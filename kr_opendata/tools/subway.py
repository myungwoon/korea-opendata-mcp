"""서울 열린데이터광장 — 지하철 실시간 도착정보."""

from __future__ import annotations

import re
from typing import Annotated, Any

from pydantic import Field

from ..errors import ApiError, Code
from ..providers import seoul_subway
from . import common

SOURCE = "서울특별시 지하철 실시간 도착정보 (서울 열린데이터광장)"
LINES = {
    "1001": "1호선", "1002": "2호선", "1003": "3호선", "1004": "4호선", "1005": "5호선",
    "1006": "6호선", "1007": "7호선", "1008": "8호선", "1009": "9호선", "1061": "중앙선",
    "1063": "경의중앙선", "1065": "공항철도", "1067": "경춘선", "1075": "수인분당선",
    "1077": "신분당선", "1081": "경강선", "1092": "우이신설선", "1093": "서해선", "1032": "GTX-A",
}


async def get_subway_arrival(
    station: Annotated[str, Field(min_length=1, max_length=30, description="역 이름 (예: 강남, 서울역, 홍대입구)")],
    line: Annotated[str | None, Field(max_length=10, description="호선 필터 (예: 2호선, 신분당선)")] = None,
) -> dict[str, Any]:
    """서울 지하철역의 실시간 열차 도착 정보를 조회합니다 (호선, 방면, 도착 예정, 현재 위치)."""
    name = re.sub(r"역$", "", station.strip()) or station.strip()
    rows = await seoul_subway("realtimeStationArrival", 0, 30, name, "realtimeArrivalList")
    if not rows:
        raise ApiError(Code.NOT_FOUND, f"'{station}' 역의 도착 정보가 없습니다.",
                       "역 이름을 '역' 없이 정확히 넣으세요 (예: 강남, 홍대입구).",
                       "운행 시간이 아니면 결과가 없을 수 있습니다.")
    trains = []
    for r in rows:
        line_name = LINES.get(str(r.get("subwayId")), r.get("subwayId"))
        if line and line.replace(" ", "") not in str(line_name):
            continue
        secs = common.num(r.get("barvlDt"))
        trains.append({
            "line": line_name, "direction": r.get("updnLine"), "train_line": r.get("trainLineNm"),
            "destination": r.get("bstatnNm"), "train_type": r.get("btrainSttus"),
            "arrival_message": r.get("arvlMsg2"), "current_location": r.get("arvlMsg3"),
            "arrival_in_sec": secs if secs else None, "is_last_train": r.get("lstcarAt") == "1",
            "updated_at": r.get("recptnDt"),
        })
    return {"station": name, "count": len(trains), "trains": trains, "source": SOURCE}


TOOLS = [get_subway_arrival]
