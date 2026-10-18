# START HERE — 산업 독립 발견 / 같은 제품의 원문 비교

기준 2026-10-18T14:48:14+09:00. 사용자 승인: **허용 뉴스 → 경제행동 우선 발견 → 원문 기업·제품·산업 연결 → 미분류 포함 관찰**. 기존 반도체V1/전력기기 심층해석·Era 연결은 보존. Chat+Remote로 이 문서→AGENTS.md→PROJECT_STATE.md→DECISIONS.md→NEXT_TASK.md 최신내용과 Git 상태를 확인하고 CONTINUE. 관리도구·반복검수·새산업 전용분석기보다 실제 입력→처리→출력 우선.

## 최신 기능/운영
기능 및 dashboard 배포 **2c3b80c5b01343ea63de7cf64aea58d74f9d57ff**. 기존 PRODUCT_LAUNCH 관측에서 **같은 원문회사명·정확제품명**을 가진 제목을 비교해 동일제목내용/같은문서판본수정/계획·보도단계차이/단순회사제품일치를 구분한다. 기존 normalization·출처보고서 SHA/PIT·제품 span·ThemeStore·선택export 재사용. 별칭/번역·유사명·버전숫자 제거로 매칭하지 않고, 미확보회사/불명확제품도 원 관찰에는 남긴다. 비교는 병합·신규시장재료 인증·후보점수 조정이 아니다.
실자료 **UVJC/NovaJet 한국어·영문 제목2개 → 비교묶음1**. 회사·제품·출시행동 일치/표기언어차이를 보여주되 같은발표·번역·재배포/독립사건 여부는 미확인. 원 source별 ID/제목SHA·관측시각·두제목·일치단어 span을 함께 표시. 동일제품의 다른날 발표도 함부로 합치지 않고 비교근거가 나타나기 전 as_of에는 표시하지 않는다. 비교ID는 요청시각이 아니라 원문/사건기준이다.
기존 **382제목·45주제·50출처관측·37미분류·회사명34** 유지, 추가비교1(제목2). 관련 **175PASS/FAIL0**. 실제 운영14:46 HTTP200/배포JS/선택export45테마 중 비교확장2 확인. 기존18source·설정·user파일 및35보고서SHA불변. source/파생DB 쓰기0·재수집/AI0·Era코드/DB/Git/순위 변경0. 중복제목은 내용추가근거 없음, 모호한 교차언어는 확인된중복으로 세지 않는다.

## 현재 경로·버전
개발 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path). BASE=~/Library/Application Support/NewsCatalystOS. **dashboard만 BASE/releases/2c3b80c5b01343ea63de7cf64aea58d74f9d57ff로 교체**, research-approved는 기존4fd8c755d3c4 공통추출v2/기존시간당예약 유지. core/MOTIR·분석 DB·키/예산/원문권리·PIT/SHA·무주문 보존. 원 source BASE/research_workspaces; dev output/*_live_dev는 보관본(재수집금지). 파생관찰 BASE/document_analysis/economic_discovery.
UI http://127.0.0.1:8766/ → 뉴스에서 발견한 경제 변화·관찰 분야 → 같은 회사·제품의 출시 보도 비교. API /api/economic-discovery의 launch_comparisons와 ?export=1의 선택 discovery_launch_comparison. 전방 기존 Era 고정판본/순위에 무분별한 자동가산 없음. 증거/rollback output/discovery_launch_comparison_20261018/targeted_tests.json·real_comparison_proof.json·activation.json.
사용자dirty AGENTS/DECISIONS/비전3·Era/운영SSD 원본 보존·Public GitHub 무push. 기존36/36은 V1기록,45주제=45산업완료가 아니다. 다음 NEXT_TASK.md.
