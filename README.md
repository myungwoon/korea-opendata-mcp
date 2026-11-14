# korea-opendata-mcp — 한국 공공 API MCP 서버

공공데이터포털(data.go.kr), 한국은행 경제통계시스템(ECOS), 서울 열린데이터광장의 오픈 API를 Claude, Cursor 같은 MCP 클라이언트에서 쓸 수 있게 해 주는 MCP 서버입니다. [FastMCP](https://gofastmcp.com)로 만들었습니다.

연결하면 이런 질문에 실제 공공 데이터로 답합니다.

- "지금 강릉 날씨 어때? 내일 비 와?"
- "서울 미세먼지 어때? 종로구 측정소 수치는?"
- "올해 남은 공휴일 알려줘"
- "경복궁 근처 관광지 찾아줘", "이번 달 축제 뭐 있어?"
- "최근 한 달 원/달러 환율 추이는?", "기준금리 언제 바뀌었어?"
- "강남역 2호선 언제 와?"

> **API 키는 이 저장소에 들어 있지 않습니다.** 각자 무료로 키를 발급받아 자신의 MCP 클라이언트 설정이나 `.env` 파일에 넣어야 합니다. 서비스마다 키가 따로이고, **필요한 서비스의 키만** 넣으면 됩니다.

## 도구

| 도구 | 하는 일 | 데이터 출처 | 필요한 키 |
|---|---|---|---|
| `get_weather_now` | 현재 날씨 (기온, 습도, 강수, 바람) | 기상청 단기예보 조회서비스 | `DATA_GO_KR_SERVICE_KEY` |
| `get_weather_forecast` | 3일 예보 (최저/최고기온, 강수확률, 하늘상태, 시간별 선택) | 기상청 단기예보 조회서비스 | `DATA_GO_KR_SERVICE_KEY` |
| `get_air_quality` | 미세먼지·초미세먼지·대기질 (시도 평균, 측정소별) | 한국환경공단 에어코리아 | `DATA_GO_KR_SERVICE_KEY` |
| `get_holidays` | 공휴일·대체공휴일, 기념일, 24절기 | 한국천문연구원 특일 정보 | `DATA_GO_KR_SERVICE_KEY` |
| `search_tour_spots` | 관광지·음식점·숙박·문화시설 키워드 검색 | 한국관광공사 국문 관광정보 (TourAPI) | `DATA_GO_KR_SERVICE_KEY` |
| `search_festivals` | 기간별 축제·공연·행사 | 한국관광공사 국문 관광정보 (TourAPI) | `DATA_GO_KR_SERVICE_KEY` |
| `get_exchange_rate_history` | 원화 환율 일별 추이 (USD, JPY, EUR, GBP, CNY) | 한국은행 ECOS | `ECOS_API_KEY` |
| `get_base_rate` | 기준금리 월별 추이와 변경 시점 | 한국은행 ECOS | `ECOS_API_KEY` |
| `get_key_statistics` | 100대 경제지표 최신값 (환율, 금리, 물가, GDP, 고용 등) | 한국은행 ECOS | `ECOS_API_KEY` |
| `search_ecos_statistic` | ECOS 통계표 코드로 직접 조회 (고급) | 한국은행 ECOS | `ECOS_API_KEY` |
| `get_subway_arrival` | 서울 지하철 실시간 도착 정보 | 서울 열린데이터광장 | `SEOUL_OPENAPI_KEY` |
| `get_service_status` | 서비스별 키 설정 여부 (값은 숨김) | — | — |

- 모든 도구는 읽기 전용입니다 (`readOnlyHint`).
- **위치**는 도시명(`서울`, `부산광역시`, `강릉`, `제주`, `경기` 등 40여 곳) 또는 `위도,경도`(`37.5665,126.9780`)로 넣습니다. 날씨 도구는 좌표를 기상청 격자(nx, ny)로 자동 변환합니다.
- **날짜**는 `20261114`, `2026-11-14` 둘 다 됩니다.

## 1. API 키 발급

| 환경변수 | 발급처 | 할 일 |
|---|---|---|
| `DATA_GO_KR_SERVICE_KEY` | [공공데이터포털](https://www.data.go.kr) | 회원가입 후 아래 4개 API를 각각 검색해 **[활용신청]** 합니다. 승인은 대부분 자동이며, 반영까지 1~2시간 걸릴 수 있습니다. 마이페이지의 **일반 인증키**(Decoding 또는 Encoding 아무거나)를 씁니다. |
| `ECOS_API_KEY` | [한국은행 ECOS Open API](https://ecos.bok.or.kr/api/) | 회원가입 후 **인증키 신청**. |
| `SEOUL_OPENAPI_KEY` | [서울 열린데이터광장](https://data.seoul.go.kr) | 회원가입 후 **실시간 지하철 인증키**를 신청합니다 (일반 인증키와 다릅니다). |

공공데이터포털에서 활용신청할 API (검색창에 이름을 넣으세요):

1. 기상청_단기예보 ((구)_동네예보) 조회서비스
2. 한국환경공단_에어코리아_대기오염정보
3. 한국천문연구원_특일 정보
4. 한국관광공사_국문 관광정보 서비스_GW

쓰지 않을 API는 신청하지 않아도 됩니다. 그 API를 쓰는 도구만 `[AUTH_ERROR]`를 냅니다.

> **바로 시험해 보기:** ECOS와 서울 열린데이터광장은 시험용 키 `sample`을 제공합니다. `ECOS_API_KEY=sample`, `SEOUL_OPENAPI_KEY=sample`로 설정하면 키 발급 없이 환율·금리·지하철 도구를 써 볼 수 있습니다 (조회 건수 제한: ECOS 10건, 서울 5건).

## 2. 설치

Python 3.10 이상이 필요합니다.

### 방법 A: `uvx`로 바로 실행 (설치 없이)

[uv](https://docs.astral.sh/uv/)가 있으면 저장소를 내려받지 않아도 됩니다.

```bash
uvx --from git+https://github.com/myungwoon/korea-opendata-mcp korea-opendata-mcp
```

### 방법 B: 저장소 클론

```bash
git clone https://github.com/myungwoon/korea-opendata-mcp.git
cd korea-opendata-mcp
python -m venv .venv
```

```bash
# Windows
.venv\Scripts\pip install -e .
# macOS / Linux
.venv/bin/pip install -e .
```

## 3. API 키 설정

서버는 아래 순서로 키를 찾고, 먼저 찾은 값을 씁니다.

1. **환경변수** — MCP 클라이언트 설정의 `env` 블록에 넣는 방법 (권장)
2. `KOREA_OPENDATA_ENV_FILE` 환경변수 또는 `--env-file` 옵션이 가리키는 `.env` 파일
3. 서버를 실행한 작업 디렉터리(또는 상위)의 `.env`
4. 저장소 루트의 `.env` (방법 B로 클론한 경우)

`.env`를 쓰려면 예시 파일을 복사해 쓸 서비스의 키만 채웁니다. `.env`는 `.gitignore`에 들어 있어 커밋되지 않습니다.

```bash
cp .env.example .env
```

```dotenv
DATA_GO_KR_SERVICE_KEY=공공데이터포털_일반인증키
ECOS_API_KEY=한국은행_ECOS_인증키
SEOUL_OPENAPI_KEY=서울_실시간지하철_인증키
```

- 공공데이터포털 키는 **Decoding 키와 Encoding 키 둘 다** 그대로 넣으면 됩니다 (`%`가 들어 있으면 서버가 한 번 디코딩해 이중 인코딩을 막습니다).
- 키 없이도 서버는 뜹니다. 키가 없는 서비스의 도구를 호출하면 `[CONFIG_ERROR]`와 발급·설정 방법을 돌려줍니다.
- 설정 상태는 `get_service_status` 도구로 확인할 수 있습니다.

## 4. MCP 클라이언트에 연결

### Claude Desktop

`claude_desktop_config.json`에 추가합니다. 파일 위치는 설치 방식에 따라 다릅니다.

| 설치 방식 | 설정 파일 경로 |
|---|---|
| Windows (claude.ai 설치 파일) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Windows (Microsoft Store) | `%LOCALAPPDATA%\Claude-Data\claude_pzs8sxrjxfjjc\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

> 어느 경로인지 헷갈리면 Claude Desktop에서 **설정 → 개발자 → 구성 편집(Edit Config)** 을 누르세요. 앱이 실제로 쓰는 파일이 열립니다. Store 버전은 `%APPDATA%\Claude\`의 파일을 읽지 않습니다.

uvx 사용 시:

```json
{
  "mcpServers": {
    "korea-opendata": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/myungwoon/korea-opendata-mcp", "korea-opendata-mcp"],
      "env": {
        "DATA_GO_KR_SERVICE_KEY": "공공데이터포털_일반인증키",
        "ECOS_API_KEY": "한국은행_ECOS_인증키",
        "SEOUL_OPENAPI_KEY": "서울_실시간지하철_인증키"
      }
    }
  }
}
```

클론한 경우 (경로는 자신의 위치로 바꾸세요):

```json
{
  "mcpServers": {
    "korea-opendata": {
      "command": "C:\\path\\to\\korea-opendata-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\korea-opendata-mcp\\server.py"],
      "env": { "ECOS_API_KEY": "한국은행_ECOS_인증키" }
    }
  }
}
```

쓰지 않는 서비스의 키는 `env`에서 빼도 됩니다. 클론한 경우 `env` 대신 저장소 루트의 `.env`에 키를 넣어도 됩니다. 파일을 고친 뒤에는 Claude를 **트레이 아이콘에서 완전히 종료**하고 다시 켜야 적용됩니다.

### Claude Code

```bash
claude mcp add korea-opendata -e DATA_GO_KR_SERVICE_KEY=키 -e ECOS_API_KEY=키 -e SEOUL_OPENAPI_KEY=키 -- uvx --from git+https://github.com/myungwoon/korea-opendata-mcp korea-opendata-mcp
```

### Cursor 등 다른 클라이언트

`command`/`args`/`env` 형식은 위 Claude Desktop 예시와 같습니다. 클라이언트의 MCP 설정 파일(예: Cursor는 `~/.cursor/mcp.json`)에 넣으세요.

### HTTP로 실행

```bash
korea-opendata-mcp --transport http --port 8000   # http://127.0.0.1:8000/mcp
```

기본은 로컬(`127.0.0.1`)에만 바인드합니다. 인증 기능이 없으므로 외부에 공개하려면 앞단에 인증 프록시를 두세요.

## 응답과 에러

실패하면 첫 줄이 대괄호 코드로 시작하고, 다음에 해볼 일을 번호로 붙입니다.

```
[AUTH_ERROR] 공공데이터포털 기상청 단기예보: 등록되지 않은 서비스키입니다 (SERVICE_KEY_IS_NOT_REGISTERED_ERROR).
제안:
  1. data.go.kr 마이페이지에서 '기상청 단기예보' 활용신청이 승인됐는지 확인하세요 (승인 후 반영까지 최대 1~2시간).
  2. DATA_GO_KR_SERVICE_KEY 에는 포털의 'Decoding' 또는 'Encoding' 일반 인증키를 그대로 넣으면 됩니다.
```

| 코드 | 뜻 |
|---|---|
| `CONFIG_ERROR` | 해당 서비스의 API 키가 설정되지 않음 |
| `AUTH_ERROR` | 키 오류, 활용신청 미승인, 호출 한도 초과 |
| `INVALID_PARAMETER` | 위치·날짜·코드 등 인자 오류 |
| `NOT_FOUND` | 측정소·역 등 대상이 없음 |
| `UPSTREAM_ERROR` | 외부 서버 장애. **대상이 없다는 뜻이 아닙니다** |

- 네트워크 오류와 5xx 응답은 최대 3번까지 재시도합니다.
- 응답을 짧게 캐시해 호출 한도를 아낍니다 (지하철 20초, 날씨·대기질 5~30분, 공휴일 하루).
- API 키는 에러 메시지와 로그에 남기지 않습니다.

## 개발

```bash
pip install -e ".[dev]"
pytest
```

테스트는 외부 API를 목킹하므로 키 없이 돌아갑니다.

### 구조

```
kr_opendata/
├─ app.py          FastMCP 인스턴스, 실행 옵션
├─ config.py       서비스별 API 키 로딩 (환경변수 · .env)
├─ http.py         공용 호출: 재시도, 캐시
├─ providers.py    data.go.kr / ECOS / 서울시 응답·오류 형식 통일
├─ geo.py          지명 → 좌표, 기상청 격자 변환, 시도명
└─ tools/          weather, air, holiday, tour, finance, subway
```

새 공공데이터포털 API를 붙일 때는 `providers.data_go_kr()`로 호출하고 `items_of()`로 목록을 꺼내면 인증·오류 처리를 그대로 재사용할 수 있습니다.

## 데이터 출처와 이용 조건

- 기상청, 한국환경공단, 한국천문연구원, 한국관광공사 데이터: [공공데이터포털](https://www.data.go.kr)
- 경제 통계: [한국은행 경제통계시스템(ECOS)](https://ecos.bok.or.kr)
- 지하철 실시간 도착: [서울 열린데이터광장](https://data.seoul.go.kr)

각 서비스의 이용약관을 따르고 출처를 표기하세요. 에어코리아 실시간 자료는 확정되지 않은 측정값입니다. 이 프로젝트는 위 기관들과 관련이 없는 비공식 도구입니다.

## 라이선스

[MIT](LICENSE)
