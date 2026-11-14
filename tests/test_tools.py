"""도구 동작 테스트 — FastMCP in-memory 클라이언트 + respx 로 외부 API 목킹 (키 없이 실행)."""

from __future__ import annotations

import re
from datetime import datetime

import httpx
import pytest
import respx
from fastmcp import Client

from kr_opendata import geo, http
from kr_opendata.app import mcp
from kr_opendata.tools import common, weather

DG = "https://apis.data.go.kr"
ECOS_RE = re.compile(r"https://ecos\.bok\.or\.kr/api/(\w+)/([^/]+)/json/kr/(.*)")
SEOUL_RE = re.compile(r"http://swopenapi\.seoul\.go\.kr/api/subway/([^/]+)/json/(.*)")
NOW = datetime(2026, 11, 14, 15, 5, tzinfo=common.KST)


def dg_ok(items, **body):
    return httpx.Response(200, json={"response": {
        "header": {"resultCode": "00", "resultMsg": "NORMAL_SERVICE"},
        "body": {"items": {"item": items} if items is not None else "", **body}}})


DG_NOT_REGISTERED = httpx.Response(403, json={"OpenAPI_ServiceResponse": {"cmmMsgHeader": {
    "errMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR", "returnAuthMsg": "등록되지 않은 서비스키",
    "returnReasonCode": "30"}}})


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "dg-key%2Babc%3D%3D")   # Encoding 키 형태
    monkeypatch.setenv("ECOS_API_KEY", "ecos-key")
    monkeypatch.setenv("SEOUL_OPENAPI_KEY", "seoul-key")
    monkeypatch.setattr(common, "now_kst", lambda: NOW)

    async def no_sleep(_):
        return None
    monkeypatch.setattr(http.asyncio, "sleep", no_sleep)
    http.clear_cache()
    yield
    http.clear_cache()


async def call(name, args):
    async with Client(mcp) as c:
        return await c.call_tool(name, args, raise_on_error=False)


def text(r):
    return r.content[0].text


def data(r):
    return r.structured_content


# --- 공통 -------------------------------------------------------------------

async def test_tools_registered():
    async with Client(mcp) as c:
        names = {t.name for t in await c.list_tools()}
    assert len(names) == 12 and "get_service_status" in names


async def test_service_status_hides_values(monkeypatch):
    monkeypatch.delenv("SEOUL_OPENAPI_KEY")
    r = await call("get_service_status", {})
    s = {x["env"]: x for x in data(r)["services"]}
    assert s["ECOS_API_KEY"]["configured"] is True
    assert s["SEOUL_OPENAPI_KEY"]["configured"] is False
    assert "ecos-key" not in text(r)


async def test_missing_key_only_blocks_that_service(monkeypatch):
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY")
    r = await call("get_holidays", {"year": 2026, "month": 12})
    assert text(r).startswith("[CONFIG_ERROR]") and "DATA_GO_KR_SERVICE_KEY" in text(r)


def test_grid_conversion_matches_kma_reference():
    assert geo.latlon_to_grid(37.5665, 126.9780) == (60, 127)    # 서울
    assert geo.latlon_to_grid(35.1796, 129.0756) == (98, 76)     # 부산
    assert geo.latlon_to_grid(33.4996, 126.5312) == (53, 38)     # 제주


def test_base_times():
    assert weather.ncst_base(datetime(2026, 11, 14, 15, 5)) == ("20261114", "1400")
    assert weather.ncst_base(datetime(2026, 11, 14, 15, 45)) == ("20261114", "1500")
    assert weather.vilage_base(datetime(2026, 11, 14, 15, 5)) == ("20261114", "1400")
    assert weather.vilage_base(datetime(2026, 11, 14, 1, 0)) == ("20261113", "2300")


def test_place_resolution():
    assert geo.resolve_place("부산광역시").name == "부산"
    assert geo.resolve_place("37.5,127.0").lat == 37.5
    assert geo.resolve_sido("수원") == "경기"
    assert geo.resolve_sido("강원특별자치도") == "강원"


async def test_unknown_place():
    r = await call("get_weather_now", {"location": "아틀란티스"})
    assert text(r).startswith("[INVALID_PARAMETER]")


# --- 공공데이터포털 ----------------------------------------------------------

