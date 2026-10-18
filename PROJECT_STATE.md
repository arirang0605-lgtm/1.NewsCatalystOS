# PROJECT_STATE — 기간 조회 최적화·표시된 기업 비교 저장 운영 완료

**목적·흐름:** 실제 뉴스 → 뉴스 분석(경제 변화·공통 사건·초기 테마) → 관련 산업·기업 → 기업별 근거·원문 조회. 전력기기 우선 적용. 사실/추론·계획/실행·미확인, 원본/PIT/비밀·무주문을 지킨다.

기준 2026-10-18T20:07:18.188409+00:00. News dashboard8766 운영/기능 고정판 **6bd5b55f1527bcbad2da320b5dd5f08893a48bc1**. 기존 V1 **36/36** 유지. 아래 News 독립 운영과 Era 공동 전체 제품 완료를 구분한다.

## 새로 작동하는 입력→처리→출력
- 기존 실제 비교13건·세 기업의 검증된 Era 평가를 재사용한다. 단일 요청 안에서 같은 기준 시점의 완료 평가 수신본을 재사용하며, 다음 요청에서는 원본/PIT/SHA/손상을 다시 확인한다. 영구 캐시나 검증 생략이 아니다. 빈 기업 후보는 재무 파일을 읽지 않는다.
- 여러 완료 판본을 모두 보유하지 않고 기존 정렬 기준상 최신 가용 판본만 유지한다. 과거 조회·동률 선택·미래 자료 제외·오류 격리는 보존했다.
- ‘이 비교 자료 저장’은 화면에 표시된 전체 비교와 고정된 as_of/since/outlook_id를 그 순간 JSON으로 묶어 SHA 파일명으로 저장한다. 클릭 후 다른 화면으로 이동해도 이미 선택한 자료가 저장된다. 새 조회/AI/본문 저장 없이 회사별 평가의 실제 변경 전후·원문·계약 실행 비교를 함께 내보낸다.
- 실제 브라우저 클릭으로 저장 완료 및 파일 생성 확인. 파일273,730 bytes, SHA c13884bee1cab7146570b6ef4b0feb012ba0ffe565501cf3d7a799c0be338e29. 비교13건·기업평가3개를 포함한다. 운영 API의 같은 기준 자료와 일치한다. API별 since/as_of의 KST/UTC 표기는 동일 순간으로 비교했다.
- 현재 추가 자료 전후 세 기업 평가 근거는 유지된다. 일간 시작 대비 HD는 첫 평가 연결이며 상향이 아니다. LS/효성은 근거 유지다. 넓은 사업 가설은 SUPPORT_ADDED이나 추적 계약 모두 NO_NEW_EXECUTION_PROOF. 실제 취소·수요 감소 미확보는 약화 또는 취소 없음 인증이 아니다. 이번에는 새 뉴스를 확보·추가한 것으로 세지 않았다.

## 기능 시험·실자료·운영 증거
- DEV 관련117 PASS/0 FAIL/0 SKIP, 고정판 SSD **117 passed in 55.87s**. 요청 내 재사용·다음 요청 손상 탐지·PIT·격리·정렬·실 HTTP 호출 수·다운로드 내용/선택 시점/SHA 검증. JS 구문·diff 검사 통과. 기존 변경 없는 전체 회귀를 다시 실행한 것으로 표시하지 않는다.
- 동일 실제 입력·고정시각에서 이전/현재 기간 API 응답1,044,502 bytes가 바이트까지 동일했다. 평가 수신 파일 읽기65→26, 스냅샷 선택5→2. 관측 조회69.176→37.000초; 새 측정은 관련 시험과 겹쳐 통제된 성능 보장/SLA로 쓰지 않는다. 실제 UI에서 로딩 대기가 있었으며 전체 기간 조회가 즉시 응답한다고 주장하지 않는다.
- 사용자 새 명시 승인으로 dashboard 한 서비스만 1b1f1f8→6bd5b55 실행 경로 전환·재시작 완료. 최초 자동 검토는 이전 승인이1b에 한정됐다는 이유로 거절했으며, 새 승인 후 적용했다. 다른 News 예약 plist SHA 동일. Era 코드/DB/Git/설정·수집예약 변경0. 임시8767 종료. 운영 화면 새 저장 버튼·비교13건·세 평가AVAILABLE, 같은 기준 API 확인7.891초.
- HD2024/2025 기존 CFS 예외는 완료 원본/평가만 재사용. 재수집/재평가0, 유료AI0, 새 의존성0. 기존 사용자 untracked vision SHA 보존.

## 합의한 완료조건의 현재 판정
조건 정의 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md. 기왕의 유효 증거를 재사용하고 새로운 최소 표본/사람 검수/추가 기다림 게이트를 만들지 않았다.

