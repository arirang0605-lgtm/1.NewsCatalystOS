# 2_3~2_6 — 사건 묶음/광고·루머/원천독립/라벨 평가

## 2_3 유사 기사 묶음 — 기능 구현
- `event_cluster.py`: 이미 `NormalizedText` 형태로 검증된 제목을 **사전에 검토한 동일 원천 `origin_reference`·사건 subject**가 있을 때만 유사도 조건으로 묶는다. 제목이 비슷하다는 이유만으로 서로 다른 원천의 경제 사건을 합치지 않는다.
- 각 변형 문서에 최초 사용 가능시각, 원본 event ID, 공급자 ID, 숫자/금액/기간 마커 및 새로 등장한 마커·정정 플래그를 남긴다. 새 금액/정정 출처를 이전 사건에 덮어쓰지 않고 별도 `StoryVariant`에 보존.
- 사건을 새로 그룹화한 시점 이전에 새 묶음의 결과를 조회하지 못하도록 `grouped_at` PIT 보호. 이 단계는 후보 그룹이지 독립 검증된 사실 이벤트는 아님.

## 2_4 광고·루머 분류 — 기능 구현
- `claim_filter.py`: 명시 광고/유료협찬/스팸, 루머/익명 제보, `SOCIAL`/ `ANONYMOUS`는 자동 사실 승격 차단. 공식 채널의 헤드라인/배포 보도자료 역시 실제 독립 issuer 검증 없이는 사실 확정하지 않는다.
- 공식 정부 채널 관측은 검토 후보가 될 수 있지만 `is_verified_fact=False` 유지. 뉴스와이어 같은 배포 서비스는 독립 언론 보도나 복수 원천으로 자동 승격하지 않는다.

## 2_5 인용 원천/독립성 — 기능 구현
- `origin_provenance.py`: 4개 언론이 하나의 원보도자료를 재인용한 경우 `claimed_root_count=1`, `independently_verified_fact_count=0`. 원천 미기재 SNS·익명 기사는 독립 증거로 계산하지 않는다.
- 공식 반박·서로 다른 주장 충돌은 `CONTRADICTORY_SOURCES_HOLD`, 정정은 `CORRECTION_PENDING_PRIMARY_REVIEW`; 단순 출처 수로 투자 사실 신뢰 점수를 올리지 않는다.

## 2_6 정답셋 성능 평가 — 모듈 구현, **완료 조건 미충족**
- `filter_evaluation.py`: 정답 `true_duplicate`, 예측 `predicted_duplicate`, 중요 기사 `important_event`, 제외 `predicted_excluded`의 confusion matrix, 정밀도·재현율, 중요 누락 목록, 결정적 제외 표본 추출.
- 분모가 0이면 정확도 100%로 가장하지 않고 `None`. 합성 fixture에서 정밀도 100%가 나와도 `release_gate_verified=False`. **실제 검수된 독립 정답셋에서 중복 식별 precision >=95%와 중요 사건 누락을 별도 확인할 때만 2_6 완료 인정**.
- 이후 명세 3_1 PIT 과거 상태 조회는 기술적으로 독립 구현 가능하지만 2_6 실물 gold set 평가 게이트는 계속 열려 있어 전체 V1.0 종료 불가.

## 공통 경계
- 모든 관측 결과는 PIT 이용 가능시각 이후에만 사용. 기업 ID·공식 공표시각 미확인 자료는 UNKNOWN, EraLeader 원본·DART/SEC/KRX 수집 API 재사용/수정 없음.
- 테스트는 synthetic 기사/원천/정정 값만 사용, 유료 원문 저장/외부 AI 호출/자동매매 구현 없음.
