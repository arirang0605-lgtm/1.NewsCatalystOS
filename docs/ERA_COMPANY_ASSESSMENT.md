# 기업 후보에 EraLeader 재무 근거 연결

완료된 `eraleader.kr_early_watch_queue.v1`의 `WATCH_FUNDAMENTAL_EVIDENCE_AND_RISK_V1` 평가를 선택적으로 읽는다. 생산자 코드를 import하거나 실행하지 않고, 운영 DB와 공식 수집기에도 접근하지 않는다. WATCH는 생산자가 JSON/HTML을 만든 뒤 판본 폴더를 원자적으로 게시하는 기존 형식을 그대로 사용한다.

## 사용

```sh
python3 scripts/import_era_assessment.py \
  --era-root /절대경로/EraLeader프로젝트 \
  --watch-manifest /절대경로/EraLeader프로젝트/output/early_leader_watch_queue/KR_YYYYMMDD_판본/watch_queue.json \
  --expected-sha256 실제로확인한파일SHA
python3 scripts/search_themes.py --with-financials --query 기업코드
```

가져온 결과는 NewsCatalystOS의 기존 비공개 document_analysis/era_assessments 아래에 저장한다. `--output-root`, `--assessment-root`로 개발용 캐시를 지정할 수 있다. 생산자 내부를 출력 폴더로 지정하면 거부한다. 같은 원본 SHA는 재사용하며 최초 확보시각을 바꾸지 않는다. 캐시는 생산자 발행물의 사본이므로 Git/공개 배포 대상이 아니다.

- 기존 대시보드 기업 근거에 긍정·약화 관측, 위험 신호, 확보 항목 수, 결측, 한계, 재무기간/통화/공시/자료 가용시각을 표시한다.
- `GET /api/company-research` 또는 CLI `--with-financials`는 `newscatalyst.company_research.v1` 결과를 제공한다. `--export-root`로 비공개 고정 JSON을 저장할 수 있다.
- 기존 `/api/themes` 및 v3 `CompanyCandidates` 계약은 그대로다. 새 소비 결과의 기업 schema는 v2이며 재무 객체에 생산자·원본 SHA·수신 영수증 SHA·게시/확보시각을 명시한다. 기존 EraLeader의 NewsCatalystOS v3 소비 작업을 깨지 않는다.

## 연결과 한계

가장 최근의 가용 WATCH 한 판본을 선택한다. 과거 판본의 기업을 가져와 최신 판본에서 누락된 기업을 몰래 채우지 않는다. `DART_CORP`/`KRX_STOCK`의 정확한 코드만 연결하며 회사 이름으로 추측하지 않는다. 같은 법인에 복수 종목이 있어 연결이 모호하면 해당 평가를 미확인으로 둔다. 미국 SEC 기업에는 한국 평가를 적용하지 않는다.

발행 SHA/내부 content SHA/평가 SHA, 기업·시장일·연간 기간·통화·원본 시점과 평가 입력의 연결을 확인한다. 생산자 판단을 재계산하는 별도 평가기를 만들지는 않는다. 가져온 평가는 EraLeader의 관측 설명이며 독립적인 재무 인증·수혜 확정이 아니다.

현재 가격 매력·사업 해자·재무 안전성 종합 판단은 생산자에서 N/A이므로 그대로 유지한다. 위험 신호가 없더라도 안전 확정으로 표시하지 않는다. 재무가 부족하면 INSUFFICIENT_DATA, 코드 미확인은 IDENTITY_UNRESOLVED, 미포함은 COMPANY_NOT_IN_SNAPSHOT 등으로 이유를 구분한다. 캐시 일부가 손상되어도 뉴스 기업 후보를 삭제하지 않으며 source 상태에 읽기 실패를 표시한다.

과거 조회는 원본 게시뿐 아니라 **NewsCatalystOS가 실제 가져온 시각**도 충족해야 한다. 새 평가를 옛 테마 판본에 소급 저장하지 않는다. 테마 판본/점수/과거 이력은 읽기 전용이다.

실자료 수신과 실제 뉴스 기업의 재무 연결 성공은 별개다. 최신 PROJECT_STATE에 두 수치를 구분한다. 이후 생산자의 새 중립 export가 완료되면 그 실제 계약과 필요성을 확인해 지원하며 진행 중인 산출물을 임의 소비하지 않는다.
