# PROJECT_STATE — 반도체 운영 + EraLeader 읽기전용 평가 연결

기준 2026-10-17T22:23:35+09:00. 연결 기능·운영 SHA **09e1bfbbf43fabd491c372153452c4962b73ed51**. 기본 코드작업36/36 기록 유지. 이전 전체회귀7140PASS는 이전 배포의 근거이며 이번 변경은 관련 **68PASS**와 실제 운영 연결로 확인.

## 이번에 새로 작동
- 완료된 EraLeader 일일 평가 snapshot을 News 소유 사설 수신함에 원본 SHA·내용SHA·동일 browser/주식ID·기간/시점 확인 후 가져온다. 50후보/44연간재무/50보관 종가를 원래 결측/한계 그대로 보존. 현재 반도체 뉴스에서 SK하이닉스 한 기업을 공식 DART00164779·종목000660으로 정확 연결. 이름유사 추측/수혜확정/새 평가 계산 없음.
- 실운영 8766 기사 검색 54조 → 동일 기사 경제사건/기업 → FY2025 매출·영업익/이익률·현금흐름 + 2026-10-16 종가 + Era의 기존 강화/약화/한계 표시. 기사 자체 회사 ID는 이름만 표기한 원본 그대로 유지하고 별도 평가 근거를 구분. 계획→집행으로 승격0. 일간 테마에서도 같은 평가 열람.
- 기존 /api/themes 기본 출력16테마(base9+company1+NIST6) 제공, 기존 baseID 불변·독립 store는 source-qualified ID. Era 기존 수신 함수의 실제 loopback GET/원본SHA/시점 검사 및 정확DART match 성공1. 새로운 영구 Era 측 입력/DB·순위·보고서/스케줄은 건드리지 않음. 최신 daily의 평가를 반환하는 News 조회 방향은 운영 완료이며, Era 자체 WATCH 어댑터의 latest daily 영구 소비는 독립 후속 범위.
- News 기존 hourly research runner에 완료평가 갱신 옵션 연결(뉴스 데이터/호출권한 보존). 등록직후 실제 자동실행exit0·5/5정상·ALREADY_IMPORTED50. 동일 보고서면 최초수신시각 유지, 새 판본만 새 receipt. producer 실패는 평가만 미확인 처리. 순수 공개설정/코드만 Git, private config/전체평가/원장/백업은 ignored 비공개.

## 테스트·실자료·보존
핵심 정상/공식기업 일치/중복 import/과거 조회/내용변조/회사혼선/결측/보관가격/화면 JS **68 PASS·0 FAIL**. 실제 운영선택 기업1·기사/테마/평가 API HTTP200·JS배포 SHA 확인, 수신일 이전 금융/ID 조회 차단. 저장 전체 기사372/일간199/중요후보9 유지. 재무/가격 평가 자료44/50은 커버리지이지 뉴스기업50개 자동연동 성공이 아님.
Era 원본 completed report/index 및 News 사용자 dirty3 SHA불변. 이 턴 Era 코드/DB/Git·스케줄 쓰기0(다른 담당자의 정당한 Era HEAD 업데이트는 유지). News dashboard/research-approved만 새 snapshot으로 교체, 원 core/MOTIR 및 source 원장·이전release 보존. 신규 공식API/유료AI/주문0·Public GitHub push0. 미국 회사평가 및 Era 자체 정기 수신 전체인수는 미완료로 구분.
