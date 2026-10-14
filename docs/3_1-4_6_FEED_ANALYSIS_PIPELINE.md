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
취소·부인·광고·루머를 신규 계약처럼 AI에 보내지 않는다. 취소·장애 제거 등의
전체 후속 사건 분석은 이 버전의 신규 주장 규칙에 포함하지 않는다.

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
추가한다. 설정은 기존 `AIModel` 필드만 포함한다. 키는 비공개 환경변수에 두고
설정/터미널 출력/Git에 넣지 않는다. 코드에 현재 모델명·요금의 임의 기본값은 없다.
기존 월 비용 원장의 5만원 상한·중복 요청 방지를 사용한다. 승인 없는 상태에서도
캐시된 결과를 읽을 수 있다. 요청한 AI가 실패하면 출처가 붙은 부분 결과를 저장하고
종료코드4를 반환한다. 규칙 전용 실행의 성공을 AI 실사용으로 표시하지 않는다.

## 이번 실행 증거
- 실제 기존 메타데이터: core80 + motir10, 총90개 제목 버전 분석/결과 저장,
  두 CLI exit0. 실제 반도체 용어가 정확히 일치한 제목 각1건, 유료 호출 대상0건.
  원본6파일 SHA 동일, 새 출처 수집·유료AI·인적답안 생성0.
- 합성 RSS + 가짜 HTTP 응답을 사용한 두 독립 Python 프로세스:
  첫 실행 분석1/모의HTTP1, 두 번째 캐시1/모의HTTP0, 동일 AI 결과 SHA 보존.
  `market_expectation=UNKNOWN`이어도 다른 근거가 충분한 정상 분석 경로를 확인했다.
- 로그는 `logs/feed_analysis_live_check.json`, `logs/feed_analysis_process_smoke.json`,
  `logs/feed_analysis_regression.log`에 비공개로 보존한다. 실제 AI 청구·정확도
  500건·반도체 관계 성능·5거래일/최종 출시 인수의 증거는 아니다.
