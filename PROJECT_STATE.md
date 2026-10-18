# PROJECT_STATE — 새 완료 평가의 크기 제한 장애 수정 · 두 News 서비스 적용 승인 대기

**목적·흐름:** 실제 뉴스 → 뉴스 분석(경제 변화·공통 사건·초기 테마) → 관련 산업·기업 → 기업별 근거·원문 조회. 전력기기 우선 적용. 사실/추론·계획/실행·미확인, 원본/PIT/비밀·무주문을 지킨다.

기준 2026-10-18T21:03:34.057771+00:00. 실제 수신 장애 수정 고정판 **fc5072bf12f656e16bccd0d32832b7e9e93798f0** / 원V1 **36/36** 유지. 운영은 기존 **6f77b68da618c5ce31233ad05a434bc08b19373f**이며 아직 이번 새 판본을 적용하지 않았다.

Era 현재 홈에 새 완료 일간50기업 게시 f2e248c5b7c396e21b4b637fd8047534f964f11dbf5ed49039ce6134978ff6c5 / 파일 SHA41c03b345565522c2319c8e3e2579f475c7916438b358fd181d214c542b22050 / 평가시각2026-10-18T20:47:50.217894+00:00이 도착했다. 직전 대기의 ‘새 게시 없음’은 해소됐다. 다만17,067,081 bytes가 기존16MiB를 넘어 기존 수신기가 실제 거부했다. 기존 뉴스·평가는 보존됐고 새 원본을 다시 수집하지 않았다.

기존 수신/검증 경로의 JSON32MiB·수신기록64MiB 한도로 수정했다. HTML/기업 식별 view16MiB와 SHA·완료표시·정확 기업·PIT·원본 보존·무주문 검증은 유지한다. DEV52 PASS / SSD고정판52 PASS(19.76초,0실패·0skip). 큰 정상 게시의 저장 바이트·재조회·과거 조회·중복 방지·한도 초과 거부를 확인했다. 새 의존성/평가 엔진/수집기 없음.

분리 폴더 실자료 수신50·반복 ALREADY_IMPORTED·과거 snapshot 동일·무효0. 실제 검증 API 비교15건·과거 전체 비교 객체 동일·HD 공식 종목 조회 AVAILABLE. 새 게시에는 생산자 WATCH의 HD도 있어 세 기업 모두 같은 일간판에 연결되지만 News가 WATCH를 강제 편입하지 않았다. 세 기업 연간 재무 지표 변화0. LS/효성 근거 유지, HD는 기존 개별 평가→일간 평가의 설명/한계 표현 변경으로 근거 변경이며 상향·새 실적·납품 인증이 아니다. 당일 시작 대비 HD 첫 연결과 직전 수신 대비 설명 변경을 구별한다. 가격 정식배수 N/A는 유지한다.

## 운영 적용 승인 대기 — 기존 질문 한 건
사용자에게 ‘검증된 fc5072b의 큰 평가자료 수신 장애 수정’으로 News 대시보드+기존 research-approved 자동 수신 서비스 **총2개**의 판본 변경·재시작을 한 번 질문했다. 기존 승인은 dashboard 한 서비스에 한정돼 자동 수신까지 확대하지 않는다. 승인 답변 전 실행 금지·같은 질문 재요청 금지. 수신 재시작 시 기존 허용 출처1회 처리가 가능함을 질문에 명시했다. 예약 간격/인자·출처·Era 코드/DB/Git/설정 변경은 제외한다.

고정 dashboard는 /Users/shmoon/Library/Application Support/NewsCatalystOS/releases/fc5072bf12f656e16bccd0d32832b7e9e93798f0. 자동 수신은 기존7e0001c8 판본 복사본 /Users/shmoon/Library/Application Support/NewsCatalystOS/releases/fc5072bf12f656e16bccd0d32832b7e9e93798f0-research에서 era_daily_assessment.py의 크기 검사만 변경했다(다른 파일 바이트 동일). 이 별도 판본으로 실제 새 게시 check_only·세 기업 읽기 AVAILABLE·무효0 확인. before/planned plist·원판본·보호 해시 준비. 실행 도구 /private/tmp/nc_activate_daily_size.py는 문법 확인만 했고 미실행이다. 승인 후 기존 수신 작업이 실행 중이면 현재 PID의 종료를 기다리고 두 서비스만 전환한다. RunAtLoad로 시작한 실제 수신의 완료/첫 수신 시각·반복0·운영15비교·과거 동일을 확인한다. 같은 판본의 수동 수신을 동시에 시작하지 않는다.

