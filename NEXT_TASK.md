# NEXT_TASK — 과기정통부 신규 보도자료 RSS의 완전 수집→반도체→경제 변화→출력 경로 (NC-01/02/03/06)

## 최신 완료
NEWS-20261017-APPROVED-MSTIT-RSS-EXPANSION / 기능 SHA `e6967a2da6235ce6e4cc2e3f07b8efd2f0d27ec5`.
과기정통부 보도자료(94)·연구개발정책(65) 2개 공식 RSS metadata-only 개발 registry 추가, 기존 코드 RSS 상한128KiB→1MiB, fetch timeout6→10초, 추가 도구/중복 수집기 없음. 실제 정책 RSS50 기사(반도체 후보1) → private dev 수집/ACK/기본 분석 저장/검색 화면 HTTP200 성공. 실제 press RSS50 기사(반도체 후보6)는 파서 성공, scheduler 최초 6초 네트워크 실패로 원장에 시간제한; 패치 후 허용된 실제 다음 tick 미확인. 합성 대형 official RSS 50기사→규칙 반도체 사건/ThemeStore/검색·중복 안전 정상. 집중 **41 PASS**, 실패0, 유료AI0, 본문저장0. dev 상태 output/msit_live_dev gitignored, 운영 원본·GitHub 미변경.

## 다음 실사용 작업
1. 기존 원장이 허용하는 **2026-10-17 13:02:15 KST 이후** dev 전용 private registry/state에서 `msit-official-press` 1회 기존 `run_scheduled_triage.py --once`로 실행. **시간 전 강제 실행·ledger 초기화·별도 우회 호출 금지**. 출처 장애가 여전히 발생하면 실제 분기를 확인하고 다른 승인 출처 처리를 계속. 최초 실패를 새 정상 실행이라고 소급하지 않는다.
2. 성공 시 기존 아카이브/ACK→50건 선별→최신 저장 경제변화/테마/기업(없으면 명시 N/A)→검색·일간 대시보드 HTTP를 연결 확인. Press 50 중 실제 반도체 키워드6은 **후보**일 뿐이고 자동 수혜자/경제 행동 확정이 아니다. 다른 채널의 오래된 공표시각을 신규 경제 사건으로 과장하지 않는다.
3. 필요한 실제 장애만 국소 수정하고 변경 영향 최소 테스트. 신규 관리/검증 프레임워크·상시 외부 재수집/유료AI·본문 복제 금지. 승인된 전체 뉴스 수집 범위 확장 방향 유지.
4. dev 전용 실행 상태와 운영 설치 분리. 운영 SSD/launchd/공유 EraLeader/GitHub Public·비밀 등은 사용자 승인 범위 내에서만 변경. 기능·실자료·운영 출시는 사용자 기존 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md로 분리 보고.

기존 36/36 코드 구현 기록은 유지하되 실제 제품 출시 완료로 환산하지 않는다.
