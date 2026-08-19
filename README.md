# SHIFT SCHEDULER 사용 설명서

의료진 D/E/N 근무표를 자동 생성하는 OR-Tools CP-SAT 기반 스케줄러입니다.  
날짜별 **Minimal(최소) / Ideal(선호) 인원**, 개인별 근무 불가/강제 요청, 연차, 직전 5일 실제 스케줄, 야간 후 휴식, 연속근무 제한, grade 기반 인력 구성, 개인별 D/E/N/Total 정확 고정, `maximum_total` 상한, 결과표 셀 고정 등을 함께 반영합니다.

> 현재 문서는 2026-08-19 기준의 `app.py + scheduler.py` 동기화 버전을 설명합니다.  
> `app.py`, `scheduler.py`, `README.md`는 같은 폴더에 두는 것을 권장합니다. 앱은 자기 옆의 `scheduler.py`를 불러오고, `README.md`가 있으면 앱 안의 사용 설명서에도 표시합니다.

---

## 1. 핵심 개념

| 항목 | 의미 | 예시 |
|---|---|---|
| Duty 설정 | 날짜별 D/E/N의 **Minimal hard 최소 인원 + Ideal soft 선호 인원** | 9/1 Min 1/2/1, Ideal 1/2/1; 9/2 Min 1/2/1, Ideal 2/3/2 |
| 근무 요청 / 날짜 설정 | 개인별 특정 날짜의 불가/연차/강제 근무 | `d`, `x`, `a`, `N` |
| 직전 5일 스케줄 | 이번 스케줄 시작 직전 5일의 실제 근무 | 8/29 N, 8/30 N, 8/31 OFF |
| 개인 규칙 / Grade | grade, 근무 조정값, fixed/maximum count, 근무 패턴 제한 | grade 3, fixed_Total 18, N 후 2일 off |
| `fixed_D/E/N` | 해당 shift의 월 근무수를 **정확히** 고정 | fixed_N = 5 → N 정확히 5개 |
| `fixed_Total` | 월 총근무수를 **정확히** 고정 | fixed_Total = 18 → 정확히 18개 |
| `maximum_total` | 월 총근무수의 **상한** | maximum_total = 18 → 0~18개 가능 |
| Grade 정책 | 고년차/저년차/초저년차 기준과 duty 구성 rule | grade ≥ 6 고년차 |
| 결과표 셀 고정 | 결과표에서 선택한 셀을 다음 실행에도 유지 | 특정 날짜를 D로 고정 |
| Soft penalty | 가능한 범위에서 더 좋은 근무표를 선택하는 기준 | 총근무, N, 휴일, D/E, grade 편차 |

### 세 가지 숫자를 구분해서 생각하기

이 스케줄러에서 가장 중요한 구분입니다.

```text
DutyRequests (D/E/N) = 그 날짜/shift에 반드시 필요한 Minimal 인원
Ideal_D/E/N = **선택 입력값**. 빈칸이면 사용하지 않고, 숫자를 입력한 날짜/Duty에만 추가 배정 선호도를 적용
fixed_Total  = 그 사람이 반드시 해야 하는 정확한 월 근무수
maximum_total = 그 사람이 넘으면 안 되는 월 총근무 상한
```

예:

```text
9/1 Day Minimal = 7, Ideal = 8
→ Day에 최소 7명은 반드시 필요
→ 추가근무가 필요하면 8명까지는 이 duty를 우선 선호
→ Ideal=8 자체가 8번째 근무를 새로 만들어내지는 않음

A fixed_Total = 18
→ A는 반드시 정확히 18근무

B maximum_total = 18
→ B는 18근무 이하여야 함. 15, 16, 17, 18 모두 가능
```

### Hard rule과 Soft rule

| 종류 | 설명 | 예시 |
|---|---|---|
| Hard rule | 반드시 만족해야 함. 서로 충돌하면 해가 없음 | Duty 최소인원, 대문자 D/E/N, x/a, fixed_Total, maximum_total, N-rest, 고년차 최소, 초저년차 최대 |
| Soft rule | 가능하면 맞추되 필요하면 편차 허용 | 총근무 균형, N 균형, 휴일 균형, D/E 균형, grade 편차, 저년차 분산 |

### 추가 인원 배정의 우선순위

DutyRequests는 최소값이므로 실제 인원은 더 많아질 수 있습니다. 하지만 solver는 아무 이유 없이 인원을 늘리지 않습니다.

```text
1단계: Minimal을 넘는 **추가 배정 수 자체를 최소화**
2단계: 그 추가배정 수를 고정한 뒤
       Ideal 선호 + 날짜 분산 + duty 분산을 함께 최적화
3단계: 그 placement score 안에서 총근무/N/휴일/D-E/grade 등의 기존 penalty를 최소화
```

즉 Ideal은 중요하지만 절대 우선순위는 아닙니다. 기본 placement 가중치는 **Ideal 초과 3 : 날짜 몰림 2 : duty-cell 몰림 1**입니다. 한 날짜의 Ideal을 끝까지 채우는 것보다 다른 날짜에 조금 나누는 편이 전체 placement score가 더 좋아지면 solver가 그렇게 분산할 수 있습니다.

따라서 fixed_Total 때문에 4근무를 추가해야 한다면 가능한 범위에서 약 4개만 추가하고, 그 4개는 Ideal 쪽을 더 선호하되 특정 날짜/D/E/N에 지나치게 몰리지 않도록 절충해서 배치합니다.

예를 들어 9/1 Min=1/2/1, Ideal=1/2/1이고 9/2 Min=1/2/1, Ideal=2/3/2라면 추가근무는 9/2 쪽을 우선 선호합니다. 다만 여러 날짜에 Ideal 여유가 있으면 한 날짜의 Ideal을 전부 채우고 다음 날짜로 가는 방식보다 **날짜별 추가배정의 최대 몰림을 줄이는 방향**으로 분산합니다.

---

## 2. 전체 작업 순서

```text
1. 앱 시작 시 기본 달력 확인
   - 기본값은 현재 달이 아니라 다음 달 1일~말일

2. 사이드바에서 근무자 이름 추가 또는 설정 Excel 불러오기

3. 직전 5일 스케줄 입력
   - 이번 달 1일 이전의 실제 근무를 입력해 월 경계 rule을 연결

4. 근무 요청 / 날짜 설정
   - 날짜 유형, d/e/n/x/a/D/E/N 입력

5. Duty 설정
   - 날짜별 D/E/N Minimal + Ideal 인원 입력

6. 개인 규칙 / Grade
   - grade, 근무 조정값, fixed_D/E/N/Total, maximum_total, 개인 rule 입력

7. 월 근무수 요약 확인
   - Duty 최소합, Duty 기준 평균, fixed_Total 지정자/합, 미지정 인원, 연차 확인

8. 스케줄 생성

9. 해가 없으면 결과 탭에서 진단모드 실행

10. 결과 확인
    - 근무 통계
    - 추가 근무 가능일
    - 근무 일정표
    - Daily duty 실제/Min/Ideal 및 Ideal 부족/초과
    - Excel 내보내기
```

처음 사용할 때는 이름을 넣고 `설정 Excel 저장`으로 템플릿을 만든 뒤 Excel에서 대량 편집하고 다시 불러오는 방식이 편합니다.

