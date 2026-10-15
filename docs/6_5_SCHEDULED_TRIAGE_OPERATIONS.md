# 6_5 승인 RSS 2종 실운영 정기 실행 — 2026-10-14

## 현재 설치 설정 — 2026-10-15 Gemini 연결

core/MOTIR 두 기존 서비스 모두 `--analysis-model-config`와 `--allow-paid-ai`, `--analysis-ai-ledger`를 설정하여 Gemini·캐시·공유 월 한도를 사용한다. 모델은 Mac 사용자 전용 `ai-settings/gemini_v3.json`, 공통 원장은 `state/ai_costs.sqlite3`. 기존 plist는 `launchd/*.before_gemini.plist`로 백업했다. 서비스 재등록·첫 실행 정상, core 건강도 정상 확인. 원문·키는 로그로 출력하지 않는다. 회복용 replay와 dry-run은 유료 호출하지 않는다.


> 현재 운영 기준은 [D-059](V1_RELEASE_POLICY_2026-10-15.md)이다. 아래는 당시 구현·실행 이력이며, 500건 검수·5거래일 사전 대기·독립 장치/릴리스 인증 조건은 현재 필수가 아니다. 예약 AI는 모델 설정과 `--allow-paid-ai`로 활성화할 수 있다.

## 실행 대상
- macOS 사용자 `launchd` 라벨: `com.newscatalystos.triage`
- Mac 비공개 로그인 에이전트: `~/Library/LaunchAgents/com.newscatalystos.triage.plist`
- 실행: `/Volumes/T5DATA/1.NewsCatalystOS/scripts/run_scheduled_triage.py --once` (Python 3.12, `PYTHONPATH=src`). **매 3,600초(1시간)** 시작하되 `RunAtLoad=false`, `KeepAlive=false`로 무한 재시작하지 않음. 중첩 호출은 macOS launchd의 단일 라벨/프로세스 제약과 기존 1_3 SQLite 요청 예산이 보호한다.
- 소스는 기존 Mac 소유/승인 등록부의 `mss-official-press`, `newswire-public-rss-it` **두 이름을 plist에 고정**했다. 새 등록부 소스를 실수로 자동 수집하지 않음. 권한이 해제되면 해당 소스는 `DATA_UNAVAILABLE`, 나머지는 격리 실행. 개발 목적 외 SNS/유료 원문/DART·SEC·KRX/EraLeader 원본/AI 호출·자동매매·웹사이트 기능 없음.
- `run_scheduled_triage.py`는 기존 `run_feed_triage.evaluate`를 호출하고, 기존 허용 RSS 1회 GET→메타 SHA checkpoint→SQLite 수신/중복→최초 분석→private triage 게시→ACK 흐름을 그대로 재사용한다. 요청 예산/백오프·명시 재수신 방지는 `incremental_ingest.py` 단일 구현이 담당한다. 한 제공자가 실패해도 다른 제공자의 호출을 진행한다.
- 로그는 Mac 내부 `~/Library/Application Support/NewsCatalystOS/logs/triage_stdout.log` 및 `triage_stderr.log` (소유자만 읽기 0600). 제공자 ID·건수·결과 상태만 기록하고 기사 본문/비밀키/유료 원문/증거 원문은 출력하지 않는다. 각 작업은 완료 후 종료하며 장기 메모리 점유 작업 아님.

## 실제 설치·단발 구동 증거
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/run_scheduled_triage.py --dry-run \
 --registry "$HOME/Library/Application Support/NewsCatalystOS/providers/authorized_sources.json" \
 --provider-id mss-official-press --provider-id newswire-public-rss-it
