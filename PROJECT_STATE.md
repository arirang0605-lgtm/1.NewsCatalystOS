# PROJECT_STATE — 세 전력기기 기업의 뉴스·공식 재무·평가 연결

**목적·흐름:** 실제 뉴스 → 뉴스 분석(경제 변화·공통 사건·초기 테마) → 관련 산업·기업 → 기업별 근거·원문 조회. 전력기기 우선 적용. 사실/추론·계획/실행·미확인, 원본/PIT/비밀·무주문을 지킨다.

기준 2026-10-18T18:41:25.881075+00:00. 현재 News 운영 **7e0001c8b1349847c3e0a66f454197530003368a**, 개별 평가 연결 기능 **d09d6d01893c75ad54c08e0d8a1817a44af6d121**. 기존 DEV codex/real-data-path·SSD 코드 내보내기·운영 release를 분리한다.

## 새로 작동하는 HD 경로
- 2026-10-19 사용자 승인 “HD 한 기업의 기존 수집·평가 실행 허용”에 따라 267260의 누락 2024·2025 연간 연결 CFS만 기존 Era 수집기로 확보했다. 기존 공식 기업 명부를 재사용했고 DART 재무 요청은2회. Era 코드/DB/Git/운영설정은 변경하지 않았다. 다른 기업·다른 연도 수집 권한을 확장하지 않았다.
- 기존 dart_annual_margin_context·company_assessment.evaluate를 그대로 실행한 HD 개별 연구 평가를 새 고정 출력으로 게시했다. 종목267260·DART_CORP:01205851, 공식 공시20250320001309/20260316000940, 파일 SHA a686ca997288f40cf04bc5b13bd655d671037d5bc8f985377fb7de716150704f. News 최초 수신 2026-10-18T18:24:03.013911+00:00.
- 실제 HD 기사3건에서 읽기 비교 → 공식 연결재무 FY2025와 전년 비교 → 기존 재무·위험 평가 → 2024/2025 DART 원문을 운영 화면8766에서 확인했다. 최신 원문·영업현금 등은 같은 보고서 영수증에 결속된다. 사업 경쟁우위·현재 저평가·실제 뉴스 수혜·종합 재무 안전성은 N/A.
- LS ELECTRIC·효성중공업의 기존 완료 평가도 유지한다. HD는 개별 기업 조회이고 WATCH 선정과 별개다. 기존 daily50 명단·선정·점수·순위·원래 뉴스 사건/테마는 유지한다. 기존 선정 입력에서는 INDIVIDUAL_ASSESSMENT_OUTSIDE_WATCH로 남겨 새 WATCH 후보로 만들지 않는다.
- 새 자료는 실제 News 수신 이후에만 사용한다. 수신 전 HD 평가 조회의 HTTP bytes SHA는 동일하며 COMPANY_NOT_IN_SNAPSHOT을 유지했다. 반복 수신은 ALREADY_IMPORTED와 최초 시각을 보존한다.

## 뉴스·테마 비교의 현재 범위
원문 비교10건(기준 읽기3건 별도), 관찰49주제/54행동/409제목판본. LS 별도 변압기 계약·미국 AI 배전 납품 사례·영국 Hyosung 변압기 운송/설치 사례와 HD/효성 위험 참고를 연결한 상태다. 날짜 미확인2건은 v3 reported_date=null·후속 이행 시점 판단 제외, 원문 미명시 수요 원인은 빈 분류로 보존한다.
넓은 사업 근거 SUPPORT_ADDED, 세 추적 계약 모두 NO_NEW_EXECUTION_PROOF. 실제 취소/수요 감소 발생 근거는 선택 자료에서 미확보다. 다른 고객/제품/기간·납품 예정·우려를 같은 계약의 실제 이행·취소로 합치지 않는다.
기존 Era v1 평가 입력은 날짜 미확인2건·납품 계획 실행 단계1건을 받지 못하므로 News 조회에 보존하고 해당 평가 입력에서만 제외한다. 현재 고정 게시70테마, 회사 경제 입력7건·기존 선정 수신5건·오류0, HD는 WATCH 밖 미매핑이다. HD 재무 조회 완료와 선정 미편입을 구분한다.

## 시험·실자료·운영
- 개별 연결 기능 d09d6d0 DEV/SSD 각각 **97 PASS**. 이후 기존 예약 수신 보완7e0001c의 관련31 PASS 증거를 재사용하고, 통합 고정판 SSD 내보내기에서 **99 PASS/0 FAIL/0 SKIP** 확인. 중복 시험 수를 합산하지 않는다. 이번 전체7500여 회귀를 재실행한 것으로 표시하지 않는다.
- 비교10건 모두 세 기업 평가 AVAILABLE인 검증용 조회, 현재 운영 HD 기사3건 AVAILABLE, 공식 코드/공시2개·과거 조회 bytes·WATCH50 보존 확인. 직접 운용 화면의 HD 금융 평가와 원문 링크까지 열었다. 운영 HD 기사 조회4.438~4.485초. 동시 검증용 서버/프로파일 부하 중 지연은 해당 검증 서버 종료 후 정상 조회로 확인했으며 새 캐시/추가 검증 게이트를 만들지 않았다.
- 별도 실행이 7e0001c 운영 반영과 기존 research-approved의 명시 개별 평가 파일/SHA 수신을 완료한 상태를 발견하고 그 변경을 보존했다. 해당 실행의 activation_verified.json을 재사용했다. 새 예약 tick COMPLETE·개별 평가 ALREADY_IMPORTED·신규 기사0·AI0·Era API0·70테마 게시 누락0. core/MOTIR 유지.
- 이 턴의 직접 서비스 중지·plist 교체 요청은 자동 승인 검토가 “서비스 변경의 명시 승인 부족”으로 거부하여 실행하지 않았다. 우회/재시도 없이 검증 서버를 사용했고, 이후 이미 운영 반영된 7e0001c를 읽기 검증했다. 검증용8767 서버는 종료했다. 현재 서비스 교체를 다시 할 필요가 없어 추가 승인 대기는 없다.
- 원V1 **36/36** 기록 유지. 이번 HD 연결 완료를 Era 전체 제품/모든 기업/미국/공동 전체 인수 완료로 확대하지 않는다. 새로운 기사 전체 수집·기사 원문 권한·새 금융 점수 모델을 뜻하지 않는다.

증거: output/hd_official_financial_20261019/의 captured_annuals.json·individual_publication.json·actual_import.json·integrated_ssd_tests.txt·integrated_validation.json·live_verification.json·hd_official_company_proof.png. 예약/배포 증거는 output/individual_scheduled_check/activation_verified.json·live_assessment.json. 이전 뉴스 비교 증거 output/power_followups_20261019/. 원본·원문·DB·백업·이 출력들은 Git 제외, public push 없음. 기존 untracked vision 파일 보존.
