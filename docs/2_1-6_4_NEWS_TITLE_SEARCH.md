# NewsCatalystOS V1.0: 실제 허가 RSS 제목 검색

## 기능 및 근거
- 기존 `run_feed_triage.py`의 승인 RSS 분석 결과만 소비하는 **NewsCatalystOS 개인 로컬 검색**이다. 새로운 HTTP/DART/SEC/KRX API 요청·EraLeader 쓰기·AI 호출·원문 수집을 수행하지 않는다.
- 개인 `inbox/feed_triage/acked/`에서 완료 영수증을 읽고 각각의 SHA 체크포인트, SQLite 1_3 성공 커밋, private `output/feed_triage_<SHA>/` 완료 출력을 재검증한다. 변조/출처 불일치 시 색인하지 않고 실패 처리한다.
- **제목·출처 링크·event/원문 제목 SHA·검토 상태·관측 시각만** `output/search_cache/news_search.sqlite3`에 저장한다. 유료 원문, RSS 본문, 비밀키, 거래·실적 확정 주장은 기록하지 않는다. 캐시는 완료 영수증에서 다시 만들 수 있고 `.gitignore`에 의해 Public Git에서 제외된다.
- 원본 공급자가 승인 상태일 때만 결과 검색이 가능하다. 색인을 최초 완성한 시각이 기록되며 과거 시점에 소급해 검색 가능했다고 주장하지 않는다. 제목 정정은 별도 SHA 버전, 동일 재조회는 하나의 결과로 취급한다.
- FTS5 trigram 3글자 이상 검색, 두 글자 한글은 문자열 `LIKE` 검색. 반도체 산업 후보 검색은 **키워드와 광고/루머 필터**를 통과한 항목만 사람 검토로 표시한다. 실제 고객사/공급사 관계, 수혜기업, 정량 매출과 추천은 모두 미검증이다.