PYTHONPATH=src python3 scripts/create_triage_agent.py --write
plutil -lint "$HOME/Library/LaunchAgents/com.newscatalystos.triage.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.newscatalystos.triage.plist"
launchctl kickstart "gui/$(id -u)/com.newscatalystos.triage"
launchctl print "gui/$(id -u)/com.newscatalystos.triage"
tail -n 5 "$HOME/Library/Application Support/NewsCatalystOS/logs/triage_stdout.log"
PYTHONPATH=src python3 scripts/check_feed_operations.py
```
- **2026-10-14 Mac 실제 실행:** 설치 전 label 미존재, `--dry-run` 두 승인 제공자 확인/HTTP 0. plist `plutil -lint: OK`, `launchctl bootstrap` 정상. 최초 `kickstart` 성공/label `runs=1`/`last exit code=0`/`run interval=3600 seconds`. 로그에 두 제공자 `FEED_METADATA_TRIAGE_READY` 기록, 실패 0, 신규 ID 0, 키워드 후보 0, AI/DART/SEC/KRX 요청 0. 로그 파일 0600 소유자 전용.
- 시작 전 6_5 실운영 자료는 2026-10-14 승인 2곳 완료 ACK 2개와 실제 운영날짜 1개였다. 같은 날짜 여러 번 재실행하더라도 일자 수는 1개이며 5거래일 자동으로 소급 인증하지 않는다. **시간이 지나 Mac이 켜 있고 SSD가 마운트된 상태에서 실제 개별 종료 코드/ACK가 누적되어야 운영일로 인정 가능**하다.
- 위 실동작은 현재 설치 확인 결과만 말한다. Mac 절전, 사용자 로그아웃, T5DATA SSD 분리, RSS 네트워크/권한 장애 시 실행 성공은 보장하지 않는다. 재연결 후 `check_feed_operations.py`/stderr로 실패를 확인하고 필요하면 무네트워크 `--replay-only`를 먼저 사용한다.

## 안전한 중지/조회·설정 변경
```sh
# 설치 및 현재 프로세스/실행 주기 확인 (네트워크 요청 없음)
launchctl print "gui/$(id -u)/com.newscatalystos.triage"
# 자동 작업 중단 (실행 데이터/ACK/DB/백업은 유지)
launchctl bootout "gui/$(id -u)/com.newscatalystos.triage"
# 자동 시작 방지(로그인 재진입도 중지): 소유자의 LaunchAgents plist를 별도 비활성 폴더로 옮김.
# 다시 시작하려면 plist를 확인한 뒤 해당 LaunchAgents 경로로 복구해 bootstrap 사용.
```
- 다른 `com.newscatalystos.incremental` 개발용 템플릿은 **설치/활성화하지 않았다**. 같은 RSS를 두 스케줄러로 중복 요청하지 않도록 한다.
- 서비스 스키마·출처 추가/주기 변경 시 기존 동작 및 로그인 plist를 임의 덮어쓰지 않고 운영 점검·백업을 먼저 확인한다. `create_triage_agent.py --write`는 기존 파일을 덮어쓰지 않는 `O_EXCL` 방식이다.

## V1.0 인수 경계
- 실제 5개 **거래소 거래일**, 동시 모든 승인 소스 정상/장애 후 회복, PIT/원장 무결성, 미처리 0 등은 향후 실제 운영 기록으로 인수. `weekday_candidate_days`는 단순 월~금이며 한국/미국 증시 휴장·실제 거래일 검증을 대신할 수 없다.
- 로컬 다른 물리 장치 드라이브 간 DR/SHA PIN 검증은 이미 완료했지만, 원거리 오프사이트 백업과 5거래일 동작, 5_2 공식 반도체 거래문서, AI 실비용 및 500건 독립 라벨 검증은 미완료. **23/36 유지**, `6_5` 최종 완료·V1.0 릴리스 태그는 보류.


## 2026-10-14 | 실사용 자동작업 상태 진단 (6_5 health)
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/check_triage_agent_health.py
```
- 기존 서비스/승인RSS를 **읽기 전용** 조회한다. 새 수집·API·AI 호출, launchctl 시작/중지, 운영 원장/백업/로그 수정 없음. 종료코드 0은 최근 관측된 자동실행 상태 OK, 종료코드 4는 운영자 점검 필요.
- 실제 owner-only Mac LaunchAgent plist를 기존 승인 2소스/1시간 설정과 비교하고, `launchctl print`의 실행 횟수·마지막 종료코드·간격 및 오래되지 않은 마지막 stdout JSON을 확인한다. 비활성 `com.newscatalystos.incremental` 중복 실행 시 오류로 보고한다.
- `AGENT_HEALTHY_OBSERVED` 는 로컬 자동실행이 최근 정상이라는 **운영 건강도만 뜻하며**, 뉴스 최신성·공시 첫 공개시각·5거래일 인증·실제 공급관계/수혜·V1 출시 합격은 뜻하지 않는다.
- 대표 실패사유: `AGENT_NOT_LOADED`(스케줄러 정지), `NO_RECENT_TICK`(마지막 로그가 2시간 15분보다 오래됨), `LAST_RUN_FAILED`, `AGENT_CONFIG_MISMATCH`, `LAST_TICK_UNVERIFIED`, `DUPLICATE_SCHEDULER_ACTIVE`. 맥북 잠자기·SSD 연결해제·권한 오류가 발생한 경우 원인 확인 후 기존 `check_feed_operations.py`로 실제 ACK/PIT/물리복원 여부를 따로 확인한다.
- Mac 로그는 사용자의 `~/Library/Application Support/NewsCatalystOS/logs/` 내부 owner-only 파일을 마지막 일부만 읽는다. 로그 원문·개인경로는 JSON에 출력하지 않으며 Private 저장 원칙을 유지한다. 서비스 간격 중 `state=not running`은 정상일 수 있으므로 오류로 간주하지 않는다.
- 실제 2026-10-14 Mac 단발 검증: `runs=4`, `last_exit_code=0`, 승인 제공자 2개, `AGENT_HEALTHY_OBSERVED`, 외부 신규 API 0, 인수 운영일은 별도 1일 기록에 머문다. 기능은 자동 운영 완료를 인증하거나 V1.0 태그를 발급하지 않는다.


