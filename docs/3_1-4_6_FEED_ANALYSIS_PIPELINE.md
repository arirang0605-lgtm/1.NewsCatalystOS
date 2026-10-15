# RSS 경제변화 판정 → 기존 AI·예산·캐시 → 비공개 분석 결과

## 작동 경로
기존 승인 RSS의 완료 ACK·관측 원장·제목 SHA를 읽기 전용 확인한다. 후속
`feed_analysis.py`는 `prior_fact_state`, `novelty_detection`, `impact_triage`,
`fact_extraction`, `run_budgeted_openai_analysis`, `analysis_cache`를 연결한다.
기존 수집·triage/ACK·검색·Gold·공급망 v1/v2 코드는 변경하지 않는다.
이 CLI는 새 수집기나 사람 검수 도구가 아니다.

제목의 명시된 공급계약·투자·상용화·출시 등으로 경제적 주장 후보를 분류하고,
반도체 용어/금액의 실제 문자열을 기존 추출 검증에 통과시킨다. 회사 식별자,
매출·실현수혜·확정 공급관계는 생성하지 않는다. 계획은 계획으로 남긴다.
취소·부인·광고·루머를 신규 계약처럼 AI에 보내지 않는다. `rss-title-economic-v4`는
**명시적인 공급계약 해지·취소·철회 제목**을 `CONTRACT_TERMINATION`이라는 별도
미검증 사건 후보로 분류한다. 당초 계약의 확인/실행, 해지 효력·매출 영향은 여전히
미확인이다. 체결·해지가 한 제목에 섞인 경우와 부인·루머는 기존처럼 AI 대상에서 제외한다.
3_4의 기존 `change_followup.assess_followup`을 재사용하여, 동일 제공자·사건·문서ID·URL에 **해지보다 먼저 관측된 명시적 계약 체결 제목**이 있을 경우 저장된 보고서의 `followup_change.status`를 `INVALIDATED_CANDIDATE`로 출력한다. 과거 계약 제목 버전 SHA·그 시점에 관측한 시각·기존 주장 SHA를 함께 연결하되 `prior_claim_verified=false`, `realization_confirmed=false`를 유지한다. 과거 계약 제목이 없거나 계획/루머/다른 문서만 있으면 `NO_PRIOR_EVENT_HOLD`이고, 일반 뉴스에는 `followup_change=null`이다. 기존 RSS·공시 수집, 유료 AI, 운영 DB, 외부 프로젝트로 쓰지 않는다.
`rss-title-economic-v4`는 공급계약 **금액·규모의 명시적 감액 제목**을 `CONTRACT_REDUCTION`으로 분리한다. 같은 제공자·사건·문서 ID·URL에 앞서 관측된 계약 체결 제목이 있으면 기존 3_4 판정기로 `WEAKENED_CANDIDATE`를 출력하고 과거 제목 SHA·관측시각을 연결한다. 선행 계약 주장이 없거나 다른 문서에만 있으면 `NO_PRIOR_EVENT_HOLD`이며 AI 검토 대상에서도 제외한다. 계획·부인·루머·체결/해지 혼합 제목은 감액 후보로 분류하지 않는다. 제목의 금액은 감액 차액이나 실매출 손실로 해석하지 않아 규모는 `UNKNOWN`이다.
`rss-title-economic-v4`는 공급·납품계약의 **명시적 납기·인도·공급 일정 연기/지연 제목**을 `CONTRACT_DELAY`로 분리한다. 같은 제공자·사건·문서 ID·URL에 먼저 관측된 계약 체결 제목이 있을 때만 3_4 `DATE_DELAYED`의 `WEAKENED_CANDIDATE`와 이전 제목 SHA·관측시각을 출력한다. 선행 주장이 없으면 `NO_PRIOR_EVENT_HOLD`이며 AI 대상에서 제외한다. 계획·루머·부인·체결/감액 혼합 제목은 지연 후보로 분류하지 않는다. 제목에 금액이 있더라도 지연 규모·실제 납품·매출 영향은 `UNKNOWN`이다. 저장된 비공개 보고서는 기존 읽기전용 소비자로 확인할 수 있다.
이는 신규 주장 후보와 이미 관측한 제목을 현재 분석 시점에 비교한 **부분 3_4 구현**이다. 실제 계약 이행·감액·취소의 공식 원문 증거 및 장애 제거 등 나머지 후속 사건은 별도 실증 대기다.

## 판단의 의미와 한계
- 신규성 비교는 동일 제공자/문서 URL의 현재 로컬 주장 이력에 한한다.
  새로운 RSS ID·첫 관측은 세계 최초 경제사건의 증명이 아니다.
- 같은 원문 제목 버전은 모델/프롬프트별 기존 AI 캐시를 사용한다. 같은 URL의
  같은 주장 재발행은 신규 주장으로 분석하지 않는다. 금액·제목 정정은 별도 버전이다.
- 시장 기대는 추정하지 않는다. 기존 importance의 완전 점수가 없더라도,
  알려진 차원의 기존 가중치 합이 8 이상인 신규/변경 후보는 AI 검토로 보낼 수 있다.
  이 합은 **규칙 점수의 하한**이지 확정 경제적 영향의 하한이나 매매점수가 아니다.