## 사용법
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/search_news.py --query 기업 --limit 20
PYTHONPATH=src python3 scripts/search_news.py --query 반도체 --semiconductor-only
PYTHONPATH=src python3 scripts/search_news.py --query 중소 --source-id mss-official-press
```
- 각 실행 시 이전 ACK를 SHA 검증하고 새 제목 버전만 저장한 뒤 검색한다. 결과에는 `verified_economic_fact=false`, `verified_supply_transaction=false`, `confirmed_beneficiary=false`를 명시한다.

## 2026-10-14 Mac 실자료 검증
- 완료 영수증 4개, 기승인 중기부 RSS 20건 및 IT 뉴스와이어 15건, 고유 제목 버전 **35건**을 실제 SQLite 검색 색인에 입력했다.
- 2글자 `기업` 검색에서 5건 표시(`--limit 5`), 반도체 후보 검색은 0건이었다. 이는 **현재 보유된 두 제공자의 제목 35개**에 관한 결과일 뿐 실제 반도체 사건 부재를 의미하지 않는다.
- 추가 외부 네트워크/API/AI 호출 0, EraLeader 소스/DB/Git 수정 0, 기사 본문·개인정보 공개 0.
- 이 검색 CLI는 기존 1_3~3_5·6_5 증거를 활용하는 **운영 편의 기능**이며 36개 단계의 새로운 완료 번호가 아니다. 5_2 공식 공급망 문서/6_5 실제 5거래일/AI 공급자/독립 gold 및 최종 릴리스 인수는 그대로 미완료다.

## 2026-10-14 추가: 격리된 3개 출처 통합 제목 검색

기존 기본 검색과 SQLite FTS 캐시는 유지한다. `--scope all`은 원래의 중기부·뉴스와이어 IT 작업공간과 산업통상부 전용 작업공간을 각각 검증한 뒤 **조회 결과만** 합친다. 등록부·수집 DB·Gold 답안지·LaunchAgent는 합치거나 수정하지 않는다. `--scope motir`는 산업통상부 자료만 조회한다. 새로운 수집기나 홈페이지가 아니라 기존 2_1/2_3/2_5/6_4 메타데이터 소비 기능의 연결이다.

```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
# 세 승인 출처의 반도체 제목 후보 조회
PYTHONPATH=src python3 scripts/search_news.py --scope all --query 반도체 --semiconductor-only
# 산업통상부만 조회
PYTHONPATH=src python3 scripts/search_news.py --scope motir --query 반도체 --semiconductor-only
# 기존 두 출처 FTS 검색은 종전 기본값 그대로
PYTHONPATH=src python3 scripts/search_news.py --query 기업 --limit 20
```

### 조회·출처·시점의 의미

- 기존 `news_search.read_completed_title_snapshots`에서 완료 ACK·원본 체크포인트·SHA·PIT·현재 승인 출처를 검증하는 부분을 재사용한다. `check_committed_ingest(..., read_only=True)`는 SQLite `mode=ro`로 수집 원장을 열어 조회 중 새 운영 DB/테이블을 초기화하지 않는다. 기존 수집·복구 호출의 기본 동작은 유지한다.
- 통합 모드는 별도 캐시를 만들지 않는다. 모든 검증된 후보에 대소문자를 구분하지 않는 **제목 부분문자열** 검색을 적용하고 출처·반도체 필터, 전체 결과 정렬 후 `--limit`을 적용한다. 동일 제공자/사건ID/제목SHA의 반복 관측은 하나로 표시하되 가장 이른 검증 관측시각을 유지한다. 동일 ID의 변경된 제목SHA/금액 정정은 별도 버전으로 보존한다.
- `source_available_at`은 RSS 메타를 검증한 시각이며 외부 공인 발행시각이 아니다. `search_verified_at`은 이번 검색을 검증한 시각이다. 과거에 같은 통합 검색 결과가 이미 존재했다고 소급하지 않는다.
- `metadata_overlap_hints`는 **현재 반환된 결과 안에서만** 서로 다른 제공자의 정확히 동일한 정규화 제목/공통 URL을 검토 대상으로 표시한다. 제목이 달라진 정정 자료도 삭제하지 않는다. 금액을 지우거나 유사도를 이용해 강제로 사건을 병합하지 않는다. `same_economic_event_verified=false`, `source_independence_verified=false`를 유지하며 뉴스와이어는 `PRESS_RELEASE`이지 독립 취재원이 아니다.
- 한 작업공간의 등록부·체크포인트·DB·결과가 없거나 손상되면 해당 범위는 `SEARCH_DATA_UNAVAILABLE`로 남기고 정상 범위의 결과만 반환한다. 전체 상태는 `FEDERATED_SEARCH_PARTIAL_DATA_UNAVAILABLE`, 종료코드 **4**, `coverage_complete=false`이다. 한 등록부에 승인된 출처 중 완료 자료가 없는 제공자도 누락 목록에 표시한다. 손상된 범위의 이전 캐시를 정상 자료처럼 보여주지 않는다.
- `coverage_complete=true`는 요청한 범위의 현재 승인 출처별 검증 가능한 완료 자료가 있다는 뜻이다. 자료가 시장 전체를 포괄하거나 최신 HTTP 호출이 성공했다는 뜻이 아니다. 실제 독립 경제사건 수는 `null`, 인간 Gold 평가/공급관계·수혜·매매 판정은 모두 미검증이다.

### Mac 실자료 및 변경 영향 검증

2026-10-14 **18:04 KST** 실행에서 완료 영수증 **23개**(기존 범위22/산업부1), 제공자 **3개**, 검증된 제목 버전 **83개**(기존 범위73/산업부10)를 조회했다. `--scope all --query 반도체 --semiconductor-only`는 **2건**(뉴스와이어 IT1/산업부1), 산업부 단독 검색은 **1건**, `HBM`은 **0건**, 두 글자 `기업` 검색은 **14건**을 반환했다. 모두 종료코드0이다. 반환 결과의 정확 일치/공통 URL 중복 힌트는 0건이나 이는 전체 자료의 경제사건 독립성을 증명하지 않는다. 83개는 제목 메타 버전이지 83개의 독립 인적 정답이 아니다.

원래의 두 승인 등록부 및 네 수집·중복제거 SQLite 파일, 총 **6개 파일**을 실행 전후 SHA256 대조해 동일함을 확인했다. 이 조회에서 추가 외부 RSS/DART/SEC/KRX/API/AI 호출0, EraLeader 접근·변경0, 원문 저장0. 기존 자동 수집 서비스와 Gold PIN·검수 답안지는 수정하지 않았다.

`test_federated_news_search.py`, `test_news_search.py`, `test_feed_recovery.py`, `test_feed_operations.py`, `test_feed_triage.py`, `test_incremental_ingest.py`, `test_live_gold_samples.py`, `test_live_gold_incremental.py`, `test_gold_capture_once.py`의 변경 영향 테스트 **100 PASS / 0 FAIL**. 실제 ACK 파이프라인을 사용한 합성 테스트에서 세 출처 결합·정정 보존·동일 버전 멱등성·전역 제한·광고 제외·미승인/손상 자료 부분 실패·PIT·운영 입력 불변·기본 CLI 호환을 검증했다. 전체 프로젝트 회귀나 실제 사람 평가를 새로 완료한 것은 아니다.

**V1.0 완료는 23/36(63.9%) 유지.** 2_6/3_6 독립 인적 정답, 5_2 공식 반도체 공급관계 본문/양사 식별자, 승인된 실 AI·요금, 6_5 실제 5거래일 및 6_6 최종 인수는 별도 미완료이다.

## 검색 결과에서 기존 PIN 고정 검수 사례로 이동 (2026-10-14)

`--review-links`는 검색된 `provider_id/event_id/title_sha256`를 기존 Gold
사례 SHA에 정확히 연결한다. 기존 승인 RSS의 완료 ACK와 원장, 별도 디스크
PIN 및 동결된 제목/링크를 재검증하고 **선택한 검수자 공간만** 읽는다.
등록부·수집 DB·Gold 묶음·검수 답안지·서비스는 합치거나 새로 만들지 않는다.

```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/search_news.py \
  --scope all --query 반도체 --semiconductor-only \
  --review-links --reviewer-slot UNASSIGNED_A
