# PROJECT_STATE — NewsCatalystOS 최신 기능·실자료·운영 구분

기준 2026-10-17T18:43:25+09:00, 로컬 기능 SHA b167bc4b76e3a35ee11b241b0bf7c74ae65f6fc5. V1 반도체 1산업. 과거 코드 구현36/36 기록과 실자료·무인운영·출시인수 별도.

## 실제 새 작동
- NIST Manufacturing RSS 공식 metadata-only https://www.nist.gov/news-events/manufacturing/rss.xml 을 기존 Electronics RSS와 같은 provider_id/원장/ACK에 교대 연결. 별도 등록사1개를 추가한 것으로 계산하지 않음. 기존 Electronics 기사40 중 제조업 RSS40 수집에서 고유18/중복22, 누적 NIST58, 저장 분석58. 시간당1회 한도 준수, 다음 허용 2026-10-17T10:36:54.826477+00:00(19:36:54 KST). 정부 지원 정책 사건5·ThemeStore3 유지, 새로운 반도체 사건0/N/A, 유료 AI/본문·이미지 저장0. 실제 source tick 정상 종료0.
- 전체 공식 승인 고유 provider8개 / 5 source-scope, 저장뉴스판본372 = core156/motir18/MSIT100/company40/NIST58. 통합 개발 HTTP 검색/일간 정상: 2026-10-17 기사199, 중요 후보6(NIST 정책5·SK 투자계획1). NIST GlobalFoundries 지원금 변경 예정 POLICY_CHANGE/PLANNED, 정확 기사/회사상태 READY, 집행·수혜 비인증. 실제 사건 날짜와 첫 수집 관측시각 혼동 금지.
- 변경영향 집중 7 PASS, 실패0, 운영/개발 원본 source/state/theme 13파일 SHA 불변. 로컬 코드 커밋 b167bc4b76e3a35ee11b241b0bf7c74ae65f6fc5. SSD 운영본, live launchd, EraLeader, 공개 GitHub push 불변; 사용자 기존 dirty AGENTS.md/DECISIONS.md/비전 파일3 SHA 불변. 사업용 라이선스 불명확한 GF IR RSS는 활성화하지 않음.

## 다음
NEXT_TASK.md: 출처 권리가 확보된 직접 반도체 제조·장비 계약/투자/양산 공식 RSS 또는 재사용 허용 정부 발표를 확보하여 실뉴스 입력→경제 행동→ThemeStore→기업 근거와 사용자 화면까지. 반복 검증/관리 도구 신설 금지. 독립 실운영·출시/연동 인수는 승인된 완료 기준으로 별도 판단.