---

## 3. 사이드바

### 3.1 기본 설정

| 항목 | 설명 |
|---|---|
| 시작 날짜 | 스케줄 첫 날짜 |
| 총 일수 | 생성할 날짜 수 |

앱을 새로 시작하면 기본값은 **현재 날짜 기준 다음 달 1일**입니다. 총 일수도 그 다음 달의 실제 일수로 자동 설정됩니다.

예:

```text
현재 날짜 2026-08-19
→ 기본 시작 날짜: 2026-09-01
→ 총 일수: 30일
```

12월에 실행하면 다음 해 1월 1일로 넘어갑니다.

시작 날짜를 바꾸면 토/일 날짜 유형과 직전 5일 기준 날짜도 함께 달라집니다.

### 설정 Excel을 불러올 때 날짜 처리

현재 버전에서는 `DutyRequests` 시트의 날짜 index를 읽을 수 있으면 그 날짜를 기준으로 시작 날짜를 맞춥니다. 또한 불러온 DutyRequests 행 수를 총 일수로 사용합니다.

따라서 최신 형식 Excel에서는 보통 별도로 날짜를 다시 맞출 필요가 없습니다.

### 3.2 근무자 관리

- 이름을 추가, 수정, 삭제할 수 있습니다.
- 실제 운영 중에는 Excel에서 명단을 정리한 뒤 다시 불러오는 방법이 안전합니다.
- grade, 근무 조정값, fixed_D/E/N/Total, maximum_total 등은 `개인 규칙 / Grade` 탭에서 관리합니다.
- Excel 시트 간 이름 매칭이 있으므로 이름 변경 시 ShiftRequests와 PreviousSchedule도 함께 확인하세요.

### 3.3 Solver 설정

| 모드 | 설명 |
|---|---|
| 최적해 1개 | objective가 가장 좋은 해 하나를 찾습니다. 가장 빠르고 안정적입니다. |
| 다중 솔루션 탐색 | 먼저 최적값을 찾고, 허용 편차 범위 안의 여러 후보를 탐색합니다. |

다중 솔루션은 기본적으로 다음 흐름입니다.

```text
1단계: 최소 추가배정 + soft penalty가 가장 좋은 해 탐색
2단계: 허용 범위 안에서 여러 solution 탐색
```

---

## 4. 근무 요청 / 날짜 설정 탭

이 탭에서는 날짜 유형과 개인별 근무 요청을 입력합니다.

### 4.1 날짜 유형

| 값 | 의미 | 휴일 통계 포함 |
|---|---|---|
| 평일 | 일반 평일 | 아니오 |
| 토 | 토요일 | 예 |
| 일 | 일요일 | 예 |
| 공 | 평일 공휴일 | 예 |

결과표에서는 토/일/공휴일이 구분되어 표시됩니다.

### 4.2 개인 근무 요청 입력값

| 입력 | 의미 | Solver 처리 |
|---|---|---|
| 빈칸 | 특별 요청 없음 | 자동 배정 가능 |
| `d` | Day 불가 | D 불가 |
| `e` | Evening 불가 | E 불가 |
| `n` | Night 불가 | N 불가 |
| `de` | D/E 불가 | D/E 불가 |
| `dn` | D/N 불가 | D/N 불가 |
| `en` | E/N 불가 | E/N 불가 |
| `den` | D/E/N 모두 불가 | 전체 근무 불가 |
| `x` | 해당 날짜 전체 불가 | 전체 근무 불가 |
| `a` | 연차 | 전체 근무 불가 + 연차 통계 |
| `D` | Day 강제 | 반드시 D |
| `E` | Evening 강제 | 반드시 E |
| `N` | Night 강제 | 반드시 N |

대문자 `D/E/N`은 단순 선호가 아니라 **hard-fixed 근무**입니다. 개인 sequence rule과 충돌하면 해가 없어질 수 있습니다.

예:

```text
직전 스케줄이 8/29 N, 8/30 N
N 후 완전 off = 2일
9/1 N을 대문자로 강제
→ 9/1 mandatory OFF와 9/1 N이 충돌
→ 진단모드 0차에서 확인 가능
```

### 4.3 연차 `a`

`a`는 해당 날짜의 완전 off입니다. solver에서는 `x`와 마찬가지로 D/E/N 모두 불가로 처리하고, 결과 통계에서는 연차로 별도 표시합니다.

`a` 자체가 solver 내부에서 몰래 근무 조정값을 변경하지는 않습니다.

```text
a 1개
= 해당 날짜 D/E/N 불가
+ 연차 통계 1개
```

근무량 보정이 필요하면 `개인 규칙 / Grade`의 월 근무수 표에서 `자동계산`을 사용한 뒤 `저장`해야 실제 근무 조정값에 반영됩니다.

#### fixed_Total이 있는 경우

```text
fixed_Total = 18
연차 = 2일
→ 실제 D/E/N 총근무는 여전히 정확히 18개
→ 연차 때문에 fixed_Total이 자동으로 16으로 줄지 않음
```

연차 때문에 월 총근무 자체를 줄여야 한다면 `fixed_Total` 값을 실제 목표값으로 직접 입력해야 합니다.

---

## 5. Duty 설정 탭

각 날짜/D/E/N에 대해 **Minimal은 필수로 입력**하고, **Ideal은 필요할 때만 선택적으로 입력**합니다. 새 스케줄의 Ideal preset은 모두 빈칸입니다.

예:

| 날짜 | Min D | Min E | Min N | Ideal D | Ideal E | Ideal N |
|---|---:|---:|---:|---:|---:|---:|
| 9/1 | 1 | 2 | 1 | 1 | 2 | 1 |
| 9/2 | 1 | 2 | 1 | 2 | 3 | 2 |
| 9/3 | 1 | 2 | 1 | 2 | 2 | 1 |

### Minimal과 Ideal의 의미

```text
Minimal = 반드시 채워야 하는 hard 최소 인원
Ideal   = 선택적 soft 선호 인원. **빈칸이면 해당 날짜/Duty에는 Ideal 선호도를 적용하지 않음**
```

예를 들어 `Min D=1, Ideal D=2`이면 D 1명은 반드시 필요하고, fixed_Total 등 때문에 추가근무가 생기면 두 번째 D를 넣는 것을 선호합니다. 하지만 Ideal 때문에 추가근무 총량을 일부러 늘리지는 않습니다.

기존 의미를 유지하기 위해 `Minimal=0`인 duty는 **닫힌 duty**입니다. 이 경우 Ideal도 0으로 처리되고 아무도 배정되지 않습니다.

```text
Minimal = 0 → 정확히 0명, closed duty
Minimal > 0 → 그 숫자 이상 배정 가능
Ideal을 입력하는 경우 Ideal >= Minimal. **빈칸은 허용되며 'Ideal 미사용'을 의미**
```

> **V11 변경:** `Ideal_D/E/N`의 기본 preset은 모두 **빈칸**입니다. 빈칸인 셀은 Ideal objective에 전혀 참여하지 않습니다. 예를 들어 9/2 E에만 `Ideal_E=3`을 입력하면 그 셀만 추가배정 선호 대상으로 사용됩니다. `Ideal=Minimal`을 명시적으로 입력하면 그 duty는 Minimal을 넘는 추가배정을 상대적으로 피하도록 하는 soft target으로 작동할 수 있습니다.

