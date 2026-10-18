# PROJECT_STATE — 명시 수요 원인→반도체 사업 행동

기준 2026-10-18 16:12 KST. 기능/dashboard **5a7ada1dd2a5a369f54d9308cd4a87d7bf853376**. 기존 V1 기능 구현36/36 기록과 이후 정상 코드·산업분류 없는 관찰·기업 문맥·제품출시 비교·사업대상 종합은 보존한다. 이번에 완료 수를 올리지 않는다.

## 새로 작동하는 경로
- 저장 발견 사건/보고서의 정확한 원문·기업·행동을 기존 economic_changes와 common_cause_comparison 검증에 연결한다. 명시 수요처, 수요/주문 구분, 확대/회복 구분이 일치하는 HBM·DRAM·NAND의 서로 다른 제품 행동을 묶는다. 원문 밖 공통 시장충격·거래·지출·수혜는 미확인이다.
- 대시보드에 원인→제품→행동/계획→원문 기업/링크·조건부 기회/반증을 표시한다. /api/economic-discovery?common_causes=1 및 &export=1 선택 확장 discovery_common_causes로 같은 결과를 조회한다. 기본 조회·기본 표준bytes와 기존 사건/점수/가용시각은 유지한다. 새 해석은 interpretation_at을 따로 기록하며 당시 저장 판정으로 가장하지 않는다.
- 반증/무효 사건·미래 자료·누락 원문·다른 주체/수요처/변화/수요대상은 연결하지 않는다. 투자 집행 계획은 실제 집행 보도로 승격하지 않는다. 업종표·새 AI·수집·운영 DB replay·상대 프로젝트 변경 없음.

## 확인 범위
- 합성 입력→기존 저장→조회/선택 표준→HTTP/화면 경로. 관련135개 고유 시험 단계별 PASS. 초기133PASS/구판 계약 예상값2FAIL은 변경 전 HEAD에서도 동일 재현. 두 예상값을 현재 catalyst_material 확장에 맞춰 수정 후 신규14+수정2=16PASS. SSD 고정 판본16PASS. 전체 회귀를 반복한 기록은 아니다.
- 실제 저장383제목 판본 중 수요 표현4·연결양성0. 기존45주제50출처관측/회사명34·사업대상 종합38 유지. 원source·파생726파일 SHA 동일, 실제 연결양성 확보는 미완료다. 합성 양성을 실자료 검증 완료로 세지 않는다.
- dashboard만 고정 release에 반영. 운영 API/기간API HTTP200·JS SHA·CUA 실제 화면 확인. /api/themes 고정 게시bytes와 core/MOTIR/research-approved 설정3 동일. 새 fetch/AI0, Era 코드/DB/Git 변경0, Public push0.

SSD 기존 코드·미커밋을 보존하고 output/discovery_causes_20261018/code/에서 기능 SHA를 재검증했다. 최신 개발 Git은 DEV 경로, 운영 실행은 BASE/releases/5a7ada1dd2a5a369f54d9308cd4a87d7bf853376. 과거 SSD 재개 파일은 비공개 백업 후 최신 내용으로 갱신한다. 사용자dirty AGENTS/DECISIONS/비전3 SHA 유지.

증거 DEV/output/discovery_causes_20261018/ 및 SSD/output/discovery_causes_20261018/. NC-02/03/04/06 변경 기능·합성 경로/실행 확인, OP-03 원본·PIT 보존. 해당 실제 연결양성·전체제품/공동 연동 완료는 미선언. 다음 NEXT_TASK.md.
