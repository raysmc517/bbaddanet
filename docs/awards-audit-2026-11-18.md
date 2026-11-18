# 수상 데이터 전수 점검 — 2026-11-18

> **2026-11-19 후속**: 명예의 전당 누락 8명의 원인은 원본 API가 아니라 요청의 `sportId=1` 필터였다(필터 없이 받으면 354명 모두 있음). 같은 원인으로 Williams·Giménez도 빠졌다. 행크 애런상 2026 2명도 지금은 원본에 있다. HOF 누락·연도, Williams·Giménez, 2026 실버슬러거·행크 애런상, 포지션 빈 값은 고쳤다. 남은 항목은 [보완점](improvements.md)과 [개발 일지](devlog.md) 4일차에 있다.

조사 대상은 로컬 main `1d3d1f30e`의 수상 19종, 11,819행, 인물 3,410명이다. 사이트 데이터의 갱신 시각은 2026-11-17 16:01:14 KST다. 이번 작업은 조사이며 `data/`, 화면, 수집·계산 코드는 수정하지 않았다.

## 결론과 검사 범위

- 34개 MLB Stats API 수상자 응답을 모두 받아 저장 데이터와 선수 ID·상·연도·리그·구단을 비교했다. 요청 실패 0건. 최신 API에만 있는 20행 외에는 행 키와 구단 값이 일치한다.
- 별도 MLB 공식 역대 수상 페이지 14개에서 16개 수상 항목, 이름이 있는 3,417행을 추출해 이름 표기 차이를 검토했다. 공동 수상, 초기 통합 리그, 이도류·복수 부문을 따로 검토했다.
- 명예의 전당 공식 전체 목록 354명과 저장된 346명을 대조했다. 별명 차이 7건을 확인해 제외하고 8명 누락, 5명 연도 오류를 확인했다.
- 명단 누락 합계는 **33건 = 명예의 전당 8 + 다른 상 25**다. 같은 사람의 별도 부문 수상 손실 2건, 구단 불일치, 포지션 오류는 이 숫자와 별도로 센다.
- 올스타 전체 명단과 개인별 월드시리즈 우승은 API 전수 비교까지다. 각 연도의 최초 선발·대체 선수·실제 출장자·우승 반지 수령자까지 독립 자료로 전부 검증했다는 뜻은 아니다. 월드시리즈 우승 구단·연도는 별도 `data/franchise/`의 `post=WS`와 전수 일치한다.
- 명예의 전당 회원 목록의 연도·선출 방식·득표율은 기존 연결 346명 모두 저장값과 일치한다. 세부 기자단 투표 73개 연도 재조회는 10개 연도 성공, 63개 연도 HTTP 429 제한으로 미검증이다. **득표수·투표 차수 전체의 정확성은 확정하지 않았다.**

기계 판독 결과: [API·명예의 전당·포지션 상세](awards-api-audit.json), [공식 수상 표 대조 상세](awards-page-audit.json). 이름 표기 정규화는 조사 후보를 찾는 데만 사용하며 선수 ID나 사이트 데이터를 변경하지 않는다.

## 1. 실제 명단 누락

### 명예의 전당: 8명

| 헌액 연도 | 누락 인물 |
|---|---|
| 1977 | Martín Dihigo |
| 2011 | Pat Gillick |
| 2017 | John Schuerholz |
| 2017 | Bud Selig |
| 2018 | Vladimir Guerrero |
| 2020 | Marvin Miller |
| 2022 | Bud Fowler |
| 2022 | Buck O'Neil |