# 다른 검수자는 같은 명령의 슬롯을 UNASSIGNED_B로 지정한다.
```

결과 `review_entry_argv`는 기존 `review_news_interactive.py`를 특정
`--batch-sha256`/`--case-sha256`에 연결하는 **실행하지 않은 인자 목록**이다.
실제 검수자가 프로젝트 폴더에서 본인의 `--reviewer-code`를 추가해 실행해야 한다.
대화형 프로그램은 출처 확인, 중복/중요 여부, 근거 메모 및 최종 확인을
사람에게 직접 요구한다. 프로그램이 선택한 뉴스 대신 묶음의 첫 사례를
검수하지 않으며, 이미 제출한 사례는 다른 사례로 자동 대체하지 않는다.

- `READY_FOR_HUMAN_REVIEW`: 기존 PIN과 선택한 빈 검수 사례가 일치한다.
- `SELECTED_SLOT_ALREADY_SUBMITTED`: 선택한 슬롯에 제출된 답변이 있으므로 재입력하지 않는다. 답변 내용/정답 여부는 표시하지 않는다.
- `NOT_FROZEN_YET`: 검색된 제목 버전이 아직 기존 Gold에 없으며, 새 PIN/답안지를 임의 생성하지 않는다.
- `GOLD_DATA_UNAVAILABLE` / `REVIEW_ENTRY_UNAVAILABLE`: PIN·동결 자료·작업공간 누락/손상 또는 출처 불일치. 정상 범위의 결과만 유지하고 exit 4로 불완전함을 알린다.

이 모드에서는 자동 중복 힌트·모델 분류/예측·다른 검수자의 답변을 숨긴다.
특정 키워드로 선택된 검수 목록은 **평가용 무작위 표본이나 전체 정답셋이 아니다**.
`review_links_complete`는 반환된 검색 결과의 연결 상태이고, 전체 검색 건수는
`matched_document_versions`, 잘린 결과 여부는 `has_more_matches`로 구분한다.
인적 합의/정확도는 기존 `run_gold_review.py aggregate`에서 실제 답변으로만 평가한다.

실제 Mac 확인(2026-10-14 18:24 KST): 승인 3소스의 제목 버전 **89건** 중
반도체 검색 후보 **2건**(뉴스와이어IT·산업통상부)을 기존 PIN Gold에 연결했다.
A/B 각 슬롯에서 2건 모두 정확한 선택 사례를 읽었으며 인적 라벨 추가 **0건**,
새 Gold 생성 **0건**, 외부/AI 호출 **0건**이다. 조회 전후 등록부·운영 DB·
Gold/PIN/검수 파일 **55개 SHA가 동일**했다. 89건은 독립 사건/정답 수가 아니다.
변경 영향 9개 테스트 파일 **119 PASS / 0 FAIL**, 컴파일·diff 검사 PASS.
전체 V1.0 인수는 **23/36 유지**이며 공급관계·실AI·5거래일/출시 조건은 별도다.

## 뉴스 검색 → 기존 경제 사건 분석 결과 연결 (2026-10-15)
기존 `search_news.py`가 찾은 승인 RSS 제목을 **이미 게시된 분석 결과**와 연결할 수 있다. 검색 결과는 종전과 동일하며 아래 세 옵션을 모두 명시한 경우에만 각 결과의 `saved_analysis`에 원래 분석 행을 첨부한다. 보고서 파일/SHA는 예약 분석 또는 별도 생산자 출력에서 **기존에 기록된 것**을 전달해야 한다. 검색 시 재분석·새 RSS 수집·유료 AI 호출은 없다.

```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/search_news.py --scope all --query 반도체 \
  --analysis-report-file "/private/approved/reports/feed_analysis_<SHA>.json" \
  --analysis-reports-root "/private/approved/reports" \
  --analysis-expected-sha256 "<producer_retained_report_sha256>"
