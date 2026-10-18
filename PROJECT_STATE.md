# PROJECT_STATE — 다기업 실제 뉴스에서 초기 테마·기업 근거까지 작동

**목적·개발 기준:** 실제 뉴스 → 뉴스 분석(경제 변화·공통 사건·초기 테마) → 관련 산업·기업 연결 → 기업별 근거·원문 조회. 여러 사건과 기업을 연결해 초기 테마와 잠재 수혜 기회를 근거와 함께 발견한다. 산업·기업은 분석 결과로 연결하고 미분류/미확보 사건도 보존한다. 전력기기는 이 공통 흐름의 첫 실자료 적용 분야다. 매 개발 시작·진행·종료 시 목적 기여를 확인하며 세부 산업 규칙/검증 보완에만 치우치지 않는다. AGENTS.md/DECISIONS.md의 PROJECT-PURPOSE-20261018을 적용한다.

기준 2026-10-18 17:29 KST. 기능/운영 **ac5b08d1397c6bb420155e46595ebae77b868bda**. 실제 뉴스 → 경제 행동 → 공통 사업 대상 초기 테마 → 관련 산업·기업 → 정확한 기사 근거·공식 원문 경로를 이어 개발했다. HD현대일렉트릭과 LS ELECTRIC의 변압기 수주 발표2건을 '변압기 관련 경제 변화 / 복수 기업의 움직임'으로 연결했다. 공통 수요 원인·독립 계약·납품·매출·수혜·시장 신규성은 미확인이다.

LS 제목 'LS ELECTRIC, 5,610억 원 규모 HVDC 변환용 변압기 사업 수주', 공식 게시일2024-12-02. 기존 HD 제목 게시일2025-09-22. 둘 다 역사적 실제 뉴스이며 최초 가용일은 이번 확보/입력2026-10-18로 유지했다. 현재 시장의 새 테마라고 소급 주장하지 않는다.

LS 공식 자동 목록은 HTTP999 또는 빈 API 응답으로 확인 불가했다. 우회/재시도 수집기 확장 대신 공개 공식 페이지에서 확인한 제목·주소를 **MANUAL_METADATA(수동 입력)** 로 명시해 연결했다. 자동 수집 성공/정기 수집은 미선언. 본문·요약·이미지 저장0, 유료AI0. 원문 https://www.lsholdings.com/ko/media/news/73503435576655704a5651473669346761776f5678586d50576e646f34736a76 .

DEV=/Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, branch=codex/real-data-path. BASE=~/Library/Application Support/NewsCatalystOS. 공통 분석 BASE/document_analysis/economic_discovery. HD source BASE/research_workspaces/power_live_dev, LS 수동 source BASE/research_workspaces/ls_power_manual_dev (scope ls_power). 새 명령 scripts/run_manual_company_news_once.py 는 소유자 전용 제목 JSON을 기존 원장/체크포인트/ACK→공통 발견으로 연결하며 HTTP를 호출하지 않는다. CLI 설명을 참고하며 실제 수동 자료를 자동 feed로 위장하지 않는다.

운영 http://127.0.0.1:8766/ → 경제 변화 공통 관찰 → 주목할 테마 후보·관련 산업 → 변압기 관련 경제 변화 → 기회·반증·원문 근거 → 이 테마의 기업·분석 근거 보기 → 정확한 기업 근거 문장/원문. 저장뉴스 '변압기' 검색도 두 회사 자료를 반환하며 LS에는 수동 입력 표시가 있다.

영향140개 고유시험 단계별PASS(82 + 별도42 + 화면/테마16, 최종 화면군28은 수동시험12와 중첩). SSD 고정판34PASS. 실자료2개사의 정확한 HTTP 기업/제목 근거 READY, 재처리 새판본0, 과거 기본export bytes·고정 /api/themes bytes 동일. 실제 화면에서 공통 테마→LS 기업·산업→근거 문장 조회 확인. 개발/합성시험과 실자료 확인을 분리하며 전체제품 인수·공동연동 완료로 선언하지 않는다.

현재 공통 발견47주제52사건, 명시 회사명36, 제목판본398. 운영 dashboard만 고정 release와 ls_power 읽기 source를 추가했다. 기존 수집/예약 설정3 SHA 동일. 개발·테스트·백업 분리, SSD 원래 코드/Git/미커밋·사용자dirty3 SHA 보존, Era 코드/DB/Git 변경0, Public push0. 기존 V1 36/36 기록은 유지하며 전체제품/전력기기 완료율로 환산하지 않는다. 증거 DEV/SSD output/power_multi_company_20261018/, SSD 최신 시험판 code_final/.
