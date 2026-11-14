"""API 키 로딩 — 키는 코드에 넣지 않고 사용자 환경에서 읽는다.

서비스마다 키가 따로 있다. 쓰지 않을 서비스의 키는 비워 두면 되고,
그 서비스의 도구만 [CONFIG_ERROR] 로 설정 방법을 안내한다.

우선순위 (먼저 찾은 값 사용):
  1. 환경변수  (MCP 클라이언트 설정의 "env" 블록 권장)
  2. KOREA_OPENDATA_ENV_FILE 또는 --env-file 이 가리키는 .env
  3. 현재 작업 디렉터리(및 상위)의 .env
  4. 이 프로젝트 루트의 .env  (git clone 해서 쓰는 경우)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from dotenv import find_dotenv, load_dotenv

from .errors import ApiError, Code

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Provider:
    env: str
    name: str
    signup: str
    note: str = ""


DATA_GO_KR = Provider(
    "DATA_GO_KR_SERVICE_KEY", "공공데이터포털(data.go.kr)", "https://www.data.go.kr",
    "키 발급 후 사용할 API마다 [활용신청]을 해야 합니다 (기상청 단기예보, 에어코리아 대기오염정보, "
    "한국천문연구원 특일정보, 한국관광공사 국문 관광정보).")
ECOS = Provider("ECOS_API_KEY", "한국은행 ECOS", "https://ecos.bok.or.kr/api/")
SEOUL = Provider("SEOUL_OPENAPI_KEY", "서울 열린데이터광장", "https://data.seoul.go.kr",
                 "지하철 실시간 도착정보는 [실시간 지하철 인증키]를 따로 신청해야 합니다.")
PROVIDERS = (DATA_GO_KR, ECOS, SEOUL)


def load_env_files() -> None:
    explicit = os.environ.get("KOREA_OPENDATA_ENV_FILE")
    if explicit:
        load_dotenv(Path(explicit).expanduser(), override=False)
    found = find_dotenv(usecwd=True)
    if found:
        load_dotenv(found, override=False)
    project_env = PROJECT_ROOT / ".env"
    if project_env.is_file():
        load_dotenv(project_env, override=False)


def get_key(p: Provider) -> str:
    key = os.environ.get(p.env, "").strip().strip('"').strip("'")
    if not key:
        hints = [f"{p.signup} 에서 키를 발급받으세요."]
        if p.note:
            hints.append(p.note)
        hints += [f'MCP 클라이언트 설정의 "env" 에 "{p.env}": "발급받은키" 를 넣거나 .env 파일에 {p.env}=발급받은키 를 적으세요.',
                  "설정 후 MCP 클라이언트를 재시작하세요."]
        raise ApiError(Code.CONFIG_ERROR, f"{p.name} API 키가 설정되지 않았습니다 (환경변수 {p.env}).", *hints)
    if p is DATA_GO_KR and "%" in key:
        # 포털의 'Encoding' 키를 넣어도 동작하게 한 번 디코딩한다 (httpx 가 다시 인코딩함).
        key = unquote(key)
    return key


def is_sample(p: Provider) -> bool:
    """ECOS·서울시는 시험용 'sample' 키를 제공한다 (조회 건수 제한)."""
    return os.environ.get(p.env, "").strip() == "sample"


def configured() -> dict[str, bool]:
    return {p.env: bool(os.environ.get(p.env, "").strip()) for p in PROVIDERS}
