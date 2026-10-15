# 3_2~3_6 — 경제적 변화 탐지 및 이력 (2026-10-13)

> 현재 기준은 D-060/D-059이다. 사람 검수 절차와 관련 도구는 삭제했다. 아래 실행 기록은 당시 기록이며 현재 완료 상태는 PROJECT_STATE.md를 따른다.

## 3_2 없던 경제적 사실 후보 등장
- `novelty_detection.py`: 3_1 `PriorState`의 **현재 시점 조회**를 기준으로, 계약/신규투자/상용화/제품·고객/허가 등 검토된 구조화 fact_key 및 값 SHA를 비교한다.
- 새로운 제목이 아니라 과거 동일 fact_key가 없을 때만 `NEW_FACT_CANDIDATE_NEEDS_EVIDENCE`. 같은 값이면 `EXISTING_ECONOMIC_CLAIM`; 금액·규모 변경의 값 SHA가 다르면 `CHANGED_ECONOMIC_CLAIM_REVIEW`로 처리한다. 사실 독립 검증 없이는 `fact_verified=False`.

## 3_3 장애물 제거 후보
- `barrier_changes.py`: 과거 PIT상 확인된 규제·생산 중단·공급망 병목·허가 지연 같은 장애물이 이미 있던 경우에만 새로운 해소 주장을 비교한다. 과거 장애물 기록이 없으면 `NO_PRIOR_OBSTACLE_RECORDED`, 값이 같으면 `NO_ECONOMIC_BARRIER_CHANGE`, 이전 주장이 반박됐으면 보류. 외부 근거 없는 경제적 이익을 확정하지 않는다.

## 3_4 기존 사건의 실현·훼손
- `change_followup.py`: 명시적 후속 주장 `ORDER_FULFILLED`, `DATE_DELAYED`, `CONTRACT_REDUCED`, `BUSINESS_CANCELLED`, `SOURCE_CORRECTED` 등을 이전 동일 주체/키의 fact SHA에 연결. 기준 없음·동일 값·과거 반박은 별도 HOLD. 이전 버전/원본 값 SHA를 변경하지 않는다.
- 결과 `STRENGTHENED_CANDIDATE`, `WEAKENED_CANDIDATE`, `INVALIDATED_CANDIDATE`는 **검토 후보**이며 실제 실현이나 손익 확정이 아님.

## 3_5 중요도 초벌 평가
- `impact_triage.py`: 공급된 규모·영향범위·반복성·신규성·사전 기대를 분리하여, 근거를 알 수 없는 항목은 `UNKNOWN`/점수 `None`으로 반환. 완전히 입력된 경우에만 rule-based `HIGH_PRIORITY_REVIEW`/일반 검토를 분류. 실제 매출액, 수혜주 확정, 예상 수익률·투자 주문은 생성하지 않는다.
- 점수/우선순위의 정확도나 시장 성과는 아직 정답셋으로 검증되지 않았다.

## PIT/권한·검증 경계
- 모든 기준 스냅샷·후속 주장·정정 근거를 동일 `decision_at` 이전으로 제한. 정정/기업 ID/산업 수혜는 확인되지 않으면 UNKNOWN/검토 보류. 유료 기사 원문/비밀키나 EraLeader 코드/DB/Git 기록 변경·API 중복 수집 없음.
- 관련 변경 테스트는 synthetic typed evidence/시점/숫자 해시와 장애 케이스의 단위 시험. 실제 반도체 정답셋·기업 수혜 검증, 5거래일 운영은 **V1.0 별도 필수 게이트**다.
