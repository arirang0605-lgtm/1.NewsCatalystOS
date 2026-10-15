# NewsCatalystOS V1.0: 실제 허가 RSS 제목 검색

> 현재 기준은 D-060/D-059이다. 사람 검수 절차와 관련 도구는 삭제했다. 아래 실행 기록은 당시 기록이며 현재 완료 상태는 PROJECT_STATE.md를 따른다.

## 사용법
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/search_news.py --query 기업 --limit 20
PYTHONPATH=src python3 scripts/search_news.py --query 반도체 --semiconductor-only
PYTHONPATH=src python3 scripts/search_news.py --query 중소 --source-id mss-official-press
```
- 각 실행 시 이전 ACK를 SHA 검증하고 새 제목 버전만 저장한 뒤 검색한다. 결과에는 `verified_economic_fact=false`, `verified_supply_transaction=false`, `confirmed_beneficiary=false`를 명시한다.

## 2026-10-14 추가: 격리된 3개 출처 통합 제목 검색

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