## 과거 이력: 2026-10-14 Gold 예약 등록 / 2026-10-15 비활성화

현재 `com.newscatalystos.gold`는 사용자 운영규칙 간소화에 따라 disable·bootout 완료했다. 기존 연구 자료와 plist는 보존한다. 아래는 등록 당시 이력이다.

- 기존 `com.newscatalystos.triage` RSS 2제공자 1시간 수집·분석/예산·PIT 서비스와 독립적으로 Mac 사용자 `com.newscatalystos.gold`를 새로 등록했다. `gold`는 **RSS HTTP를 호출하지 않으며**, 이미 완료된 SHA 검증 ACK·기수집 뉴스 메타에서 신규 동결 후보만 수집해 private T5DATA 골드/별도 Mac PIN·두 빈 검수자 시트를 생성한다. 실 AI 호출/사람 정답 자동 생성 없음.
- 기존 RSS LaunchAgent plist·EraLeader 원본·DB·Git은 건드리지 않는다. 실제 신규 골드 agent의 첫 launchctl kickstart 실행 `runs=1`, `last exit code=0`, stdout 상태 `NO_NEW_VERIFIED_RSS_CANDIDATES`, stderr 0바이트. 기존 triage는 `runs=9`, `last exit code=0`. Mac 잠자기/SSD 분리·호출 충돌 시 해당 gold 동결만 안전 실패하며 진짜 출처별 인수 5거래일 완료 선언을 하지 않는다.
- 중지: `launchctl bootout gui/$(id -u)/com.newscatalystos.gold`. 상태: `launchctl print gui/$(id -u)/com.newscatalystos.gold`. 사용자 private 로그: `~/Library/Application Support/NewsCatalystOS/logs/gold_stdout.log`, `gold_stderr.log`. 수동 단발 체크: `PYTHONPATH=src python3 scripts/run_gold_capture_once.py`. 공개 저장소에는 사용자 plist·운영 로그·PIN·원문/DB가 포함되지 않는다.
