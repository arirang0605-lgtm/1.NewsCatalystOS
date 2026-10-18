# START HERE — V1 운영 보존 / V1.1 선택형 전력기기 개발

기준 2026-10-18T10:59:16+09:00. Chat + Remote Desktop Commander로 계속한다. 기존 재개 순서: 이 문서 → AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md의 최신 내용과 Git 상태. 기본 V1은 반도체 한 산업·기존36/36 구현/독립 운영 유지, 후속 V1.1과 구별한다. 완료한 V1이나 Era 연결을 미완료로 되돌리지 않는다.

## 현재 단계
- News 재료→Era 기존 후보 강화/약화/유지 연결은 Era의 docs/313_NEWS_MATERIAL_EXISTING_PRIORITY_20261018.md에 완료. 해당 실제 기록은 SK 유지 판정이며 억지 순위 상승 아님. 상대 프로젝트 코드·DB·Git·설정 변경 금지.
- 이번 대화에서 제안한 **전력기기(변압기·차단기·배전설비)**를 V1.1의 선택형 개발 옵션으로 시작했다. 신규 기능 SHA **c2393d4379d996142425c1ee90593eb1b55a33bc**. 기본 SEMICONDUCTOR 규칙·운영 예약을 바꾸지 않는다. 별도 유료AI·다른 산업/발전·원전·배터리까지 확대하지 않는다.
- 기존 run_feed_analysis.py --industry POWER_EQUIPMENT에 **분리된 analysis-root/theme-root**를 지정해 기존 승인된 RSS 저장자료를 읽고 계약·투자결정/집행·증설·생산/납품 개시를 처리. 기존 ThemeStore·원문 근거 조회·search_themes.py --materials --material-industry POWER_EQUIPMENT 표준 내보내기 재사용. 한 제목의 실제 기업/설비/행동만 인정, 수혜기업·주가상승/매출 확정 없음.
- 관련 **157 PASS/0 FAIL**, 합성 양성7개 입력→저장→테마→기업 원문→전달 성공. 실제 기존 승인216기사(6제공자) 재분석은 power제목/사건0이었다. 이것은 실제 전력기기 사건 양성 검증이 아니며, 새 산업 모니터링·운영완료로 주장하지 않음. 원본/설정 등18파일 replay 전후SHA동일, 새수집/유료AI0.

## 위치·보호
개발 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path). 운영코드 /Users/shmoon/Library/Application Support/NewsCatalystOS/releases/168ea012ddcade5555964f1f849edae4200fb261 그대로, 운영 http://127.0.0.1:8766/ . 이번 선택형 기능은 **개발본에만**, 배포·예약 활성화 없음. 운영 source /Users/shmoon/Library/Application Support/NewsCatalystOS/research_workspaces, 과거 dev output/*_live_dev는 보관본(수집 실행금지). 사용자 dirty AGENTS/DECISIONS/비전3 보존.
V1.1 근거 output/v11_power_equipment_20261018/saved_source_replay.json·feature_commit.json, 범위/사용법 docs/V1_1_POWER_EQUIPMENT_PROFILE_20261018.md. 운영 SSD/Era 원본·비밀/권리·PIT/SHA·예산/무주문 유지, Public GitHub push 없음.
다음: 실제 전력기기 경제 행동이 포함된 이용허용 공식 뉴스 입력을 기존 경로에 연결한다. 추가 관리·반복검수로 대체하지 않는다.
