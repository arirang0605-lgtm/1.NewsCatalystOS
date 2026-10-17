# NEXT_TASK — SK하이닉스 동일 원장 RSS 자동교대 실제 tick

## 직전 완료 증거
최신 기능 SHA `00184a3f8172a745a449bd326e3da5b7922cb320`: 기존 제목 경제 사건 `INVESTMENT/PLANNED`로 저장된 SK하이닉스 54조원 반도체 생산시설 투자 발표를 큰 **출처 보고 계획의 중요 검토 후보**로 실제 일간/기사 화면에 노출. 띄어 쓴 원 단위 직접 인식, 기존 대형 규모 임계값 재사용, 새 AI/실제 집행·수혜 사실 승격 없음. 실제 dev 사설 저장 뉴스20개 규칙 재분석·새 report SHA, 당일 전체 화면 기사140/검토1, 기존 투자 테마1 변경0, HTTP200. 변경 영향 **97 PASS**, 운영·dev registry/원장/ThemeStore 8개 SHA 불변.

## 다음 필수 실사용 작업 1개
1. 기존 수집 원장 SK하이닉스 next_allowed_at=2026-10-17T07:11:55.500573+00:00 (KST **16:11:55**) 이후에만 기존 dev private `output/company_live_dev`에서 `--alternate-registry`를 지정해 `run_scheduled_triage.py --once` 실제 1회 실행. 승인 primary `providers/authorized_sources.json` / alternate `providers/skhynix_press_variant_authorized_sources.json`, 기존 provider `skhynix-newsroom-korea`, 기존 SQLite state/inbox/ACK/dedup/feed_analysis/core/ThemeStore 루트 모두 재사용한다. 무효화/원장 리셋/회피하거나 기존 기사 본문을 복제하지 않는다.
2. 완료 ACK2건 기준으로 다음 실제 일반 RSS primary 선택이 작동하는지, 신규 기사 수/중복 보도 건수, 경제 변화 검출 결과, 기존 54조원 `INVESTMENT/PLANNED` 테마·기업/하이라이트 유지 여부를 확인한다. 실제 새로운 경제 변화가 없으면 N/A로 정직하게 표시. 허용 전이라면 다른 독립 공식 RSS 핵심 구현을 진행하고 무의미한 중복 호출 금지.
3. 개발 기능 테스트는 변경 핵심만. 다른 수집기/관리도구 확장으로 대체하지 않는다. EraLeader 승인 공유 스냅샷 외 수정 금지, 운영 SSD·launchd·Public GitHub push 및 키·원문·유료 AI/주문 권한 확대 금지.
4. Git 기능 SHA/테스트/현재 완료 코드36/36 및 실자료·정기운영·제품 출시는 분리 보고한다. 최종 인수조건 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md 기준 유지.

사용자 확정 약속: 허용 뉴스 수집 범위와 반도체 핵심 4단계 자동 처리 우선. 세부 검수·관리 반복확장 금지.
