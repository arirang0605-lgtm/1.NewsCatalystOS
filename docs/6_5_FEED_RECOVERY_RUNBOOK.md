# 6_5 — 허가된 RSS 수집 성공 후 분석실패 복구·운영 영수증

## 정상 처리·복구 계약
- 기존 `incremental_poll`의 선택적 `before_commit` 훅으로 **승인 RSS의 제목/문서 ID/URL 메타만** Mac 내부 NewsCatalystOS 전용 비공개 폴더에 원자 게시한다. 이 복구용 기록의 내구성 확인이 끝나야 1_3 SQLite의 `seen_events`와 `last_success_at` 성공 트랜잭션을 커밋한다. 기본 1_3 호출자는 인자 미지정 시 이전 동작을 그대로 유지한다.
- 비공개 복구 입력: `~/Library/Application Support/NewsCatalystOS/inbox/feed_triage/pending_<SHA>/`. `feed.json`의 로컬 SHA와 별도 마커를 검증한다. DART/SEC/KRX/다른 프로젝트 파일·유료 기사 본문·RSS description·API 키는 복사/저장하지 않는다. 실제 사용은 승인된 공급자의 허용 **메타데이터**에만 한정하며 원문 재배포 권리를 의미하지 않는다.
- **원자 게시 → SQLite 성공 커밋** 사이에서 프로세스가 죽으면 파일만 남는 orphan 가능성이 있다. 재처리 전 실제 SQLite 마지막 성공 watermark/각 `seen_events`를 검사하므로 orphan을 성공 자료로 승격하지 않는다. 명시 오류 시 자동 재수집·자동 완료 처리하지 않고 운영자 확인을 요구한다.
- 이후 후속 정규화/중복/광고 필터/반도체 제목 사전선별/비공개 결과 게시 중 예외나 프로세스 종료가 나면 기존 수신 메타 checkpoint가 남는다. **다음 실행은 checkpoint 우선**, 같은 피드를 다시 GET하지 않고 새 로컬 검증시각으로 분석·게시한다. 과거 최초 RSS 공개시각/과거 분석 성공을 소급 만들지 않는다.
- 출력 `output/feed_triage_<SHA>`의 완료 마커/SHA 및 출처·건수를 확인한 뒤에만 Mac 내부 `inbox/.../acked/<checkpointSHA>.json`을 새로 생성한다. ACK에는 공급자·확인 시각·SHA·기사 건수/출력 경로만 기록한다. 헤드라인/원문은 ACK에 저장하지 않는다. 악성/변조 ACK와 다른 공급자 ACK는 무효다. 장애 뒤 재처리됐음을 `replayed_from_checkpoint=true`로 표시한다.
- `exact_index_status=DUPLICATE`는 재처리 때문에 색인에 이미 등록된 제목일 수도 있다. 별도의 `source_new_identity`가 1_3 최초 수신 여부를 나타내며, 양쪽 모두 검증된 **새 경제사건** 인증은 아니다. 반복 감시 중 AI 자동 호출 0회.

## 실제 Mac 운영 명령
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/run_feed_triage.py \
 --registry "$HOME/Library/Application Support/NewsCatalystOS/providers/authorized_sources.json" \
 --provider-id mss-official-press
# 외부 요청 없이 미처리된 checkpoint 1건만 후속 분석:
PYTHONPATH=src python3 scripts/run_feed_triage.py \
 --registry "$HOME/Library/Application Support/NewsCatalystOS/providers/authorized_sources.json" \
 --provider-id mss-official-press --replay-only