검증 화면 http://127.0.0.1:8767/ 은 분리 데이터·임시 PID66221, UI 새 판본 SHA/공식 재무/가격 N/A·LS/효성 유지 확인, preview.png 저장. 운영 수신본·다른 서비스·Era 원본 변경0. 승인/적용 후 임시 화면을 종료한다. 운영 데이터를 미리 신판 수신본으로 바꾸지 않는다.

## 새로 연결된 실제 입력→분석→기업·원문·출력
- Semco 2023-06-13 공식 EPC 발표는 Baltica 2 해상변전소 4기와 Hyundai Electric의 주요 하도급 참여를 명시한다. 이 계약 당사자는 Semco/PTSC 컨소시엄이며 HD 개별 수주액·장비 인수 증거로 승격하지 않는다.
- PTSC M&C 2026-09-16 공식 원문은 9월13일까지 4기 상부구조물의 반출·출항 완료를 보도한다. 같은 프로젝트·PGE/Ørsted·Semco/PTSC·4기 범위로 앞선 계약 원문과 연결한다. 후속 원문에는 HD 개별 장비의 인도·대금·최종 인수가 없고 해상 설치/최초 전력·상업 가동은 이후 계획이다.
- 기존 북미 빅테크 기본계약·765kV 사업과 별도 프로젝트다. 최초 확보 시각을 실제 각 환경의 입력 이후로 보존했다. 2023년 계약·2026년9월 출항을 오늘의 신규 수요로 세지 않는다. 회사 원문·직접 수행사 보도상 주장과 독립 검증을 구분한다.
- 기존 후속 비교를 v4의 출하 단계와 명시 범위(PROJECT_ONLY/NAMED_COMPANY)로 확장했다. 프로젝트 출하는 SOURCE_REPORTED_PROJECT_PROGRESS로 표시하고 reported_execution_progress=false를 유지한다. 개별 장비 최종 납품·계통 가동으로 자동 변환하지 않는다. 기존 v1~v3 출력은 보존했다. 유럽을 글로벌 수요로 확대하지 않도록 EU 지역 코드를 추가했다.
- 운영 실제 비교13→15건. 이번 입력 전후 세 기업의 평가 모두 AVAILABLE/UNCHANGED_ASSESSMENT. HD의 프로젝트 출하 진전은 넓은 신재생 전력망 가설의 이행 근거를 보완하며 기업 평가 상향·매출 확정은 아니다. LS/효성은 추적 계약의 새 이행 근거 미확보를 유지한다. 실제 취소·수요 감소 미확보를 약화나 취소 없음 인증으로 만들지 않는다. 일간 시작 대비 HD 평가 첫 연결과 이번 자료 추가 전후 평가 유지를 구분한다.
- 원문 제목에 HD 이름이 없어도 출처에 묶인 읽기 분석으로 기업을 연결하고, 해당 기사→HD 기존 공식 재무 평가 AVAILABLE와 두 원문을 실제 조회했다. 출처 회사 이름을 기사 제목에 삽입하거나 원래 사건·WATCH 순위를 바꾸지 않았다.
- 화면 ‘이 비교 자료 저장’의 실제 브라우저 파일15건 확인:281,657 bytes·SHA0b793d71ca40d7c48c34965d7035c38f9b4a39f577459b0aa5bc69a338b23b41. 고정 조회시각·원문·프로젝트 범위·세 기업 평가를 포함한다.

