# 🏥 Shift Scheduler — Streamlit Web App

의료진 근무표 자동 최적화 시스템 (OR-Tools CP-SAT 기반)

---

## 📁 파일 구조

```
scheduler_app/
├── app.py           # Streamlit 프론트엔드
├── scheduler.py     # OR-Tools 솔버 핵심 로직
├── requirements.txt
└── README.md
```

---

## ⚡ 빠른 시작

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 앱 실행
```bash
streamlit run app.py
```

---

## 🖥 사용 방법

### Step 1 — 기본 설정 (사이드바)
- **시작 날짜** & **총 일수** 설정
- **의사 이름** 추가/삭제
- **솔버 모드** 선택:
  - `최적해 1개 (main)` → 빠른 단일 최적 스케줄
  - `다중 솔루션 탐색 (main_alt)` → 여러 대안 탐색

### Step 2 — 근무 요청 탭 `📅`
| 셀 값 | 의미 |
|-------|------|
| `d` / `e` / `n` | 해당 근무 **불가** |
| `D` / `E` / `N` | 해당 근무 **희망** |
| `x` | 해당 날 **전체 불가** |
| `de`, `dn`, `en`, `den` | 복합 불가 |

### Step 3 — Duty 설정 탭 `📋`
- 날짜별 D(주간) / E(저녁) / N(야간) 필요 인원 수 입력

### Step 4 — 개인 규칙 탭 `⚙`
| 규칙 | 설명 |
|------|------|
| 하루 근무 횟수 | 1회 / 2회 / 주말 2회 등 |
| 야간 후 휴무 | Night 근무 후 쉬는 날 수 |
| Evening 후 Day 금지 | E 다음날 D 배정 방지 |
| Evening 3연속 금지 | EEE 패턴 방지 |
| 연속 근무 금지 | 최대 N일 연속 근무 |
| 야간 후 야간 금지 | N 이후 N 다시 배정까지 간격 |

### Step 5 — 결과 탭 `📊`
- 근무 통계 테이블 (D/E/N/Total/Holiday 수)
- 컬러 코딩된 전체 일정표
- ◀ 이전 / 다음 ▶ 버튼으로 복수 솔루션 탐색

---

## ☁ 클라우드 배포

### Streamlit Cloud (무료, 추천)
1. GitHub에 이 폴더를 push
2. [streamlit.io/cloud](https://streamlit.io/cloud) 접속 → New app
3. 리포지토리 / 브랜치 / `app.py` 선택 후 Deploy

### AWS Lambda 분리 (추후)
`scheduler.py`의 `build_and_solve()` 함수는 외부 의존성 없이 독립적으로 실행 가능.
FastAPI wrapping 후 Lambda에 배포하고, `app.py`에서 HTTP 호출로 교체할 수 있습니다.

```python
# app.py 에서 로컬 import 대신:
import requests
resp = requests.post("https://<lambda-url>/solve", json=params)
solutions, summaries = resp.json()["solutions"], resp.json()["summaries"]
```

---

## 🔑 Colab → Web 변경 사항

| Colab | Web App |
|-------|---------|
| Google Sheets 읽기 | UI 직접 입력 |
| `main()` | solver_mode = "최적해 1개" |
| `main_alt()` | solver_mode = "다중 솔루션 탐색" |
| `export()` → gspread | (추후 Excel 다운로드 추가 예정) |
| `fx()` 인터랙티브 버튼 | Streamlit 내비게이터 버튼 |
