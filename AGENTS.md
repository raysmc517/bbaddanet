# 빠따넷 에이전트 작업 기준

이 파일은 Codex, Claude Code 등 이 저장소에서 작업하는 에이전트의 공통 기준이다. 사용자 지시를 우선하고, 제품 범위와 결정 사항은 `PRD.md`를 함께 확인한다.

## 작업 시작과 인계

- 작업 전에 이 파일, `PRD.md`, `git status --short`, 최근 커밋과 관련 코드를 확인한다.
- 다른 에이전트의 대화가 자동으로 공유됐다고 가정하지 않는다. 파일과 Git 기록으로 확인한 사실, 사용자 설명, 아직 확인하지 못한 내용을 구분한다.
- 기존 미커밋 변경은 보존한다. 요청 범위 밖의 코드나 데이터를 일괄 수정하지 않는다.
- 한국어로 소통하며, 완료 시 변경 내용·검증 결과·남은 일을 간결하게 전달한다. 실행하지 않은 검증을 통과했다고 보고하지 않는다.
- 제품 요구나 중요한 결정이 바뀌면 `PRD.md`를 갱신한다. 중단되는 작업은 관련 문서에 완료한 일, 남은 일, 재현 명령을 남겨 다음 에이전트가 이어갈 수 있게 한다.
- 사이트에 보이는 변경을 마치면 `docs/changelog.md`에 날짜별로 짧게 적는다. 새로 드러난 한계는 `docs/improvements.md`에 적고, 고친 항목은 그 파일에서 지운다. 원인과 해결 과정이 남길 만하면 `docs/devlog.md`에 적는다. 요구사항과 결정은 `PRD.md`에 둔다.
- 공통 규칙은 이 파일에서 관리한다. `CLAUDE.md`에 같은 규칙을 복제하지 않는다.

## 제품과 현재 구현

- 빠따넷은 야구 성적과 자체 계산 세이버매트릭스를 제공하는 개인 포트폴리오용 비상업적 사이트다.
- Python으로 수집·계산하고 HTML/CSS/JavaScript로 JSON을 읽는 정적 사이트 구조를 유지한다. 프레임워크, 서버, DB, 의존성은 작업에 필요한 경우에만 도입하고 이유를 설명한다.
- 2026-11-17 확인 기준: MLB, MiLB AAA·AA의 2024~2026 데이터, 리더보드, 선수 페이지, Pipeline 유망주 연계 코드가 있다. 코드가 있다는 사실을 기능 검증 완료로 간주하지 않는다.
- KBO·NPB 수집기, 용어 설명 페이지 등 PRD의 계획을 이미 구현된 기능으로 설명하지 않는다. 실제 파일과 실행 결과를 확인한다.
- 자동 갱신·배포는 `.github/workflows/update.yml`(매일 한국 시간 09:00·14:00, GitHub Pages)에 있다. 동작 여부는 GitHub Actions 실행 기록으로 확인한다.
- 현재 생성된 시즌 범위는 2024~2026이다. 추가 요구사항은 `PRD.md` 13절을 따른다: High-A·Single-A 확대, 마이너리그를 포함한 프로 첫 출전부터의 선수 커리어. 요구사항과 구현 완료 상태를 구분한다. MLB 데뷔일을 프로 데뷔일로 사용하지 않는다.

## 코드 위치와 변경 원칙

- `scripts/collectors/`: 외부 데이터 수집. `scripts/sabermetrics/`: 지표 및 파크팩터 계산.
- `scripts/build.py`: 데이터 생성 진입점. `scripts/prospects.py`: 유망주 스냅샷과 화면용 데이터. `scripts/validate.py`: MLB 공식 값과 비교.
- `scripts/teams.py`: MLB 구단·산하 구단·구장 정보와 구단 역사(`data/teams.json`). `scripts/awards.py`: 수상 기록·명예의 전당(`data/awards.json`). `scripts/hof_votes.py`: 명예의 전당 득표율·투표 차수(`data/hof_votes.json`).
- `scripts/past_players.py`: 은퇴 선수 등 과거 MLB 선수 추가. `scripts/search_index.py`: 선수 검색 색인(`data/search.json`).
- `scripts/moves.py`: 리그 전체 이동 소식(`data/moves_{시즌}.json`)과 입단 경로(`data/arrivals.json`). `scripts/past_moves.py`: 2009~2023 시즌 이적 기록. `scripts/franchise.py`: MLB 구단 연도별 성적(`data/franchise/`). `scripts/leaders.py`: 시즌·리그별 기록 1위(`data/leaders.json`). `scripts/standings.py`: 리그·지구별 순위(`data/standings_{시즌}.json`). `scripts/rosters.py`: MLB 구단 선수단(`data/rosters/{시즌}/{구단 ID}.json`).
- `index.html`, `standings.html`, `roster.html`, `player.html`, `prospects.html`, `teams.html`, `team.html`, `franchise.html`, `moves.html`, `awards.html`, `search.html`: 화면 진입점. `js/common.js`: 공통 표시 형식과 열 정의. `css/style.css`: 스타일.
- `data/`: 생성된 JSON과 랭킹 기록. 데이터 오류는 수집·계산 원인을 먼저 고친다. 대량 JSON을 손으로 수정하지 않는다.
- 기존 코드 스타일과 UTF-8 인코딩을 유지한다. JSON 필드 변경 시 생성 코드, 소비하는 화면, 기존 데이터와의 호환성을 함께 확인한다.
- 브라우저는 저장된 JSON을 읽는다. 원본 사이트의 수집 요청은 Python에서 수행한다.
- 표의 정렬·필터·검색, 선수 링크, 모바일 가로 스크롤을 보존한다. 누락된 값과 실제 0을 구분한다.
- 시즌·월 등 기간 선택 상자는 최신 기간이 먼저 오는 내림차순으로 둔다(2026-11-17 사용자 결정).

