# START HERE — NewsCatalystOS

## 사용자 확정 개발 원칙
Git status → AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md의 최신 내용만 확인. 기존 코드 CONTINUE, 기능 우선: **허용 뉴스 수집→V1 반도체 선별→중요 경제 변화→출처 명시 테마·기업/근거 화면**. 새 관리자·검증 프레임워크/부가 UI 반복 신설 금지. 출처권리·SHA/PIT·비밀·중복/유료AI 예산·실주문 금지 유지. 실제 운영 배포/출시·EraLeader 독립 프로젝트를 개발·실자료 확인과 분리한다.
개발: /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path). 운영 SSD /Volumes/T5DATA/1.NewsCatalystOS 및 EraLeader 코드·DB·Git은 쓰지 않는다. EraLeader 승인된 스냅샷만 읽기 전용. 기존 1_1~6_6 **코드 구현 기록36/36**은 출시 인수 완료가 아님. 완료 기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md 및 docs/V1_RELEASE_POLICY_2026-10-15.md.

## 최신 기능/증거 — 2026-10-17T17:38:10+09:00
**NEWS-20261017-NIST-CHIPS-SOURCE** 기능 SHA **1c3a182a133e4bb634462f7c9acc2945c83a3979**. NIST 공식 RSS 제공 안내 https://www.nist.gov/coo/nist-rss-feeds 및 저작권/공공정보 이용 https://www.nist.gov/copyrights-disclaimers 검토. 공식 Electronics RSS https://www.nist.gov/news-events/electronics/rss.xml 새 provider nist-official-electronics metadata-only 등록. 기존 scheduler --once로 사설 개발 output/nist_live_dev 원장/ACK/분석 보고서 40건 실제 수집(반도체 일반 키워드 후보7). 원문/이미지·유료AI 0. 초기 기존 경제 규칙상 사건0이었지만 추가 좁은 영문 NIST CHIPS 확정/변경 지원 협약 템플릿 v12로 **출처 보고 정책변경 후보5/테마3/출처에 명시된 기관·기업5** 저장, AI 추가/외부 재수집0. 명시 주체 Powerex, GlobalFoundries, SandboxAQ, Bosch, I-Pulse; 회사명=원문 source name only, 미국/한국 상장종목 식별·투자 수혜/현금 지급 미확인. GlobalFoundries 지원금 변경은 PLANNED로 판정, 확정 협약은 SOURCE_REPORTED(지급 완료 아님). 실제 기사 게시일은 오래될 수 있으며 모든 5건을 당일 새 발생으로 주장하지 않는다. PIT 기준은 RSS 공급원 게시시각이 아니라 **프로그램 최초 확인 시각**이다.
별도 NIST ThemeStore를 기존 core/MOTIR/MSIT/기업스토어와 읽기전용 분리, 메인 개발 대시보드 5 scope 저장 검색판본 **354건**(기존 sources에 motir +1 판본), 2026-10-17 기준 일간 **181건/중요 검토6건**, NIST 실제 기사40/경제 정책5/테마3/출처명 회사5. GlobalFoundries 정확 기사 제목 223자 및 공급원 SHA·권한·PIT 검증 후 보기 READY HTTP200, 확정 투자/수혜 false. source/theme 기존 파일13 SHA 유지. 변경 영향 **117 PASS / FAIL0**, 기능 commit 위 SHA. 운영 SSD·live launchd·공개 GitHub push 미반영; 기존 사용자 AGENTS.md/DECISIONS.md/비전 dirty 3파일 불변.

## 다음
NEXT_TASK.md: 합법적인 다른 공식 반도체 장비/제조사 IR RSS(기업 원문 자체 게시)를 늘리고, 영문 계약·생산 확대·수주라는 실제 사건을 기존 사고안전 경로로 묶어 사용자 화면까지. NIST 서류상 지원액·지원 의향/협약·지급을 다르게 표현하고 불확실한 건 N/A. 새 검증관리 도구로 대체하지 않는다.