| 조건 | 기능·시험 / 실제 자료·운영 / 근거 | 남은 항목 |
|---|---|---|
| NC-01 | 완료: 허용 출처 자동 수집·중복/재개. continuous_completion_20261018/first_tick_summary.json 실제 예약 COMPLETE·5출처 실패0, real_incremental.json 반복 중복 방지 | 새 원문이 없으면 없다고 유지 |
| NC-02 | 완료: 경제 행동·발표/계획/취소·정정 및 원문 연결. 기존 전체 회귀와 관련117, 실제 전력기기 비교13 | 개별 자료에 없는 이행 사실을 생성하지 않음 |
| NC-03 | 완료: 기존 이름표에 한정하지 않는 공통 사업/행동 관찰50주제·55행동·미분류39, 실제 관찰→테마→출처 조회 | 공통 인과·독립 시장사건 확정은 별도 사실 |
| NC-04 | 완료: 기업 식별·직접/추론·분리된 수혜 가설. 실제3기업 뉴스→검증 평가 AVAILABLE·원문 조회 | 기업 언급을 실수혜 확정으로 만들지 않음 |
| NC-05 | 완료: 최초·이전 판본/PIT 보존, 후속·정정·취소 판정 및 중복 방지 시험. 실제13자료의 과거/별도 사업과 동일 계약 후속을 구분 | 같은 계약 실제 추가 발주/납품/취소는 현재 선택 자료에 미확보; 기능 실패/새 출시 게이트 아님 |
| NC-06 | 완료: 대시보드·검색·기간 비교·기존 보고/표준 출력. 이번 화면 비교 저장의 실제 파일+운영 일치 | 전체 기간 로딩 지연 관측은 남김 |
| OP-01 | News 완료: continuous_completion_20261018/first_tick_summary.json·company_economic_bridge_20261018/real_integration_proof.json·이번 운영 API/UI | Era 전체 운영 완료와 구분 |
| OP-02 | News 완료: 기존 core/MOTIR/research-approved 실제 예약·오류 재시도/재개 시험과 operational_verification.json, 예약 설정 보존 | Era 별도 첫 예약 실행/복구는 읽기 전용 외부 경로 |
| OP-03 | News 완료: 실제 source/SHA/PIT, 읽기 전용 Era 공유·비밀/원본 분리·관련 시험 | 새로 찾은 과거 뉴스를 과거에 가용했던 것으로 만들지 않음 |
| OP-04 | News 완료: 기존 출시 전체 회귀7502개 적용 범위(7492통과10skip0실패 및 수정 후 coverage reconciliation) + 이번117 영향 시험. 출력 full_regression_reconciled.json·ssd_tests.txt | 이번117을 새 전체 회귀로 합산하지 않음 |
| OP-05 | News 완료: operational_verification.json의 비용/캐시 DB 별도 폴더 복원·무결성, dashboard 이전 plist/고정판 보존 및 재개 | 다른 물리 장치 새 조건 없음 |
| OP-06 | News 완료: 실제 Gemini 생성·비용/캐시·월5만원 제한. 기존 증거 settled110건90.279원/미정산2건예약15.1552원(당시 값), 이번 호출0 | 현재 잔액 재검사를 새 게이트로 추가하지 않음 |
| INT-01 | 대표 실연동 완료: 회사 경제변화→기존 Era 소비→50WATCH·보고, company_economic_bridge_20261018/real_integration_proof.json | 시장 전체/HD WATCH 강제 편입을 뜻하지 않음 |
| INT-02 | 부분: 세 기업의 사업 근거·공식 연간 재무·위험 평가 실제 연결 및 값 보존. HD는 WATCH 외 개별 연구 | 현재 가격 평가 N/A 및 산업 전체 경쟁력 평가의 생산자 근거 미확보 |
| INT-03 | 완료: 같은 판본 재소비 ALREADY_IMPORTED/ALREADY_PUBLISHED, 미래·오류 제외·한쪽 결측 격리 기존 시험/실제 반복 | 외부 미확보 자료를 생성하지 않음 |
| INT-04 | 대표 뉴스→사업·재무·위험→화면/보고 실경로 완료, News6bd5b55·Era 게시 소비 기존934ff8f 및 개별 평가 원본SHA 고정 | 가격/시장 전체를 포함한 공동 완료는 부분; 현재 EraHEAD bb7f5a7은 읽기 확인이며 생산자 고정판과 혼용 금지 |

Era ER-01~06 전체 인수는 News에서 변경할 권한이 없고 완료 인증하지 않는다. 읽기 확인 당시 Era PROJECT_STATE: KR WATCH50/연간44/peer21/strict가격0/N/A50, FY2025 산업전체 자료 미게시(예정10/21 12:00KST) 및 분류 매핑, KRX 권한/주식 귀속·완료세션 근거, Era 신규 평일10시 예약의 첫 실제 실행/복구가 남아 있다. US 일부 후보는 전시장 완료가 아니다. 같은401/403·결측·미실행을 반복 확인하거나 Era 수집기/평가기를 News에 새로 만들지 않는다. 전체 공동 목표는 미완료이나 News 독립 운영은 계속된다.

비공개 최신 증거 output/query_output_completion_20261019/: actual_query_comparison.json, ui_comparison_download.json, candidate.json, ssd_tests.txt, saved_comparison_ui.png, activation.json, operating_verification.json, operating_query_output_ui.png, public_range_check.json. 기존 continuous_completion_20261018 및 company_economic_bridge_20261018 증거 보존. 비공개 원본·DB·출력은 Git 제외.