## 야구 데이터 원칙

- 이닝은 계산 시 아웃 수(`outs`)를 사용한다. 화면의 `5.1`은 5⅓이닝이므로 십진수 5.1로 계산하지 않는다.
- 리그·시즌·MiLB 레벨 및 하위 리그별 기준을 존중한다. 지표 공식이나 상수를 바꿀 때 근거와 결과 차이를 기록한다.
- 자체 계산 `sWAR`는 간이 WAR로 표시하고 공식 `WAR`와 구분한다. 리그 평균 100인 지표를 리그 간 절대 실력이 같다는 뜻으로 설명하지 않는다.
- MLB·MiLB·Pipeline 연결에는 MLB 선수 ID를 사용한다. 이름만으로 서로 다른 선수를 병합하지 않는다.
- 수집 실패나 빈 응답으로 정상 데이터를 덮어쓰지 않도록 한다. 마지막 정상 데이터와 갱신 시각을 구분하고, 실패를 성공처럼 표시하지 않는다.
- PRD의 출처·수집 범위를 따른다. 요청 간격을 유지하고 불필요한 재수집을 피한다. Pipeline 리포트 본문과 사진은 수집하지 않는다. 선수 얼굴 사진은 파일을 저장하지 않고 MLB 공식 이미지 주소로만 표시한다(`js/player.js`, 2026-11-17 사용자 결정).

## 실행과 검증

아래 명령은 저장소 루트에서 실행한다. Python 수집 코드는 `requests`를 사용한다. 처음 받은 PC에서는 `python -m pip install -r requirements.txt`로 설치한다. 외부 패키지를 추가하면 `requirements.txt`에 버전을 고정(`==`)해 적는다.

| 목적 | 명령 | 주의 사항 |
|---|---|---|
| 로컬 화면 확인 | `python -m http.server 8000` | `http://localhost:8000`에서 확인. 파일 직접 열기는 피한다. |
| 수집 옵션 확인 | `python scripts/build.py --help` | 옵션 확인용이다. |
| 전체 데이터 수집·생성 | `python scripts/build.py` | 외부 요청과 다수 JSON 변경이 발생한다. 데이터 작업에 필요한 경우 실행한다. |
| 성적 재수집 생략 | `python scripts/build.py --skip-stats` | 오프라인 모드가 아니다. Pipeline·프로필 등의 외부 요청과 파일 변경이 남는다. |
| 최근 시즌만 수집 | `python scripts/build.py --current-season` | 일일 자동 갱신과 같은 범위다. 끝난 시즌 파일은 그대로 둔다. |
| Pipeline 강제 갱신 | `python scripts/build.py --pipeline` | 성적 수집도 실행한다. 주간 랭킹 재사용을 건너뛸 필요가 있을 때 사용한다. |
| 공식 값과 대조 | `python scripts/validate.py 2026` | 기존 MLB JSON과 네트워크가 필요하다. 오차를 출력하는 비교 도구이며 자동 합격 판정 테스트가 아니다. |

- 문서만 수정할 때는 링크·명령·실제 코드와의 일치 및 `git diff --check`를 확인한다. 전체 수집을 실행할 필요는 없다.
- 화면 변경은 관련 페이지를 로컬 서버에서 확인하고 정렬, 필터, 링크, 좁은 화면 등 변경에 영향을 받는 동작을 검증한다.
- 계산 변경은 0분모, 누락값, 이닝 변환 등 관련 경계 사례와 대표 계산값을 검증한다. 필요하면 공식 값 비교도 수행하며 간이 WAR와 공식 WAR의 차이를 고려한다.
- 수집 변경은 실패·빈 응답 처리와 생성 JSON 구조를 확인한다. 전체 재수집 전에 가능한 한 작은 범위로 확인한다.
- 완료 전에 `git diff --check`와 변경 목록을 확인한다. 외부 접근이나 실행 환경 문제로 확인하지 못한 사항은 명시한다.

## 커리어 및 하위 레벨 확장 실행