근거: [명예의 전당 공식 전체 목록](https://baseballhall.org/hall-of-fame/hall-of-famers-by-election-method). 개별 공식 프로필 주소는 상세 JSON에 있다. 위키백과 전체 회원 목록과도 동일한 누락 결과다. 임원·니그로리그 인물도 현 화면의 제공 대상에 포함되므로 선수 페이지가 없다는 이유로 제외하면 안 된다.

원인: `awards.py`는 MLBHOF 응답 하나에 의존하고, 응답이 비어 있는지만 검사한다. 현재 원본 API부터 이 8명이 없다. `hof_votes.py`도 이미 존재하는 HOF 행에만 투표 정보를 붙여 누락을 복구하지 않는다. `MIN_MATCHED=200`은 소수 누락을 검출하지 못한다. 수상 화면뿐 아니라 해당 선수의 수상 경력과 구단별 HOF 목록에도 영향이 있다.

### 다른 상: 25행

| 상 | 연도 | 누락 | 현재 API에도 없는가 |
|---|---|---|---|
| All-MLB 퍼스트 팀 | 2026 | Chris Sale | 예 |
| All-MLB 세컨드 팀 | 2023 | Devin Williams | 예 |
| AL 플래티넘 글러브 | 2023 | Andrés Giménez | 예 |
| AL 행크 애런상 | 2026 | Yordan Alvarez | 예 |
| NL 행크 애런상 | 2026 | Pete Crow-Armstrong | 예 |
| 실버슬러거 | 2026 | AL 10명, NL 10명 | 아니오, 최신 API에는 20명 모두 있음 |

근거: [All-MLB 역대 표](https://www.mlb.com/awards/all-mlb), [플래티넘 글러브 역대 표](https://www.mlb.com/awards/platinum-glove), [행크 애런상 역대 표](https://www.mlb.com/awards/hank-aaron), [실버슬러거 역대 표](https://www.mlb.com/awards/silver-slugger). 2023년 누락은 [Williams 수상 보도](https://www.mlb.com/news/devin-williams-all-mlb-team-2023)와 [Giménez 수상 보도](https://www.mlb.com/yankees/news/fernando-tatis-jr-andres-gimenez-win-2023-platinum-glove-awards)에서도 확인했다.

2026년 실버슬러거 누락 전원:

- AL: Dillon Dingler, Pete Alonso, Chase Meidroth, Junior Caminero, Bobby Witt Jr., Randy Arozarena, Riley Greene, Chase DeLauter, Yordan Alvarez, Kevin McGonigle.
- NL: Gabriel Moreno, Matt Olson, Brandon Lowe, Alex Bregman, Elly De La Cruz, Pete Crow-Armstrong, James Wood, Jackson Chourio, Kyle Schwarber, Jake Bauers.

실버슬러거는 재생성으로 복구할 수 있지만 다른 5행은 같은 API를 다시 받는 것만으로 복구되지 않는다. 월요일에만 수상을 갱신하는 워크플로 때문에 발표 직후 기록이 늦게 반영될 수 있다. 실제 게시 시각을 조사하지 않았으므로 20명 전부가 마지막 실행 이후 발표됐다고 단정하지 않는다.

## 2. 헌액 연도 오류: 5명

| 인물 | 현재 수상 행/화면 | 공식 헌액 연도 |
|---|---|---|
| Jim Leyland | 2023 | 2024 |
| Gil Hodges | 2021 | 2022 |
| Jim Kaat | 2021 | 2022 |
| Minnie Miñoso | 2021 | 2022 |
| Tony Oliva | 2021 | 2022 |

`hof_votes.json.year`에는 올바른 헌액 연도가 있지만 `js/awards.js`는 `awards.json`의 `row[1]`을 표시하고 기간 필터에도 쓴다. 선수 페이지도 같은 잘못된 연도로 “년 헌액”을 표시하며 구단 역사에도 전달된다. 원본의 선출 연도를 헌액 연도와 구별해야 한다. 단순히 투표 정보의 연도만 고쳐서는 해결되지 않는다.

## 3. 부문·회차 정보 손실과 통산 횟수

- **J.D. Martinez, 2018 실버슬러거**: 원본 API와 공식 표 모두 OF·DH 두 부문이다. `assemble()`의 중복 키에 부문이 없어 하나가 제거된다. 현재 통산 2회(2015·2018)로 계산되며 부문 기준 실제 3개 수상을 표현하지 못한다.
- **Shohei Ohtani, 2023 All-MLB 퍼스트 팀**: 공식 표에는 DH·SP 두 자리, API에는 SP 한 행만 있다. 현재 퍼스트 팀 기록은 5개 선정 연도이며 부문 기준 6개 자리다. 여기서는 원본 단계부터 DH가 빠진다.
- **1959~1962 올스타**: 한 해 두 경기의 동일 선수 행 196쌍을 합친다(1959 43, 1960 61, 1961 45, 1962 47). 따라서 현재 “통산 N회”는 대체로 선정 연도 수이며 경기별 선정 횟수와 다르다. 이를 무조건 오류 데이터로 복제하지 말고 “선정 시즌”과 “선정 횟수/부문”의 제품 정의를 정해야 한다.
- 2026 AL 재기상의 Yordan Alvarez 원본 2행은 같은 부문 중복이다. 진짜 복수 부문과 이런 단순 중복을 구별해야 하며, 중복 제거 자체를 없애면 안 된다.

## 4. 포지션 덮어쓰기: 691명, 4,907행

현재 인물 표에서 포지션이 빈 인물은 1,565명이다. 이 중 **691명은 같은 API 응답들에 정상 포지션이 존재하지만 최종 인물 표에는 빈 값**이다. 해당 인물이 등장하는 수상 행은 4,907개다. 나머지 빈 값은 감독·임원 등의 미제공도 포함하므로 모두 오류로 취급하지 않는다.

원인은 `assemble()`의 `people[id] = ...` 무조건 덮어쓰기다. 마지막에 읽는 월드시리즈 우승 데이터의 `X`가 빈 문자열로 변환돼 앞서 받은 정상 값을 지운다. 예: Chipper Jones는 HOF·MVP·실버슬러거 응답에서 3B이지만 WSCHAMP의 X가 최종값이 된다. 전체 691명과 원본에서 확인된 포지션은 API 상세 JSON의 `overwritten_positions`에 있다.

빈 값만의 문제가 아니다. API의 수상 행 포지션은 연도·부문에 따라 변하는데 이를 전역 인물 표 한 칸에 넣는다. 최신 실버슬러거를 포함해 조립하면 Kevin McGonigle은 SS→UT, Pete Crow-Armstrong은 CF→OF로 전역값이 바뀐다. 화면 설명의 “선수의 주 포지션”을 보장하지 않는 구조다. 프로필 주 포지션과 수상 부문을 별도 필드로 관리해야 한다.

## 5. 구단 불일치: 6건 검출, 판단 구분 필요

공식 표의 구단 도시명·역사적 이름을 팀 ID 후보로 변환해 비교했다. New York·Boston처럼 여러 구단이 가능한 도시명은 넓은 후보 집합으로 비교했으므로 같은 도시 내 잘못된 팀까지 모두 검출한다는 보장은 없다.

| 상·연도·인물 | 사이트/API | 공식 역대 표 | 판단 |
|---|---|---|---|
| 2026 All-MLB 2nd James Wood | CHC | Washington | 사이트/API 불일치. 같은 해 실버슬러거 API도 WSH여서 All-MLB 행 정정 필요 |
| 2016 GG Ian Kinsler | TEX | Detroit | 사이트/API 오류 확정. 당시 [수상 발표](https://www.mlb.com/press-release/ian-kinsler-named-rawlings-gold-glove-award-winner-at-second-base-208428540)도 Detroit |
| 1995 GG Wade Boggs | BOS | NY Yankees | 사이트/API 오류 확정. [명예의 전당 프로필](https://baseballhall.org/hall-of-famers/boggs-wade)도 Yankees에서 수상 |
| 2021 GG Joey Gallo | NYY | Texas | 시즌 중 이적. 수상 발표 시점 팀과 수비 성과를 낸 팀의 기준 차이 검토 필요 |
| 2021 Clemente Nelson Cruz | TB | Minnesota | 시즌 중 이적. 수상 팀 기준 차이 검토 필요 |
| 1995 SS Gary Gaetti | KC | Minnesota | 사이트가 맞음. [수여 기관 Louisville Slugger](https://www.slugger.com/en-us/pages/silver-slugger-awards)는 Kansas City. 공식 MLB 역대 표 오류 |

명예의 전당 팀은 별도 문제다. 빈 약칭 31명 외에 문자열 `No team`이 54명에게 있다. 구단 없는 명판과 원본 미제공을 구별하지 못하고, 화면의 “없으면 비워 둔다” 설명과도 다르다. 전원 명판 사진·공식 명판 선택 발표를 대조하지 않았으므로 85명을 일괄 보정하면 안 된다. 공식 인물 페이지의 Primary Team 역시 명판 모자 팀과 같은 뜻이 아니다.

구단 30개 파일의 우승·주요 수상 횟수·HOF 행은 현재 `awards.json`으로 다시 계산한 값과 일치한다. 즉 파생 파일의 별도 계산 오류는 확인되지 않았지만 원본 누락과 연도·팀 오류가 그대로 전파된다.

## 6. 명예의 전당 투표 세부 값

- 기자단 회원 중 득표율 null 1명, 득표수 null 5명, 투표 차수 null 65명이다. Lou Gehrig의 특별 선출과 초기 투표는 정상적인 미제공이 섞여 있다.
- 득표수가 비어 있는 사람: Roberto Clemente, Lou Gehrig, Rich Gossage, Fergie Jenkins, Red Ruffing.
- Clemente는 일반 연례 표가 아닌 특별 투표다. 393표는 [MLB의 특별 선출 설명](https://www.mlb.com/news/roberto-clemente-made-hall-of-fame-history)에서 확인된다. Ruffing은 결선 266표가 [명예의 전당 공식 설명](https://baseballhall.org/discover/inside-pitch/ruffing-elected-to-hall-of-fame-via-rare-runoff-election)에 있다. 일반 표 파서만으로 처리하기 어렵다.
- `parse_ballot()`는 같은 이름이 여러 표에 있으면 첫 값을 유지한다. 결선 선출자에게 본투표 수치를 붙일 위험이 있다. 이번에는 Ruffing이 null이므로 잘못된 본투표 숫자가 저장돼 있다고 단정하지 않는다.
- 이름 연결이 단계마다 다르다. 회원→수상 ID는 성만 유일하면 연결하는 보조 규칙이 있지만, 회원→연도별 표는 전체 이름 정규화만 사용한다. 실제 1937 Tris/Tristram Speaker, 1938 Grover Cleveland/Grover Alexander 이름 차이를 재현했다. 별명 문제를 동명이인 오연결 없이 해결해야 한다.
- 73개 연도 중 10개를 다시 받은 범위에서는 연결된 인물의 득표수·차수 불일치가 없었다. 나머지 63개는 429 제한으로 완료하지 못했다. 새 조사 도구는 429를 만나면 이후 요청을 중단하도록 수정했다. 이 부분은 전수 정확성 검증 완료로 보고하지 않는다.

## 7. 항목별 전체 결과

아래 “명단 대조 일치”는 독립 공식 표의 연도·이름 집합 비교 결과이며, 앞서 설명한 포지션·구단·회수 문제까지 정상이라는 뜻은 아니다.

| 항목 | 저장 행 | 제공 연도 | 점검 결과 |
|---|---:|---|---|
| 명예의 전당 | 346 | 1936~2026 | 8명 누락, 연도 5건 |
| MVP | 193 | 1931~2026 | 공식 명단 대조 일치 |
| 사이영상 | 132 | 1956~2026 | 공식 명단 대조 일치. 초기 양 리그 통합 수상 중복 제외 |
| 신인왕 | 160 | 1947~2026 | 공식 명단 대조 일치. 1947~48 통합 수상 중복 제외 |
| WS MVP | 74 | 1955~2026 | 공식 명단 대조 일치 |
| LCS MVP | 98 | 1977~2026 | 공식 명단 대조 일치 |
| 올스타 MVP | 65 | 1962~2026 | 공식 명단 대조 일치 |
| 올스타 | 5,586 | 1933~2026 | API 조립 결과 일치. 2경기 시절 회수 정보 손실 |
| All-MLB 1st | 126 | 2019~2026 | Sale 누락, Ohtani 2023 DH 자리 누락 |
| All-MLB 2nd | 127 | 2019~2026 | Williams 누락, Wood 팀 불일치 |
| 골드글러브 | 1,265 | 1957~2026 | 이름·연도 일치, 구단 3건 검출 |
| 플래티넘 글러브 | 31 | 2011~2026 | Giménez 누락 |
| 실버슬러거 | 836 | 1980~2025 | 2026년 20명 미반영, Martinez 복수 부문 손실 |
| 행크 애런상 | 54 | 1999~2025 | 2026년 2명 원본 누락 |
| 올해의 구원투수 | 26 | 2014~2026 | Rivera/Hoffman 상 계열 명단 일치 |
| 재기상 | 44 | 2005~2026 | 공식 명단 대조 일치. 원본 단순 중복 1건 |
| 클레멘테상 | 57 | 1971~2026 | 이름·연도 일치. Cruz 이적 팀 기준 차이 |
| 올해의 감독 | 89 | 1983~2026 | 공식 명단 대조 일치 |
| 월드시리즈 우승 | 2,510 | 1903~2026 | API 일치, 우승 구단·연도는 franchise 데이터와 일치 |

이름 별칭·오타 27개 비교 후보는 실제 누락에서 제외했다. 예: Mike/Michael Soroka, Dee Gordon/Dee Strange-Gordon, Jr./Sr., MLB 역대 표의 Ezquiel/Ezequiel Tovar와 Luiz/Luis Arraez. 실버슬러거 표의 2023~25 Team Award 행 6개는 개인 수상 범위 밖이다. 구원투수 페이지에 추가된 2026 BBWAA 상도 기존 Rivera/Hoffman 상과 분리해야 하며 Louis Varland를 기존 ALREL 수상자로 덮어쓰면 안 된다.

기록 공백도 실제 미개최와 구별했다. 1994 WS·LCS, 1904 WS, 1945·2020 올스타, 2002·2020 올스타 MVP의 빈 연도를 기계적으로 채우지 않는다.

## 8. 재현과 수정 순서

기존 테스트 `test_awards.py` 4개, `test_hof_votes.py` 3개 모두 통과했다. 기존 테스트는 실제 명단 완전성, 복수 부문, 포지션 덮어쓰기, 화면의 헌액 연도 선택을 검증하지 않으므로 통과가 데이터 정확성을 뜻하지 않는다. `git diff --check` 통과. 화면 변경이 없어 브라우저 UI 회귀 검사는 실행하지 않았다.

```powershell
# 사이트 데이터를 쓰지 않는 조사 도구. requests 외 추가 의존성 없음.
python scripts/audit_awards.py --out docs/awards-api-audit.json
python scripts/audit_awards_pages.py --out "$env:TEMP\bbaddanet-awards-audit\pages.json"
python scripts/compare_award_pages.py "$env:TEMP\bbaddanet-awards-audit\pages.json" docs/awards-page-audit.json
# 아래는 요청 제한이 해제된 뒤 재개. 연도별 캐시가 있는 파일은 재사용.
python scripts/audit_hof_votes.py "$env:TEMP\bbaddanet-awards-audit" "$env:TEMP\bbaddanet-awards-audit\votes-audit.json"
python -m unittest discover -s scripts -p test_awards.py
python -m unittest discover -s scripts -p test_hof_votes.py
git diff --check
```

`audit_awards.py`는 OS 임시 폴더의 URL별 캐시를 사용하며 `--refresh`로 다시 받는다. `audit_awards_pages.py`는 출력 폴더의 HTML 캐시를 재사용하므로 새 조사 때는 별도의 출력 폴더를 사용한다. 저장된 감사 결과는 조사 시점 스냅샷이며 캐시 재사용만으로 최신 원본을 다시 확인한 것은 아니다. 이 PC의 기본 python 별칭은 실행 차단되어 uv의 Python 3.11 실제 실행 파일과 이미 설치된 requests를 사용했다.

권장 수정 순서:

1. 부문·회차와 헌액 연도를 저장할 구조를 정하고, 정상 포지션을 빈 값으로 덮는 코드를 고친다.
2. 출처를 갖춘 누락 보완 자료와 명단 완전성 검사, 팀 정정 규칙을 도입한다. HOF 임원 등 MLB 선수 ID가 확인되지 않는 사람은 별도의 안전한 식별 방식이 필요하다.
3. 수상·투표·구단 역사 데이터를 순서대로 다시 만들고, 선수 경력 카드와 기간 필터·통산 횟수까지 검증한다.
4. 남은 독립 전수 검증: 63개 연도 투표 세부 값, HOF 명판 팀 전체, 올스타 경기별 선발·대체 명단과 개인 우승 제공 범위. 이번 검사 결과만으로 이 범위까지 무오류라고 선언하지 않는다.
