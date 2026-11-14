"""FastMCP 인스턴스와 실행 진입점."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from fastmcp import FastMCP

from . import tools
from .config import PROVIDERS, configured, load_env_files

log = logging.getLogger("korea-opendata-mcp")

INSTRUCTIONS = (
    "한국 공공 API 모음입니다: 기상청 날씨, 에어코리아 미세먼지, 공휴일, 한국관광공사 관광·축제(공공데이터포털), "
    "한국은행 환율·기준금리·주요 경제지표(ECOS), 서울 지하철 실시간 도착(서울 열린데이터광장). "
    "서비스마다 API 키가 따로이며, 일부만 설정돼 있을 수 있습니다. "
    "[CONFIG_ERROR]/[AUTH_ERROR] 가 나오면 추측하지 말고 get_service_status 로 키 상태를 확인해 사용자에게 설정을 안내하세요. "
    "[UPSTREAM_ERROR] 는 서버 장애이지 대상이 없다는 뜻이 아닙니다. "
    "날짜는 YYYYMMDD 또는 YYYY-MM-DD, 위치는 도시명(서울, 강릉) 또는 '위도,경도'로 넣습니다."
)

mcp = FastMCP(name="korea-opendata", instructions=INSTRUCTIONS)
tools.register(mcp)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="한국 공공 API(data.go.kr·ECOS·서울시) MCP 서버")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio",
                        help="전송 방식 (기본 stdio). http 는 http://HOST:PORT/mcp")
    parser.add_argument("--host", default="127.0.0.1", help="http 바인드 주소 (기본 로컬 전용)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--env-file", help="API 키를 읽을 .env 파일 경로")
    args = parser.parse_args(argv)

    # stdout 은 stdio JSON-RPC 전용 — 로그는 stderr 로만.
    logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)   # 요청 URL(키 포함) 로그 억제

    if args.env_file:
        os.environ.setdefault("KOREA_OPENDATA_ENV_FILE", args.env_file)
    load_env_files()
    state = configured()
    missing = [p.env for p in PROVIDERS if not state[p.env]]
    if len(missing) == len(PROVIDERS):
        log.warning("API 키가 하나도 설정되지 않았습니다. 도구 호출 시 설정 안내 에러를 반환합니다.")
    elif missing:
        log.info("키 미설정 서비스: %s (해당 도구만 사용 불가)", ", ".join(missing))

    if args.transport == "stdio":
        mcp.run(show_banner=False)
    else:
        mcp.run(transport="http", host=args.host, port=args.port, path="/mcp", show_banner=False)
