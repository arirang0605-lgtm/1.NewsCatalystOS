# PROJECT_STATE — NewsCatalystOS 최신 기능·실자료·운영 구분

기준 2026-10-17T17:38:10+09:00. 로컬 기능 SHA **1c3a182a133e4bb634462f7c9acc2945c83a3979**. 원래 코드36/36 작업 구현 기록과 운영·출시/통합 인수는 별개. V1 심층 산업 반도체 한 분야.

## 핵심 입력→처리→출력 최신 작동
- NIST 공식 Electronics RSS의 허용된 title/link/guid 40건을 별도 dev private 승인 registry·SQLite 원장/ACK/분석 저장. 공급원 nist-official-electronics, 공식 링크 https://www.nist.gov/news-events/electronics/rss.xml, 이용조건 https://www.nist.gov/copyrights-disclaimers. 본문/이미지·유료AI·기존운영원본 직접 저장 없음. 원래 반도체 keyword 후보7, keyword-only가 5가지 정확 정책 지원 이벤트를 누락하던 것을 좁은 U.S. Department of Commerce CHIPS 확정/협약 변경 + 해당 테마·실제 명시 기업만 추출하도록 개선. legacy 최초 RSS 접수 키워드 규칙은 그대로 보존해 저장 SHA 검증을 깨지 않음.
- RSS 제목 리플레이 후 source reported 정책 행동5, NIST 독립 ThemeStore 버전3, 직접 출처 기업 이름 Powerex/GlobalFoundries/SandboxAQ/Bosch/I-Pulse 5. 지원 변경 예정 = PLANNED, 확정·서명 협약 보도 = SOURCE_REPORTED, 지급완료/매출·주가 수혜는 전부 비인증. 소비자 company_evidence에 같은 NIST title/행동/주체/sha를 다시 맞춰 원문 저장된 짧은 구간만 조회하도록 기존 경로 수정.
- 개발 메인 화면 5 RSS workspace: 8개 provider 등록 범위(core2/motir1/msit2/company2/nist1), 저장판본**354**(core156/motir18/msit100/company40/nist40), 2026-10-17 KST 일간 **181건/중요 검토6건**(NIST 정책5, 이전 SK 투자계획1), NIST source 단독 40기사/중요 정책5/테마3/회사명5. GlobalFoundries 정확 기사·회사 근거 원제목223자 READY HTTP200; 타사·미래·SHA 불일치 접근은 거부, verified_real_benefit=False. 초기 RSS 확인일 Oct17은 게시원본의 실제 사건 발생일 아님. 기존 개발/운영 registry/state/theme 13개 SHA 변경 없음.
- 국소 변경 영향 테스트 **117 PASS·0 FAIL**, 원본 보존 및 소스 공개 전 제한 검사, 로컬 Git feature SHA `1c3a182a133e4bb634462f7c9acc2945c83a3979`. 기존 사용자 dirty3 보존, 운영 SSD/launchd·EraLeader·Public GitHub push 미실행. 제조사 추가 RSS와 실제 무인 운영/최종 인수는 별도 과제.

## 다음
NEXT_TASK.md — 제조사/장비기업 공식 RSS 및 출처 허용 확인 후 기존 수집기에서 새 경제 사건(계약·설비·양산)의 메타데이터 분석을 실자료로 연결한다. 과거 정부 기사와 당일 새 발생을 혼동하지 않고 권리/PIT/AI 비용 준수. 새 점검·관리 도구 반복 확대 금지.
