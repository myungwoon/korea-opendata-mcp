"""공용 HTTP 호출 — 재시도, 짧은 응답 캐시.

키가 URL(쿼리나 경로)에 들어가므로 URL·예외 문자열은 에러 메시지와 로그에 넣지 않는다.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

import httpx

from .errors import ApiError, Code

TIMEOUT = httpx.Timeout(10.0, connect=5.0)
ATTEMPTS = 3
CACHE_MAX = 512

_cache: dict[tuple, tuple[float, Any]] = {}


def clear_cache() -> None:
    _cache.clear()


async def fetch(
    service: str,
    url: str,
    params: dict[str, Any] | None,
    parse: Callable[[httpx.Response], Any],
    *,
    ttl: float = 600,
    cache_key: tuple | None = None,
) -> Any:
    """`parse(resp)` 가 서비스별 오류 판별과 본문 추출을 맡는다.

    parse 가 None 을 돌려주면 '재시도할 만한 일시 장애'로 본다.
    cache_key 는 키를 뺀 요청 식별자 (키가 캐시 키에 남지 않게).
    """
    ck = cache_key
    if ck is not None:
        hit = _cache.get(ck)
        if hit and hit[0] > time.monotonic():
            return hit[1]

    last: str | None = None
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": "korea-opendata-mcp"}) as client:
        for attempt in range(ATTEMPTS):
            try:
                resp = await client.get(url, params=params)
            except httpx.HTTPError as e:
                last = type(e).__name__
            else:
                result = parse(resp)
                if result is not None:
                    if ck is not None and ttl > 0:
                        if len(_cache) >= CACHE_MAX:
                            _cache.pop(next(iter(_cache)))
                        _cache[ck] = (time.monotonic() + ttl, result)
                    return result
                last = f"HTTP {resp.status_code}"
            if attempt < ATTEMPTS - 1:
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise ApiError(Code.UPSTREAM_ERROR, f"{service} 서버 응답 실패 ({last}).",
                   "잠시 후 다시 시도하세요. 대상이 없다는 뜻이 아닙니다.")


def json_or_none(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return None