## 시험·실자료·운영
- DEV 영향 시험91 PASS 후 혼재 이행 판정까지 포함한 출하 시험12 PASS. 최종 고정판 SSD **92 passed in 55.82s / 0 FAIL / 0 SKIP**. 중복 실행을 합산하지 않는다. 과거 조회·중복 입력0·스키마/범위 오류 거부·개별 출하/프로젝트 출하 정상 경로·차질 혼재·원문 링크·화면·저장 출력 확인. 기존 전체 회귀는 변경 없는 부분의 유효 증거를 재사용했다.
- 운영을 먼저 건드리지 않고 문서/출처 워크스페이스 복사본에서 실제 두 원문을 기존 경로로 입력·비교15건·과거13건·기업 평가 유지와 UI/파일 저장을 확인했다.
- 사용자가 새6f77b68에 대해 ‘News 대시보드 한 서비스 적용 허용’을 명시 승인했다. 기존6bd→6f 실행 경로 전환·재시작 완료. 다른 News 예약 plist SHA 동일. 임시8767 종료. 수집 예약·Era 코드/DB/Git/설정 변경0.
- 승인 후 운영 입력에서 새 두 제목/읽기를 다시 처리해 운영 확보 시각을 보존했다. 기존 출처 허용 항목 값은 동일하며 신규 수동 메타데이터 출처2개만 추가했다. HTTP 자동 수집이나 예약 출처를 늘리지 않았다. 원문 본문 저장0·유료AI0·새 의존성0. 기존 읽기/입력 파일은 유지했다.
- 운영 비교15건·이전 조회13건·PTSC 개별 기사→HD 평가 AVAILABLE·이번 추가 전후 세 평가 근거 유지 확인. API 검증3건 합계19.538초이며 단일 요청 응답 시간으로 표시하지 않는다. 기존 중복 평가 읽기 최적화와 저장 기능은 보존했으나 전체 기간 즉시 응답을 보장하지 않는다.
- 운영 입력 전 표준 내보내기는 바이트 동일하게 재조회했고 반복 읽기 게시0을 확인했다. HD2024/2025 기존 CFS 예외 원본·평가만 재사용하며 재수집/평가 재생산0. 사용자 untracked vision SHA 보존. 이전 dashboard plist/고정판 보존. 구판으로 되돌릴 때는 이 작업에서 추가한 EU/v4 읽기2개도 비공개 보존 영역으로 분리한 뒤 구판을 사용해야 한다.

## 통합 전체의 별도 잔여
Era ER02 최신 산업기간/정확 분류·ER04 공식 가격 분모/접근·Era OP02 첫 평일10시 예약 실행 증거는 별도 잔여다. FY2025 산업 통계는 생산자 문서상10/21 12KST 예정이며 게시/원본 검증 전 완료로 세지 않는다. 같은401/403·미실행 확인을 반복하지 않는다. 이 외부 잔여가 이번 News 수신 장애 수정을 차단하지 않았다. 전체 공동 목표는 미완료이며 이번 운영 적용 승인만 해당 두 서비스에 국소 대기한다.

## 합의한 완료조건의 현재 판정
조건 정의 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md. 기왕의 유효 증거를 재사용하고 새로운 최소 표본/사람 검수/추가 기다림 게이트를 만들지 않았다.

