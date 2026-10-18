# PROJECT_STATE — 발주·납품 근거와 위험 비교

**목적·흐름:** 실제 뉴스 → 뉴스 분석(경제 변화·공통 사건·초기 테마) → 관련 산업·기업 → 기업별 근거·원문 조회. 전력기기 우선 적용. 사실/추론·계획/실행·미확인, 원본/PIT/비밀·무주문을 지킨다.

기준 2026-10-18T17:49:35.405544+00:00. News 기능·운영 고정판 **42904c78c2952d0cde5e7660739d399444418a29**. 개발 codex/real-data-path와 SSD 출력 코드 내보내기/운영 release를 분리했다.

## 새로 작동하는 경로
- LS 10월1일 북미 AI 데이터센터 9개 변전소 초고압변압기 계약, LS America 미국 AI 배전 납품 사례, Collett 영국 National Grid Hyosung 변압기 운송·설치 완료의 제목·원문3건을 기존 입력→분석→연결→조회 경로로 추가했다. 제목 판본406→409, 관찰49주제/54행동. 원문 전문 저장0, 추가 AI0.
- 기존 비교7→10건. HD 환율·발주 전환 시점 전망과 효성 고마진 매출 인식 이연·중동 운송 지연 설명을 외부 위험 참고로 연결했다. 기존 두 분석의 새 판본이며 새 계약/뉴스 제목으로 중복 집계하지 않았다.
- 날짜 없는 공식 납품 사례2건은 v3에서 reported_date=null. 실제 수신 시점은 유지하며 PUBLICATION_DATE_UNAVAILABLE로 표시하고 같은 계약의 후속 진전·차질 판정에서 제외한다. 수집일·다른 보도자료 날짜·목록의 월을 발행일로 만들지 않는다.
- v3에서 원문이 수요 원인을 명시하지 않으면 factor_codes=[]로 보존한다. 영국 납품을 노후 전력망 교체로 추정 분류하지 않았다. 기존 v1/v2 분류 형식은 유지한다.
- 넓은 사업 근거 SUPPORT_ADDED, 세 회사 추적 계약 모두 NO_NEW_EXECUTION_PROOF. 실제 취소·수요 감소 발생 근거는 선택 자료에서 미확보. 관련 사업의 완료 실례를 기존 계약의 이행으로 전이하지 않는다.
- 모든 비교10건의 실제 정확 기사 조회 성공. LS·효성은 기존 Era 공식 연결재무·기업 평가 AVAILABLE, HD는 COMPANY_NOT_IN_SNAPSHOT. LS 납품 사례에서 기존 평가까지 실제 화면 확인.

## 시험·실자료·운영
- 최종 DEV 관련 시험 **59 PASS/0 FAIL/0 SKIP**, 동일 고정판 SSD 시험 **59 PASS/0 FAIL/0 SKIP**. ERALEADER_SOURCE_ROOT를 읽기 전용으로 지정해 기존 수신 계약 시험10건도 실행했다. 개발 중 UI 조사 표현 오류와 날짜 없는 자료의 수신 계약 불일치는 수정 후 재검증했다.
- 기존 Era v1 경제영향 입력은 날짜를 요구하며 DELIVERY_PLANNED 실행 단계가 없다. 날짜 없는2건과 해당 계획 단계1건은 News 원문·읽기·기업 평가 화면에 보존하고 이 버전 평가 입력에서는 제외한다. 날짜 위조/분석 삭제/수신기 수정 없이 호환한다. 실제 최신 고정 게시 수신: 3개 주제/7개 입력, 기존 평가 수신 5개, 오류0, HD는 미연결.
- 과거 고정 시점 기본/확장 내보내기 SHA 동일. 분석 재입력 신규0, 고정 게시 재실행 ALREADY_PUBLISHED. 기존 게시·분석 파일과 기존 제공자 설정 값 보존.
- dashboard와 research-approved만 새 코드로 교체, 기존 시간당 주기·출처·경로 유지, core/MOTIR 설정 SHA 동일. 최신 RunAtLoad 실행 COMPLETE·신규 분석0·게시 재사용. 고정 게시70테마. Era 코드/DB/Git/운영설정/수집기는 변경하지 않았다.
- 원V1 **36/36** 기록 유지. 이전 fa4e862 전체 범위 7492 PASS/10 SKIP 증거는 이전 코드 기준이며 이번 전체 재실행으로 표시하지 않는다. 공동 전체 제품·미국·모든 회사 인수 완료와 구분한다.

## HD 남은 단절과 권한
현재 Era 완료 daily50 판본 SHA 17df8208f1e508e1e350c5b97691534867b0feec2364f5c1e749e78b1417989e에는 HD가 없다. 최신 전시장 원본도 WAIT_VERIFIED_ANNUAL_CFS_MISSING. 정확한 종목명/가격이나 공개 IR을 검증 연간재무·완료 기업 평가로 바꾸지 않는다.
사용자에게 HD(267260)의 누락 2024·2025 연간 CFS만 기존 Era 작업으로 확보·평가하고 새 결과를 소비하는 읽기 전용 예외를 요청했다. **아직 응답·승인 없음**. 원본 재사용, 새 연구 결과만, Era 코드/DB/Git/운영설정 무변경을 제안했으며 실행하지 않았다. 최신 응답이 있으면 그 범위부터 적용한다. 승인 대기는 HD에만 적용했고 가능한 News 기능·실자료·운영 작업은 완료했다.

증거: output/power_followups_20261019/의 selected_source_metadata.json, followup_reading_input.json, ingest_receipts.json, publication_and_activation_latest.json, live_verification_latest.json, actual_receiver_before.json·after.json, ssd_tests_latest.txt, ls_delivery_company_proof.png. output은 Git 제외·비공개. 기존 untracked vision 파일 보존. 공개 push 없음. 다음 NEXT_TASK.md.