- `python scripts/build.py --levels high_a single_a`: 두 레벨의 2024~2026 성적을 수집하고 선수·유망주 데이터를 재생성한다.
- `python scripts/careers.py`: 미수집 선수의 MLB·마이너리그 과거 정규시즌 기록을 수집한다. `--ids 694973`으로 범위를 좁히고 `--refresh`로 기존 캐시를 갱신한다. `--traded`는 최근 시즌에 여러 팀에서 뛰었는데 팀별 행 합이 시즌 합계와 맞지 않는 선수만 다시 받는다(일일 갱신에서 실행). 합이 맞으면 `merge_cached`가 최근 시즌 행에 팀별 행(`splits`)을 붙이고 선수 페이지가 "N팀" 아래에 보여준다.
- 과거 기록의 팀 표기는 최근 시즌과 같은 약자로 바꾼다. 레벨·시즌별 약자는 `data/team_abbr.json`에 저장하고 없는 레벨·시즌만 받는다. 원래 팀 이름은 행의 `teamName`에 남는다.
- 실행 순서: 성적 빌드 → 커리어 수집. 일반 빌드는 `data/careers/`의 과거 기록을 보존한다. 기존 커리어의 새 시즌·정정 기록까지 갱신하려면 `--refresh`를 사용한다.
- `python -m unittest discover -s scripts -p test_careers.py`: 중복·합계 행 제거, 과거 기록 갱신과 최근 세이버 지표 보존을 검증한다.
- 최초 제공 시즌은 정확한 프로 데뷔일과 다르다. 해외 리그 데이터 누락 가능성을 화면에 안내한다.

## 과거 선수(은퇴 선수)와 검색 실행

- `python scripts/past_players.py`: 1876년부터의 시즌별 MLB 명단으로 선수 ID를 모으고, 선수 파일이 없는 선수의 프로필과 커리어를 만든다. 은퇴 선수(프로필의 `past` 표시)는 MLB 기록을 받고, 2000년 이후 MLB 출전 기록이 있을 때만 마이너리그 기록도 받는다(`PAST_MINOR_FROM`, 2026-11-17 사용자 결정). `careers.py --refresh`도 이 기준을 따른다. 전체 실행은 요청이 1,000회 이상이고 파일 수만 개가 생기므로 먼저 `--ids 118377`이나 `--from 1999 --to 1999`로 좁혀 확인한다.
- 이미 있는 선수 파일은 덮어쓰지 않는다. 커리어가 없는 선수만 받으므로 중간에 끊겨도 다시 실행하면 이어진다.
- 과거 시즌의 세이버 지표는 계산하지 않는다(리그 상수·파크팩터 미수집). 최근 시즌 상수를 대신 적용하지 않는다.
- 옛 시즌은 원본에 없는 항목(도루 실패, 희생플라이, 고의4구, 홀드 등)이 있다. `careers.convert`는 이를 0이 아닌 `None`으로 저장한다.
- `python scripts/search_index.py`: 선수 파일로 `data/search.json`을 다시 만든다(외부 요청 없음). `build.py`와 `past_players.py` 끝에서도 실행된다.
- `python -m unittest discover -s scripts -p "test_*.py"`: 전체 단위 테스트.
- `data/careers/`와 `data/drafts/`는 수집 캐시이며 브라우저가 읽지 않는다. 배포 시 제외할 수 있다.

## 구단·구장 정보 실행

- `python scripts/teams.py`: MLB와 산하 마이너리그(AAA~Rookie) 구단·구장 정보를 6회 요청으로 받아 `data/teams.json`을 만든다. 실패하거나 MLB 구단 수가 30개가 아니면 기존 파일을 유지한다.
- 파크팩터는 성적 빌드 결과(`constants_{시즌}.json`)를 읽어 붙이므로 성적 빌드 뒤에 실행한다. 없는 값은 1.000으로 채우지 않고 미제공으로 둔다.
- `python -m unittest discover -s scripts -p test_teams.py`: 산하 구단 묶기, 모구단 불명 구단 제외, 파크팩터 누락, 도미니카 구장 위치 보정을 검증한다.
- 구장 사진·로고 파일은 저장하지 않는다. MLB 구단 로고는 MLB 공식 이미지 주소로(`js/team.js`, 2026-11-17 사용자 결정), MLB 구장 사진은 위키미디어 공용 자유 라이선스 사진 주소로 걸고 저작자·라이선스를 적는다(2026-11-18 사용자 결정). 지도는 좌표로 외부 지도 링크만 건다.
- `python scripts/venue_photos.py`: `teams.json`의 MLB 홈구장 이름(또는 `WIKI_TITLE`)으로 위키백과 대표 사진을 찾아 주소·저작자·라이선스를 `data/venue_photos.json`에 둔다(요청 약 60회). 자유 라이선스만 넣고, 요청이 실패한 구장은 이전 값을 쓴다. 구장이 바뀔 때 `teams.py` 뒤에 직접 실행한다.
- MLB 구단에는 구단 역사(`history`: 월드시리즈 우승 연도, MVP·사이영상·신인왕 횟수, 명예의 전당, 영구결번)와 소개 글(`note`)이 붙는다. 우승·수상·명예의 전당은 `data/awards.json`에서 팀 ID로 세므로 `awards.py` 뒤에 실행한다. 파일이 없으면 0이 아닌 미제공(`null`)으로 둔다. 영구결번은 구단별로 30회 더 요청한다.
- 소개 글은 `data/team_notes.json`(구단 ID → 글)에 직접 작성해 관리하는 파일이다. 스크립트가 만들지 않으며, 바뀔 수 있는 숫자(우승 횟수 등)는 글에 쓰지 않고 수집 데이터로 표시한다.

## 수상 기록·명예의 전당 실행

