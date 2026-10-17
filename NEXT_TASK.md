# NEXT_TASK — 승인된 SK하이닉스 RSS 2종의 동일 원장 자동 교대 실자료 1회

## 완료 증거
기능 SHA **7bf2c2dd9d427bcce39918c2764ef6213f670228**: 회사용 기존 `run_scheduled_triage.py`에 `--alternate-registry` 도입. SK하이닉스 `skhynix-newsroom-korea` 회사 ID/원장 유지, 공식 일반 RSS vs 보도자료 RSS를 기존 확인 완료한 source ACK 수로 자동 번갈아 선택. 소비자는 기존 triage/규칙 분석/ThemeStore/기업·일간 UI 전부 그대로 재사용. 합성 2회 출처 교대 + 같은 GUID/원장 한도, 권리/도메인 변조 거부, 실제 소스 ACK 2건 다음 primary 선택·네트워크 없는 dry-run 정상. 변경 영향 **44 PASS**.
실뉴스 2026-10-17 오전/오후 SK 일반10·PRESS10 제목 모두 저장. PRESS에서 54조원 메모리 생산 시설 투자 제목이 `INVESTMENT/PLANNED`로 사건1·테마1·기업 SK하이닉스1·원문 정확 구간까지 HTTP200. 전체 승인 저장 판본 313. 집행/매출·수혜 미인증, 유료AI/본문 저장0, 운영 SSD 미배포/공개 GitHub 미푸시.

## 다음 실사용 경로
1. 시간당 1회 승인 원장의 `next_allowed_at=2026-10-17T07:11:55.500573+00:00` (KST 16:11:55) **이후에만** dev private 회사 원장으로 `python3 -B scripts/run_scheduled_triage.py --once --registry output/company_live_dev/providers/authorized_sources.json --alternate-registry output/company_live_dev/providers/skhynix_press_variant_authorized_sources.json --provider-id skhynix-newsroom-korea --state output/company_live_dev/state/incremental_feeds.sqlite3 --inbox-root output/company_live_dev/inbox/feed_triage --dedup-state output/company_live_dev/state/triage_exact_index.sqlite3 --output-root output/company_live_dev/triage --analysis-root output/company_live_dev/feed_analysis/core --analysis-theme-root output/company_live_dev/document_analysis/theme_history` 실행. 위 모든 파일 경로는 작업트리의 절대경로로 전달. **실제 일반 RSS 자동 선택/소스 신규·중복수·지난 투자 사건과 테마 보존**을 사용자 결과로 보고. 제한 전 재시도·기존 개발 호출 원장 삭제 금지.
2. 다음 실제 뉴스에 계약/생산능력 확대/경제 변화가 있으면 원래 규칙→테마→기업 저장/기존 대시보드 경로로 보여준다. 없으면 0/N/A 유지. 필요하지 않은 검증·관리 도구 반복 구축 금지.
3. 외부 출처 승인·유료 본문/이미지·비밀, EraLeader 운영 원본, SSD 정기 운영/공개 push는 승인된 범위에서만. 완료 판정 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md에 따른 기능·실자료·운영·연동 분리.

사용자 확정 약속: 허용 뉴스 수집 범위 확대와 핵심 4단계 실사용 구현 우선. 기존 36/36은 과거 코드 구현 기록이지 전체 출시 완료 아님.
