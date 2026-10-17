# PROJECT_STATE — NewsCatalystOS 최신 기능·실자료·운영 구분

기준 2026-10-17T12:08:51+09:00. 기능 SHA `e6967a2da6235ce6e4cc2e3f07b8efd2f0d27ec5` 개발 로컬. 1_1~6_6 코드 36/36 과거 기록 유지, 실제 제품·운영/출시·연동 완료로 주장하지 않는다. 사용자 우선순위: 전체 허용 뉴스 수집 범위 확대, 반도체 선별, 경제 변화 자동 발견, 테마/기업 근거 연결; 필수 최소 검증만.

## 신규 실사용 기능과 실제 입력
- config/msit_rss_metadata_registry.json: 공식 과학기술정보통신부 보도자료 RSS(94), 연구개발·미래인재정책 RSS(65) 2개 승인 출처의 metadata-only 전용 registry. 공개 RSS 주소/정책만 포함. 실제 운영 승인 출처는 기존3개 그대로, 개발 실험 추가 출처2개(전체 설정상5개). 개별 게시물·첨부문서/AI 훈련 사용권을 포괄한다고 해석하지 않음.
- 신규 공식 press 응답 822,828 bytes, 50제목/반도체 키워드6. 개발 현재 제한 128KiB로 미지원하던 큰 RSS를 최대 1MiB로 받아 **제목·URL·안전한 고유ID만 저장**, content:encoded는 분석 결과/체크포인트/출력에 보존하지 않음. 정부 HTTPS/no redirect/PIT/중복/상한 유지. 기존 6초 timeout→10초(기존 최대 상한)로 조정.
- 실제 research-policy(65) 50제목/반도체1: 기존 scheduler --once로 dev private SQLite/ACK/중복 → 규칙50 → 저장보고→개발 dashboard /api/period 및 /api/news-search HTTP200. 명시 경제변화0/저장 테마0 (뉴스 전체가 중대 사건이라고 조작하지 않음), 유료 AI0, 원문 보존0. 개발 작업경로 output/msit_live_dev, 프로젝트 gitignore 범위/운영과 완전 분리.
- 실제 press(94) RSS direct parser50/반도체6 성공. dev scheduler 최초 1회는 6초 만에 DATA_UNAVAILABLE(exit4), 원장 next_allowed_at 2026-10-17T04:02:15+00:00 보존. 10초 시간제한 코드 변경 이후 예정된 간격에 대한 신규 live 수집 성공은 미확인, 더 일찍 호출하지 않음.
- 합성 동일 공식 RSS 대형50개 → scheduler 수집/triage → 1 중요한 반도체 경제변화 → 기존 ThemeStore → 승인 뉴스 검색+ 중복/소스 본문 미보존 경로 통과. 관련 변경영향 **41 PASS / 실패0**. 공개 파일 감도검사·기존 사용자 dirty3 불변. GitHub push, 운영 SSD·원본 registry/launchd/기존 운영 DB·Era 코드/DB 쓰기 없었음.

## 다음
NEXT_TASK.md: 신규 press 1회 기존 rate limit이 허용될 때 실제 dev 파이프라인 끝까지 연결, 두 출처의 완료 기록으로 뉴스 검색 범위 정상 확보; 새 승인 외부 출처 추가/공식 기능 개발은 기존 구조 우선, 관리도구 신설 금지. 배포·출시/공동연동 인수는 별도로 인정.