### 5.1 Ideal을 이용한 추가배정 위치 선택

Ideal은 **추가근무 총량을 결정하지 않습니다.** 추가근무 총량은 Minimal, fixed_Total, fixed_D/E/N, 개인 hard rule 등에 의해 필요한 만큼만 생깁니다.

추가근무 총량을 먼저 최소화한 뒤, 위치는 다음 placement score로 결정합니다.

```text
placement score
= (Ideal을 넘긴 추가인원 × 3)
+ (날짜별 추가인원 몰림 cost × 2)
+ (D/E/N cell별 추가인원 몰림 cost × 1)
```

날짜/duty 몰림 cost는 첫 번째 추가인원에는 0, 두 번째에는 추가 cost 1, 세 번째에는 추가 cost 2처럼 점점 커지는 방식입니다. 그래서 Ideal은 선호하지만 한 날짜에 계속 몰아넣는 것도 점점 불리해집니다.

예를 들어 한 날짜에 Ideal 여유가 많더라도, 추가인원을 계속 그 날짜에만 넣는 것보다 다른 날짜에 1명 정도 분산하는 편이 placement score가 낮아지면 분산을 선택합니다. 반대로 분산하려면 Ideal을 너무 많이 초과해야 하는 경우에는 Ideal 쪽을 더 선호합니다.

### 5.2 fixed_Total 합이 Duty 최소합보다 많은 경우

이 경우는 **오류가 아닙니다.**

예:

```text
Duty 최소합 = 580
exact fixed_Total 때문에 최소 필요한 월 총근무 = 588

→ 580명을 억지로 맞추지 않음
→ 8근무를 활성 D/E/N duty에 추가 배정
→ 개인 hard rule과 grade rule을 만족하는 위치를 solver가 선택
→ 불필요한 추가배정은 최소화
```

즉 간호사 스케줄에서 월별 정확 근무수를 채워야 해서 Duty 최소값보다 인력이 더 들어가는 상황을 허용합니다.

### 5.3 fixed_Total 합이 Duty 최소합보다 적은 경우

#### fixed_Total이 없는 사람이 있는 경우

남은 최소 근무를 fixed_Total 미지정자가 나누어 채웁니다.

예:

```text
Duty 최소합 = 580
fixed_Total 지정자 합 = 100
fixed_Total 미지정 = 30명

→ 남은 최소 근무 = 480
→ 미지정자들이 개인 rule/shift_adj 등을 반영해 나누어 채움
```

#### 모든 사람에게 fixed_Total이 있는 경우

```text
Duty 최소합 = 580
모든 사람의 fixed_Total 합 = 570

→ 정확 총근무는 570밖에 만들 수 없음
→ 최소 필요 근무는 580
→ 불가능
```

반대로 모든 사람의 fixed_Total 합이 590이면 590근무를 정확히 만들면서 Duty 최소를 충족하면 됩니다.

### 5.4 현재 상단 요약 박스

Duty 설정 및 개인 규칙 탭에서는 다음과 같은 핵심 정보만 간단히 표시합니다.

```text
Duty 최소합 580 (D 190 / E 210 / N 180)
Ideal 합 620 (+40)
최소기준 평균 15.7/명
fixed_Total 0명 · 합 0
미지정 37명
연차(a) 0
```

`최소기준 평균`은 단순 참고값입니다.

```text
최소기준 평균 = Duty 최소합 ÷ 전체 인원
```

이는 화면의 자동계산 참고 기준이며, 실제 solver에서 fixed_Total 미지정자의 total balance target은 fixed_Total 지정자와 근무 조정값을 고려하여 다시 계산됩니다.

### 5.5 fixed_Total 미지정자의 Total 평준화 방식

Solver 내부의 기본 total target은 residual 방식입니다.

```text
target_total_duty = max(Duty 최소합, fixed_Total 합)

free 평균
= (target_total_duty - fixed_Total 합 - free 사람들의 shift_adj 합)
  ÷ fixed_Total 미지정 인원수

개별 free 목표
≈ free 평균 + 그 사람의 근무 조정값
```

따라서 휴가 등으로 몇 명의 fixed_Total이 작으면 나머지 미지정자가 남은 Duty를 더 나누어 맡는 방향으로 평준화됩니다.

예:

```text
Duty 최소합 180
A fixed_Total 12
B fixed_Total 14
나머지 8명 free

→ 남은 최소 근무 154
→ free 8명 평균 약 19.25
```

반대로 fixed_Total 지정자의 정확 근무합만으로 Duty 최소합을 이미 넘으면 free 그룹의 기본 total 목표는 0 근처가 될 수 있습니다. 그래도 특정 날짜/shift의 최소인원, grade rule 등을 만족하기 위해 free 인력이 필요한 경우에는 실제로 배정될 수 있습니다.

### 5.6 D/E/N별 평준화

D/E/N도 각각 별도로 기본 평균을 계산합니다.

- 해당 shift의 `fixed_D/E/N`이 있는 사람은 정확값을 사용합니다.
- 나머지 사람은 해당 shift의 Duty 최소합에서 fixed shift 합을 뺀 잔여량을 기준으로 평준화합니다.
- 근무 조정값은 D/E/N 비율에 따라 shift target에도 영향을 줍니다.
- fixed_Total 때문에 실제 Duty가 Minimal보다 늘어난 부분은 **Ideal 선호 + 날짜/duty 분산 objective**로 위치를 먼저 정하고, 그 안에서 기존 soft balance를 최적화합니다.

---

## 6. 개인 규칙 / Grade 탭

### 6.1 월 근무수 설정 표

현재 탭 상단에는 월 근무수와 상한을 한 표에서 관리합니다.

주요 컬럼은 다음과 같습니다.

```text
No | Name | maximum_total | fixed_Total | Grade | Senior | Junior | 초저년차
   | 연차(a) | 근무조정값 | fixed_D | fixed_E | fixed_N
```

핵심 의미:

```text
fixed_D/E/N = 해당 shift의 정확한 월 근무수
fixed_Total = 정확한 월 총근무수
maximum_total = 월 총근무 상한
근무조정값 = exact count가 없는 경우 평준화 target을 +/- 조정
```

빈칸은 자동/제한 없음을 의미합니다.

`maximum_total`은 상단 표가 주 편집 위치이며, 개인별 rule 영역에서도 같은 값을 확인/수정할 수 있습니다.

표는 form 안에 있으므로 여러 칸을 수정한 뒤 **저장**을 눌러야 solver와 진단모드에 반영됩니다.

### 6.2 Grade 정책 설정

Grade는 개인의 숙련도/연차를 숫자로 표현합니다. 현재 권장 범위는 1~10입니다.

| 항목 | 의미 | 예시 |
|---|---|---|
| 고년차 기준 grade ≥ | 이 grade 이상이면 고년차 | 6 |
| Duty별 고년차 최소 | 각 활성 D/E/N duty의 고년차 최소 | 1 |
| 저년차 기준 grade ≤ | 이 grade 이하이면 저년차 | 3 |
| Duty별 저년차 권장 최대 | 한 duty의 저년차 권장 최대 | 1 |
| 저년차 초과 penalty | 권장 최대 초과 시 soft penalty | 1 |
| 초저년차 기준 grade ≤ | 초저년차 hard rule 대상 기준 | 1 |
| 초저년차 최대 허용 | duty당 초저년차 최대. 0=사용 안 함 | 1 |

