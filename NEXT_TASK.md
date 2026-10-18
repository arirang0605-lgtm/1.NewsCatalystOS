# NEXT_TASK — 기업 간 동일 수요 원인의 실제 근거 확장

**목적·개발 기준:** 실제 뉴스 → 뉴스 분석(경제 변화·공통 사건·초기 테마) → 관련 산업·기업 연결 → 기업별 근거·원문 조회. 여러 사건과 기업을 연결해 초기 테마와 잠재 수혜 기회를 근거와 함께 발견한다. 산업·기업은 분석 결과로 연결하고 미분류/미확보 사건도 보존한다. 전력기기는 이 공통 흐름의 첫 실자료 적용 분야다. 매 개발 시작·진행·종료 시 목적 기여를 확인하며 세부 산업 규칙/검증 보완에만 치우치지 않는다. AGENTS.md/DECISIONS.md의 PROJECT-PURPOSE-20261018을 적용한다.

기준 2026-10-18 17:51 KST. 기능/운영 **73dcd85a3d4e3a938f69c4bd1fe393cc3adaff12**. 효성중공업 실제 공식 제목을 기존 공통 분석·정확한 기업/원문 조회에 연결했다. 화면과 common_causes=1 출력에서 HD현대일렉트릭·LS ELECTRIC·효성중공업의 변압기 수주2건+증설1건이 '변압기 관련 경제 변화 / 우선 조사 후보'로 함께 나타난다.

효성 원문 https://blog.hyosung.com/6137 , 제목 '효성중공업, 글로벌 전력 인프라 수요 폭증에 초고압변압기 공장 증설', 게시일2024-06-12. 제목/주소를 MANUAL_METADATA로 명시해 입력했다. 자동수집·본문 사용권 확보로 주장하지 않는다. 기존 LS2024-12-02/HD2025-09-22와 모두 역사적 실제 뉴스이며 이번 확보2026-10-18 이후만 가용하다. 오늘 발생한 뉴스나 시장 신규 테마라고 소급하지 않는다.

실자료 수요 근거는 **효성 원문에만 '글로벌 전력 인프라 수요 폭증' 명시**. HD·LS의 동일 원인은 미확인이다. PARTIAL_SOURCE_COVERAGE이며 기업 간 동일 수요원인 일치/공통 시장충격·납품·매출·수혜·독립 사건은 미검증. 다른 기업에 효성의 원인을 전이하지 않는다. 증설의 물리적 완료도 제목만으로 단정하지 않아 PLANNED/완료 미확인으로 보존한다.

다음 핵심 경로: HD/LS 또는 다른 전력기기 기업에서 같은 수요처·시장 범위가 명시된 공식 제목/사용권 있는 본문 근거를 확보해 동일 원인 주장을 비교한다. 지금은 공통 제품+수주/증설 행동 연결과 효성 단독 수요 주장이며, 추가 근거가 없으면 같은 원인으로 승격하지 않는다. 서로 다른 원인이나 반증이 나오면 개별 관찰과 함께 보여준다.

새 최소 기업 수·승인·대기 게이트는 추가하지 않는다. 같은 차단 사유의 재점검이나 산업별 규칙 확장을 기능 개발 대신 반복하지 않는다. 현재의 정확한 입력→공통 분석→산업/기업→원문 조회를 재사용하고 수요 근거 부족은 그 주장에만 적용한다.

운영 http://127.0.0.1:8766/ → 뉴스에서 발견한 경제 변화 → 변압기 관련 경제 변화 → 수요 근거와 미확인 기업 → 기회·반증·원문 근거 → 이 테마의 기업·분석 근거 보기 → 기업 근거 문장·공식 원문. 저장뉴스 검색도 같은 경로다.

DEV=/Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, branch=codex/real-data-path. BASE=~/Library/Application Support/NewsCatalystOS, release=BASE/releases/73dcd85a3d4e3a938f69c4bd1fe393cc3adaff12. 분석=BASE/document_analysis/economic_discovery. 추가 source=BASE/research_workspaces/hyosung_manual_dev (scope hyosung); 기존 power_live_dev/ls_power_manual_dev 유지. 수동 입력 명령 scripts/run_manual_company_news_once.py 재사용. 실제 입력 자료는 소유자 전용이며 Git 제외.

검증: DEV258개 고유시험 단계별PASS(115 + 후속163, 새 시험20 중첩). SSD 고정판42PASS. 합성 기능시험과 별도로 실제3개사 정확한 HTTP 기업·제목 근거 READY, 선택 공통테마 export 확인. 실제 화면 공통테마→효성 기업/산업→정확한 근거 문장 확인. 이전 운영 release와 새 코드의 입력 전 기본export bytes 동일, 입력 전 시점export/고정 /api/themes bytes 보존, 재처리 추가판본0, 기존 수집/예약 설정3 SHA 동일.

현재 공통 발견48주제53사건·명시 회사명37·제목판본399. 새 자동 수집/예약 설치0, 본문·요약·이미지 저장0, 유료AI0. dashboard만 고정 release와 hyosung 읽기 source를 추가했다. 재시작 실패는 기존 설정 복구 후 단계별 재시작으로 해소, 운영 HTTP/화면 정상. 사용자dirty3 SHA·SSD 원래 소스/Git/미커밋·Era 읽기전용 보존, Era 코드/DB/Git 변경0, Public push0.

기존 V1 36/36 기록은 유지한다. 전력기기/전체제품·공동연동·정기수집·공통 수요 원인 검증 완료로 환산하지 않는다. 증거 DEV/SSD output/hyosung_demand_20261018/, SSD 최신 고정 시험판 code_final/.
