"""MCP 도구 등록."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..config import PROVIDERS, configured
from . import air, finance, holiday, subway, tour, weather
from .common import READ_ONLY

SERVICE_TOOLS = {
    "DATA_GO_KR_SERVICE_KEY": [f.__name__ for f in weather.TOOLS + air.TOOLS + holiday.TOOLS + tour.TOOLS],
    "ECOS_API_KEY": [f.__name__ for f in finance.TOOLS],
    "SEOUL_OPENAPI_KEY": [f.__name__ for f in subway.TOOLS],
}


async def get_service_status() -> dict[str, Any]:
    """어떤 서비스의 API 키가 설정됐는지(값은 숨김)와 서비스별 사용 가능한 도구를 보여줍니다. 도구가 키 오류를 낼 때 먼저 확인하세요."""
    state = configured()
    return {"services": [{
        "service": p.name, "env": p.env, "configured": state[p.env],
        "tools": SERVICE_TOOLS[p.env], "signup": p.signup, "note": p.note or None,
    } for p in PROVIDERS]}


ALL_TOOLS = [*weather.TOOLS, *air.TOOLS, *holiday.TOOLS, *tour.TOOLS,
             *finance.TOOLS, *subway.TOOLS, get_service_status]


def register(mcp: FastMCP) -> None:
    for fn in ALL_TOOLS:
        mcp.tool(fn, annotations=READ_ONLY)
