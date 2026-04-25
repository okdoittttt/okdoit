# okdoit

> 자연어 목표를 입력하면, AI가 브라우저를 직접 조작해 결과를 가져옵니다.

CLI 와 FastAPI sidecar 두 형태로 실행 가능하며, 데스크탑 앱(Electron) 통합이 다음 마일스톤으로 진행 중입니다(`.plan/` 참조).

---

## 핵심 컨셉

사용자가 자연어로 작업을 던지면 에이전트가
(1) 작업을 **subtasks 로 분해**하고,
(2) 브라우저를 실제로 조작해 단계를 수행하고,
(3) 진행이 막히면 **계획을 동적으로 재구성**하면서 목표를 달성합니다.

---

## The Loop — 핵심 동작 원리

목표를 달성할 때까지 아래 그래프를 돈다. `plan` 은 시작 시 한 번, `replan` 은 정체가
감지될 때 동적으로 진입한다.

```
START → plan → observe → think → act → verify → {END | observe | replan}
                                                  │
                                                  └──(plan_stale)──▶ replan ──▶ observe
```

| 단계 | 파일 | 책임 |
|------|------|------|
| Plan    | `core/nodes/plan.py`    | 목표를 subtasks 로 분해 |
| Observe | `core/nodes/observe.py` | 스크린샷 + DOM 인덱싱(`data-oi-idx`) + URL 수집 |
| Think   | `core/nodes/think.py`   | LLM 에 컨텍스트 전달, 다음 액션 결정 |
| Act     | `core/nodes/act.py`     | navigate / click / type / scroll / extract / wait 실행 |
| Verify  | `core/nodes/verify.py`  | 종료 / 루프 패턴 / replan 트리거 판정 |
| Replan  | `core/nodes/replan.py`  | stuck 또는 plan 부족 시 새 subtasks 로 교체 |

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 언어 | Python 3.12 |
| 브라우저 자동화 | [Playwright](https://playwright.dev/python/) + playwright-stealth |
| HTML → 텍스트 | BeautifulSoup4, markdownify |
| LLM (다중 지원) | Anthropic Claude · Google Gemini · Ollama (로컬) · OpenAI |
| LLM 추상화 | LangChain |
| 오케스트레이션 | [LangGraph](https://github.com/langchain-ai/langgraph) |
| API 서버 | FastAPI + uvicorn (sidecar) |
| 설정 | pydantic-settings |
| 테스트 / 정적 검사 | pytest, pytest-asyncio, mypy, ruff |

---

## 프로젝트 구조

```
okdoit/
├── agent.py                       # CLI 진입점
├── core/                          # 에이전트 도메인
│   ├── state.py                   # AgentState TypedDict
│   ├── graph.py                   # LangGraph StateGraph + 라우터
│   ├── browser.py                 # Playwright BrowserManager (싱글톤)
│   ├── nodes/
│   │   ├── plan.py / replan.py
│   │   └── observe.py / think.py / act.py / verify.py
│   ├── actions/                   # 액션 레지스트리 + 핸들러
│   │   ├── _registry.py / result.py
│   │   └── navigation.py / interaction.py / file_io.py
│   ├── llm/                       # LLM 프로바이더 추상화
│   │   ├── base.py / factory.py / adapter.py
│   │   └── anthropic.py / gemini.py / ollama.py / openai.py
│   ├── context/                   # 프롬프트 컨텍스트 빌더
│   └── utils/
├── server/                        # FastAPI sidecar
│   ├── main.py                    # uvicorn CLI 진입점
│   └── internal/                  # FastAPI 앱 / 라우터 / 도메인
│       ├── app.py / config.py / deps.py
│       ├── runner.py / event_builders.py / session.py
│       ├── events/                # session.* / plan.* / step.* 이벤트
│       ├── routes/                # health / run / sessions / events_ws
│       └── schemas/               # 요청 / 응답 모델
├── prompt/                        # LLM 시스템 프롬프트
├── tests/                         # core/ + server/ 테스트
│   ├── server/                    # FastAPI sidecar 단위/통합 테스트
│   ├── test_actions/ / context/ / utils/ / eval/
│   └── test_*.py                  # core/ 노드 / 그래프 / 브라우저
├── .plan/                         # 데스크탑 앱 마일스톤 + 설계 문서
├── scripts/
├── .env.example
├── pytest.ini
└── requirements.txt
```

---

## 개발 환경 설정

```bash
# 저장소 클론
git clone https://github.com/okdoittttt/okdoit.git
cd okdoit

# 의존성 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium

# 환경변수 설정
cp .env.example .env   # 값 채우기
```

### 환경변수 (`.env`)

```env
# ── LLM ────────────────────────────────────────
LLM_PROVIDER=anthropic                 # anthropic | gemini | ollama | openai
LLM_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=your-api-key-here
# GOOGLE_API_KEY=...                   # gemini 사용 시
# OPENAI_API_KEY=...                   # openai 사용 시
# OLLAMA_BASE_URL=http://localhost:11434

# ── 브라우저 ───────────────────────────────────
# BROWSER_HEADLESS=false               # 기본 true

# ── sidecar (선택) ────────────────────────────
# OKDOIT_HOST=127.0.0.1
# OKDOIT_PORT=8765
# OKDOIT_LOG_LEVEL=info
# OKDOIT_HEADLESS_DEFAULT=false
```

---

## 실행 방법

### CLI — 단일 작업

```bash
# 기본 실행 (headless)
python agent.py --task "내일 서울 날씨 알려줘"

# 브라우저 창 표시
python agent.py --task "내일 서울 날씨 알려줘" --no-headless
```

### FastAPI Sidecar — 데스크탑 앱 / 외부 클라이언트용

#### 서버 실행

```bash
# 기본 실행 — 127.0.0.1:8765 에 바인딩
python -m server.main

# 포트 변경
OKDOIT_PORT=9000 python -m server.main

# 헤드리스 기본값 변경 + 디버그 로그
OKDOIT_HEADLESS_DEFAULT=false OKDOIT_LOG_LEVEL=debug python -m server.main

# 코드 변경 시 자동 재시작 (개발 모드)
uvicorn server.internal.app:app --host 127.0.0.1 --port 8765 --reload
```

#### 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/health` | 헬스체크 + protocol_version |
| `POST` | `/run` | 새 세션 시작 (`{ "task": str, "headless": bool? }` → `{ "session_id": str }`) |
| `GET` | `/sessions[/{id}]` | 세션 목록 / 단일 스냅샷 |
| `POST` | `/sessions/{id}/{pause,resume,stop}` | 실행 제어 |
| `WS` | `/sessions/{id}/events` | 노드 단계별 이벤트 스트림 |

#### 사용 예시

```bash
# 1) 헬스체크
curl http://127.0.0.1:8765/health
# → {"status":"ok","protocol_version":"0.1"}

# 2) 작업 시작
curl -X POST http://127.0.0.1:8765/run \
  -H 'Content-Type: application/json' \
  -d '{"task":"내일 서울 날씨 알려줘","headless":false}'
# → {"session_id":"3f2c..."}

# 3) 이벤트 스트림 구독 (wscat 필요: npm i -g wscat)
wscat -c ws://127.0.0.1:8765/sessions/3f2c.../events

# 4) 일시정지 / 재개 / 중단
curl -X POST http://127.0.0.1:8765/sessions/3f2c.../pause
curl -X POST http://127.0.0.1:8765/sessions/3f2c.../resume
curl -X POST http://127.0.0.1:8765/sessions/3f2c.../stop

# 5) Swagger UI (브라우저)
open http://127.0.0.1:8765/docs
```

엔드포인트 명세, 이벤트 스키마, 데스크탑 앱 마일스톤은 `.plan/01-backend-fastapi.md`,
`.plan/02-event-protocol.md`, `.plan/06-roadmap.md` 참조.

---

## 출력 예시 (CLI)

```
((.venv) ) Developer/okdoit$ python agent.py --task "내일 서울 날씨 알려줘" --no-headless

[태스크] 내일 서울 날씨 알려줘
────────────────────────────────────────────────────────────
[Observation]
[Thought]      현재 URL이 'about:blank'이므로, 목표 달성을 위해 날씨 정보를 검색할 수 있는 검색 엔진 웹사이트로 이동해야 합니다. 네이버나 구글과 같은 검색 엔진으로 이동하는 것이 적절합니다. 여기서는 네이버로 이동하여 '내일 서울 날씨'를 검색하겠습니다.
[Action]       https://www.naver.com으로 이동
[Verify]       반복 1회 / 최대 20회
[Observation]  NAVER 공지사항 Partners Developers 네이버 정책 및 약관 네이버 AI 모델이 내 검색 이력을 기준으로, 내 관심사와 맥락에 어울리는 맞춤형 검색어를 추천해 드려
[Thought]      네이버 메인 페이지로 성공적으로 이동했습니다. 이제 '내일 서울 날씨'를 검색창에 입력하고 검색을 실행해야 합니다. 검색창은 '검색어를 입력해 주세요.'라는 플레이스홀더와 연관되어 있으며, 그 옆에 검색 버튼이 있습니다. 가장 명확한 액션은 검색창에 텍스트를 입력하는 것입니다.
[Action]       검색창에 '내일 서울 날씨' 입력
[Verify]       반복 2회 / 최대 20회
[Observation]  NAVER 내일 서울 날씨 검색 결과 서울특별시 날씨 제공사 설정 오늘의 날씨 시간별 예보 확률 강수량 시간대 풍향 풍속 습도 내일의 날씨 모레의 날씨 날씨전망 주간예보 날씨아이콘
[Thought]      검색 결과 페이지에 도달했으며, '내일 서울 날씨'에 대한 다양한 정보가 표시되고 있습니다. 스크린샷과 DOM 텍스트를 분석한 결과, 중앙에 가장 구체적이고 시각적으로 정리된 '시간별 예보' 섹션이 있습니다. 또한, 아래쪽 '내일' 섹션에서도 서울의 내일 날씨 정보를 확인할 수 있습니다. 현재 목표는 '내일 서울 날씨'를 아는 것이므로, 시간별/종합 예보 섹션의 정보를 종합하여 사용자에게 제공하는 것이 최선입니다. 별도의 클릭 없이 페이지에 나타난 정보를 취합하여 결과로 전달하겠습니다.
[Verify]       반복 3회 / 최대 20회
────────────────────────────────────────────────────────────
[Success]      내일 서울 날씨는 전반적으로 맑은 날씨가 예상됩니다.
- 최저 11°C / 최고 25°C
- 일출 06:33 / 일몰 19:33
- 일교차가 크니 얇은 겉옷을 챙기시는 것이 좋겠습니다.
```

---

## 테스트

```bash
# 단위 + 라우터 통합 (외부 서비스 의존 X)
pytest tests/ --ignore=tests/eval --ignore=tests/test_ollama_integration.py

# sidecar 테스트만
pytest tests/server/ -v

# 통합 테스트 (Ollama 서버 필요)
pytest tests/ -v -m integration

# 타입 체크
mypy core/ server/
```

---

## 로드맵

### 완료 ✅
- The Loop 구현 (plan / observe / think / act / verify / replan)
- Playwright 브라우저 제어 + DOM 인덱싱
- CLI 인터페이스 (`agent.py`)
- 멀티 LLM 프로바이더 (Anthropic / Gemini / Ollama / OpenAI)
- 동적 replan (stuck 패턴 / 계획 부족 자동 감지)
- 액션 결과 분류 + 복구 힌트 (ActionResult)
- 메모리 컴팩션 (history_items + memory)
- **FastAPI sidecar** (REST + WebSocket 이벤트 스트리밍)
- **세션 제어** (pause / resume / stop)

### 진행 예정 (`.plan/06-roadmap.md` 참조)
- **v0.1** — Electron 데스크탑 앱: 활동 로그 1-pane UI
- **v0.2** — Pause / Resume / Stop UI, 동적 포트, 작업 템플릿
- **v0.3** — 멀티 세션, 결과 아티팩트 패널, 세션 히스토리
- **v0.4** — 패키징(.dmg / .exe), 자동 업데이트, 코드 사이닝
- **v0.5** — 사전 승인 게이트, Take Over, BrowserView 임베드
