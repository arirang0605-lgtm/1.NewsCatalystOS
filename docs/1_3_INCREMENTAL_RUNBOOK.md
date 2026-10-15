# 1_3 — 증분 수집 / watermark / 오류 격리 (운영형 기본 구현)

## V1.0 기능 범위
- `incremental_ingest.py`: 이미 승인된 `ProviderRegistry`만 수용. `feed_transport.py` HTTPS 단발 GET 재사용, EraLeader DART/SEC/KRX 공식 수집에 손대지 않음.
- 권한 확인 → SQLite 요청 예약/호출 간격·시간당 예산 → 허용된 공급원 GET 1회 → ID 해시 유일키 충돌 검사 → **한 트랜잭션으로 새 이벤트 digest와 마지막 성공 watermark** 갱신.
- 로컬 원장의 내용은 `provider_id`, 해시 `event_id`, `first_verified_at`, 마지막 성공·요청시각, 실패/다음 가능시각만. RSS 제목·URL·본문·API 비밀정보·운영계좌/원본 파일은 저장하지 않는다. 공개 최초 발행시각 인증 `RawEvent=0` 및 당시 과거 정보 소급 금지.
- 새 이벤트는 처음 검증 완료한 시각 이후에만 사용한다. **동일 feed ID의 재방문은 신규 이벤트를 재생산하지 않음**. 기사 수치/본문 정정 탐지는 3_4 단계에서 별도 버전/근거 정책으로 처리한다.

## 개인용 SQLite 원장
- Mac 내부: `~/Library/Application Support/NewsCatalystOS/state/incremental_feeds.sqlite3`. 디렉터리 owner-only 0700, SQLite 파일 0600. NewsCatalystOS 전용이며 EraLeader 소스/DB/Git 쓰기 0건. `.gitignore`가 `*.sqlite3` 및 `output/` 차단.
- 요청 예약은 SQLite `BEGIN IMMEDIATE`로 원자화. 같은 Mac의 병렬 재실행도 예산/호출 간격 확인 없이 두 번 요청하지 않는다.
- 실패: `last_success_at`과 기존 seen ID는 보존한다. HTTP 429/일시적 5xx의 실패 횟수에 따라 60~3600초 지수 백오프 후 **다음 정기 실행**이 다시 시도한다(즉시 재시도 금지). HTTP 401/403은 중지 상태로 유지. 유효한 출처 설정의 갱신 시각(`reviewed_at`, 기존 필드명)이 차단 시각보다 늦으면 다음 예약 실행에서 자동 복구한다. 설정이 같거나 접근권한이 만료되면 해당 출처만 건너뛰며, 호출 한도·재시도 간격은 유지한다. 수동 해제 명령은 삭제했다.
- 성공하더라도 수집주기 미도래·시간당 호출 예산 소진 시 `NOT_DUE`로 중단하고 네트워크 호출하지 않는다. 허용 소스 하나가 실패해도 다른 소스의 watermark/진행은 보호한다. 다운타임 동안 놓친 기사는 RSS 피드에 아직 남아 있는 만큼만 회복할 수 있고, 오래 전에 사라진 기사를 복원한다고 보장하지 않는다.

## Mac에서 단발 검증
```bash
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_incremental_feed.py \
  --registry "$HOME/Library/Application Support/NewsCatalystOS/providers/authorized_sources.json" \
  --all-approved
```
- 실제 허용 RSS(중기부 `mss-official-press`, 뉴스와이어 `newswire-public-rss-it`)에 최초 1회 실행: **신규 메타 20 + 15건, 중복 0**. 같은 시점 재실행 `NOT_DUE` 2건(추가 GET 0). 관측 SHA 식별자와 watermark는 비공개 내부 디스크에서만 저장.
- 사용자 소유/비공개 `authorized_sources.json`은 1_2에서 미리 0600으로 승인된 두 소스만 포함. 미승인 기업 IR 또는 403 발생 소스는 수집 불허.

## 15분 실행 예약 설정(기능 준비; 자동 실행은 미활성)
```bash
PYTHONPATH=src python3 scripts/launchd_incremental.py --write
plutil -lint "$HOME/Library/Application Support/NewsCatalystOS/launchd/com.newscatalystos.incremental.plist"
```
- 900초 간격의 `launchd` private plist를 생성·검증하지만 사용자 Mac의 `launchctl bootstrap`을 자동 호출하지 않는다. 작업을 등록·시작하는 경우 **한 프로젝트씩** 자원 사용량을 확인하고 백업/외부 SSD 쓰기와 겹치는 고부하 작업을 피한다. 완료 조건인 5거래일 자동운영은 별도 V1.0 단계에서 실제 운영 후 검증.
- 실행 예약/로그 파일에는 기사 본문이나 인증정보를 넣지 않는다.

## 테스트 인수 조건
- 다른 프로젝트 영향 0, Python 변경범위 전체 pytest/compileall 및 git 공개보안 검사 종료코드 0.
- 추가 단위 테스트: 초기 수집/재방문 신규0/워터마크 보존·추가 이벤트, 시간당 제한과 즉시 재호출 차단, 네트워크 HTTP 403/429, 복구 전 권한 확인, 상태 경로 심볼릭링크·퍼미션 거부, SQLite 트랜잭션 롤백, 제한된 실제 소스 1회+반복 실행.
- `launchd` 설정이 준비됐다는 사실과 **실제 백그라운드 서비스가 이미 활성화됐다**는 주장은 구분한다. PIT 과거 공시 최초 공개 인증은 계속 선택적 검증이며 원장 기능만으로 사실 인증하지 않는다.
