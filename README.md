# okdoit

> 터미널에 목표를 입력하면, AI가 브라우저를 직접 조작해 결과를 가져옵니다.

---

## 핵심 컨셉

사용자가 터미널에 자연어로 목표를 입력하면, AI가 브라우저를 직접 실행하여 웹사이트를 탐색하고, 클릭·입력 등을 수행하며 최종 결과(데이터 추출, 동작 완료 등)를 보고하는 시스템입니다.

---

## The Loop — 핵심 동작 원리

okdoit은 목표를 달성할 때까지 아래 4단계 루프를 반복합니다.

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   Observe → Think → Act → Verify → Observe → ...   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

| 단계 | 파일 | 설명 |
|------|------|------|
| Observe (관찰) | `core/nodes/observe.py` | 스크린샷 촬영, DOM 텍스트 추출, 현재 URL 수집 |
| Think (사고) | `core/nodes/think.py` | 스크린샷 + DOM을 LLM에 전달해 다음 액션 결정 |
| Act (행동) | `core/nodes/act.py` | navigate / click / type / scroll / wait 실행 |
| Verify (검증) | `core/nodes/verify.py` | 종료 조건 판단 (목표 달성 / 에러 / 최대 반복 초과) |

---

## 기술 스택

| 역할 | 기술 |
|------|------|
| 언어 | Python 3.12 |
| 브라우저 자동화 | [Playwright](https://playwright.dev/python/) |
| LLM | Anthropic Claude / Ollama (로컬) |
| 오케스트레이션 | [LangGraph](https://github.com/langchain-ai/langgraph) |
| LLM 추상화 | LangChain (`langchain-anthropic`, `langchain-ollama`) |

---

## 프로젝트 구조

```
okdoit/
├── agent.py                  # CLI 진입점
├── core/
│   ├── state.py              # AgentState TypedDict 정의
│   ├── graph.py              # LangGraph StateGraph 정의
│   ├── browser.py            # Playwright BrowserManager (싱글톤)
│   ├── llm/
│   │   ├── base.py           # BaseLLMProvider 추상 클래스
│   │   ├── anthropic.py      # Anthropic Claude 프로바이더
│   │   ├── ollama.py         # Ollama 로컬 프로바이더
│   │   └── factory.py        # LLM_PROVIDER 환경변수로 프로바이더 선택
│   └── nodes/
│       ├── observe.py        # 관찰 노드
│       ├── think.py          # 사고 노드
│       ├── act.py            # 행동 노드
│       └── verify.py         # 검증 노드
├── prompt/
│   └── agent.md              # LLM 시스템 프롬프트
├── tests/
│   ├── test_browser.py
│   ├── test_observe.py
│   ├── test_think.py
│   ├── test_act.py
│   ├── test_verify.py
│   ├── test_graph.py
│   ├── test_agent.py
│   └── test_ollama_integration.py
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
cp .env.example .env
# .env 파일을 열어 값 입력
```

### 환경변수 설정 (`.env`)

```env
# LLM 프로바이더 선택: anthropic | ollama
LLM_PROVIDER=anthropic

# LLM 모델명
LLM_MODEL=claude-sonnet-4-6

# Anthropic API 키 (LLM_PROVIDER=anthropic 일 때 필수)
ANTHROPIC_API_KEY=your-api-key-here

# Ollama 서버 주소 (LLM_PROVIDER=ollama 일 때, 기본값: http://localhost:11434)
# OLLAMA_BASE_URL=http://localhost:11434

# 브라우저 헤드리스 모드 (기본값: true)
# BROWSER_HEADLESS=false
```
---

## CLI 사용법

```bash
# 기본 실행 (headless 모드)
python agent.py --task "내일 서울 날씨 알려줘"

# 브라우저 창 표시
python agent.py --task "내일 서울 날씨 알려줘" --no-headless
```

### 출력 예시

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
[Success]      네, 검색 결과 페이지에 '내일 서울 날씨' 예보가 자세히 나와 있습니다. 종합적으로 파악된 정보는 다음과 같습니다.

**🌞 오늘 날씨 (4/12)**
*   **전반적:** 구름 많이 낀 날씨이며, 미세먼지는 보통, 초미세먼지는 나쁨입니다.
*   **시간별:** 오전 7시경부터 8~12도 사이로 점차 올라가며, 오후 2~3시 사이에 최고 22도까지 오르지만, 구름이 많고 전반적으로 흐린 경향이 있습니다.

**🗓️ 내일 날씨 (4/13)**
*   **날씨:** 전반적으로 맑은 날씨가 예상됩니다.
*   **최저/최고 기온:** 최저 기온은 11°C, 최고 기온은 25°C로 예상됩니다. (종합 예보 기준)
*   **일출/일몰:** 일출은 06:33, 일몰은 19:33으로 예상됩니다.
*   **시간대별 예측:** 하루 종일 맑은 날씨가 이어지며, 기온은 오전 11°C부터 오후 2~3시 사이에 25°C까지 오르는 것으로 보입니다.

**💡 참고 사항:**
*   **일교차:** 오늘과 내일 모두 일교차가 크므로, 얇은 겉옷을 챙기시는 것이 좋겠습니다.
*   **미세먼지:** 미세먼지 농도는 보통이나, 초미세먼지 관리는 필요해 보입니다.
```

---

## 테스트

```bash
# 단위 테스트 전체 실행
pytest tests/ -v -m "not integration"

# 통합 테스트 (Ollama 서버 필요)
pytest tests/ -v -m integration

# 특정 파일만 실행
pytest tests/test_graph.py -v
```

---

## 로드맵

- [x] 기본 The Loop 구현 (LangGraph)
- [x] Playwright 브라우저 제어 연동
- [x] CLI 인터페이스 구현
- [x] 스크린샷 기반 관찰 기능
- [x] DOM 텍스트 트리 파싱
- [x] Anthropic / Ollama 멀티 프로바이더 지원
- [ ] FastAPI 서버 래핑
- [ ] 작업 히스토리 저장 및 재실행
