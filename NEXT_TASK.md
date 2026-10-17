# NEXT_TASK — 읽기전용 연동 이후의 실제 필요 작업

## 완료
사용자 “연동하자” 요청으로 News 측 운영에 EraLeader 완료 일일평가를 연결. 기능/배포 SHA **09e1bfbbf43fabd491c372153452c4962b73ed51**, 관련68PASS. SK 투자계획 기사→공식 DART00164779/종목000660→Era FY2025 연결재무·2026-10-16 종가/기존 긍정·약화·위험한계→뉴스 상세/일간 화면 실제 성공. 완료평가50개 수신·44재무/50가격 중 실제 뉴스 공식기업 연결1. 기존 Era reader의 운영 /api/themes16테마 수신 및 ID match도 read-only 확인. News 시간당 runner는 같은 Era 완료판본 ALREADY_IMPORTED 처리, 새판본이면 최초수신시각을 기록한다.

## 후속 범위 구분
1. 사용자가 실제 이용/갱신을 요청하면 이미 지난 News hourly 로그에서 era_daily_connection 최신 상태와 현재 Era 완료 snapshot 갱신만 확인한다. 같은 성공검증·재수집·무의미한 원장 초기화 반복 금지. 생산자 출력이 잠시 없으면 뉴스는 계속, 평가만 N/A.
2. **Era 자체 화면/정기수신 파이프라인이 최신 daily를 직접 소비하는 부분은 별도 미완료**다. 이번은 News 소비기와 기존 Era pure reader 검증이며, 상대 소스/DB/Git/설정을 직접 바꾼 것이 아니다. Era 개발 담당자의 현재 작업을 방해하지 말고 기존 News API/default16테마, 완료평가 SHA 계약을 재사용한다. 전체 양방향 자동화 완료로 과장하지 않는다.
3. 미국기업 평가 연결은 SEC 식별/완료평가 판본이 가용한 범위에서 후속 구현; 재무결측·이름모호·복수증권은 N/A. 추가 생산자 수집·인적검수·관리도구·새 투자점수 없음. 원래 INT 완료조건은 실증된 범위로만 구분한다.

운영 base=/Users/shmoon/Library/Application Support/NewsCatalystOS; 수신 설정 era_daily_connection.json·document_analysis/era_daily_assessments. 기존 dev output/*_live_dev는 보관본, 실제 뉴스수집은 base/research_workspaces만. News 배포코드 base/releases/09e1bfbbf43fabd491c372153452c4962b73ed51 읽기전용, 개발수정은 repo에서 후속 새snapshot. rollback/proof: output/era_integration_20261017. 코드36/36 기록≠미국연동/상대서비스인수/수익보장. 출처권리·PIT/SHA·비밀·비용/무주문 유지.