- `python scripts/awards.py`: `AWARDS` 목록의 상별 역대 수상자를 받아 `data/awards.json`을 만든다 (요청 68회: 상마다 `sportId=1` 응답과 필터 없는 응답. `sportId=1`만 쓰면 팀이 없거나 MLB 구단이 아닌 명예의 전당·수상 행이 빠진다. 그런 행은 팀을 비운다). 명예의 전당 연도는 헌액 연도로, 원본 선출일이 12월이면 다음 해다. 포지션은 선수 파일의 주 포지션을 먼저 쓴다. 하나라도 실패하거나 비면 기존 파일을 유지한다.
- 리그별로 나뉜 상(AL/NL MVP 등)은 하나의 키로 묶고 리그를 행에 남긴다. 행은 `[상 키, 시즌, 리그, 선수 ID, 팀 약칭, 팀 ID]`, 선수 표는 `{선수 ID: [이름, 포지션, 선수 페이지 여부]}`다.
- 선수 페이지 링크 여부는 `data/players/`에 파일이 있는지로 정하므로 `past_players.py` 뒤에 실행한다. 감독·구단주 등 선수 파일이 없는 인물은 링크 없이 이름만 보여준다.
- 포지션은 선수의 주 포지션이며 수상 당시 포지션이 아니다. 명예의 전당의 팀은 명판 기준이고 원본에 없으면 비운다.
- 자동 갱신에서는 월요일에만 `awards.py` → `teams.py` 순서로 실행한다.
- `python scripts/hof_votes.py`: 명예의 전당 선출 방식·득표율·득표수·투표 차수를 `data/hof_votes.json`으로 만든다. MLB API에 득표율이 없어 위키백과 공개 문서(회원 목록, 연도별 투표 결과, CC BY-SA)에서 사실 자료만 가져온다(요청 약 60회, 1.5초 간격). 자동 갱신에는 넣지 않고 선출 발표(1월 기자단, 12월 위원회) 뒤 `awards.py` → `hof_votes.py` 순서로 직접 실행한다.
- 선수는 `awards.json`의 명예의 전당 행과 같은 연도(없으면 앞뒤 1년, 전체 이름 일치만)·이름(Jr./Sr. 무시)으로 맞춘다. 맞추지 못한 회원은 넣지 않고 출력한다. 연도별 문서가 실패하면 그 연도만 득표수·차수를 비운다. 투표 차수는 원본 표에 차수 열이 있는 연도만 채운다.
- `python -m unittest discover -s scripts -p test_hof_votes.py`: 회원 목록·투표 표 해석, 위원회 칸, 이름·연도 맞추기를 검증한다.
- `python -m unittest discover -s scripts -p test_awards.py`: 리그 묶기, 중복 제거, 정렬을 검증한다.

## 구단 연도별 성적 실행

- `python scripts/franchise.py`: MLB 30개 구단의 1876년부터 시즌별 승패·순위·득실점·기대 승패·포스트시즌 결과를 `data/franchise/{구단 ID}.json`으로 만든다. 화면은 `franchise.html?id={구단 ID}`(구단 페이지의 구단 역사에서 연결). 시즌별 원본은 `data/franchise/seasons.json`(수집 캐시)에 두고 받은 시즌은 다시 받지 않는다. 처음 전체 실행은 요청 약 280회다. `--current-season`은 최근 시즌만(요청 2회) 받으며 자동 갱신이 매일 실행한다. `--refresh`는 전 시즌을 다시 받는다.
- 현재 구단 목록은 `data/teams.json`에서 읽으므로 `teams.py` 뒤에 실행한다. 팀 ID로 묶어 연고지 이전 전 시즌도 같은 구단이며 그 시즌의 팀 이름을 남긴다. 해체된 옛 구단은 넣지 않는다.
- 원본에 순위가 없는 옛 시즌(예: 1892)은 건너뛰고 알린다. 최근 시즌이 비거나 요청이 실패하면 받은 시즌까지만 캐시에 저장하고 화면용 파일은 바꾸지 않는다.
- 포스트시즌은 1903년부터이며 동률 결정전(R)은 넣지 않는다. 결과는 우승(WS), 월드시리즈 준우승(W), 챔피언십시리즈(L)·디비전시리즈(D)·와일드카드(F) 탈락이다.
- `python -m unittest discover -s scripts -p test_franchise.py`: 지구·리그 순위, 포스트시즌 결과 판정, 진행 중 시리즈, 기대 승패를 검증한다.

## 리그 1위 실행

- `python scripts/leaders.py`: 1876년부터 시즌·리그(AL·NL)별 주요 기록 1위를 `data/leaders.json`으로 만든다. 받은 시즌은 다시 받지 않고 최근 시즌만 다시 받는다. 처음 전체 실행은 요청 약 550회다. `--current-season`은 최근 시즌만 받으며(요청 4회) 자동 갱신이 매일 실행한다. `--refresh`는 전 시즌을 다시 받는다.
- 선수 페이지 연도별 성적의 MLB 행에서 1위 기록을 굵게 표시하는 데 쓴다. 동률은 모두 1위이고, 값이 0이거나 동률이 요청 한도(10명) 이상이면 비운다. 기록 키를 바꾸면 `js/common.js` 열 키와 맞춘다.
- 중간에 실패하면 받은 시즌까지만 저장하고 실패한 시즌은 기존 값을 유지한다. 다시 실행하면 이어서 받는다.
- `python -m unittest discover -s scripts -p test_leaders.py`: 1위 추출(동률, 0 값, 동률 한도)을 검증한다.