고년차 최소는 hard rule입니다.

저년차 권장 최대는 soft rule입니다.

초저년차 최대 허용은 hard rule입니다.

### 6.3 편차 가중치

| 항목 | 의미 |
|---|---|
| D/E 편차 가중치 | D와 E 불균형을 줄이는 정도 |
| 휴일 편차 가중치 | 토/일/공휴일 불균형 감소 |
| 총 근무 편차 가중치 | fixed_Total 미지정자의 Total 평준화 |
| N 편차 가중치 | Night 불균형 감소 |
| Grade 편차 가중치 | duty별 grade 구성이 평균에서 과도하게 치우치지 않게 함 |

가중치가 높을수록 해당 균형을 더 중요하게 봅니다. 단, **추가 Duty 인원 최소화가 이 soft balance보다 우선**합니다.

### 6.4 개인별 Grade

각 근무자의 grade를 입력합니다.

예시:

| Grade | 의미 예시 |
|---:|---|
| 1~3 | 저년차 |
| 4~5 | 중간 |
| 6~8 | 고년차 |
| 9~10 | 최고년차/책임 가능 인력 |

실제 기준은 병원 상황에 맞게 설정하면 됩니다.

### 6.5 근무 조정값

근무 조정값은 fixed_Total이 없는 사람의 자동 평준화 목표를 조정할 때 사용합니다.

| 값 | 의미 |
|---:|---|
| 0 | 기본 평준화 target |
| +1 | 기본 target보다 약 1근무 더 |
| -1 | 기본 target보다 약 1근무 덜 |

#### 자동계산 버튼

화면에 표시되는 `estimated average`는 다음 값입니다.

```text
estimated average = Duty 최소합 ÷ 전체 인원
```

자동계산은 다음 기준으로 **화면의 근무조정값 칸에만** 권장값을 넣습니다.

```text
fixed_Total이 있으면
→ 권장 shift_adj = fixed_Total - estimated average

fixed_Total이 없으면
→ 권장 shift_adj = -연차(a) 개수

절대 차이가 1 미만이면 0
```

자동계산 후에는 반드시 `저장`을 눌러야 실제 설정에 반영됩니다.

중요:

> 화면의 `estimated average`는 자동계산용 단순 기준이고, solver의 fixed_Total 미지정자 실제 Total 평준화 target은 5.4의 residual 방식으로 계산됩니다. fixed_Total 지정자가 많으면 두 숫자가 같지 않을 수 있습니다.

### 6.6 fixed_D/E/N, fixed_Total, maximum_total

#### fixed count

| 입력 | 의미 |
|---|---|
| 빈칸 | 자동 평준화 |
| 0 | 정확히 0개 |
| 1 이상 | 정확히 그 개수 |

예:

| fixed_D | fixed_E | fixed_N | fixed_Total | 의미 |
|---:|---:|---:|---:|---|
| 빈칸 | 빈칸 | 빈칸 | 빈칸 | 모두 자동 |
| 빈칸 | 빈칸 | 빈칸 | 18 | 총근무 정확히 18, D/E/N 구성 자동 |
| 5 | 빈칸 | 빈칸 | 빈칸 | D 정확히 5 |
| 6 | 6 | 6 | 18 | D/E/N = 6/6/6, Total 18 |

#### maximum_total

| 입력 | 의미 |
|---|---|
| 빈칸 | 상한 없음 |
| 0 | 근무 0개 이하 → 사실상 근무 불가 |
| 18 | 총근무 18개 이하 |

`maximum_total=18`은 18개를 채우라는 의미가 아닙니다. 15~18개도 허용됩니다.

#### 서로의 관계

다음은 hard rule입니다.

```text
fixed_Total > maximum_total → 불가능
fixed_D/E/N의 지정된 양 합 > fixed_Total → 불가능
fixed_D/E/N의 지정된 양 합 > maximum_total → 불가능
fixed_D/E/N을 모두 지정했고 fixed_Total도 지정했다면 그 합은 fixed_Total과 같아야 함
```

이전 config의 `-1`은 자동값으로 계속 읽지만 앱과 새 Excel에서는 빈칸으로 표시합니다.


### 기본 개인 rule preset

새로 인원을 추가했을 때 개인 rule은 아래 값으로 시작합니다.  
기존에 저장되어 있거나 Excel에서 불러온 개인 rule은 이 preset으로 덮어쓰지 않습니다. Rule 컬럼이 없는 과거 설정 파일에서는 누락값의 기본값으로 사용됩니다.

| rule | 기본값 | 의미 |
|---|---:|---|
| `rule_max_shifts_per_day` | 1 | 하루에 D/E/N 중 최대 1개 근무 |
| `rule_n_block_max` | 2 | N은 최대 2연속까지 허용 |
| `rule_n_rest` | 2 | N block 종료 후 완전 OFF 2일 |
| `rule_n_gap` | 4 | N block 종료 후 다음 N까지 총 간격 4일 |
| `rule_no_day_after_eve` | 1 | E 다음날 D 금지 |
| `rule_no_3eve_consec` | 0 | EEE 금지 rule 사용 안 함 |
| `rule_no_3eve_in_4days` | 0 | 4일 중 E 3회 금지 rule 사용 안 함 |
| `rule_max_consec_days` | 5 | 최대 5일 연속 근무 |
| `rule_max_shifts_per_week` | 5 | 어느 연속 7일 구간에서도 최대 5근무 |
| `rule_no_3day_consec` | 0 | DDD 금지 rule 사용 안 함 |

즉 기본 preset은 다음과 같습니다.

```text
1 / 2 / 2 / 4 / 1 / 0 / 0 / 5 / 5 / 0
```



### maximum_N: 개인별 Night 근무 상한

`maximum_N`은 한 사람에게 한 달 동안 배정할 수 있는 **Night 근무의 최대 개수**를 정하는 hard rule입니다.

```text
빈칸 = 제한 없음
0    = N 근무 금지
4    = N을 최대 4개까지 허용
```

`fixed_N`과 의미가 다릅니다.

| 설정 | 의미 |
|---|---|
| `fixed_N = 4` | N을 **정확히 4개** 배정 |
| `maximum_N = 4` | N을 **0~4개** 범위에서 자동 배정 |
| `fixed_N = 4`, `maximum_N = 4` | N은 정확히 4개 |
| `fixed_N = 5`, `maximum_N = 4` | 서로 충돌하므로 infeasible / 진단 오류 |

`maximum_N`은 `maximum_total`과 동시에 사용할 수 있습니다. 예를 들어 `maximum_N=4`, `maximum_total=18`이면 총근무는 최대 18개이고 그중 N은 최대 4개입니다.

모든 사람의 `fixed_N` 또는 `maximum_N`으로 계산한 N 상한 합이 월간 N Duty 최소합보다 작으면 스케줄을 만들 수 없으므로, 스케줄 생성 전 pre-check 및 진단모드에서 알려줍니다.


### 6.7 개인별 근무 규칙

