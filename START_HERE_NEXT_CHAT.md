# START HERE — 전력기기 후속 개발 재개

**목적·개발 기준:** 실제 뉴스 → 뉴스 분석(경제 변화·공통 사건·초기 테마) → 관련 산업·기업 연결 → 기업별 근거·원문 조회. 여러 사건과 기업을 연결해 초기 테마와 잠재 수혜 기회를 근거와 함께 발견한다. 산업·기업은 분석 결과로 연결하고 미분류/미확보 사건도 보존한다. 전력기기는 이 공통 흐름의 첫 실자료 적용 분야다. 매 개발 시작·진행·종료 시 목적 기여를 확인하며 세부 산업 규칙/검증 보완에만 치우치지 않는다. AGENTS.md/DECISIONS.md의 PROJECT-PURPOSE-20261018을 적용한다.

기준 2026-10-18 16:35 KST. **현재 개발 대상은 전력기기: 변압기·차단기·배전설비.** 사용자 재확인 “아직도 반도체야? 전력기기 하기로 햇지않나?”를 우선한다. 오래된 반도체 전용 범위/재개 문서 때문에 다시 반도체 보완으로 돌아가지 않는다. V1.0 반도체 검증 기록은 보존하고 전력기기 전환의 추가 선행조건으로 쓰지 않는다.

START → AGENTS → PROJECT_STATE → DECISIONS → NEXT_TASK를 읽되, 작업 선택은 위 최신 사용자 지시와 docs/V1_1_POWER_EQUIPMENT_PROFILE_20261018.md의 전력기기 미완료 경로를 적용한다. 기존 선택형 POWER_EQUIPMENT 코드가 있으므로 재작성하지 않는다. 다음은 공식 실자료→공통 뉴스 분석→관련 산업·기업 연결(전력기기 우선 적용)→분리 저장→기업·원문 조회·표준 출력 연결이다.

DEV=/Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, branch=codex/real-data-path. 실제 개발·시험은 Remote Desktop Commander. SSD 원래 소스/미커밋과 사용자dirty AGENTS/DECISIONS/비전3 보존. BASE=~/Library/Application Support/NewsCatalystOS, 운영 dashboard=5a7ada1dd2a5a369f54d9308cd4a87d7bf853376. 이번 전력기기 방향 복구는 운영 설정/수집/배포 변경이 아니다.

기존 반도체 기능7a3a007·인계c203b99는 보존하되 후속 정정·취소 작업을 현재 주 작업에서 내린다. 당시 DEV170PASS/SSD28PASS는 그 반도체 변경의 증거이며 전력기기 완료 증거로 재사용하지 않는다. 원V1 36/36 기록 유지, 전력기기 실자료·운영·제품전체/공동연동 완료는 별도다. 다음 NEXT_TASK.md.