## 순위 실행

- `python scripts/standings.py`: MLB와 AAA~Single-A의 2024~2026 순위를 시즌별 파일로 만든다(시즌당 요청 약 17회). `--current-season`은 최근 시즌만 받으며 자동 갱신이 매일 실행한다. 실패하거나 MLB 구단이 30개가 아니면 그 시즌 파일을 유지한다.
- 시즌 목록(`SEASONS`)은 `build.py`와 같게 유지한다. 기대 승패는 자체 계산(피타고리안, 지수 1.83)이다.
- `python -m unittest discover -s scripts -p test_standings.py`: 기대 승패, 리그 묶기, 빈 응답·구단 수 검사를 검증한다.

## 구단 선수단 실행

- `python scripts/rosters.py`: 2024~2026 시즌마다 MLB 30개 구단의 시즌 선수단(원본 fullSeason)과 그 구단에서의 정규시즌 성적을 `data/rosters/{시즌}/{구단 ID}.json`으로 만든다. 최근 시즌 파일에는 기준일의 40인 명단(상태 포함, `current`)도 넣는다. 요청은 시즌당 약 121회, 최근 시즌은 31회 더. `--current-season`은 최근 시즌만 받으며 자동 갱신이 매일 실행한다. `--date 2026-08-01`로 40인 명단 기준일을 바꿀 수 있다. 한 구단이라도 실패하거나 인원이 비정상이면 그 시즌 파일을 하나도 바꾸지 않는다.
- 원본 40인 명단은 60일 IL 선수를 포함하므로 시즌 중 40인 수에서 뺀다. 액티브 로스터는 정규시즌·포스트시즌(`phase`)에만 보여준다. 비시즌에는 원본의 액티브 표시도 40인으로 보여준다.
- 부상 내용은 원본 영문을 그대로 보여주고 번역하거나 추정하지 않는다.
- 선수 이동(`moves`)은 구단·시즌당 `/transactions` 1회로 받고 `classify_move`가 MLB 관련 이동만 남긴다. 분류를 바꾸면 `js/roster.js`의 `MOVE_GROUPS`·`MOVE_LABEL`도 함께 고친다.
- 시즌 선수단의 기록은 `teamId`로 받은 구단 기록이라 이적 선수는 그 구단 기록만 들어간다. 리더보드의 시즌 합계와 다를 수 있다.
- `python -m unittest discover -s scripts -p test_rosters.py`: 시즌 단계, 정렬, 명단 크기 검사, 명단과 기록 합치기, 선수 이동 분류·중복 제거를 검증한다.

## 리그 이동 소식 실행

- `python scripts/moves.py`: `rosters.py`가 만든 구단별 이동(`moves`)을 합쳐 시즌마다 `data/moves_{시즌}.json`과 선수별 마지막 영입 색인 `data/arrivals.json`을 만든다. 외부 요청은 없으며 `rosters.py` 뒤에 실행한다. 자동 갱신은 선수단 단계에서 `--season`으로 최근 시즌만 다시 만든다.
- 넣는 이동은 트레이드·FA 계약·웨이버 클레임·40인 명단 등록·양도지명·아웃라이트·방출·FA 선언이다. 양쪽 구단에 있는 같은 트레이드·클레임은 한 건으로 묶는다. 분류는 `rosters.classify_move`를 따르므로 분류를 바꾸면 `js/moves.js`의 `TYPES`도 함께 고친다.
- 공식 처리된 이동만 있으며 보도·루머는 넣지 않는다. 입단 경로는 2009년 이후 이동(2024~는 `rosters.py`, 2009~2023은 `past_moves.py`)만 알며, 확인되지 않은 입단 경로는 연도를 추정하지 않고 미확인으로 표시한다.
- `python -m unittest discover -s scripts -p test_moves.py`: 트레이드 묶기와 방향, 클레임 중복 제거, 최신순, 마지막 영입을 검증한다.

## 과거 시즌 이적 기록 실행

- `python scripts/past_moves.py`: 2009~2023 시즌 MLB 30개 구단의 공식 이동 기록(`/transactions`)에서 이적(트레이드·FA 계약·웨이버 클레임·방출·FA 선언)만 골라 `data/moves_{시즌}.json`을 만든다(파일에 `scope: "transfers"`). 시즌당 요청 31회. 콜업·IL·양도지명 등은 넣지 않는다(2026-11-19 사용자 결정). 분류는 `rosters.classify_move`, 묶기는 `moves.assemble`을 그대로 쓴다.
- 원본 이동 기록은 2009년 무렵부터라(2008년 이전은 구단당 연 10건 안팎) 2009년부터 받는다. 이미 있는 시즌은 건너뛰고 `--refresh`로 다시 받는다. `--from`·`--to`로 범위를 좁힌다. 한 구단이라도 실패하면 그 시즌 파일을 만들지 않는다.
- 끝에 `moves.save_arrivals()`로 `data/arrivals.json`을 저장된 모든 시즌으로 다시 만든다. 일일 갱신의 `moves.py`도 같은 함수를 쓰므로 과거 시즌이 입단 경로에 유지된다. 과거 시즌은 바뀌지 않으므로 자동 갱신에 넣지 않았다.
- `js/moves.js`의 시즌 목록(2009~2026)과 맞춘다. `python -m unittest discover -s scripts -p test_past_moves.py`: 이적만 남기기, 모든 시즌으로 입단 경로 만들기를 검증한다.

