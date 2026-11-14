"""서비스별 호출 래퍼 — 응답 형식과 오류 표현이 서비스마다 달라 여기서 통일한다."""

from __future__ import annotations

import re
from typing import Any

import httpx

from . import http
from .config import DATA_GO_KR, ECOS, SEOUL, get_key
from .errors import ApiError, Code

# --- 공공데이터포털 ----------------------------------------------------------

DATA_GO_KR_AUTH_CODES = {
    "20": "서비스 접근이 거부되었습니다 (SERVICE_ACCESS_DENIED_ERROR).",
    "22": "일일 호출 한도를 넘었습니다 (LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR).",
    "30": "등록되지 않은 서비스키입니다 (SERVICE_KEY_IS_NOT_REGISTERED_ERROR).",
    "31": "활용 기간이 만료되었습니다 (DEADLINE_HAS_EXPIRED_ERROR).",
    "32": "등록되지 않은 IP입니다 (UNREGISTERED_IP_ERROR).",
}


def _data_go_kr_auth(code: str, msg: str, api_name: str) -> ApiError:
    return ApiError(
        Code.AUTH_ERROR, f"공공데이터포털 {api_name}: {DATA_GO_KR_AUTH_CODES.get(code, msg)}",
        f"data.go.kr 마이페이지에서 '{api_name}' 활용신청이 승인됐는지 확인하세요 (승인 후 반영까지 최대 1~2시간).",
        "DATA_GO_KR_SERVICE_KEY 에는 포털의 'Decoding' 또는 'Encoding' 일반 인증키를 그대로 넣으면 됩니다.",
    )


def _data_go_kr_parser(api_name: str):
    def parse(resp: httpx.Response) -> Any:
        text = resp.text
        if "OpenAPI_ServiceResponse" in text or "returnReasonCode" in text:
            code = (re.search(r'returnReasonCode"?\s*[:>]\s*"?(\d+)', text) or [None, ""])[1]
            msg = (re.search(r'errMsg"?\s*[:>]\s*"?([A-Z_]+)', text) or [None, "알 수 없는 오류"])[1]
            if code in DATA_GO_KR_AUTH_CODES:
                raise _data_go_kr_auth(code, msg, api_name)
            if code in ("1", "4", "5"):        # 서버 내부 오류 계열 → 재시도
                return None
            raise ApiError(Code.INVALID_PARAM, f"공공데이터포털 {api_name} 오류: {msg} (코드 {code})")
        if resp.status_code >= 500 or resp.status_code == 429:
            return None
        if resp.status_code in (401, 403):
            raise _data_go_kr_auth("30", "Unauthorized", api_name)
        if resp.status_code >= 400:
            raise ApiError(Code.UPSTREAM_ERROR, f"공공데이터포털 {api_name}이(가) HTTP {resp.status_code} 를 반환했습니다.")
        data = http.json_or_none(resp)
        if not isinstance(data, dict) or "response" not in data:
            # 일시적으로 XML 오류 페이지 등을 돌려주는 경우가 있다
            return None
        header = data["response"].get("header", {})
        rc = str(header.get("resultCode", "00"))
        if rc in ("00", "0000", "03"):        # 03 = NODATA_ERROR → 빈 결과
            return data["response"].get("body") or {}
        if rc in DATA_GO_KR_AUTH_CODES:
            raise _data_go_kr_auth(rc, header.get("resultMsg", ""), api_name)
        if rc in ("01", "02", "04", "05"):
            return None
        raise ApiError(Code.INVALID_PARAM, f"공공데이터포털 {api_name} 오류: {header.get('resultMsg')} (코드 {rc})",
                       "인자 형식을 확인하세요.")
    return parse


async def data_go_kr(api_name: str, url: str, params: dict[str, Any], *, ttl: float = 600) -> dict[str, Any]:
    key = get_key(DATA_GO_KR)
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    ck = ("data.go.kr", url, tuple(sorted(clean.items())))
    return await http.fetch(f"공공데이터포털 {api_name}", url, {"serviceKey": key, **clean},
                            _data_go_kr_parser(api_name), ttl=ttl, cache_key=ck)


