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