## 입단 정보 실행

- 프로필은 최초 제공 시즌 대신 지명 연도·라운드·전체 순위·계약금을 표시한다. 국제 계약은 별도로 구분하며 확인된 출처가 없는 순위·계약금은 만들지 않는다. `python scripts/recruitment.py`로 생성하고 `--refresh`로 캐시를 갱신한다.
- 국제 아마추어 계약: `python scripts/recruitment.py --pipeline`이 MLB Pipeline 팀별 Top 30(요청 31회)에서 지명 없이 계약한 선수의 계약일·구단을 읽고, 소개 글의 "signed … for $X" 문장에서 금액만 뽑는다(본문 저장 안 함, 구단 한도 등 다른 금액 제외). `data/drafts/international_pipeline.json`에 쌓으며 순위에서 빠져도 지우지 않는다. 우선순위는 `recruitment_overrides.json` > Pipeline > 공식 지명. `python -m unittest discover -s scripts -p test_signings.py`로 날짜·금액 읽기를 검증한다.
- 해외 프로 리그 출신(`scripts/signings.py`): `python scripts/recruitment.py --foreign`이 위키백과 포스팅 표(NPB·KBO)에서 포스팅 날짜·전 소속팀·MLB 구단·포스팅 금액·MLB 계약을 읽는다. 일본·한국·대만 출신 MLB 선수 목록에서 포스팅이 아닌 선수는 선수 문서 정보 상자로 MLB 데뷔 전 마지막 해외 프로 구단(NPB·KBO·CPBL)을 찾아 "해외 리그 이적 (포스팅 아님)"으로 둔다(원본이 포스팅 여부만 구분하므로 해외 FA와 옛 임대·판매 이적을 나누지 않는다). 요청 약 80회, 1.5초 간격. 선수 연결은 MLB.com 주소의 ID를 먼저 쓰고, 없으면 이름이 한 명에게만 맞을 때만 연결한다. 미국 출신의 KBO·NPB 복귀 선수(예: Merrill Kelly)는 목록이 없어 넣지 않는다.
- 이동 기록 첫 계약: `python scripts/recruitment.py --transactions`가 미국·캐나다·푸에르토리코 밖 출신이고 지명 기록이 없으며 프로 첫 시즌이 2009년 이후인 선수의 `/transactions`에서 MLB 구단과의 첫 FA 계약(SFA)을 받아 `data/drafts/first_signings.json`에 쌓는다(선수당 1회, 받은 선수는 건너뜀, `--refresh`로 다시 받음). 원본 이동 기록은 2009년 무렵부터라 계약 연도가 프로 첫 시즌보다 늦거나 2년 넘게 이르면 첫 계약이 아닌 것으로 보고 버린다. 23세 미만의 마이너리그 계약은 국제 아마추어 계약, 나머지는 지명 없는 FA 계약이다. 계약금은 원본에 없다.
- 우선순위: `recruitment_overrides.json` > 공식 지명 > 포스팅·해외 리그 이적 > Pipeline 국제 계약 > 이동 기록 첫 계약. 화면 표시는 `js/player.js`의 `ENTRY_TYPE`과 맞춘다.
- `python -m unittest discover -s scripts -p test_signings.py`: 포스팅 표(합친 칸, 글로 쓴 날짜, 링크만 있는 행), 선수 목록 표시, 정보 상자 구단, 이름 순서, 첫 계약 판정을 검증한다.

## 금지약물 징계 표시

- `python scripts/ped.py`: 위키백과 "List of Major League Baseball players suspended for performance-enhancing drugs"에서 MLB·마이너리그 약물 방지 프로그램의 공식 징계만 받아 `data/ped.json`을 만든다(요청 1회). MLB API 이동 기록은 사유 없이 제한 명단(restricted list)으로만 적어 쓰지 않는다. 독립리그·국제대회 징계와 징계 없이 이름만 거론된 경우(미첼 보고서 등)는 넣지 않는다(2026-11-18 사용자 요구).
- 선수 연결: 이름(가운데 머리글자·Mike/Michael 차이 무시)이 한 명에게만 맞고 징계 연도가 그 선수의 프로 경력 기간 안일 때만. 동명이인은 투수·야수로 거르고, 그래도 여럿이면 넣지 않고 출력한다. 연결 수가 100명 미만이면 기존 파일을 유지한다.
- 화면: `js/common.js`가 모든 페이지의 선수 링크(`player.html?id=`) 뒤에 `*`를 붙이고, 선수 페이지는 이름 뒤 `*`와 징계 목록(날짜·구단·징계·검출 약물, 출처)을 보여준다. 자동 갱신에는 넣지 않았으므로 새 징계 발표 뒤 직접 실행한다.
- `python -m unittest discover -s scripts -p test_ped.py`: 합친 칸(rowspan), 서식·각주 정리, 독립리그 표 제외, 동명이인·경력 기간 밖 이름 제외를 검증한다.


## 지난 시즌과 비교 팝업