| 규칙 | 의미 |
|---|---|
| 하루 근무 횟수 | 하루에 D/E/N을 몇 개까지 허용할지 |
| N 뭉치 최대 길이 | 연속 Night 허용 길이 |
| N뭉치 후 완전 Off 의무일 | N block 종료 후 반드시 완전 off인 날짜 수 |
| N뭉치 후 다음 N까지 총 간격 | 다음 Night까지의 간격 |
| Evening 후 Day 금지 | E 다음날 D 금지 |
| Evening 3연속 금지 | EEE 금지 |
| 4일내 Evening 3회 금지 | 특정 4일 구간의 E 3회 패턴 제한 |
| 최대 연속 근무일수 | 입력한 날짜 수까지 연속 근무 허용 |
| 7일 구간 최대 근무수 | 어느 sliding 7일 구간에서도 허용할 최대 근무수 |
| Day 3연속 금지 | DDD 금지 |

예:

```text
최대 연속 근무일수 = 6
→ 6일 연속까지 허용
→ 7일 연속은 금지
```

`7일 구간 최대 근무수`는 달력 주 단위가 아니라 **모든 연속 7일 sliding window**에 적용됩니다. 직전 5일도 가능한 범위에서 함께 연결됩니다.

---

## 7. 직전 5일 스케줄 탭

이번 스케줄 시작 직전 5일의 **실제 근무 결과**를 입력합니다.

예를 들어 시작일이 2026-09-01이면:

```text
2026-08-27
2026-08-28
2026-08-29
2026-08-30
2026-08-31
```

이 5일이 표시됩니다.

### 입력값

| 입력 | 의미 |
|---|---|
| D | 실제 Day 근무 |
| E | 실제 Evening 근무 |
| N | 실제 Night 근무 |
| DE / DN / EN / DEN | 실제 복수 shift 근무가 있었던 경우 |
| 빈칸 | 근무 없음 |
| A / OFF | 근무 없음 |

### 왜 필요한가

월 1일부터만 rule을 적용하면 전달 마지막 며칠의 근무가 사라져 잘못된 근무표가 나올 수 있습니다.

직전 5일은 다음과 같은 개인 sequence rule의 월 경계를 연결하는 데 사용됩니다.

- N block 최대 길이
- N block 후 mandatory OFF
- N gap
- Evening 후 Day 금지
- Evening 연속 제한
- Day 3연속 제한
- 최대 연속 근무일수
- sliding 7일 최대 근무수
- 하루/2일 구간 근무수 제한이 적용되는 rule

예:

```text
8/29 N
8/30 N
8/31 OFF
N-rest = 2

→ 9/1도 mandatory OFF가 될 수 있음
```

### 월 근무수에는 포함되지 않음

직전 5일은 **이번 달 Total/D/E/N 통계에 더하지 않습니다.** 오직 월 경계를 넘는 rule continuity를 위한 context입니다.

---

## 8. 결과 탭

### 8.1 근무 통계

근무 통계는 입력 순서를 유지합니다.

주요 컬럼:

| 컬럼 | 의미 |
|---|---|
| No | 입력 순서 |
| Name | 이름 |
| Grade | 개인 grade |
| Senior / Junior / 초저년차 | Grade 정책에 따른 표시 |
| D / E / N | 각 shift 근무수 |
| Total | D+E+N 총근무수 |
| maximum_total | 설정한 총근무 상한. 없으면 빈칸 |
| 연차 | 요청 `a` 개수 |
| Total+연차 | Total + 연차 |
| Holiday | 토/일/공휴일 근무수 |
| Fri_N | 금요일 N 수 |
| 주간평균hr | 주당 평균 근무시간 추정치 |

### 8.2 추가 근무 가능일 · 개인 hard rule 기준

현재 완성된 스케줄에 특정 D/E/N 근무를 **1개 더 추가해도 개인 hard rule을 지키는지** 계산합니다.

표에는 다음이 표시됩니다.

```text
현재 Total
maximum_total
max까지 여유
추가 가능 날짜 수
추가 가능 날짜/shift
```

판정에 포함되는 것:

- 현재 결과 스케줄
- 개인 근무 불가 요청
- 직전 5일 연속 rule
- N-rest/N-gap 등 개인 sequence rule
- fixed_D/E/N
- fixed_Total
- maximum_total

따라서 이미 `fixed_Total`을 정확히 채운 사람은 추가 근무 후보가 나오지 않습니다.

중요한 한계:

> 이 표는 **대체근무/증원 후보 탐색용**입니다. 특정 사람에게 1근무를 더 넣을 때 개인 rule만 검사하며, 그 날짜의 senior/junior/grade 구성, Duty 전체 인원 조합 같은 그룹 조건은 다시 풀지 않습니다.

### 8.3 편차 / penalty 정보

결과 화면에는 다음과 같은 objective 구성요소가 표시됩니다.

```text
추가배정 수
Duty 최소합 → 실제 총 배정
편차*가중치 합
D/E 편차
휴일 편차
Total 편차
N 편차
Grade 편차
저년차 초과 penalty
```

추가배정 수가 먼저 최소화되고, 그 범위 안에서 나머지 penalty가 낮은 해를 선호합니다.

### 8.4 근무 일정표 / 셀 선택 & 고정

근무 일정표는 입력 순서를 유지하며 이름 옆에 grade를 표시합니다.

```text
Kim [G8]
Lee [G3]
Park [G6]
```

| 표시 | 의미 |
|---|---|
| D | Day |
| E | Evening |
| N | Night |
| A | 연차 |
| · | Off |
| 🔒D / 🔒E / 🔒N / 🔒· / 🔒A | 결과표에서 고정된 셀 |

### 8.5 셀 고정 / 고정 해제

결과표에서 셀을 선택해 고정하면 다음 실행에도 유지할 수 있습니다.

내부적으로 요청은 두 층입니다.

```text
base_shift_requests  = 사용자가 직접 입력한 원래 요청
fixed_shift_requests = 결과표에서 추가로 고정한 값
solver 입력           = base 위에 fixed layer를 덮어쓴 값
```

고정을 해제하면 원래 `d/en/빈칸` 등이 다시 살아납니다.

고정/해제는 먼저 예정 상태로 표시되고 **저장**을 눌러야 실제 fixed layer에 반영됩니다.

### 8.6 Daily duty 구성 요약

날짜별 D/E/N마다 **실제 / Minimal / Ideal**을 비교합니다.

주요 컬럼:

| 컬럼 | 의미 |
|---|---|
| 날짜 | 날짜/요일 |
| 유형 | 평일/토/일/공 |
| Duty | D/E/N |
| 실제/Min/Ideal | 실제 배정 / hard 최소 / soft 선호 |
| Min초과 | Minimal보다 추가된 인원수 |
| Ideal부족 | Ideal에 아직 못 미친 인원수 |
| Ideal초과 | Ideal보다 더 들어간 인원수 |
| 평균 Grade | 해당 duty 실제 근무자의 평균 grade |
| 근무자 | 이름 [grade] |

예:

```text
실제/Min/Ideal = 2/1/3
Min초과 = 1
Ideal부족 = 1
```

이 경우 최소 1명은 충족했고 추가 1명이 배정되었지만, Ideal 3명까지는 아직 1명 부족하다는 뜻입니다.