| 조건 | 기능·시험 / 실제 자료·운영 / 근거 | 남은 항목 |
|---|---|---|
| NC-01 | 완료: 허용 출처 자동 수집·중복/재개. continuous_completion_20261018/first_tick_summary.json 실제 예약 COMPLETE·5출처 실패0, real_incremental.json 반복 중복 방지 | 새 원문이 없으면 없다고 유지 |
| NC-02 | 완료: 경제 행동·발표/계획/취소·정정 및 원문 연결. 기존 전체 회귀와 기존117 및 이번92, 실제 전력기기 비교13 | 개별 자료에 없는 이행 사실을 생성하지 않음 |
| NC-03 | 완료: 기존 이름표에 한정하지 않는 공통 사업/행동 관찰50주제·55행동·미분류39, 실제 관찰→테마→출처 조회 | 공통 인과·독립 시장사건 확정은 별도 사실 |
| NC-04 | 완료: 기업 식별·직접/추론·분리된 수혜 가설. 실제3기업 뉴스→검증 평가 AVAILABLE·원문 조회 | 기업 언급을 실수혜 확정으로 만들지 않음 |
| NC-05 | 완료: 최초·이전 판본/PIT 보존, 후속·정정·취소 판정 및 중복 방지 시험. 실제15자료의 과거/별도 사업·프로젝트 출하와 개별 기업 최종 납품을 구분 | 같은 계약 실제 추가 발주/납품/취소는 현재 선택 자료에 미확보; 기능 실패/새 출시 게이트 아님 |
| NC-06 | 완료: 대시보드·검색·기간 비교·기존 보고/표준 출력. 이번 화면 비교 저장의 실제 파일+운영 일치 | 전체 기간 로딩 지연 관측은 남김 |
| OP-01 | News 완료: continuous_completion_20261018/first_tick_summary.json·company_economic_bridge_20261018/real_integration_proof.json·이번 운영 API/UI | Era 전체 운영 완료와 구분 |
| OP-02 | News 완료: 기존 core/MOTIR/research-approved 실제 예약·오류 재시도/재개 시험과 operational_verification.json, 예약 설정 보존 | Era 별도 첫 예약 실행/복구는 읽기 전용 외부 경로 |
| OP-03 | News 완료: 실제 source/SHA/PIT, 읽기 전용 Era 공유·비밀/원본 분리·관련 시험 | 새로 찾은 과거 뉴스를 과거에 가용했던 것으로 만들지 않음 |
| OP-04 | News 완료: 기존 출시 전체 회귀7502개 적용 범위(7492통과10skip0실패 및 수정 후 coverage reconciliation) + 기존117 및 이번92 영향 시험. 출력 full_regression_reconciled.json·ssd_tests.txt | 기존117 및 이번92을 새 전체 회귀로 합산하지 않음 |
| OP-05 | News 완료: operational_verification.json의 비용/캐시 DB 별도 폴더 복원·무결성, dashboard 이전 plist/고정판 보존 및 재개 | 다른 물리 장치 새 조건 없음 |
| OP-06 | News 완료: 실제 Gemini 생성·비용/캐시·월5만원 제한. 기존 증거 settled110건90.279원/미정산2건예약15.1552원(당시 값), 이번 호출0 | 현재 잔액 재검사를 새 게이트로 추가하지 않음 |
| INT-01 | 대표 실연동 완료: 회사 경제변화→기존 Era 소비→50WATCH·보고, company_economic_bridge_20261018/real_integration_proof.json | 시장 전체/HD WATCH 강제 편입을 뜻하지 않음 |
| INT-02 | 부분: 세 기업의 사업 근거·공식 연간 재무·위험 평가 실제 연결 및 값 보존. HD는 WATCH 외 개별 연구 | 현재 가격 평가 N/A 및 산업 전체 경쟁력 평가의 생산자 근거 미확보 |
| INT-03 | 완료: 같은 판본 재소비 ALREADY_IMPORTED/ALREADY_PUBLISHED, 미래·오류 제외·한쪽 결측 격리 기존 시험/실제 반복 | 외부 미확보 자료를 생성하지 않음 |
| INT-04 | 대표 뉴스→사업·재무·위험→화면/보고 실경로 완료, News6f77b68·Era 게시 소비 기존934ff8f 및 개별 평가 원본SHA 고정 | 가격/시장 전체를 포함한 공동 완료는 부분; 현재 읽기 확인 EraHEAD db11d2f은 생산자 고정판과 혼용 금지; 새 일간 연결은 fc5072b 분리 검증까지이며 운영 승인 대기 |

Era ER-01~06 전체 인수는 News에서 변경할 권한이 없고 완료 인증하지 않는다. 읽기 확인 당시 Era PROJECT_STATE: KR WATCH50/연간44/peer21/strict가격0/N/A50, FY2025 산업전체 자료 미게시(예정10/21 12:00KST) 및 분류 매핑, KRX 권한/주식 귀속·완료세션 근거, Era 신규 평일10시 예약의 첫 실제 실행/복구가 남아 있다. US 일부 후보는 전시장 완료가 아니다. 같은401/403·결측·미실행을 반복 확인하거나 Era 수집기/평가기를 News에 새로 만들지 않는다. 전체 공동 목표는 미완료이나 News 독립 운영은 계속된다.

비공개 최신 증거 output/project_shipment_20261019/: selected_source_metadata.json, candidate_intake.json, candidate_comparison.json, before_export.json, candidate.json, affected_tests.txt, final_scope_tests.txt, ssd_tests.txt, candidate_verification.json, ui_comparison_download.json, ui_verification.json, preview.png, activation.json, production_intake.json, production_before_export.json, operating_comparison.json, operating_verification.json, operating.png. 이전 query_output_completion_20261019·continuous_completion_20261018·company_economic_bridge_20261018 증거는 그대로 보존한다. 원본/DB/출력/스크린샷은 Git 제외.

이번 비공개 최신 증거 output/daily_publication_size_20261019/: candidate.json, real_verification.json, company_comparison.json, ssd_tests.txt, research_candidate_verification.json, candidate_api_verification.json, candidate_api_view.json, ui_verification.json, preview.png, 두 before/planned plist, public_check.json. 기존 증거는 보존한다.
