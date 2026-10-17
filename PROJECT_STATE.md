# PROJECT_STATE — NewsCatalystOS 최신 기능·실자료·운영 상태

2026-10-17T13:55:12+09:00 / 개발 feature Git 926031a995955635f3320ecfc1ec1805b9e9df25. V1 반도체 한 산업, 과거 코드 구현 36/36 기록; 독립 실운영/출시·실연동 인증 별도. 사용자 우선순위 정상 코드 보존·허용 수집 범위와 경제 변화→테마/기업 자동 처리.

## 이번에 작동하는 실제 기능
- 공식 삼성전자 뉴스룸 https://news.samsung.com/kr/feed RSS20, SK하이닉스 https://news.skhynix.co.kr/feed/ RSS10의 신규 기사 메타데이터를 별도 개발 state output/company_live_dev에서 수집(기존 scheduler→ACK·중복 제거→규칙 분석→저장, code0). 신규 키워드 반도체 후보10(Samsung0, SK10), 명시 규칙 경제 행동0/신규 테마0/수혜 미확정; 유료 AI0·원문/이미지 저장0.
- 공식 이용안내 refs: https://news.samsung.com/kr/삼성전자-뉴스룸-콘텐츠-이용에-대한-안내 및 https://news.skhynix.co.kr/guideline/ . 자체 제작 콘텐츠·제3자 콘텐츠 제약을 감안, metadata-only approved registry config/semiconductor_company_rss_metadata_registry.json, 1회/시간 제한. 다른 승인 출처 중복 수집/수정 없음.
- 기존 core156 + MOTIR17 + MSIT100 + 기업뉴스30 = 실제 저장 판본303개, 읽기 전용 4개의 source scope에서 뉴스 검색/일간/기사 저장 경제행동 상세 HTTP200. 하이닉스 제목 검색6, 2026-10-17 일간 130기사. 검색 coverage complete, 회사 뉴스 정확 title analysis READY지만 해당 제목 경제 행동0 → 출처 회사의 실제 계약/수혜로 주장하지 않음.
- 기존 open_research_dashboard.py에 반복 가능 --additional-source-root company=/절대/개발폴더 추가, --msit-source-root 호환. 각 source ThemeStore 및 회사 참여/후속 원문은 독립 저장소에서만 열람, 공통 주제명만으로 타 source 내용을 혼합하지 않음. 중요 반도체 계약 등 합성 정상 예제로 API/브라우저/동일 사건/철회 전 PIT 검증.
- 변경 영향 42 PASS, 실패0; 개발·운영 원본/승인 registry·수집 state 9파일 SHA 읽기중 불변. 격리 HTTP 종료. 운영 SSD/launchd/공개 GitHub 미배포, 사용자 AGENTS/DECISIONS/비전 dirty3 SHA 보존.

## 다음
NEXT_TASK.md — 중요한 반도체 경제 행동 제목을 실제 게시하는 추가 공식 기업 RSS/IR 뉴스원을 권리·형식·호출 한도에 맞춰 확대하고 4단계 실자료 자동 처리 완성. 신규 관리·검수 도구 반복 확장 금지.