```

- 기존 SHA/PIT reader가 **전체 보고서**를 먼저 검증한 뒤 `(provider_id,event_id,title_sha256)`와 원래 제목·URL·출처 유형·가용 시각·triage SHA까지 대조한다. 같은 ID인데 출처 값이 다른 경우 `SEARCH_DATA_UNAVAILABLE`/exit4이며 임의의 분석 내용을 연결하지 않는다.
- 이 분석 보고서에 없는 제목은 `saved_analysis: null`; `saved_analysis_unmatched`는 **해당 보고서에 미포함**이라는 뜻이다. 실제 미발생·무관계·AI 분석 실패의 증거가 아니다. `saved_analysis_matches`, 저장 SHA, 생산 시각과 **현재 소비 가능 시각**은 분리하여 출력한다.
- `saved_analysis`의 사건 분류·중요도·AI 요약·불확실성은 원본 그대로 **미확인** 상태다. 검색·연결은 `fact_verified_by_search=false`, `historical_analysis_join_certified=false`, `market_action=null`을 유지하고 과거 재생시점에 새 정보를 소급 제공하지 않는다. 결과에는 비공개 분석 메타가 포함될 수 있으므로 표준출력·JSON을 공개 로그/Git에 기록하지 않는다.
- `--review-links`의 독립 Gold 맹검 작업에는 분석값을 섞지 않는다. 세 분석 옵션과 맹검 모드를 함께 사용하면 오류를 반환한다. `--scope core`의 종전 로컬 검색 인덱스 갱신 동작은 유지되며, `--scope all/motir`은 기존 완료 스냅샷을 읽기 전용 조회한다.
- 변경 영향 8개 테스트파일 **133 PASS/0 FAIL**, 그리고 이전에 보관한 실제 승인 메타(core/MOTIR) 결과에 대해 별도 CLI 프로세스 각각 exit0, 관련 분석 결합 2건/1건, 두 보고서 SHA 무변경, 신규 네트워크/유료AI 0회 확인. **실제 뉴스 내용의 사실성·반도체 수혜관계·인적 평가·5거래일 인수는 미검증**으로 구분한다.