@respx.mock
async def test_weather_now_and_encoding_key_is_decoded():
    route = respx.get(f"{DG}/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst").mock(return_value=dg_ok([
        {"category": "T1H", "obsrValue": "12.3"}, {"category": "REH", "obsrValue": "55"},
        {"category": "PTY", "obsrValue": "0"}, {"category": "RN1", "obsrValue": "0"},
        {"category": "WSD", "obsrValue": "2.1"}, {"category": "VEC", "obsrValue": "270"}]))
    r = await call("get_weather_now", {"location": "서울"})
    d = data(r)
    assert d["temperature_c"] == 12.3 and d["precipitation_type"] == "없음"
    q = route.calls.last.request.url.params
    assert q["serviceKey"] == "dg-key+abc=="            # 한 번 디코딩 → 이중 인코딩 방지
    assert (q["nx"], q["ny"], q["base_time"]) == ("60", "127", "1400")


@respx.mock
async def test_weather_forecast_daily_summary():
    items = []
    for t, tmp, pop, sky in [("0600", 5, 10, "1"), ("1500", 14, 60, "4"), ("1800", 10, 30, "4")]:
        items += [{"fcstDate": "20261114", "fcstTime": t, "category": "TMP", "fcstValue": str(tmp)},
                  {"fcstDate": "20261114", "fcstTime": t, "category": "POP", "fcstValue": str(pop)},
                  {"fcstDate": "20261114", "fcstTime": t, "category": "SKY", "fcstValue": sky},
                  {"fcstDate": "20261114", "fcstTime": t, "category": "PTY", "fcstValue": "1" if pop >= 60 else "0"}]
    respx.get(f"{DG}/1360000/VilageFcstInfoService_2.0/getVilageFcst").mock(return_value=dg_ok(items))
    r = await call("get_weather_forecast", {"location": "강릉", "days": 1})
    day = data(r)["days"][0]
    assert (day["min_temp_c"], day["max_temp_c"], day["max_precip_prob_pct"]) == (5, 14, 60)
    assert day["sky"] == "흐림" and day["precipitation_types"] == ["비"]


@respx.mock
async def test_data_go_kr_unregistered_key_is_auth_error():
    respx.get(url__startswith=f"{DG}/B552584/").mock(return_value=DG_NOT_REGISTERED)
    r = await call("get_air_quality", {"region": "서울"})
    assert text(r).startswith("[AUTH_ERROR]")
    assert "활용신청" in text(r) and "dg-key" not in text(r)


@respx.mock
async def test_air_quality_summary_and_station_filter():
    respx.get(url__startswith=f"{DG}/B552584/").mock(return_value=httpx.Response(200, json={"response": {
        "header": {"resultCode": "00"}, "body": {"items": [
            {"stationName": "종로구", "sidoName": "서울", "dataTime": "2026-11-14 15:00", "pm10Value": "40",
             "pm25Value": "20", "pm10Grade": "2", "pm25Grade": "2"},
            {"stationName": "중구", "sidoName": "서울", "dataTime": "2026-11-14 15:00", "pm10Value": "-",
             "pm25Value": "10", "pm10Grade": "", "pm25Grade": "1"}]}}}))
    r = await call("get_air_quality", {"region": "서울특별시"})
    s = data(r)["summary"]
    assert s["pm10_avg"] == 40 and s["pm25_avg"] == 15 and s["pm25_grade_1h"] == "좋음"
    assert data(r)["stations"][0]["pm25_grade_24h"] == "보통"
    r = await call("get_air_quality", {"region": "서울", "station": "종로"})
    assert len(data(r)["stations"]) == 1
    r = await call("get_air_quality", {"region": "서울", "station": "없는곳"})
    assert text(r).startswith("[NOT_FOUND]")


@respx.mock
async def test_holidays_handles_single_dict_and_empty():
    def handler(request):
        m = request.url.params["solMonth"]
        if m == "12":
            return dg_ok({"locdate": 20261225, "dateName": "기독탄신일", "isHoliday": "Y"})
        return dg_ok(None)
    respx.get(f"{DG}/B090041/openapi/service/SpcdeInfoService/getRestDeInfo").mock(side_effect=handler)
    r = await call("get_holidays", {"year": 2026})
    d = data(r)
    assert d["count"] == 1 and d["dates"][0] == {"date": "2026-12-25", "weekday": "금",
                                                  "name": "기독탄신일", "is_holiday": True}


@respx.mock
async def test_tour_search():
    route = respx.get(f"{DG}/B551011/KorService2/searchKeyword2").mock(return_value=dg_ok(
        [{"contentid": "126508", "contenttypeid": "12", "title": "경복궁", "addr1": "서울특별시 종로구 사직로 161",
          "mapx": "126.97", "mapy": "37.57", "firstimage": ""}], totalCount=1))
    r = await call("search_tour_spots", {"keyword": "경복궁", "content_type": "attraction"})
    p = data(r)["places"][0]
    assert p["type"] == "관광지" and p["image"] is None and p["lat"] == 37.57
    q = route.calls.last.request.url.params
    assert q["contentTypeId"] == "12" and q["MobileOS"] == "ETC" and q["_type"] == "json"


