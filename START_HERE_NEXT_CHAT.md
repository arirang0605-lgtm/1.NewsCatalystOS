# START HERE — NewsCatalystOS

## 현재 재개 원칙
AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 현재 본문과 Git 상태만 확인한다. **실제 기능 구현 최우선**. 기존 정상 코드 CONTINUE·중복 검증/관리 도구 신설 금지. 핵심 ①승인 뉴스 수집 → ②반도체 선별 → ③중요 경제변화 감지 → ④테마/관련 기업·근거 자동 저장/조회. V1은 반도체 한 산업만 심층 검증. 출처권리·PIT·SHA/비밀·월 5만원 예산/중복 호출·실주문 금지 보존.
개발 브랜치 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path). 원본 운영 SSD /Volumes/T5DATA/1.NewsCatalystOS/와 EraLeader 코드·DB·Git은 불변; EraLeader 검증 스냅샷만 읽기전용 공유. 전체 1_1~6_6 36/36은 기존 코드 구현 기록이지 독립 운영/출시/공동 인수 완료가 아니다. 제품 기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md 및 docs/V1_RELEASE_POLICY_2026-10-15.md.

## 최신 작동 기능 — 2026-10-17T12:08:51+09:00
NEWS-20261017-APPROVED-MSTIT-RSS-EXPANSION / 개발 코드 SHA `e6967a2da6235ce6e4cc2e3f07b8efd2f0d27ec5`.
기존 3개 운영 RSS 외에 과기정통부 **보도자료 94 / 연구개발·미래인재정책 65** 공식 RSS 두 채널의 메타데이터 전용 운영 권한 config/msit_rss_metadata_registry.json 추가. 공식 기관 RSS 이용안내 (https://www.msit.go.kr/contents/cont.do?mId=173&mPid=147&sCode=user), 저작권 정책(https://www.msit.go.kr/contents/cont.do?mId=161&mPid=147&sCode=user) 확인. 전체 본문 권리를 부여한 것이 아니며 HTML·첨부 본문은 저장하지 않음.
실 RSS press 822,828B/50제목·반도체 키워드6, R&D 정책 21,934B/50제목·반도체 키워드1. 기존 RSS 128KiB 제한을 엄격한 1MiB로 확장, 이미 허용된 타임아웃 상한 10초를 기본으로 사용, HTTP 1회/시간·no redirect·0 자동 AI 유지. 실제 새 정책 RSS50 → dev 전용 private state/ACK → 규칙 분석50 → dev report/뉴스검색 HTTP200 완주, 경제 행동0·테마0 정확히 기록. **보도자료** 전체 1회 스케줄 경로는 기존 6초 제한으로 실패(exit4); 10초 패치 후 아직 자연 재시도 안 함, 로컬 API 직접 RSS 파싱50 성공. 보도자료 네트워크 시각 2026-10-17T03:02:15+00:00, 로컬 원장 next_allowed_at 04:02:15+00:00(13:02:15 KST). rate 제한 무시/원장 reset 금지.
기존 수집기→triage→경제 행동→테마→검색 경로를 대용량 공식 형식의 합성 50건에서 검증, 합성 새 반도체 계약은 테마 양성·중복 추가수집 0. 집중 41 PASS/실패0. dev 전용 상태 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project/output/msit_live_dev (gitignore), private owner-only 권한; 운영의 기존 source registry/agent/SSD/DB/Git 불변. 새 AI·기사 본문 수집0. GitHub push 미실행. 사용자 기존 dirty AGENTS.md, DECISIONS.md, 비전 파일 보존.

## 다음
NEXT_TASK.md의 허용 시각 후 MSIT press 1회 정상 live 경로만 진행하며 실패 시 로그와 실제 장애만 수정, 다른 기능 개발 병행. 2개 추가 dev source의 실제 RSS/반도체 후보/경제변화/테마·기사 검색 연결 결과를 완료 증거로 남긴다. 운영 배포는 별도.
