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

| 단계 | 설명 |
|------|------|
| Observe (관찰)| 현재 웹페이지의 스크린샷과 텍스트 트리(DOM)를 분석합니다 |
| Think (사고)| 목표 달성을 위해 현재 페이지에서 무엇을 해야 할지 판단합니다 |
| Act (행동) | Playwright를 통해 실제 브라우저 조작 명령을 실행합니다 |
|  Verify (검증) | 행동의 결과가 의도대로 되었는지 확인하고 다음 단계로 넘어갑니다 |

---

## 기술 스택

### Core

| 역할 | 기술 |
|------|------|
| 언어 | Python 3.11+ |
| 브라우저 자동화 | [Playwright](https://playwright.dev/python/) |
| AI / LLM | 미정 (OpenAI GPT-4o / Anthropic Claude 등) |
| 오케스트레이션 | [LangGraph](https://github.com/langchain-ai/langgraph) |
| API 서버 (선택) | [FastAPI](https://fastapi.tiangolo.com/) |

### Why LangGraph?

The Loop 구조(관찰 → 사고 → 행동 → 검증)는 **상태 기반 사이클 그래프**로 표현됩니다. LangGraph는 이 구조를 명시적으로 정의하고, 조건 분기·루프·상태 관리를 깔끔하게 처리할 수 있어 선택했습니다.

> LangChain은 선형 체인에 적합하고, LangGraph는 순환/분기가 필요한 에이전트 루프에 적합합니다.

---

## CLI 사용 예시

```bash
$ python agent.py --task "내일 물때표 확인해줘"

[Thought]      먼저 구글에서 '내일 부산 물때표'를 검색해야 합니다.
[Action]       Navigate to https://google.com
[Action]       Type "내일 부산 물때표" into search bar and press Enter
[Observation]  검색 결과 페이지가 로드되었습니다. '바다타임' 사이트가 보입니다.
[Thought]      가장 신뢰도가 높은 '바다타임' 링크를 클릭하겠습니다.
[Action]       Click on "부산 물때표, 부산 조석예보 - 바다타임"
[Observation]  바다타임 페이지가 로드되었습니다. 내일 날짜의 물때 정보가 보입니다.
[Verify]       목표 정보(내일 물때)가 화면에 존재합니다. 추출을 시작합니다.
[Success]      내일 부산 물때는 4물이며, 만조 시각은 06:32 / 18:47 입니다.
```

---

## 프로젝트 구조 (예정)

```
okdoit/
├── agent.py              # CLI 진입점
├── core/
│   ├── graph.py          # LangGraph 상태 그래프 정의
│   ├── nodes/
│   │   ├── observe.py    # 관찰 노드 (스크린샷, DOM 파싱)
│   │   ├── think.py      # 사고 노드 (LLM 호출)
│   │   ├── act.py        # 행동 노드 (Playwright 조작)
│   │   └── verify.py     # 검증 노드
│   └── browser.py        # Playwright 브라우저 관리
├── api/
│   └── server.py         # FastAPI 서버 (선택적)
├── prompts/
│   └── agent.md          # 시스템 프롬프트
├── requirements.txt
└── README.md
```

---

## 로드맵

- [ ] 기본 The Loop 구현 (LangGraph)
- [ ] Playwright 브라우저 제어 연동
- [ ] CLI 인터페이스 구현
- [ ] 스크린샷 기반 관찰 기능
- [ ] DOM 텍스트 트리 파싱
- [ ] FastAPI 서버 래핑
- [ ] 작업 히스토리 저장 및 재실행

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

# 실행
python agent.py --task "원하는 작업을 입력하세요"
```

---