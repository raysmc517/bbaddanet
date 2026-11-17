# 빠따넷 (bbaddanet)

**사이트 바로가기: https://raysmc517.github.io/bbaddanet/** (매일 한국 시간 16:00 자동 갱신)

MLB, MiLB, NPB, KBO 선수의 성적과 세이버매트릭스 지표를 한곳에서 조회하는 웹사이트입니다.
MiLB 성적은 MLB Pipeline 유망주 랭킹과 연결해 유망주의 순위와 마이너리그 성적을 함께 보여줍니다.

- 성격: 개인 포트폴리오 프로젝트 (비상업적)
- 데이터 처리: Python
- 화면: HTML / CSS / JavaScript (프레임워크 없음)
- 운영: 서버·DB 없이 정적 파일로 호스팅

> 현재 구현된 리그는 **MLB와 MiLB(AAA·AA·High-A·Single-A)** 입니다.
> MLB·MiLB만으로도 데이터가 많아 KBO·NPB는 데이터 출처의 이용 조건 문제로 수집을 보류했습니다. 자세한 내용은 [KBO·NPB](#kbonpb) 항목을 참고하세요.

## 주요 기능

| 기능 | 페이지 | 상태 |
|---|---|---|
| 리더보드: 리그·시즌·레벨·타자/투수 선택, 정렬, 팀·포지션·최소 타석(이닝) 필터, 기본/세이버 보기 전환 | `index.html` | 구현 |
| 선수 페이지: 프로필, 지명·계약 정보, 마이너리그를 포함한 연도별 커리어, Pipeline 순위 | `player.html` | 구현 |
| 순위: MLB 지구·와일드카드 순위, 마이너리그 리그·지구별 순위와 전·후반기 순위, 자체 계산 피타고리안 기대 승패 | `standings.html` | 구현 |
| 유망주: Pipeline Top 100·팀별 Top 30과 현재 레벨의 MiLB 성적, 주차별 순위 변동 | `prospects.html` | 구현 |
| 구단·구장: MLB 30개 구단과 산하 마이너리그 구단의 홈구장 정보, 자체 계산 파크팩터, 구단 역사(월드시리즈 우승, 영구결번, 명예의 전당, 소개 글) | `teams.html`, `team.html` | 구현 |
| 수상 기록: 명예의 전당과 MVP·사이영상·신인왕·골드글러브·올스타 등 역대 수상자, 선수 페이지의 수상 경력 | `awards.html`, `player.html` | 구현 |
| 선수 검색: 은퇴 선수를 포함한 MLB 출전 선수 전원 영문 이름 검색 | `search.html` | 구현 |
| 용어 설명 | `glossary.html` | 계획 |
| KBO·NPB 리더보드 | - | 보류 |
| 자동 갱신·배포 (GitHub Actions, GitHub Pages) | `.github/workflows/update.yml` | 구현 |

- 시즌별 리더보드는 최근 3개 시즌(2024~2026)을 제공합니다.
- 선수 커리어는 MLB 데뷔가 아닌 **프로 첫 출전 시즌부터** 보여줍니다. 원본이 정확한 데뷔일을 주지 않으므로 날짜를 추정하지 않습니다.
- 은퇴 선수는 MLB 정규시즌 기록을 제공하고, 2000년 이후 MLB에 출전한 은퇴 선수는 마이너리그 정규시즌 기록(재활 경기 포함)도 제공합니다. 원본이 1990년대 초 이전 마이너리그 기록을 거의 주지 않기 때문입니다.
- 원본에 없는 시즌·지표는 0이 아닌 미제공(`-`)으로 표시합니다.

## 제공 지표

### 타자

| 구분 | 지표 |
|---|---|
| 기본 | G, PA, AB, H, 2B, 3B, HR, R, RBI, BB, SO, SB, CS, AVG, OBP, SLG, OPS |
| 세이버 | ISO, BABIP, BB%, K%, wOBA, wRC+, 간이 WAR(sWAR) |

### 투수

| 구분 | 지표 |
|---|---|
| 기본 | G, GS, W, L, SV, HLD, IP, H, R, ER, HR, BB, SO, ERA, WHIP |
| 세이버 | K/9, BB/9, K%, BB%, K-BB%, BABIP, LOB%, FIP, ERA-, FIP-, 간이 WAR(sWAR) |

### 계산 원칙

- wOBA 가중치, FIP 상수, 리그 평균은 리그·시즌(MiLB는 레벨)별로 직접 계산합니다.
- wRC+, ERA-, FIP-에는 팀별 홈/원정 득점으로 구한 파크팩터를 적용하며, 기준(100)은 하위 리그(AL/NL, INT/PCL 등) 평균입니다.
- 시즌 중 팀을 옮긴 선수는 파크팩터를 중립(1.000)으로 둡니다.
- 이닝은 아웃 수로 계산합니다. 화면의 `5.1`은 5⅓이닝입니다.
- 자체 계산 WAR은 수비 데이터가 부족하므로 **간이 WAR(sWAR)** 로 표기합니다. MLB는 공식 WAR을 별도 `WAR` 열로 함께 보여줍니다.
- 리그 평균이 100인 지표는 각 리그 안에서의 상대 위치이며, 리그 간 절대 실력이 같다는 뜻이 아닙니다.
- 과거 시즌의 리그 상수·파크팩터가 없으면 최근 값을 대신 쓰지 않고 세이버 지표를 미제공으로 남깁니다.
- MLB 자체 계산값은 `scripts/validate.py`로 공식 API 값과 대조합니다.

## 데이터 출처

| 대상 | 출처 | 방식 |
|---|---|---|
| MLB | MLB Stats API (`statsapi.mlb.com`) | API 호출 |
| MiLB (AAA·AA·High-A·Single-A, 커리어용 하위 레벨) | MLB Stats API | API 호출 |
| 유망주 랭킹 | MLB Pipeline (`mlb.com/prospects`) | 순위·포지션·예상 데뷔 연도만 주 1회 스냅샷. 리포트 본문과 사진은 수집하지 않음 |
| 구단·구장 | MLB Stats API | API 호출. 사진·로고는 수집하지 않음(MLB 구단 로고는 공식 이미지 주소로 표시). 지도는 외부 링크로 연결 |
| 선수 얼굴 사진 | MLB 공식 이미지 서버 (`img.mlbstatic.com`) | 저장하지 않고 선수 ID별 이미지 주소로 표시 |
| 수상 기록·명예의 전당·영구결번 | MLB Stats API | API 호출 (상 하나당 1회, 주 1회 갱신) |

- MLB·MiLB·Pipeline은 같은 MLB 선수 ID로 연결합니다. 이름만으로 선수를 합치지 않습니다.
- 방문자의 브라우저는 원본 사이트를 호출하지 않고, Python이 미리 만든 JSON만 읽습니다.
- MLB 기록 출처: MLB Stats API. Copyright MLB Advanced Media, L.P. 비상업적 개인 프로젝트입니다.

### KBO·NPB

처음 계획은 네 리그를 모두 제공하는 것이었지만, 2026-11-17 확인 결과 두 리그 모두 승인 없이 수집하지 않기로 했습니다.

- **KBO**: `koreabaseball.com/robots.txt`가 사전 승인 없는 자동 수집을 금지하고 모든 경로를 막고 있습니다.
- **NPB**: `npb.jp`의 모든 페이지 하단에 게재 정보의 2차 이용·무단 전재 금지가 명시되어 있습니다.
- MLB Stats API에도 KBO·NPB 항목이 있지만 2025~2026 응답이 비어 있어 대체 출처가 되지 못합니다.

이용 승인을 받거나 이용이 허용된 다른 출처를 찾으면 수집기를 추가할 예정입니다. 결정 경과는 [PRD.md](PRD.md) 12절에 기록합니다.

## 실행 방법

Python 3과 `requests`가 필요합니다. 아래 명령은 저장소 루트에서 실행합니다.

```bash
pip install -r requirements.txt
```

### 화면 보기

```bash
python -m http.server 8000
```

브라우저에서 `http://localhost:8000`을 엽니다. HTML 파일을 직접 열면 JSON을 읽지 못하므로 로컬 서버를 사용합니다.

### 데이터 생성

| 목적 | 명령 |
|---|---|
| 전체 성적 수집·계산 (외부 요청과 다수 JSON 변경 발생) | `python scripts/build.py` |
| 특정 레벨만 수집 | `python scripts/build.py --levels high_a single_a` |
| 최근 시즌만 수집 (일일 자동 갱신과 같은 범위) | `python scripts/build.py --current-season` |
| 성적 재수집 생략 (Pipeline·프로필 요청은 남음) | `python scripts/build.py --skip-stats` |
| Pipeline 랭킹 강제 갱신 | `python scripts/build.py --pipeline` |
| 선수별 과거 커리어 수집 (`--ids`로 범위 지정, `--refresh`로 갱신) | `python scripts/careers.py` |
| 지명·계약 정보 생성 | `python scripts/recruitment.py` |
| 수상 기록·명예의 전당 생성 | `python scripts/awards.py` |
| 구단·구장 정보와 구단 역사 생성 (수상 기록 뒤에 실행) | `python scripts/teams.py` |
| 리그·지구별 순위 생성 (`--current-season`으로 최근 시즌만) | `python scripts/standings.py` |
| 은퇴 선수 등 과거 MLB 선수 추가 | `python scripts/past_players.py` |
| 선수 검색 색인 생성 | `python scripts/search_index.py` |
| MLB 공식 값과 대조 | `python scripts/validate.py 2026` |

권장 순서는 성적 빌드 → 커리어 수집입니다. 수집이 실패하거나 빈 응답이 오면 기존 정상 데이터를 덮어쓰지 않습니다.

### 자동 갱신·배포

[`.github/workflows/update.yml`](.github/workflows/update.yml)이 GitHub 서버에서 실행됩니다. PC가 꺼져 있어도 됩니다.

| 언제 | 하는 일 |
|---|---|
| 매일 한국 시간 16:00 (UTC 07:00) | `build.py --current-season`으로 최근 시즌 성적을 수집·계산하고, 바뀐 `data/`를 커밋한 뒤 GitHub Pages에 배포 |
| `main`에 push | 수집 없이 배포만 |
| Actions 탭에서 직접 실행 | 수집과 배포 |

- 16:00은 미국 동부 새벽 2~3시, 서부 자정 무렵으로 전날 경기가 끝난 뒤입니다. GitHub 사정으로 실행이 몇십 분 늦어질 수 있습니다.
- 끝난 시즌, 은퇴 선수(`past_players.py`), 과거 커리어 갱신(`careers.py --refresh`)은 거의 바뀌지 않으므로 매일 돌리지 않고 필요할 때 직접 실행합니다.
- Pipeline 랭킹은 `build.py`가 주 1회만 새로 받습니다.
- 수상 기록(`awards.py`)과 구단 정보(`teams.py`)는 월요일에만 다시 받습니다.
- 일부 리그·시즌이 실패하면 그 부분은 직전 데이터를 유지하고 나머지만 반영합니다. 실패는 Actions 실행 결과에 경고로 남습니다.
- 배포본에는 브라우저가 읽지 않는 수집 캐시(`data/careers/`, `data/drafts/`)를 넣지 않습니다.

### 테스트

```bash
python -m unittest discover -s scripts -p "test_*.py"
```

## 폴더 구조

```
bbaddanet/
├─ scripts/
│  ├─ collectors/      수집기 (statsapi.py, pipeline.py)
│  ├─ sabermetrics/    지표 계산(calc.py), 파크팩터(parkfactors.py)
│  ├─ build.py         성적 수집·계산 진입점
│  ├─ careers.py       선수별 과거 커리어 수집·캐시
│  ├─ recruitment.py   지명·계약 정보
│  ├─ prospects.py     유망주 스냅샷과 화면용 데이터
│  ├─ awards.py        수상 기록·명예의 전당
│  ├─ teams.py         구단·산하 구단·구장 정보, 구단 역사
│  ├─ past_players.py  은퇴 선수 등 과거 MLB 선수
│  ├─ search_index.py  선수 검색 색인
│  ├─ validate.py      MLB 공식 값과 대조
│  └─ test_*.py        단위 테스트
├─ data/
│  ├─ mlb/             MLB 시즌별 성적·리그 상수
│  ├─ milb/            레벨별 성적, 유망주, Pipeline 주차별 랭킹
│  ├─ players/         선수별 상세 ({선수ID}.json)
│  ├─ careers/         커리어 수집 캐시 (화면에서 읽지 않음)
│  ├─ drafts/          지명 정보 캐시 (화면에서 읽지 않음)
│  ├─ teams.json       구단·구장·구단 역사
│  ├─ team_notes.json  구단 소개 글 (직접 작성해 관리)
│  ├─ awards.json      수상 기록·명예의 전당
│  ├─ standings_{시즌}.json  레벨·리그·지구별 순위
│  ├─ recruitment.json 지명·계약 정보
│  ├─ search.json      선수 검색 색인
│  └─ meta.json        리그·시즌 목록, 마지막 갱신 시각
├─ index.html          리더보드
├─ player.html         선수 페이지
├─ standings.html      순위
├─ prospects.html      유망주
├─ teams.html          구단 목록
├─ team.html           구단·구장 상세
├─ awards.html         수상 기록·명예의 전당
├─ search.html         선수 검색
├─ css/
└─ js/
```

## 진행 단계

| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | MLB 수집기, JSON 출력, 리더보드 | 완료 |
| 2 | 선수 페이지, MiLB 추가 | 완료 |
| 3 | 세이버 계산 모듈 | 완료 |
| 4 | MLB Pipeline 연계 | 완료 |
| 추가 | High-A·Single-A, 프로 데뷔부터 커리어, 입단 정보, 구단·구장, 은퇴 선수 검색, 수상 기록·명예의 전당, 구단 역사 | 완료 |
| 5 | KBO 수집기 | 보류 (출처 이용 조건) |
| 6 | NPB 수집기 | 보류 (출처 이용 조건) |
| 7 | 자동 갱신, 배포, 용어 설명 | 진행 중 (자동 갱신·배포 구현, 용어 설명 예정) |

남은 일: 한글 이름 표기와 한글 검색, 과거 시즌 세이버 지표, 팀 로스터·합산 성적, 용어 설명.
제품 요구사항과 결정 사항 전체는 [PRD.md](PRD.md)를 참고하세요.