- 선수 상세 분석의 "지난 시즌과 비교" 팝업은 `js/season-compare.js`가 선수 파일과 `data/statcast/{시즌}.json`으로 그리고, 지표 목록·변화 계산은 `js/compare.js`를 쓴다(`player.html`이 함께 읽음). 비교 단위는 MLB·마이너의 시즌·레벨이며 Statcast는 MLB끼리만 비교한다. "MLB 기록만"은 MLB 기록이 두 시즌 이상일 때만 보이고 기본으로 켜진다(첫 콜업 시즌에는 숨김). 외부 요청·수집 스크립트가 없다. 지표 키를 바꾸면 `js/common.js` 열 키와 맞춘다. 상세는 PRD 21절.
- `node --test scripts/test_compare.cjs`(낮을수록 좋은 지표의 방향, 누락값, 변화 표기), `node --test scripts/test_season_compare.cjs`(시즌·레벨 목록, 기본 선택, 승격 전후, MLB 기록만, 여러 팀 합산 행).

## 선수 맥락·경기·뉴스·관심 목록 실행

- `python scripts/player_context.py`: 현재 시즌 MLB 평균과 득점권·좌우 상대·홈/원정 성적. `--from 1876 --to 2026 --averages-only`는 과거 평균만 받는다. 완료 시즌 평균은 재사용하고 `--refresh`로 갱신한다. 0분모·누락값과 아웃 수를 존중하고 실패 시 기존 시즌 파일을 유지한다.
- `python scripts/daily.py`: 최근 MLB 공식 경기일 3일과 MLB.com 공식 RSS 제목·출처·시각·링크. `--date 2025-09-28`로 날짜를 좁힌다. 본문·사진은 저장하지 않는다. 경기 일정의 정상 빈 응답은 비시즌이며 실패와 구분한다.
- `moves.save_arrivals()`는 입단 경로와 선수 전체 이적 색인(`data/player_moves.json`)을 함께 만든다. 선수 이적 내역은 연도 필터 없이 최신순이다.
- `data/contracts_manual.json`은 출처가 있는 수동 관리 자료이며 `contract_sources.py`가 Cot's 구단별 공개 사실 캐시와 합쳐 `data/contracts.json`을 만든다. 수동 자료를 우선하며 생성 파일을 직접 수정하지 않는다. `salaries`는 시즌 범위별 기본 연봉이며 계약금·보장 바이아웃은 별개 필드다. 단순 연평균을 연봉·실수령액·사치세 AAV로 설명하지 않는다. 미확인 연봉·이연액은 만들지 않는다. `salaryComplete`는 모든 보장 시즌 연봉+계약금+보장 바이아웃이 총액과 맞을 때만 켠다. 옵션 행사 결과는 출처를 붙여 조건에 남기고 최초 계약 총액에 임의로 더하지 않는다.
- 계약 변경 뒤 `python scripts/contracts.py`와 `node --test scripts/test_contracts.cjs`를 실행한다. 연도별 표는 `js/contracts.js`가 최신순으로 펼친다.
- 관심 선수·팀은 `js/favorites.js`가 이 브라우저의 localStorage에 ID·이름만 저장한다. 계정 동기화는 없다.
- 상세 요구·제공 범위는 PRD 16절. `test_player_context.py`, `test_daily.py`, `test_past_moves.py`로 계산·실패 처리·색인을 검증한다.


## Statcast 타구·구종 집계 실행

- `python scripts/statcast.py`: 2015~2026 MLB 정규시즌 공식 타구·구종 집계를 `data/statcast/`에 생성한다. `--season 2025`로 한 시즌, `--current-season`으로 최근 시즌만 받는다(시즌당 2회, 0.5초 간격). HTML·본문·영상·투구별 원본은 저장하지 않는다.
- 원본 구종 `n_ff` 등은 %지만 `n_fo`·`n_sc`는 0~1 비율이다. 개별 구종 모두 `n_{구종}_formatted` 백분율로 읽는다. 넓은 구종 묶음은 중복되므로 넣지 않고 사용률에서 개별 구수를 역산하지 않는다.
- `js/statcast.js`가 분석 시즌에 맞춰 타구 표·구종 표·수평/IVB 그림을 표시한다. 수직 값은 중력을 제외한 IVB이며 실제 궤적·낙폭과 구별한다. 속도는 km/h(mph), 움직임은 cm(in), 회전수는 rpm이다.
- 타구·구종 양쪽을 검증한 시즌만 교체한다. 빈 응답·시즌/리그 불일치·선수 수 급감 등은 기존 파일을 유지한다. 개별 누락 측정값은 0이 아닌 null이다.
- `python -m unittest discover -s scripts -p test_statcast.py`, `node --test scripts/test_statcast.cjs`로 변환·누락·비율 단위·실패 보존·시즌 전환 경쟁을 검증한다. 세부 범위는 PRD 17절.