# 기존 승인 2종의 운영 완료 영수증·미처리 큐 상태:
PYTHONPATH=src python3 scripts/check_feed_operations.py
```
- 호출량/429·403·5xx 중지 및 접근권한 관리는 기존 1_3 원장을 그대로 사용한다. `NOT_DUE`는 실패가 아니며 강제 재요청하지 않는다. 자동 launchd나 장기 실행은 설치/시작하지 않았다. 테스트용 synthetic 샘플로 만든 ACK는 실제 5거래일 운용 기록이 아니다.

## 운영 인수·완료 기준 (현재 미충족)
- `check_feed_operations.py`은 비공개 checkpoint+성공 SQLite+triage SHA+ACK를 재대조해 실제 기록된 완료 건수/모든 승인 소스가 성공한 날짜/미처리 건수를 센다. 같은 날 여러 번 돌려도 하루로 센다.
- 월~금 데이터가 5개 누적되더라도 공휴일·거래소 휴장 및 마감 직전/직후 조건은 별도 확인해야 한다. 도구는 `verified_exchange_trading_days=0`, `five_trading_day_operation_certified=false`, `independent_physical_recovery_verified=false`, `v1_release_ready=false`를 유지한다. 이는 **실행 실패**가 아니라 아직 5일 실증/물리복원을 수행하지 않았다는 뜻이다.
- 2026-10-14 실제 Mac 점검 때 기승인 중기부 RSS는 앞선 요청의 호출주기 때문에 `NOT_DUE`로 차단되었으며 `--replay-only`는 `NO_PENDING_REPLAY`(HTTP 0회). 사전 35건의 1_3 메타 처리 이력은 **본 checkpoint 도입 이전**이라 사후 소급 ACK를 만들지 않았다. 새 프로그램 도입 후 처음 통과한 실행부터 운영 인수 이력이 누적된다.
- 릴리스 `6_5` 최종 인수는 승인된 5개 실제 거래일 반복 운영/오류 회복/독립 물리 백업·복원 및 P0/P1=0, 전체 시험 등 별도 증거가 필요하다. 현재 완료 판정은 여전히 **23/36**이고 V1.0 tag는 생성하지 않는다.

## 2026-10-14 | 6_5 실제 서로 다른 물리 장치 SQLite 복원 + 독립 SHA PIN
- 기존 `backup_recovery.backup_sqlite`/`restore_to_new_dir` **코드는 재사용**한다. 신규 `physical_recovery.verify_physical_recovery`는 맥북 내부 `NewsCatalystOS/state`의 허용된 DB 2개만 지정하고, 원본 `st_dev` 및 `diskutil info -plist`의 `ParentWholeDisk`를 비교해 같은 물리장치로 판단되는 백업을 차단한다. 테스트 시점 원본 `disk3`와 T5DATA SSD `disk6`의 상이한 부모 디스크를 확인했다.
- 기존 운영 DB를 읽기 전용 SQLite 온라인 백업하여 `/Volumes/T5DATA/1.NewsCatalystOS/.local_backups/backup_<UUID>/`에 0700/개인 영수증·SHA로 저장한다. 이는 GitHub `.gitignore` 대상이며 원문/운영 DB/백업을 Public 커밋하지 않는다. 이후 맥북 내부 `~/Library/Application Support/NewsCatalystOS/restore_checks/` 아래 **새 디렉터리**에만 복원하고 SHA·SQLite integrity 및 필수 테이블 확인을 수행한다. 실행 대상 DB는 `incremental_feeds.sqlite3`·`triage_exact_index.sqlite3` 2개로 제한한다.
- 신규 `physical_recovery_pin.py`는 **백업 디스크와 물리적으로 다른 Mac 내부** `~/Library/Application Support/NewsCatalystOS/pins/physical_recovery/backup_<UUID>.pin.json`에 백업 식별자·snapshot SHA·manifest SHA·저장시각을 `O_EXCL`로 영구 고정한다. `--verify-pin`은 해당 별도 보관 SHA만으로 기존 SSD 백업을 나중에 다시 검증·새 폴더에 복원한다. 변조·소실·타 프로젝트/잘못된 경로는 차단한다. SHA PIN은 **로컬 복원 무결성**이며 공시 공개시각/외부 공증은 아니다.
- 기본 실행(새 snapshot 2개 + 핀 2개 + 일회 복원): `PYTHONPATH=src python3 scripts/check_physical_recovery.py`. 추후 복원: `PYTHONPATH=src python3 scripts/check_physical_recovery.py --verify-pin "$HOME/Library/Application Support/NewsCatalystOS/pins/physical_recovery/<백업ID>.pin.json"`.
- **실제 Mac 실행 결과:** `incremental_feeds.sqlite3` **45,056바이트**, `triage_exact_index.sqlite3` **40,960바이트**가 각각 SSD로 온라인 백업→맥북 내부 별도 복원 SHA/SQLite PASS. Mac 별도 디스크 핀 2개를 실제 작성했고 **나중 PIN 기반 cold restore 2개도 PASS**. 사용자 운영 DB, EraLeader 원본/코드/DB/Git 변경 없음. 백업 및 핀은 private 디렉터리에만 존재.
- 위 결과는 **로컬의 서로 다른 물리 장치 간 재해복구 시험**에 해당한다. Mac과 SSD가 함께 손상되는 사고까지 견디는 오프사이트 백업은 아직 미검증이며, `offsite_backup_verified=false`와 `five_trading_day_operation_certified=false`를 유지한다. 6_5 최종 합격은 5개 실제 거래일의 승인 RSS 성공 이력/장애 발생 후 회복/업무 운영 확인을 추가로 요구한다. V1.0 릴리스 태그 발행 금지.

## 2026-10-14 | 실제 장치 복원 상태의 운영 점검 연동
- `check_feed_operations.py`은 운영자에게 보고할 때 **새로운 백업을 매번 만들지 않고**, 이미 Mac 내부 다른 디스크에 보관된 2개 SHA PIN과 T5DATA 외장 SSD의 각 snapshot/manifest를 다시 **읽기 전용** 검증한다. `independent_physical_recovery_verified`는 RSS 원장·중복 인덱스 **두 상태 DB 모두**의 PIN/manifest/snapshot SHA가 일치할 때만 `true`; 하나라도 없으면 `false`, 일부라도 변조되면 오류/출시 차단한다.
- Mac 실제 조회에서 `independent_physical_recovery_verified=true`, `local_recovery_source_count=2`, `offsite_backup_verified=false`, `five_trading_day_operation_certified=false`, `v1_release_ready=false`, 운영 ACK 2개/단일 날짜 기록 1개를 확인했다. 복원 실증 자체는 `check_physical_recovery.py --verify-pin`로 별도로 실제 PASS한 증거를 사용한다. 물리 복구 상태 반영은 6_5 전체 완료나 6_6 릴리스 승인으로 자동 연결되지 않는다.
