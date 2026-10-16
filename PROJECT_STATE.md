# PROJECT_STATE — 개발 재개

<!-- PRODUCT-COMPLETION-20261016 -->
## 2026-10-16 — 완료 조건 문서화 (기능 진척 없음)
- 사용자 요청으로 [docs/PRODUCT_COMPLETION_CRITERIA_20261016.md](docs/PRODUCT_COMPLETION_CRITERIA_20261016.md)를 추가하고 AGENTS/START/운영 정책/DECISIONS에서 참조한다. 두 프로젝트와 NewsCatalystOS 실제 운영 폴더에 동일 기준을 보관한다.
- 기능 완료·실자료 확인·독립 운영 가능·공동 연동 완료를 구분한다. 문서 내용/참조/동일본·기존 변경 보존을 확인하는 작업이며 실행 코드·운영 설정·DB를 변경하거나 기능 시험을 재실행하지 않는다. 각 조건의 현재 충족 여부를 이번에 재판정하지 않는다.
- 다음 개발은 아래 기존 최신 구현과 NEXT_TASK/재개 지침을 이어가며, 완료 보고 시 해당 조건 ID와 실제 증거를 연결한다. 이 기록으로 다음 기능을 문서/관리 도구 개발로 바꾸지 않는다.


## 제품 경로와 원칙
경제 변화→공통 원인→초기 테마→기업 근거/출처→검색·대시보드·읽기 전용 출력. 완료 기준은 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md. 과거36/36은 현재 제품 완료율이 아니다. 원본·비밀·사용권·PIT/SHA·공통 예산·무인 운영·EraLeader 읽기 전용·실주문 금지를 유지한다.

## 최신 구현 — 전체 저장 뉴스 검색 대시보드 연결 (2026-10-17T08:45:29+09:00)
- 작업 NEWS-20261017-DASHBOARD-FEDERATED-NEWS-SEARCH, 로컬 기능 SHA `73d6afb412d07f5bc4d6d286b793aa4778a85c1b`. 기존 연합 뉴스 검색을 GET /api/news-search와 기존 화면의 제목 검색·반도체 후보 옵션·원문링크에 연결. 두 승인 공급자 경로 독립 유지, SHA/수집시각/개별판본 및 미검증 라벨 보존. 중복은 중복 힌트만 표시, 독립 사건으로 합치지 않는다.
- 집중시험 `tests/test_dashboard_federated_news_search.py` **3 PASS**, 기존 `test_research_dashboard.py`+`test_direct_company_search.py` **15 PASS**, Python/JS 구문 PASS. 실행된 테스트에서 실패0. 운영 실자료를 읽기 전용으로 검색해 총 **173판본(core156/motir17)**, '반도체' 일치 **3판본** / HTTP200·출처검색 scope2 정상. 네트워크/AI/원본쓰기0, 운영 registry/SQLite4파일 SHA 불변. 기존 운영 보고서 2026-10-16 43기사·8테마·5후보 읽기 전용으로 조회했으며 저장 원문은 독립 사실 확인 아님.
- **검증 분리:** 신규 UI는 개발 로컬 코드 및 임시 HTTP로만 확인, 운영 SSD/상시8766 서버 미배포·공개 push 미시도. 검색 3건은 *제목 메타데이터* 양성이며 반도체 공급망의 독립 실거래·수혜 증거는 아니다. 저장 실자료 탐색 경로 증명과 운영·연동 인수는 별개다.
- 이전 시장진출 병렬 기능 15b3848 및 신규315/영향237 PASS 보존. 사용자 dirty AGENTS/DECISIONS/비전3파일, 원본·Era·PIT/비밀/예산 경계 유지.
- **다음 실제 입력→출력 작업:** NEXT_TASK.md 참조. 제목 검색 결과의 정확 기사 판본→기존 경제변화/테마/기업 조회 연결. 증거 없으면 명시 N/A; 공식 ID나 수혜 추정 금지.

## 최신 기능 — NEWS-20261017-MARKET-COMMERCIAL-PARALLEL-01 (2026-10-17)
- 로컬 기능 SHA: `15b3848c606353d493f4e215e4ef2fe88ce9edc2`. 기존 완전 원문/단일 기업/공통 원인 검증으로 MARKET_ENTRY+DELIVERY_START 및 MARKET_ENTRY+CUSTOMER_ACQUISITION를 5원인에서 인식하고 기존 경제변화→테마→기업/근거→검색·HTTP→세 화면·JSON에 전달한다. 시장명은 각 시장진출 원문만, 고객은 새 actor가 아니며 수혜/실거래 검증 아님. 기존 legacy opt-out·행동 ID/최초 시각/PIT 및 추가·불완전행동 원자 차단 보존.
- 테스트: 신규 `tests/test_market_commercial_parallel.py` **315 PASS** (저장/기간/검색HTTP/Node UI/고정JSON 포함); 영향 기존 `tests/test_delivery_customer_parallel.py` **237 PASS**, 모두 2026-10-17 로컬 실행·실패 0. 실제 뉴스에서 이 특정 병렬 사건 양성 확인 및 운영 배포·원격 push **미수행**. 기존 사용자 dirty3 파일 불변.
- 기준: V1 기존 36/36 구현 기록은 보존하지만 NC/OP/INT 실제 인수 완료로 환산하지 않는다. 최신 완료 체크리스트는 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md. 실자료 운영 증거와 별도 예약 확인은 독립적으로 관리한다.

## 최신 판정 범위
새 기능의 양성은 합성이다. 기존 325/231/246/386/362 및 과거173제목3본문 결과를 최신 실자료 양성으로 주장하지 않는다.
현재 개발 브랜치 변경은 로컬에만 반영되고 운영 원본은 불변. 개발/테스트/실자료/예약/배포 증거를 분리한다.
사용자 dirty AGENTS.md·DECISIONS.md·비전 파일, 원본/비밀/사용권/PIT·공통 예산을 보존했다.

## 원격 반영
이전 원격 push는 구체적 승인 부족으로 거절되었다. 이번 기능의 push/배포 시도 없음.

## 다음 핵심 작업
NEXT_TASK.md — 검색 결과에 저장된 같은 기사 판본의 경제변화·테마·기업 근거를 연결하는 조회 경로를 우선 구현한다. 신규 수집/유료 AI/운영 DB 수정과 중복 검증을 대체하지 않는다.