### 8.7 다중 솔루션 이동

`이전`, `다음`, `이동`으로 이미 계산된 solution들을 비교합니다. 이동할 때 solver를 다시 실행하지 않습니다.

### 8.8 결과 Excel 내보내기

결과 Excel은 화면 전환마다 자동 생성하지 않습니다. `Excel 준비` 버튼을 눌렀을 때 생성한 뒤 다운로드합니다.

---

## 9. Excel 설정 파일 구조

`설정 Excel 저장`을 누르면 현재 설정을 Excel로 저장합니다.

현재 주요 시트:

```text
Doctors
Rules
GradeRules
PreviousSchedule
DutyRequests
ShiftRequests
FixedShiftRequests
```

### 9.1 Doctors sheet

| 컬럼 | 의미 |
|---|---|
| name | 이름 |
| shift_adj | 근무 조정값 |
| grade | 개인 grade |

### 9.2 Rules sheet

첫 번째 열은 이름입니다.

주요 컬럼:

```text
rule_max_shifts_per_day
rule_n_block_max
rule_n_rest
rule_n_gap
rule_no_day_after_eve
rule_no_3eve_consec
rule_no_3eve_in_4days
rule_max_consec_days
rule_max_shifts_per_week
rule_no_3day_consec
fixed_D
fixed_E
fixed_N
fixed_Total
maximum_total
```

`fixed_D/E/N/Total`과 `maximum_total`은 빈칸이면 자동/제한 없음입니다. 이전 파일의 `-1`도 같은 의미로 읽습니다.

### 9.3 GradeRules sheet

| key | 의미 |
|---|---|
| senior_min_grade | 고년차 기준 |
| senior_min_count | 활성 duty별 고년차 최소 |
| junior_max_grade | 저년차 기준 |
| junior_soft_max_count | 저년차 권장 최대 |
| junior_penalty_weight | 저년차 초과 penalty |
| ultra_junior_max_grade | 초저년차 기준 |
| ultra_junior_max_count | 초저년차 duty당 최대. 0=사용 안 함 |
| weight_de_dev | D/E 편차 가중치 |
| weight_holiday_dev | 휴일 편차 가중치 |
| weight_total_dev | Total 편차 가중치 |
| weight_n_dev | N 편차 가중치 |
| weight_grade_dev | Grade 편차 가중치 |

### 9.4 PreviousSchedule sheet

행은 이름, 열은 이번 스케줄 시작 직전 5개의 실제 날짜입니다.

예:

| Name | 2026-08-27 | 2026-08-28 | 2026-08-29 | 2026-08-30 | 2026-08-31 |
|---|---|---|---|---|---|
| Kim | E | E | N | N | OFF |
| Lee |  | D | D | E |  |

날짜형 컬럼을 인식할 수 있으면 앱은 현재 스케줄 시작일 바로 앞 5일에 해당하는 컬럼을 날짜 기준으로 맞춥니다.

오래된/비표준 파일처럼 날짜를 읽을 수 없는 경우에는 마지막 5개 컬럼을 fallback으로 사용합니다.

### 9.5 DutyRequests sheet

행은 날짜입니다. 기존 `D/E/N`은 계속 **Minimal**로 사용하고, `Ideal_D/E/N` 컬럼이 추가되었습니다.

| 날짜 | D | E | N | Ideal_D | Ideal_E | Ideal_N |
|---|---:|---:|---:|---:|---:|---:|
| 2026-09-01 | 1 | 2 | 1 | 1 | 2 | 1 |
| 2026-09-02 | 1 | 2 | 1 | 2 | 3 | 2 |

`D/E/N`은 hard Minimal, `Ideal_D/E/N`은 soft 선호 staffing입니다. Ideal 컬럼이 없거나 셀이 빈 기존 Excel은 **Ideal 미사용(빈칸)**으로 읽습니다. `Min_D/Min_E/Min_N` 형태의 컬럼도 불러오기 시 인식합니다. Minimal=0인 duty는 닫힌 duty라 Ideal도 0으로 정규화됩니다.

또한 최신 앱은 DutyRequests의 날짜 index를 읽어 시작 날짜를 맞추고, 행 수를 총 일수로 사용합니다.

### 9.6 ShiftRequests sheet

행은 이름, 열은 날짜입니다.

| Name | 2026-09-01 | 2026-09-02 | 2026-09-03 |
|---|---|---|---|
| Kim |  | d | a |
| Lee | x |  | N |

가능한 값:

```text
빈칸, d, e, n, de, dn, en, den, x, a, D, E, N
```

### 9.7 FixedShiftRequests sheet

결과표에서 셀 고정한 값이 저장됩니다.

- 사용자가 직접 입력한 원래 요청 → `ShiftRequests`
- 결과에서 추가 고정한 값 → `FixedShiftRequests`

두 시트를 분리하므로 고정을 해제하면 원래 요청을 복원할 수 있습니다.

---

## 10. 결과 Excel 구조

결과 Excel에는 일반적으로 다음 시트가 포함됩니다.

| Sheet | 내용 |
|---|---|
| Schedule | 최종 근무표 |
| Summary | D/E/N/Total/maximum_total/연차 등 통계 |
| Rules | 현재 개인 rule 요약 |
| AdditionalAvailability | 추가 근무 가능한 날짜/shift. 후보가 있을 때 생성 |
| GradeRules | Grade 정책/가중치 |
| Metrics | objective, 추가배정, Ideal 미충족/초과, 날짜별 추가 몰림, penalty 구성요소 |

`AdditionalAvailability`에는 대체/증원 후보를 자세히 저장합니다.

예상 컬럼:

```text
No
Name
Date
Day
Current
Can_add
Current_Total
maximum_total
Remaining_to_max
```

---

## 11. 추천 운영 방식

### 11.1 처음 세팅할 때

```text
1. 근무자 이름 추가
2. 설정 Excel 저장
3. Excel에서 Doctors / Rules / DutyRequests / ShiftRequests / PreviousSchedule 편집
4. 다시 불러오기
5. 개인 규칙 / Grade에서 월 근무수 설정 확인
6. Duty 최소합과 fixed_Total 요약 확인
7. 스케줄 생성
```

### 11.2 연차가 있는 달

```text
1. ShiftRequests에 연차 날짜를 a로 입력
2. 월 근무수 표에서 연차(a) 개수 확인
3. fixed_Total이 없는 사람이면 필요 시 자동계산으로 shift_adj 권장값 확인
4. fixed_Total이 있는 사람은 실제 월 근무수를 직접 정확값으로 입력
5. 저장
6. 결과에서 연차 / Total / Total+연차 확인
```

### 11.3 fixed_Total을 많이 사용하는 간호사 스케줄

```text
1. 월별 정확 근무수가 정해진 사람에게 fixed_Total 입력
2. DutyRequests에는 날짜별 최소 인원 입력
3. fixed_Total 합 > Duty 최소합이어도 그대로 진행 가능; 추가근무는 Ideal 쪽을 우선 선호
4. solver가 필요한 추가근무를 활성 duty에 배분
5. Daily duty에서 실제/Min/Ideal, Ideal 부족/초과 확인
6. 해가 없으면 진단모드에서 개인 fixed_Total 정확 달성 가능성 확인
```

### 11.4 maximum_total을 사용하는 경우