- 현재 금액 규모 스크리닝 가정: KRW 단일 금액 10억원 이상 MEDIUM,
  1,000억원 이상 LARGE. 여러 금액·외화만 있으면 규모 UNKNOWN. 글로벌/업계/
  다년 공급 표현도 제목 기반 힌트이며 출처 표현과 실제 영향은 다르다.
  이 규칙/임계값은 출력에 기록되는 구현 가정이지 신규 출시 합격 조건이 아니다.
- 원문과 정확히 일치한 필드, 규칙에 따른 후보 판정, AI의 미검증 해석을 분리한다.
  AI의 문장이 해당 출처에서 참임을 인증하지 않는다. 없는 정보는 미확인으로 남긴다.
- AI 미승인·키 부재·실패 시에도 출처·확인 가능한 필드를 결과로 보존한다.
  실제 실패한 요청의 기존 비용 예약은 유지하고 자동 재호출하지 않는다.
- 과거 제목 수정 이력은 현재 확인한 자료로 기록하며 과거 판단시각으로 소급하지 않는다.

## 실행
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
# 기존 메타데이터 분석. 추가 RSS/API 요청·유료 AI 없음.
PYTHONPATH=src python3 scripts/run_feed_analysis.py --scope core --limit 100
PYTHONPATH=src python3 scripts/run_feed_analysis.py --scope motir --limit 100
```
기본 사설 결과/파생 상태 위치는 `output/feed_analysis/<scope>/`이다.
`facts.sqlite3`, `ai_cache.sqlite3`, `ai_costs.sqlite3`는 기존 수집 원장과 분리한다.
출력 JSON은 `reports/feed_analysis_<SHA>.json`으로 완전 쓰기 후 원자 게시한다.
외장 SSD에서 하드링크를 지원하지 않는 실제 오류(errno45)를 해결하기 위해
짧은 게시 잠금과 원자 rename을 사용한다. 기존 결과는 덮어쓰지 않는다.

정확한 버전을 선택하려면 `--provider-id`, `--event-id`, `--title-sha256`을 쓴다.
버전 미지정 시 해당 문서의 마지막 관측 제목을 선택한다. 최대 100개 결과이며,
이 한도에 도달하면 `has_more_results`를 표시한다. 공시/기업자료를 재수집하지 않는다.

유료 실행은 **별도 승인 후** `--model-config /absolute/private/model.json --allow-paid`를
추가한다. 설정은 기존 `AIModel` 필드만 포함한다. `provider`는 `OPENAI` 또는
`GEMINI`를 고른다. Gemini는 호출 직전에 `GEMINI_API_KEY` 환경변수 또는
Mac 내부 `~/Library/Application Support/NewsCatalystOS/api-credentials/gemini_api.env`를 읽는다.
키 등록은 `python3 scripts/open_gemini_setup.py`로 연 127.0.0.1 전용 화면에서 사용자가 직접 완료한다.
비공개 폴더는 0700, 키 파일은 0600이며 명령 인자·모델 설정·터미널 출력·Git에 키를 넣지 않는다.
코드에 현재 모델명·요금의 임의 기본값은 없다.
기존 월 비용 원장의 5만원 상한·중복 요청 방지를 사용한다. 승인 없는 상태에서도
캐시된 결과를 읽을 수 있다. 요청한 AI가 실패하면 출처가 붙은 부분 결과를 저장하고
종료코드4를 반환한다. 규칙 전용 실행의 성공을 AI 실사용으로 표시하지 않는다.

## 기존 예약 실행과 자동 분석
기존 `run_scheduled_triage.py`와 `run_motir_policy_once.py`가 수집/복구 완료 후
같은 `run_feed_analysis.evaluate`를 호출해 결과를 저장한다. 새 수집기·감시 서비스·
LaunchAgent를 만들지 않고 기존 실행명령/1시간 설정을 유지한다.

- core는 선택한 제공자마다 최신 최대100개 제목 버전을 분석하고
  `output/feed_analysis/core/`에 기존 파생 상태·결과를 저장한다.
- MOTIR는 기존 별도 등록부·수집 DB·inbox·Gold를 유지하고
  `output/feed_analysis/motir/`에 저장한다. Gold 준비 실패는 분석을 막지 않지만
  원래 실패 상태를 숨기지 않는다.
- 두 실행기 모두 규칙 분석이 기본이다. `--analysis-model-config`는 기존 모델
  캐시를 읽는 용도이며 `allow_paid=False`로만 전달한다. 환경에 키가 있어도
  이 예약 경로에서 새 유료 요청은 하지 않는다. 유료 수동 실행은 앞 절의 별도 승인 경로다.
- `NOT_DUE`나 수집 실패 때에도 이전 완료 ACK가 있으면 분석할 수 있다. 수집 실패와
  분석 실패를 별도로 기록하고, 어느 쪽이든 실패하면 종료코드4를 반환한다.
  분석 오류로 성공한 ACK·수집 워터마크를 롤백하거나 RSS를 다시 요청하지 않는다.
- 선택한 제공자의 분석은 다른 제공자의 손상된 triage 결과로 막지 않는다.
  해당 제공자 자신의 SHA·PIT·현재 권한 검증은 그대로 수행한다.
- `--skip-analysis`는 기존 수집/Gold 전용 동작이다. `--analysis-root`로 파생 위치,
  `--analysis-limit 1..100`으로 제공자별 최근 버전 수를 설정할 수 있다.
  초과 이력은 `has_more_results=true`로 표시하며 전체 역사 분석 완료로 세지 않는다.
- 예약 stdout에는 상태·개수·비공개 결과 위치/SHA만 기록한다. 제목·AI 내용은
  비공개 결과파일에 남고, 일반 운영 로그에 복제하지 않는다.

이미 완료된 자료만으로 복구·분석하려면 다음을 사용한다. 새 RSS HTTP는 없다.
```sh
PYTHONPATH=src python3 scripts/run_scheduled_triage.py --replay-only \
  --registry "$HOME/Library/Application Support/NewsCatalystOS/providers/authorized_sources.json" \
  --provider-id mss-official-press --provider-id newswire-public-rss-it