@respx.mock
async def test_server_outage_retries():
    route = respx.get(url__startswith=f"{DG}/B551011/").mock(return_value=httpx.Response(503, text="busy"))
    r = await call("search_festivals", {})
    assert text(r).startswith("[UPSTREAM_ERROR]") and route.call_count == http.ATTEMPTS


# --- 한국은행 ECOS -----------------------------------------------------------

@respx.mock
async def test_exchange_rate_history():
    route = respx.get(url__regex=ECOS_RE.pattern).mock(return_value=httpx.Response(200, json={"StatisticSearch": {
        "list_total_count": 2, "row": [{"TIME": "20261112", "DATA_VALUE": "1340.5"},
                                       {"TIME": "20261113", "DATA_VALUE": "1336.7"}]}}))
    r = await call("get_exchange_rate_history", {"currency": "USD"})
    d = data(r)
    assert d["latest"] == {"time": "2026-11-13", "value": 1336.7}
    assert d["stats"]["change"] == -3.8
    svc, key, path = ECOS_RE.match(str(route.calls.last.request.url)).groups()
    assert svc == "StatisticSearch" and key == "ecos-key" and path.endswith("731Y001/D/20261015/20261114/0000001")


@respx.mock
async def test_ecos_invalid_key_and_no_data():
    respx.get(url__regex=ECOS_RE.pattern).mock(return_value=httpx.Response(200, json={
        "RESULT": {"CODE": "INFO-100", "MESSAGE": "인증키가 유효하지 않습니다."}}))
    r = await call("get_key_statistics", {})
    assert text(r).startswith("[AUTH_ERROR]") and "ecos-key" not in text(r)


@respx.mock
async def test_base_rate_changes():
    respx.get(url__regex=ECOS_RE.pattern).mock(return_value=httpx.Response(200, json={"StatisticSearch": {
        "row": [{"TIME": "202609", "DATA_VALUE": "3.25"}, {"TIME": "202610", "DATA_VALUE": "3"},
                {"TIME": "202611", "DATA_VALUE": "3"}]}}))
    d = data(await call("get_base_rate", {"months": 3}))
    assert d["current"]["value"] == 3 and d["changes"] == [{"month": "202610", "from": 3.25, "to": 3}]


# --- 서울 열린데이터광장 -----------------------------------------------------

@respx.mock
async def test_subway_arrival():
    route = respx.get(url__regex=SEOUL_RE.pattern).mock(return_value=httpx.Response(200, json={
        "errorMessage": {"code": "INFO-000", "message": "정상 처리되었습니다."},
        "realtimeArrivalList": [
            {"subwayId": "1002", "updnLine": "내선", "trainLineNm": "성수행 - 역삼방면", "bstatnNm": "성수",
             "arvlMsg2": "전역 도착", "arvlMsg3": "교대", "barvlDt": "120", "lstcarAt": "0"},
            {"subwayId": "1077", "updnLine": "하행", "arvlMsg2": "강남 도착", "barvlDt": "0", "lstcarAt": "0"}]}))
    r = await call("get_subway_arrival", {"station": "강남역", "line": "2호선"})
    d = data(r)
    assert d["station"] == "강남" and d["count"] == 1 and d["trains"][0]["arrival_in_sec"] == 120
    assert "/realtimeStationArrival/0/30/" in str(route.calls.last.request.url)


@respx.mock
async def test_subway_no_data_is_not_found():
    respx.get(url__regex=SEOUL_RE.pattern).mock(return_value=httpx.Response(200, json={
        "status": 500, "code": "INFO-200", "message": "해당하는 데이터가 없습니다."}))
    r = await call("get_subway_arrival", {"station": "없는역"})
    assert text(r).startswith("[NOT_FOUND]")


@respx.mock
async def test_subway_sample_key_other_station_explains_limit(monkeypatch):
    monkeypatch.setenv("SEOUL_OPENAPI_KEY", "sample")
    route = respx.get(url__regex=SEOUL_RE.pattern).mock(return_value=httpx.Response(200, json={
        "status": 500, "code": "ERROR-336", "message": "데이터요청은 한번에 최대 1000건을 넘을 수 없습니다."}))
    r = await call("get_subway_arrival", {"station": "강남"})
    assert text(r).startswith("[AUTH_ERROR]") and "서울" in text(r)
    assert "/realtimeStationArrival/0/5/" in str(route.calls.last.request.url)
