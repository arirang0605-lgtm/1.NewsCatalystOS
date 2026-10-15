# 3_1 — 당시 기존 사실 조회 / PIT-safe 관측 주장 원장

> 현재 기준은 D-060/D-059이다. 사람 검수 절차와 관련 도구는 삭제했다. 아래 실행 기록은 당시 기록이며 현재 완료 상태는 PROJECT_STATE.md를 따른다.

## 구현
- `src/newscatalystos/prior_fact_state.py`: 사전에 **검토된 기업·산업 subject ID** 및 fact_key 단위로, 기존 경제적 주장 `FactVersion`의 source event SHA/값 SHA/검증가능시각/실제 원장 기록시각/원래 주장 상태를 NewsCatalystOS 전용 owner-only SQLite에 추가한다.
- 현재 수집한 오래된 원문·금액이 과거에 알려졌다고 소급하지 않는다. `record_prior_fact`는 `available_at=max(입력 근거 가용시각, **현재 원장 기록시각**)`로 고정하며 `prior_state_as_of(subject,decision)`는 두 시각이 모두 결정시점 이전인 버전만 반환한다. 과거 원본의 실제 이용가능성이 별도 검증된 경우에도 최초 로컬 등록 이전으로 되돌리지 않는다.
- 새 정정/반박은 `supersedes_fact_sha256`를 통해 같은 검토 주체+fact_key의 기존 버전을 가리켜야 한다. 원래 버전과 SHA, 정정 이후 최신 상태, 양쪽의 기록시각은 불변으로 유지한다. 조회 결과 `PriorState.latest_by_key()`는 PIT상 확인된 최신 버전만 보여준다.
- 기사 제목·원문·비밀키·운영 계좌 정보, 유료 자료는 원장에 저장하지 않는다. `UNVERIFIED_CLAIM`, `OFFICIAL_CHANNEL_OBSERVED` 등 상태는 출처 주장 수준으로서 **외부 법적 사실 인증이 아니다**. 기업명이 비슷하다고 기업ID를 자동 결합하거나 공급망 사실을 추론하지 않는다.