- Statcast 완료 시즌은 캐시를 재사용한다. `--from 2015 --to 2023 --refresh`로 범위를 갱신하고 `--averages-only`로 외부 요청 없이 근사 평균을 계산한다. 타구는 BBE 가중, 투구는 구종·투구 손별 전체 구수×반올림 사용률 가중이다. 공식 공별 평균·정확한 구종 수로 설명하지 않는다. 양손 투수는 손별 표본을 보존한다.
- `python scripts/contract_sources.py`: Cot's 30개 구단 공개 계약 사실(요청 31회, 2초 간격). `--team PHI`로 좁히고 `--cached`로 외부 요청 없이 합성한다. 이름만으로 연결하지 않고 포지션·MLB ID 기반 구단 기록도 확인한다. 실패·급감 시 기존 구단 캐시 유지. 본문은 저장하지 않는다. 표제 구단·금액과 최초 계약 구단·확정 보장액을 구분하며 미확인 금액은 null이다. `test_contract_sources.py`로 파서·미확인·조건부 연봉 제외를 검증한다.

- 계약 수집은 월요일 첫 예약 실행에 포함한다. `contracts_sources/`와 `contracts_manual.json`은 합성용으로 브라우저가 읽지 않아 배포에서 제외한다. 생성된 `contracts.json`만 화면에서 읽는다.


## 입단 경로 보완

- `python scripts/arrivals.py`: MLB 및 산하 구단에 연결된 비과거 선수 전체 프로필을 점검하고 누락된 공식 영입(마이너 FA 포함)을 50명씩 조회한다. `--ids 571970`으로 좁히고 `--refresh`로 재검증한다. 일반 실행은 정상 캐시 재사용, 미확인 캐시 7일 뒤 재조회. 월요일 자동 갱신에 포함한다.
- `data/arrival_details.json`의 보완 사실을 `moves.save_arrivals()`가 색인에 유지한다. 기존보다 오래된 기록으로 최신 영입을 덮지 않는다. `arrivals.json`의 5번째 선택 필드는 공식 출처다. 마이너 FA는 입단 경로에만 추가하고 리그 전체 이동 범위는 유지한다. 확인되지 않은 경로를 ‘2009년 이전’으로 추정하지 않는다.
- `test_arrivals.py`와 `test_arrivals.cjs`로 먼시 마이너 계약, 현재 구단 불일치, 근거 없는 연도 추정 방지, 원본 실패와 일일 재생성 때 보존을 검증한다.

## 투구 위치·핫콜드존 실행

- 과거 제공 범위 확대: `python scripts/zones.py --from 2008 --to 2026 --workers 8`. 최신 시즌부터 순서대로 완료하며, 한 시즌이 실패해도 나머지 시즌을 계속 받고 마지막에 실패 시즌과 종료 코드 1을 남긴다. 요청 시작 사이 최소 1초를 유지한다. 재실행은 정상 구간 캐시를 재사용한다. 실제 화면 제공 연도는 `data/zones/index.json`을 따른다.
- 지난 시즌은 시즌이 끝난 뒤 확인한 정상 공개본과 버킷이 모두 있으면 건너뛴다. `--refresh`로 다시 받을 수 있다. 2008~2025 구간 캐시는 로컬 재개용으로 `.gitignore`에 등록해 Git 추적에서 제외하며, 현재 2026 캐시는 일일 갱신의 재수집 방지를 위해 계속 관리한다. 캐시 파일 자체를 지우지는 않는다.
- `python scripts/zones.py --season 2026`: 완료된 MLB 정규시즌 투구 CSV를 3일 단위로 읽어 위치 격자·구역별 집계를 만든다. 원본 공별 CSV는 저장하지 않는다. 첫 실행은 시즌 전체 요청이 필요하며 중단 뒤 재실행하면 구간 집계 캐시를 재사용한다. `--current-season`은 한국 시간의 현재 연도, `--refresh`는 기존 캐시를 다시 받는다.
- `data/zones/cache/{시즌}/`는 집계 캐시로 배포에서 제외한다. 화면은 `data/zones/index.json`, 시즌 색인, 해시가 붙은 선수 ID 끝 두 자리 버킷만 읽는다. 실패·누락 경기·응답 한도·급감 시 기존 공개 버전을 유지한다. 새 버킷을 모두 쓴 뒤 색인을 바꾸고 직전 버전도 한 세대 남긴다.
- `js/zones.js`는 분석 시즌과 함께 전환한다. 좌표는 포수 시점, 높이는 타자별 존 하단 0·상단 1로 정규화한다. 2026부터의 중앙 플레이트·ABS 존과 이전 기준을 합치지 않는다. 점은 작은 위치 격자의 빈도이며 실제 공별 점·목표 대비 제구 점수가 아니다.
- 타율·장타율은 타석 종료 투구의 안타/타수·루타/타수, 헛스윙률은 헛스윙/스윙이다. 주자 아웃·볼넷·사구·희생타 등을 타수로 세지 않는다. 위치 누락·0분모와 실제 0을 구분한다. 색은 해당 필터의 선수 전체 대비이며 10타수·20스윙 미만은 회색이다. 상세 정의는 PRD 20절을 따른다.
- `python -m unittest discover -s scripts -p test_zones.py`, `node --test scripts/test_zones.cjs`로 좌표 경계·분모·누락·중복·실패 보존·시즌 전환 경쟁을 검증한다.
- `python scripts/audit_zones.py --report docs/zones-audit-2026-11-20.md`는 외부 요청 없이 실제 제공 버킷의 해시·선수 연결·합계·분모를 전수 검사한다. 2008~2026 19시즌 백필은 완료했으며 상세 범위는 보고서를 따른다.