휴가/특수상황 등으로 **최대 근무수만 제한하고 정확한 개수는 자유롭게 두고 싶을 때** 사용합니다.

```text
maximum_total = 15
fixed_Total = 빈칸
→ solver가 15개를 넘기지 않음
→ 12, 13, 14, 15 모두 가능
```

### 11.5 월 경계가 중요한 경우

새 달 스케줄을 만들기 전에 직전 5일 실제 스케줄을 먼저 입력합니다.

특히 N block, N-rest, 7일 최대 근무, E→D rule이 있는 경우 중요합니다.

---

## 12. 해가 안 나올 때 확인할 것

현재 버전에서 **fixed_Total 합이 Duty 최소합보다 크다는 사실 자체는 오류가 아닙니다.** 그 차이는 추가 Duty 배정으로 흡수할 수 있습니다.

다음 순서로 확인하세요.

1. `진단모드 실행`을 먼저 눌러 0차 확정 충돌을 확인합니다.
2. 특정 사람의 `fixed_Total`이 개인 hard rule에서 실제로 가능한지 확인합니다.
3. `fixed_Total > maximum_total`인 사람이 없는지 확인합니다.
4. `fixed_D/E/N` 지정 합이 fixed_Total 또는 maximum_total보다 크지 않은지 확인합니다.
5. 모든 사람이 exact fixed_Total인데 그 합이 Duty 최소합보다 작은지 확인합니다.
6. 모든 사람에게 fixed_Total/maximum_total 상한이 있고 전체 상한 합이 Duty 최소합보다 작은지 확인합니다.
7. 대문자 D/E/N이 N-rest, E→D, 연속근무 rule과 충돌하지 않는지 확인합니다.
8. 직전 5일 N/E/D가 이번 달 초 rule과 충돌하지 않는지 확인합니다.
9. `x`, `a`, `den`이 너무 많지 않은지 확인합니다.
10. `7일 구간 최대 근무수`, 최대 연속근무일, N-rest/N-gap이 너무 엄격하지 않은지 확인합니다.
11. 고년차 후보가 모든 활성 duty에서 충분한지 확인합니다.
12. 초저년차 maximum hard rule이 지나치게 엄격하지 않은지 확인합니다.
13. 필요하면 solver 탐색 시간을 늘립니다.

### 대표적인 확정 충돌 예

```text
직전 8/29 N, 8/30 N
N-rest = 2
9/1 N 대문자 강제
→ 9/1 mandatory OFF와 hard N 충돌
```

```text
fixed_Total = 18
현재 개인 hard rule상 정확 최대 가능 Total = 17
→ exact 18을 만들 수 없으므로 전체 model infeasible
```

---

## 13. 결과가 마음에 안 들 때 조정법

| 문제 | 조정할 항목 |
|---|---|
| fixed_Total 없는 사람의 총근무가 불공평 | Total 편차 가중치, 근무 조정값 |
| Night가 불공평 | N 편차 가중치 |
| 휴일이 불공평 | 휴일 편차 가중치 |
| D/E가 불공평 | D/E 편차 가중치 |
| duty별 grade 구성이 치우침 | Grade 편차 가중치, 고년차 최소 |
| 저년차가 몰림 | 저년차 penalty 증가 |
| 초저년차가 같이 들어가면 안 됨 | 초저년차 hard rule 설정 |
| 특정 사람 월 근무수를 정확히 맞춰야 함 | fixed_Total |
| 특정 사람은 일정 개수 이하로만 근무해야 함 | maximum_total |
| 특정 shift 수를 정확히 맞춰야 함 | fixed_D/E/N |
| fixed_Total 때문에 추가인원이 어느 날 들어갔는지 궁금함 | Daily duty의 `실제/Min/Ideal`, `Min초과`, `Ideal부족/초과` 확인 |
| 대체근무 후보가 필요함 | 추가 근무 가능일 표 확인 |

---

## 14. 주의사항

- 이 프로그램은 최적화 도구이며 최종 승인자가 아닙니다. 실제 운영자가 결과를 검토해야 합니다.
- Hard rule이 너무 많으면 해가 없을 수 있습니다.
- Soft rule은 반드시 지켜지는 조건이 아니라 penalty로 유도됩니다.
- `DutyRequests > 0`인 duty는 최소인원 이상 배정될 수 있습니다.
- `DutyRequests = 0`인 duty는 닫힌 duty라 추가인원을 넣지 않습니다.
- fixed_Total은 정확한 값이므로 solver가 임의로 줄이거나 늘리지 않습니다.
- maximum_total은 상한일 뿐 목표값이 아닙니다.
- 직전 5일은 현재 월의 근무 통계에는 포함되지 않습니다.
- 추가 근무 가능일 표는 그룹 단위 senior/junior/grade 조합을 재검증하지 않습니다.
- 진단모드 0차는 개인 hard conflict를 강하게 진단하지만, 전체 인원 간 모든 조합 충돌을 항상 하나의 원인으로 증명하는 것은 아닙니다.
- 다중 솔루션 결과는 탐색 시간에 영향을 받습니다.
- `app.py`와 `scheduler.py`는 반드시 같은 동기화 세트를 사용하세요. 서로 다른 버전을 섞으면 import/API 오류가 날 수 있습니다.

---

## 15. 빠른 체크리스트

```text
[ ] app.py / scheduler.py가 같은 버전 세트인지 확인
[ ] 기본 시작 날짜가 원하는 다음 달인지 확인
[ ] 총 일수가 해당 월 일수와 맞는지 확인
[ ] 근무자 이름과 입력 순서 확인
[ ] Grade 확인
[ ] 날짜 유형 평일/토/일/공 확인
[ ] DutyRequests D/E/N은 Minimal이고, Ideal_D/E/N은 필요한 셀에만 선택 입력했는지 확인 (기본 빈칸)
[ ] ShiftRequests d/e/n/x/a/D/E/N 확인
[ ] 직전 5일 실제 스케줄 입력 확인
[ ] 연차는 a로 입력했는지 확인
[ ] fixed_D/E/N 확인
[ ] fixed_Total 정확값 확인
[ ] maximum_total 상한 확인
[ ] fixed_Total > maximum_total 충돌 없는지 확인
[ ] 근무 조정값 저장 여부 확인
[ ] GradeRules 확인
[ ] N block / N-rest / N-gap 확인
[ ] E→D / 연속 E / DDD 확인
[ ] 최대 연속 근무일수 확인
[ ] sliding 7일 최대 근무수 확인
[ ] 월 근무수 요약의 Duty 최소합 / fixed_Total 합 확인
[ ] 스케줄 생성 전 각 탭 저장 여부 확인
[ ] 실패 시 진단모드 0차부터 확인
[ ] 결과의 추가 근무 가능일 확인
[ ] Daily duty 실제/Min/Ideal 및 Ideal 부족/초과 확인
[ ] 최종 Excel 준비 및 다운로드
```

---

## 이전 버전 설정 Excel 호환

과거 버전 `scheduler_config.xlsx`도 가능한 범위에서 불러옵니다.

없어도 기본값으로 처리 가능한 항목 예:

```text
GradeRules 시트 없음
PreviousSchedule 시트 없음
FixedShiftRequests 시트 없음
Rules에 fixed_Total 없음
Rules에 maximum_total 없음
Rules에 새 rule 컬럼 없음
Doctors에 grade 없음
Doctors에 shift_adj 없음
```

기본 fallback:

```text
grade 없음              → 기본 grade
shift_adj 없음          → 0
fixed_D/E/N/Total 없음  → 자동
maximum_total 없음      → 상한 없음
PreviousSchedule 없음   → 직전 5일 context 없음
FixedShiftRequests 없음 → 결과표 고정 없음
```

불러온 뒤 다시 설정 Excel을 저장하면 현재 형식의 시트/컬럼으로 업그레이드할 수 있습니다.

### 초저년차 old key 호환

이전의 `ultra_junior_forbid_at_or_above`는 새 `ultra_junior_max_count` 방식으로 변환해서 읽습니다.

---

## 16. 진단모드: 해가 없을 때 원인 찾기

스케줄 생성에 실패하면 결과 탭의 **진단모드 실행** 버튼을 눌러 직접 진단합니다.

진단은 크게 0차 / 1차 / 2차로 나뉩니다.

### 16.1 실행 흐름

```text
1. 스케줄 생성
2. 해 없음 메시지 확인
3. 결과 탭의 진단모드 실행
4. 0차 hard conflict 확인
5. 1차 날짜/Duty 후보 확인
6. 2차 구간 capacity 확인
```

### 16.2 0차 진단 · hard coding 충돌 + fixed_Total 정확 달성 가능성

0차가 가장 먼저 볼 항목입니다.

다음 확정 입력을 서로 대조합니다.

- PreviousSchedule
- 대문자 D/E/N
- x/a/d/e/n 등의 불가 요청
- fixed_D/E/N
- fixed_Total
- maximum_total
- N block/N-rest/N-gap
- E→D
- Evening 연속 제한
- Day 연속 제한
- 최대 연속근무일
- sliding 7일 최대근무수

#### fixed_Total 정확 달성 여부

fixed_Total이 있는 사람은 단순 날짜 수를 세는 것이 아니라, **실제 개인 hard rule과 같은 CP-SAT 모델을 따로 풀어** exact fixed_Total이 가능한지 확인합니다.

필요한 경우 다음도 계산합니다.

```text
정확 개인별 최대 가능 Total
정확 개인별 최소 가능 Total
```

예:

```text
Kim fixed_Total = 18
개인 hard rule 적용 정확 최대 = 17

→ fixed_Total 달성 불가
→ 최소 1근무 부족
```

또는:

```text
fixed_Total = 10
대문자/fixed shift 때문에 개인 정확 최소 = 11
→ 정확 10을 만들 수 없음
```

0차 결과에 표시되는 충돌은 현재 hard input 그대로는 동시에 만족하기 어려운 **확정성이 높은 문제**로 보면 됩니다.

### 16.3 1차 진단 · 날짜/Duty별 후보 부족

날짜와 D/E/N별로 확인합니다.

```text
최소 필요 인원
가능 후보 수
고년차 후보
초저년차 후보
초저년차 제한 적용 후 가능 인원
hard-fixed 인원
제외 주요 원인
```

예:

```text
09/12 N 최소 6 / 가능후보 5
→ 후보 부족
```

주의: DutyRequests가 최소값이므로 `hard fixed 인원 > 최소 필요` 자체는 이제 항상 오류는 아닙니다. 실제 solver는 추가인원 배정을 허용합니다. 1차 표는 병목을 보는 참고자료로 해석합니다.

### 16.4 1차 진단 · fixed_D/E/N 후보 가능성

fixed_D/E/N이 해당 shift의 단순 가능한 날짜 수를 넘는지도 봅니다.

예:

```text
fixed_N = 7
단순 N 가능 날짜 = 5
→ 구조적으로 부족 가능성이 높음
```

fixed_Total 자체는 0차 exact personal CP-SAT 진단에서 더 정확하게 검사합니다.

### 16.5 2차 진단 · 구간별 capacity

다음 구간을 검사합니다.

```text
3일
5일
7일
전체 기간
```

각 구간에서 최소 필요근무와 단순 가능 최대치를 비교합니다.

```text
구간 09/10~09/16
전체 최소근무 140
단순 가능 최대 136
→ 부족 4
```

2차는 전체 조합을 다시 최적화하는 solver가 아니라 **병목 후보 탐색**입니다.

### 16.6 진단모드의 한계

0차 개인 fixed_Total 검사는 개인 hard rule을 매우 정확하게 다시 풀지만, 전체 scheduler의 다음과 같은 다인원 상호작용을 모두 하나의 확정 원인으로 분해하지는 못할 수 있습니다.

- 여러 사람의 exact fixed_Total이 특정 날짜에 동시에 몰리는 문제
- senior/ultra-junior 구성과 개인 sequence rule의 복합 충돌
- 여러 날짜의 추가인원 배정 위치가 서로 얽힌 문제
- 복잡한 다중 shift 허용 조합

따라서:

```text
0차 확정 충돌이 있으면 먼저 수정
0차가 깨끗하면 1차/2차 병목을 확인
그래도 원인이 명확하지 않으면 전체 조건을 단계적으로 완화하며 비교
```

---

## 17. 저장 방식

현재 주요 입력 탭은 **저장 버튼을 눌러야 실제 설정에 반영**됩니다.

### 근무 요청 / 날짜 설정

여러 셀 수정 → `저장`

### Duty 설정

여러 D/E/N 최소인원 수정 → `저장`

### 개인 규칙 / Grade

Grade / 개인 rule / maximum_total 수정 → `저장`

### 월 근무수 표

근무조정값 / fixed_D/E/N/Total / maximum_total 수정 → `저장`

`자동계산`은 근무조정값 권장치를 **화면에 미리 계산**할 뿐 실제 설정 저장은 아닙니다. 자동계산 뒤 `저장`이 필요합니다.

### 직전 5일 스케줄

실제 근무 입력 → `저장`

### 결과표 셀 고정/해제

고정 예정/해제 예정 표시 → `저장`

### 스케줄 생성 전

앱 상단의 안내처럼 관련 탭이 모두 저장되었는지 확인한 뒤 생성하는 것이 안전합니다.

---

## 18. 현재 버전에서 특히 기억할 것

```text
1. 기본 달력은 다음 달 1일~말일
2. DutyRequests D/E/N은 hard Minimal, Ideal_D/E/N은 추가배정 위치를 정하는 soft target
3. Ideal은 근무 총량을 새로 늘리지 않고, 추가근무가 필요할 때만 우선순위로 사용
4. fixed_Total은 exact
5. maximum_total은 upper bound
6. fixed_Total 합 > Duty 최소합은 허용되며 추가 duty로 흡수
7. 추가 duty 위치는 Ideal 선호(3) + 날짜 분산(2) + duty 분산(1)의 soft tradeoff로 결정
8. fixed_Total 미지정자는 residual Duty를 기준으로 평준화
9. 직전 5일을 넣어 월 경계 sequence rule 연결
10. 실패 시 진단모드 0차에서 hard coding과 exact fixed_Total 가능성 확인
11. 결과에서 추가 근무 가능 날짜/shift 확인 가능
12. app.py / scheduler.py는 반드시 같은 동기화 세트를 사용
```