PYTHONPATH=src python3 scripts/run_motir_policy_once.py --replay-only
```

## 현재 검증 증거
- 관련 **9개 테스트 파일 100 PASS/0 FAIL**. 합성 소스를 실제 수집·완료 ACK까지
  처리한 후 같은 tick에서 결과를 저장했고, 재시도/캐시·제공자 실패 격리·dry-run·
  기존 수집 전용 모드·MOTIR 분리 동작을 확인했다. 실제 유료AI·사람 정답이 아니다.
- 실제 Mac 2026-10-14 20:40 KST: 기존 실행명령에 `--replay-only`를 지정한
  별도 Python 프로세스에서 중기부23/뉴스와이어IT57/MOTIR10, 총90개 제목 버전의
  규칙 결과3개를 저장하고 SHA 확인. core/motir 종료코드0, 누락/한도초과 없음.
  등록부2·운영DB4·기존 LaunchAgent 설정3개, 총9파일 SHA 동일. RSS 신규 요청·
  실제 AI·인적 라벨 추가0. 결과는 검토 후보이며 사건/수혜 확정이나 90개 독립 정답이 아니다.
- 기존 서비스의 수동 kickstart 확인 요청은 도구 보안 차단으로 실행되지 않았다.
  20:41 KST 읽기전용 로그 관찰에서는 아직 새 분석 필드가 없는 이전 정상 tick이었다.
  **다음 자연 예약 tick의 새 분석 실행은 관찰 대기**이며 5거래일 인수로 세지 않는다.
- 증거는 `logs/scheduled_analysis_regression.log`,
  `logs/scheduled_analysis_live_check.json`,
  `logs/scheduled_analysis_service_observation.json`에 비공개 보존한다.
  앞선 AI 연결·캐시의 합성 별도 프로세스 증거는 `logs/feed_analysis_process_smoke.json`.

## 저장된 분석 결과의 별도 읽기전용 소비 (2026-10-14)
기존 `run_feed_analysis.py` 또는 예약 실행의 **비공개 결과 경로와 당시 기록된 producer `report_sha256`**를 운영자가 별도 소비자에 전달한다. SHA를 파일 내용에서 새로 계산하여 신뢰값으로 대체하지 않는다. 기존 수집기·AI·DB에 다시 연결할 필요가 없다.
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
# 아래 값은 실제 이전 생산자 결과의 private_report_file/report_sha256에서 지정한다.
REPORT_FILE="/absolute/private/reports/feed_analysis_<SHA>.json"
REPORTS_ROOT="/absolute/private/reports"
PRODUCER_SHA="<producer_report_sha256>"
PYTHONPATH=src python3 scripts/consume_feed_analysis.py \
  --report-file "$REPORT_FILE" --reports-root "$REPORTS_ROOT" \
  --expected-sha256 "$PRODUCER_SHA" --limit 20
```
필요하면 `--provider-id`, `--event-id`, `--title-sha256`(event ID 필수), `--offset`, `--limit`로 조회한다. 반환값에는 원래 출처/분석 시각·불확실성이 유지되고 `consumer_available_at`은 **현재 소비 시각**이며 과거 PIT 소급 인수 증거가 아니다. 잘못된 SHA/미지원 보고서/미래 시각 등은 종료코드4로 실패하고 원문 내용을 오류에 노출하지 않는다. CLI 출력은 비공개 분석 메타데이터이므로 공개 로그/Git에 저장하지 않는다.
- 코드 SHA `748d705f8045ccaa37be1d368ca1204fc7f42612` origin/main 반영, 관련 소비·분석·캐시 54 PASS/0 FAIL. 기존 실제 core80/MOTIR10 결과의 별도 프로세스 조회 2건 exit0, 항목90건 원본동일·보고서 SHA 불변은 `logs/feed_consumer_live_check.json`에 비공개 기록. 실제 AI/인적 정답/최종 출시 인수를 대체하지 않는다.