def items_of(body: dict[str, Any]) -> list[dict[str, Any]]:
    """body.items 가 list / {"item": list|dict} / "" 중 무엇이든 list 로."""
    items = body.get("items")
    if isinstance(items, list):
        return items
    if isinstance(items, dict):
        item = items.get("item")
        if isinstance(item, list):
            return item
        if isinstance(item, dict):
            return [item]
    return []


# --- 한국은행 ECOS -----------------------------------------------------------

ECOS_BASE = "https://ecos.bok.or.kr/api"


def _ecos_parser(service: str):
    def parse(resp: httpx.Response) -> Any:
        if resp.status_code >= 500 or resp.status_code == 429:
            return None
        data = http.json_or_none(resp)
        if not isinstance(data, dict):
            return None
        if "RESULT" in data:
            code = data["RESULT"].get("CODE", "")
            msg = data["RESULT"].get("MESSAGE", "")
            if code == "INFO-200":           # 데이터 없음
                return {"row": [], "list_total_count": 0}
            if code in ("INFO-100", "ERROR-602"):
                raise ApiError(Code.AUTH_ERROR, f"한국은행 ECOS: {msg} ({code})",
                               "ECOS_API_KEY 가 https://ecos.bok.or.kr/api/ 에서 발급받은 키와 같은지 확인하세요.",
                               "호출 한도를 넘었다면 잠시 후 다시 시도하세요.")
            if code.startswith("ERROR-5"):
                return None
            raise ApiError(Code.INVALID_PARAM, f"한국은행 ECOS 오류: {msg} ({code})")
        if service not in data:
            return None
        return data[service]
    return parse


async def ecos(service: str, *segments: str | int, ttl: float = 1800) -> dict[str, Any]:
    key = get_key(ECOS)
    if key == "sample" and len(segments) >= 2:      # 샘플 키는 최대 10건
        segments = (segments[0], min(int(segments[1]), 10), *segments[2:])
    path = "/".join(str(s) for s in segments)
    url = f"{ECOS_BASE}/{service}/{key}/json/kr/{path}"
    return await http.fetch("한국은행 ECOS", url, None, _ecos_parser(service), ttl=ttl,
                            cache_key=("ecos", service, path))


# --- 서울 열린데이터광장 -----------------------------------------------------

SEOUL_SUBWAY_BASE = "http://swopenapi.seoul.go.kr/api/subway"


def _seoul_parser(list_key: str, sample: bool = False):
    def parse(resp: httpx.Response) -> Any:
        if resp.status_code >= 500 or resp.status_code == 429:
            return None
        data = http.json_or_none(resp)
        if not isinstance(data, dict):
            return None
        info = data.get("errorMessage") or data      # 정상: errorMessage, 오류: 최상위에 code
        code = str(info.get("code", ""))
        msg = info.get("message", "")
        if code == "INFO-000":
            return data.get(list_key, [])
        if code == "INFO-200":
            return []
        if code in ("INFO-100", "ERROR-300"):
            raise ApiError(Code.AUTH_ERROR, f"서울 열린데이터광장: {msg} ({code})",
                           "SEOUL_OPENAPI_KEY 에 '실시간 지하철' 인증키를 넣었는지 확인하세요 (일반 인증키와 다름).")
        if code.startswith("ERROR-5"):
            return None
        if sample and code == "ERROR-336":
            # 샘플 키는 '서울'역만 허용하고, 다른 역은 엉뚱한 건수 오류를 돌려준다
            raise ApiError(Code.AUTH_ERROR, "시험용 sample 키로는 '서울'역만 조회할 수 있습니다.",
                           "https://data.seoul.go.kr 에서 '실시간 지하철' 인증키를 발급받아 SEOUL_OPENAPI_KEY 에 넣으세요.")
        raise ApiError(Code.INVALID_PARAM, f"서울 열린데이터광장 오류: {msg} ({code})")
    return parse


async def seoul_subway(service: str, start: int, end: int, arg: str, list_key: str) -> list[dict[str, Any]]:
    key = get_key(SEOUL)
    if key == "sample":                  # 샘플 키는 0~5 범위만 허용된다
        start, end = 0, 5
    url = f"{SEOUL_SUBWAY_BASE}/{key}/json/{service}/{start}/{end}/{arg}"
    # 실시간 정보라 캐시는 아주 짧게
    return await http.fetch("서울 열린데이터광장", url, None, _seoul_parser(list_key, key == "sample"), ttl=20,
                            cache_key=("seoul", service, start, end, arg))
