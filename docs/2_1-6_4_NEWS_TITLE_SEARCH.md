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
