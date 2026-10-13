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
