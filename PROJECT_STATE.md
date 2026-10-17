# PROJECT_STATE — News 재료판정의 자동 전방 전달

기준 2026-10-18T00:07:53+09:00. 배포 SHA **168ea012ddcade5555964f1f849edae4200fb261**. V1 반도체 1산업. 기존 코드작업36/36은 구현 이력이며, 전체 대장 후보 판단·전략 연동 완료와 별개.

## 이번 새로 해결한 입력 공백
기존 API는 호출시각/비교기간에 따라 재계산되어 원자료가 같아도 판본이 달라질 수 있었다. 이제 기존 정기 뉴스처리 완료 후 **이전 성공 판본 기준의 재료 결과를 자동 게시**하며 기본 /api/themes는 완료된 고정 bytes를 제공한다. 동일 입력은 같은 SHA/최초게시시각/사건을 유지, 변화가 있으면 새로운 불변판본이다. 이전 비교기준·원문이력/독립 source ID·정확 기업 ID·조건부 영향과 반증을 보존한다.
한 source영역 실패는 마지막 정상자료와 UNAVAILABLE 상태를 함께 전달한다. 해당 cutoff는 유지하여 복구 때 미처리 변경을 놓치지 않는다. 중간중단은 완료 pointer를 넘기지 않고 재시도 재사용. 이전 DB로 되돌아가 사건이 사라진 것과 실제 철회를 구분한다. 빈 source(경제테마 없음)는 정상이며 새 전역 gate가 아님. 소비 확인·리더순위·매매판단을 News가 만들지 않는다.

## 실제 실행·시험
- 개발 실자료 4영역17테마 발행 PUBLISHED, 같은 입력 재실행 ALREADY_PUBLISHED/동일 SHA. 원 ThemeStore·사용자dirty3 보존.
- 운영 2026-10-18 00:03 자동 RunAtLoad: exit0, 5source 모두 기존 rate한도에 따라 NOT_DUE/새기사0/AI0, 재료17테마 발행·4영역CURRENT_SNAPSHOT. 기존 Era 평가50 최신판본 선택적 읽기/수신만, 그 자체는 뉴스 신규성 변경 근거로 사용 안 함.
- 실제 기존 Era decoder/validator로 운영 기본 URL17테마 수신 확인. API 기본/명시publication/파일 bytes 동일. 실제 SK 재료 NO_NEW_MATERIAL, 후보입력 NO_NEW_CATALYST, 출처계획 PLANNED, CAPEX/SUPPLY 가설·반증 유지. 게시이전 as_of404. **Era 내부 실제 후보선정은 이번 작업에서 변경/완료하지 않았음**.
- 게시/기존 관련94PASS 및 최종API 관련48PASS, 실패0(겹치는 시험 합산 금지). core/MOTIR 설정·원본SSD·기존 소스원장·사용자dirty3와 Era코드/DB/Git/스케줄 보존. 배포는 News dashboard/research-approved만 고정snapshot 교체. Public push없음.

## 현재 전달 위치
/Users/shmoon/Library/Application Support/NewsCatalystOS/document_analysis/material_outbox/latest.json → SHA-bound material_checkpoint_<sha>.json → 기존 theme_delivery_<sha>.json. HTTP /api/themes 기본 또는 ?publication=latest. 기존 필터분석 API는 유지. 최신 검증판본SHA 4b7cd2adc53cc3a5aaa65aad80e251dd90d6a07e971c58596dea034fbccf35bc.
증거 output/material_delivery_continuation_20261017/activation.json·operating_material_publication_proof.json. 시간이 지난 다음 자연 예약에 새자료가 들어오는 경우는 후속 관찰이며 새 출시 대기조건으로 만들지 않는다.
