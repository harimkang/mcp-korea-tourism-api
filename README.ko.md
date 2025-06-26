# 한국 관광 API MCP 서버 ✈️

<!-- Badges -->

[![smithery badge](https://smithery.ai/badge/@harimkang/mcp-korea-tourism-api)](https://smithery.ai/interface/@harimkang/mcp-korea-tourism-api)
[![PyPI version](https://badge.fury.io/py/mcp-korea-tourism-api.svg)](https://badge.fury.io/py/mcp-korea-tourism-api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI Tests](https://github.com/harimkang/mcp-korea-tourism-api/actions/workflows/ci.yml/badge.svg)](https://github.com/harimkang/mcp-korea-tourism-api/actions/workflows/ci.yml)

AI 어시스턴트 내에서 직접 대한민국 관광의 경이로움을 경험하세요! 이 프로젝트는 공식 한국관광공사(KTO) API를 기반으로 하는 모델 컨텍스트 프로토콜(MCP) 서버를 제공합니다. AI가 한국 전역의 활기찬 축제, 고요한 사찰, 맛있는 레스토랑, 편안한 숙박 시설 등을 발견할 수 있도록 지원합니다.

**링크:**

- **PyPI 패키지:** [https://pypi.org/project/mcp-korea-tourism-api/](https://pypi.org/project/mcp-korea-tourism-api/)
- **GitHub 저장소:** [https://github.com/harimkang/mcp-korea-tourism-api](https://github.com/harimkang/mcp-korea-tourism-api)
- **릴리스:** [https://github.com/harimkang/mcp-korea-tourism-api/releases](https://github.com/harimkang/mcp-korea-tourism-api/releases)

## ✨ 특징

- **포괄적인 검색:** 키워드, 지역 또는 위치를 통해 관광지, 문화 유적지, 행사, 음식, 숙박, 쇼핑 정보를 찾아보세요.
- **풍부한 상세 정보:** 설명, 운영 시간, 입장료, 사진, 주소, 연락처 정보를 확인하세요.
- **위치 기반:** 특정 GPS 좌표 근처의 명소를 찾아보세요.
- **시기적절한 정보:** 날짜 범위를 기준으로 축제 및 행사를 찾아보세요.
- **다국어 지원:** KTO API에서 지원하는 다양한 언어(영어 포함)로 정보를 얻으세요.
  - **지원 언어**: 영어, 일본어, 중국어 간체, 중국어 번체, 러시아어, 스페인어, 독일어, 프랑스어
- **효율성 및 복원력:**
  - **응답 캐싱:** TTL(Time-To-Live) 캐싱을 사용하여 결과를 저장하고 중복 API 호출을 줄여 속도를 향상시킵니다.
  - **속도 제한:** API 사용 제한을 준수하여 오류를 방지합니다.
  - **자동 재시도:** 일시적인 네트워크 또는 서버 문제 발생 시 자동으로 요청을 재시도합니다.
- **MCP 표준:** 모델 컨텍스트 프로토콜을 지원하는 AI 어시스턴트와 원활하게 통합됩니다.

## ⚠️ 사전 준비 사항

시작하기 전에 **반드시** **한국관광공사(KTO) 데이터 포털**에서 API 키를 발급받아야 합니다.

1.  [KTO 데이터 포털](https://www.data.go.kr/) (또는 해당 관광 API의 특정 포털)을 방문합니다.
2.  "TourAPI" 서비스(예: `areaBasedList`, `searchKeyword`, `detailCommon` 등 정보 제공 서비스)에 대한 API 키를 등록하고 요청합니다.
3.  **서비스 키(API 키)**를 안전하게 보관합니다. 설치 또는 런타임 시 필요합니다.

> 각 언어별 요청을 위해서는 아래 API를 신청해야 합니다.
>
> - 영어: https://www.data.go.kr/data/15101753/openapi.do
> - 일본어: https://www.data.go.kr/data/15101760/openapi.do
> - 중국어 간체: https://www.data.go.kr/data/15101764/openapi.do
> - 중국어 번체: https://www.data.go.kr/data/15101769/openapi.do
> - 러시아어: https://www.data.go.kr/data/15101831/openapi.do
> - 스페인어: https://www.data.go.kr/data/15101811/openapi.do
> - 독일어: https://www.data.go.kr/data/15101805/openapi.do
> - 프랑스어: https://www.data.go.kr/data/15101808/openapi.do

## 🚀 설치 및 실행

`uv` (빠른 Python 패키지 설치 및 실행 도구) 또는 `Docker`를 사용하여 이 MCP 서버를 실행할 수 있습니다.

### Smithery를 통한 설치

[Smithery](https://smithery.ai/server/@harimkang/mcp-korea-tourism-api)를 통해 Claude 데스크톱용 한국 관광 API MCP 서버를 자동으로 설치하려면:

```bash
npx -y @smithery/cli install @harimkang/mcp-korea-tourism-api --client claude
```

### 옵션 1: `uv` 사용 (로컬 개발에 권장)

1.  **저장소 복제:**
    ```bash
    git clone https://github.com/harimkang/mcp-korea-tourism-api.git
    cd mcp-korea-tourism-api
    ```
2.  **API 키 환경 변수 설정:**
    `"YOUR_KTO_API_KEY"`를 발급받은 실제 키로 바꾸세요.

    ```bash
    # macOS/Linux
    export KOREA_TOURISM_API_KEY="YOUR_KTO_API_KEY"

    # Windows (명령 프롬프트)
    # set KOREA_TOURISM_API_KEY="YOUR_KTO_API_KEY"

    # Windows (PowerShell)
    # $env:KOREA_TOURISM_API_KEY="YOUR_KTO_API_KEY"
    ```

    _참고: 영구 저장을 위해 이 줄을 셸 설정 파일(예: `.zshrc`, `.bashrc`)에 추가하거나 시스템 환경 변수 설정을 사용하세요._

3.  **의존성 설치 및 서버 실행:**
    이 명령어는 `uv`를 사용하여 `uv.lock` (사용 가능한 경우) 또는 `pyproject.toml`을 기반으로 의존성을 설치한 다음 서버 모듈을 실행합니다.

    ```bash
    # 의존성 설치
    uv sync

    # 기본값: stdio 전송 방식 (MCP 클라이언트용)
    uv run -m mcp_tourism.server

    # HTTP 전송 방식 (웹 애플리케이션용)
    uv run -m mcp_tourism.server --transport streamable-http --host 127.0.0.1 --port 8000

    # SSE 전송 방식 (실시간 애플리케이션용)
    uv run -m mcp_tourism.server --transport sse --host 127.0.0.1 --port 8080

    # 환경 변수 사용
    export MCP_TRANSPORT=streamable-http
    export MCP_HOST=0.0.0.0
    export MCP_PORT=3000
    uv run -m mcp_tourism.server
    ```

    서버가 시작되고 지정된 전송 프로토콜을 통해 MCP 요청을 수신 대기합니다.

### 옵션 2: Docker 사용 (격리된 환경/배포에 권장)

1.  **저장소 복제:**
    ```bash
    git clone https://github.com/harimkang/mcp-korea-tourism-api.git
    cd mcp-korea-tourism-api
    ```
2.  **Docker 이미지 빌드:**
    다양한 전송 구성으로 이미지를 빌드할 수 있습니다:

    ```bash
    # 기본 빌드 (stdio 전송 방식)
    docker build -t mcp-korea-tourism-api .

    # HTTP 전송 구성으로 빌드
    docker build -t mcp-korea-tourism-api \
      --build-arg MCP_TRANSPORT=streamable-http \
      --build-arg MCP_HOST=0.0.0.0 \
      --build-arg MCP_PORT=8000 \
      --build-arg MCP_PATH=/mcp \
      --build-arg MCP_LOG_LEVEL=INFO \
      .

    # SSE 전송 구성으로 빌드
    docker build -t mcp-korea-tourism-api \
      --build-arg MCP_TRANSPORT=sse \
      --build-arg MCP_HOST=0.0.0.0 \
      --build-arg MCP_PORT=8080 \
      .
    ```

3.  **Docker 컨테이너 실행:**
    다양한 전송 구성으로 컨테이너를 실행할 수 있습니다:
    - **Stdio 전송 방식 (기본값 - MCP 클라이언트용):**

      ```bash
      docker run --rm -it \
        -e KOREA_TOURISM_API_KEY="YOUR_KTO_API_KEY" \
        mcp-korea-tourism-api
      ```

    - **HTTP 전송 방식 (웹 애플리케이션용):**

      ```bash
      # 런타임 환경 변수 사용
      docker run --rm -p 8000:8000 \
        -e KOREA_TOURISM_API_KEY="YOUR_KTO_API_KEY" \
        -e MCP_TRANSPORT=streamable-http \
        -e MCP_HOST=0.0.0.0 \
        -e MCP_PORT=8000 \
        mcp-korea-tourism-api

      # 상태 확인: curl http://localhost:8000/health
      ```

    - **SSE 전송 방식 (실시간 애플리케이션용):**

      ```bash
      docker run --rm -p 8080:8080 \
        -e KOREA_TOURISM_API_KEY="YOUR_KTO_API_KEY" \
        -e MCP_TRANSPORT=sse \
        -e MCP_HOST=0.0.0.0 \
        -e MCP_PORT=8080 \
        mcp-korea-tourism-api
      ```

    - **Docker Compose 사용 (권장):**

      ```bash
      # 환경 변수 복사 및 구성
      cp docker.env.example .env
      # .env 파일을 편집하여 API 키와 선호하는 설정을 입력

      # HTTP 전송 방식으로 실행 (기본 프로필)
      docker-compose up mcp-tourism-http

      # SSE 전송 방식으로 실행
      docker-compose --profile sse up mcp-tourism-sse

      # 디버그 로깅을 포함한 개발 설정으로 실행
      docker-compose --profile dev up mcp-tourism-dev
      ```

## 🔧 전송 방식 구성

한국 관광 API MCP 서버는 다양한 사용 사례에 맞는 여러 전송 프로토콜을 지원합니다:

### 사용 가능한 전송 방식

1. **`stdio`** (기본값): MCP 클라이언트와 직접 통합을 위한 표준 입력/출력 전송 방식
   - 적합한 용도: Claude Desktop, Cursor 및 기타 MCP 호환 AI 어시스턴트
   - 구성: 추가 설정 불필요

2. **`streamable-http`**: 웹 애플리케이션을 위한 HTTP 기반 전송 방식
   - 적합한 용도: 웹 애플리케이션, REST API 통합, 로드 밸런서
   - 특징: HTTP 엔드포인트, 상태 확인, JSON 응답
   - 기본 엔드포인트: `http://localhost:8000/mcp`

3. **`sse`**: 실시간 애플리케이션을 위한 Server-Sent Events 전송 방식
   - 적합한 용도: 실시간 웹 애플리케이션, 이벤트 기반 아키텍처
   - 특징: 실시간 스트리밍, 지속적 연결
   - 기본 엔드포인트: `http://localhost:8080/mcp`

### 구성 옵션

명령줄 인수 또는 환경 변수를 사용하여 서버를 구성할 수 있습니다:

| 설정      | CLI 인수      | 환경 변수       | 기본값      | 설명                         |
| --------- | ------------- | --------------- | ----------- | ---------------------------- |
| 전송 방식 | `--transport` | `MCP_TRANSPORT` | `stdio`     | 사용할 전송 프로토콜         |
| 호스트    | `--host`      | `MCP_HOST`      | `127.0.0.1` | HTTP 전송을 위한 호스트 주소 |
| 포트      | `--port`      | `MCP_PORT`      | `8000`      | HTTP 전송을 위한 포트        |
| 경로      | `--path`      | `MCP_PATH`      | `/mcp`      | HTTP 엔드포인트 경로         |
| 로그 레벨 | `--log-level` | `MCP_LOG_LEVEL` | `INFO`      | 로깅 레벨                    |

### 명령줄 예시

```bash
# 사용 가능한 모든 옵션에 대한 도움말 보기
python -m mcp_tourism.server --help

# 사용자 정의 포트에서 HTTP 전송 방식으로 실행
python -m mcp_tourism.server --transport streamable-http --port 3000 --log-level DEBUG

# SSE 전송 방식으로 실행
python -m mcp_tourism.server --transport sse --host 0.0.0.0 --port 8080
```

### 환경 변수 예시

```bash
# 환경 변수 설정
export MCP_TRANSPORT=streamable-http
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
export MCP_LOG_LEVEL=INFO
export KOREA_TOURISM_API_KEY="your_api_key_here"

# 서버 실행
python -m mcp_tourism.server
```

### 상태 확인

HTTP 및 SSE 전송 방식의 경우 `/health` 엔드포인트에서 상태 확인이 가능합니다:

```bash
# 서버 상태 확인
curl http://localhost:8000/health

# 예시 응답
{
  "status": "healthy",
  "service": "Korea Tourism API MCP Server",
  "transport": "streamable-http",
  "timestamp": 1640995200.0
}
```

## 🛠️ Cursor와 통합하기

Cursor 내에서 이 MCP 서버를 사용하려면:

1.  **Docker 컨테이너 실행 가능 확인:** 위의 Docker 설치 단계를 따라 이미지(`mcp-korea-tourism-api`)를 빌드합니다. 컨테이너를 수동으로 실행할 필요는 없습니다. Cursor가 알아서 합니다.
2.  **`mcp.json` 파일 찾기:** 이 파일은 Cursor용 MCP 도구를 구성합니다. 일반적으로 Cursor 설정이나 `~/.cursor/mcp.json`과 같은 경로에서 찾을 수 있습니다.
3.  **MCP 구성 추가 또는 업데이트:** `mcp.json` 파일 내 목록에 다음 JSON 객체를 추가합니다. 이 도구에 대한 항목이 이미 있는 경우 `command`를 업데이트합니다. `"YOUR_KTO_API_KEY"`를 실제 키로 바꾸세요.
    ![cursor_integrations](images/cursor_integration.png)

    ```json
    {
      "mcpServers": {
        "korea-tourism": {
          "command": "docker",
          "args": [
            "run",
            "--rm",
            "-i",
            "-e",
            "KOREA_TOURISM_API_KEY=YOUR_KTO_API_KEY",
            "mcp-korea-tourism-api"
          ]
        }
      }
    }
    ```

    또는 uv 사용 [로컬 디렉토리]

    ```json
    {
      "mcpServers": {
        "korea-tourism": {
          "command": "uv",
          "args": [
            "--directory",
            "{LOCAL_PATH}/mcp-korea-tourism-api",
            "run",
            "-m",
            "mcp_tourism.server"
          ],
          "env": {
            "KOREA_TOURISM_API_KEY": "YOUR_KTO_API_KEY"
          }
        }
      }
    }
    ```

4.  **`mcp.json` 저장**.
5.  **Cursor 재시작 또는 MCP 도구 새로고침:** Cursor가 이제 도구를 감지하고 필요할 때 Docker를 사용하여 실행합니다.

## 🛠️ 제공되는 MCP 도구

이 서버는 AI 어시스턴트를 위해 다음과 같은 도구를 제공합니다:

1.  `search_tourism_by_keyword`: 키워드(예: "경복궁", "비빔밥")를 사용하여 관광 정보를 검색합니다. 콘텐츠 유형, 지역 코드로 필터링합니다.
    ![search_tourism_by_keyword](images/search_tourism_by_keyword.png)
2.  `get_tourism_by_area`: 지역 코드(예: 서울='1')로 관광 정보를 탐색합니다. 콘텐츠 유형, 시군구 코드로 필터링합니다.
    ![get_tourism_by_area](images/get_tourism_by_area.png)
3.  `find_nearby_attractions`: 특정 GPS 좌표(경도, 위도) 근처의 관광 명소를 찾습니다. 반경 및 콘텐츠 유형으로 필터링합니다.
    ![find_nearby_attractions](images/find_nearby_attractions.png)
4.  `search_festivals_by_date`: 지정된 날짜 범위(YYYYMMDD) 내에 열리는 축제를 찾습니다. 지역 코드로 필터링합니다.
    ![search_festivals_by_date](images/search_festivals_by_date.png)
5.  `find_accommodations`: 호텔, 게스트하우스 등을 검색합니다. 지역 및 시군구 코드로 필터링합니다.
    ![find_accommodations](images/find_accommodations.png)
6.  `get_detailed_information`: 콘텐츠 ID를 사용하여 특정 항목에 대한 포괄적인 상세 정보(개요, 이용 시간, 주차 등)를 검색합니다. 콘텐츠 유형으로 필터링합니다.
    ![get_detailed_information](images/get_detailed_information.png)
7.  `get_tourism_images`: 콘텐츠 ID를 사용하여 특정 관광 항목과 관련된 이미지 URL을 가져옵니다.
    ![get_tourism_images](images/get_tourism_images.png)
8.  `get_area_codes`: 지역 코드(시/도) 및 선택적으로 하위 지역(시군구) 코드를 검색합니다.
    ![get_area_codes](images/get_area_codes.png)

## ⚙️ 요구 사항 (`uv` 방법의 경우)

- Python 3.12 이상
- `uv` 설치됨 (`pip install uv`)

## 사용 예시

이 MCP와 통합된 AI 어시스턴트는 다음과 같은 쿼리를 처리할 수 있습니다:

- "명동역 근처 식당 찾아줘."
- "불국사 사진 보여줘."
- "다음 달 부산에 축제 있어?"
- "경복궁(콘텐츠 ID 264337)에 대해 더 자세히 알려줘."
