# 실제 RSS 메타 → 뉴스 검토/반도체 키워드 사전선별 통합 (2026-10-14)

## 구현한 연결 범위
- 새 `scripts/run_feed_triage.py`는 승인된 NewsCatalystOS 전용 RSS 1곳을 **기존 1_3 `incremental_poll`의 호출량·권한·백오프 원장**으로 한 번 조회한다. 같은 HTTP 응답의 `IncrementalResult.observations`만 사용하여 추가 GET 없이 후속 검토를 실행한다. EraLeader DART/SEC/KRX API/DB/Git 호출이나 쓰기는 없다.
- 2_1 `normalize_feed_metadata`(UTF-8/URL 정규화), 2_2 `register_exact`(프로젝트 자체 owner-only SQLite SHA 중복), 2_4 `classify_claim`(광고·스팸·익명 루머 보류), 2_3 `group_event_stories`(근거 없는 서로 다른 기사는 강제 병합 안 함), 3_5 `triage_importance`(경제규모·기대·실적 모르면 `INSUFFICIENT_EVIDENCE_REVIEW`)을 호출한다.
- **반도체 관련 후보는 제목의 키워드 일치에 불과하다.** `KEYWORD_CANDIDATE`는 사실인정/새 경제사건/매출·거래/주식추천이 아니다. SNS·보도자료는 공식·독립 언론의 검증으로 승격하지 않고, 뉴스와이어 배포 RSS는 `PRESS_RELEASE`로 보수적으로 분류한다. 실제 핵심 변화 검토·AI 호출은 사람 확인 및 기존 3단계 사실 검토 이후에만 가능한 후속 작업이다. 이번 코드는 AI를 실행하지 않는다.
- 원본 기사 본문·RSS description·제공자 인증정보는 분석에 저장하지 않는다. 승인된 제목/원문 링크 등의 **메타데이터만** NewsCatalystOS 비공개 `output/feed_triage_<SHA>/`에 원자 게시한다. `triage.json`/완료 `publication.json`은 로컬 SHA로 확인한다. 기존 1_3 SQLite는 이벤트 ID/시간/상태만 보존하고, 반도체 제목은 새로 저장하지 않는다.
- **신규 사건 구분:** `new_provider_ids`는 1_3 원장에 최초 등장한 ID 수다. 별도 2_2 인덱스에 처음 나타났더라도 이전에 1_3 수집된 ID는 `INDEX_BOOTSTRAP_PRIOR_SEEN_ID`로 표기하고 신규 뉴스로 세지 않는다. 이 정보는 3_2의 실제 최초 경제적 사실 확정과 다르며 `verified_new_economic_fact_count=0`이다. 같은 문서 ID의 수정 제목은 `REVISED`로 이력을 추적한다.

## 실제 맥북 단발 실행
```bash
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/run_feed_triage.py \
  --registry "$HOME/Library/Application Support/NewsCatalystOS/providers/authorized_sources.json" \
  --provider-id mss-official-press
PYTHONPATH=src python3 scripts/run_feed_triage.py \
  --registry "$HOME/Library/Application Support/NewsCatalystOS/providers/authorized_sources.json" \
  --provider-id newswire-public-rss-it
```
- 2026-10-14 단발 실연동: 중기부 RSS **20건**, 뉴스와이어 IT RSS **15건**, 1_3 원장 신규 ID **양쪽 0건**, 제목 키워드 후보 **양쪽 0건**. 모두 `SUCCESS_UNCHANGED`였으며 개인 `output/` JSON 원자 게시/내용 SHA 검사 PASS. 뉴스 본문·AI 호출·DART/SEC/KRX 중복 수집 **0건**. 키워드 후보 0건은 반도체 재료가 시장에 없다는 판단이 아니라 *이 시점 두 승인된 피드 최신 화면의 제한된 제목 목록에 해당 단어가 없었다*는 뜻이다.
- 이 첫 실행에서 2_2 독립 제목 SHA 색인에 기존 35건이 최초 등록되었지만 1_3 최초 수신 이벤트는 0건이다. 기존 `output/` 결과의 `exact_index_status=NEW`는 **새 뉴스가 아니라 색인 최초 초기화**를 뜻하며, `source_new_identity=false`가 실제 신규 ID의 기준이다. 이후 코드에서는 표시 자체를 `INDEX_BOOTSTRAP_PRIOR_SEEN_ID`로 개선했다.
- 이번 실행은 **한 시점의 두 소스 조회**이지 5거래일 연속 운용, 수혜기업 정확도, 실제 독립 검수 500건, 릴리스 합격이 아니다. 다음 실행은 기존 원장 1_3 호출 제한을 지키며 수행하며, `NOT_DUE` 시 새 요청을 하지 않는다. 자동 장기 운영은 아직 활성화하지 않는다.

## 아직 남은 연결
- 5_2 기존 DART 100개 공시 표본의 보고서 제목 조회(새 API 요청 없는 원본 SHA 확인)에서는 공급계약·수주·설비증설 유형을 발견하지 못했다. 해당 **한정된 표본**은 실거래관계 증거가 없어 `UNKNOWN`으로 남긴다. 공식 제출 본문/고객·공급자 2개 공식 ID의 실제 검토가 오기 전에는 5_2 완료 처리하지 않는다.
- RSS 분석의 장애·중간결과 손실 상황을 복구하는 운영 원장, 2_6·3_6·5_6 실제 독립 라벨, 4단계 승인 AI·실청구, 6_5 5거래일 운영/독립장치 복원, 5단계 실관계와 외부 소비 검증은 미완료다.
