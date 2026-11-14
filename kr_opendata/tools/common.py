"""도구 공용 — 날짜 파싱, 숫자 변환, 메타데이터."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ..errors import ApiError, Code

KST = timezone(timedelta(hours=9))
READ_ONLY = {"readOnlyHint": True, "destructiveHint": False,
             "idempotentHint": True, "openWorldHint": True}


def now_kst() -> datetime:
    return datetime.now(KST)


def today_kst() -> date:
    return now_kst().date()


def parse_date(value: str | None, default: date) -> date:
    if not value:
        return default
    digits = re.sub(r"[-./\s]", "", value)
    try:
        return datetime.strptime(digits, "%Y%m%d").date()
    except ValueError:
        raise ApiError(Code.INVALID_PARAM, f"날짜 형식을 해석할 수 없습니다: {value!r}",
                       "YYYYMMDD 또는 YYYY-MM-DD 형식으로 입력하세요 (예: 20261114).") from None


def iso(d: Any) -> str | None:
    s = re.sub(r"\D", "", str(d or ""))
    if len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    if len(s) == 12:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:]}"
    return str(d).strip() or None if d else None


def num(v: Any) -> float | None:
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() else f
