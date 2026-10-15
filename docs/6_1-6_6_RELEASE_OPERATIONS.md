# 6_1~6_6 — NewsCatalystOS V1.0 이력·캐시·연동·운영/릴리스 검증

> 현재 운영 기준은 [D-059](V1_RELEASE_POLICY_2026-10-15.md)이다. 아래는 당시 구현·실행 이력이며, 500건 검수·5거래일 사전 대기·독립 장치/릴리스 인증 조건은 현재 필수가 아니다. 예약 AI는 모델 설정과 `--allow-paid-ai`로 활성화할 수 있다.

2026-10-13. 기존 정상 1_1~5_5 코드 보존(CONTINUE). EraLeader 원본/수집기/운영 DB/Git 불변.

## 6_1 — 기본 기능 완료
- event_lifecycle.py: DETECTED→CONFIRMED(기존 AnchoredOfficialPublication 타입의 검증된 signed proof 객체가 있고 underlying event ID 일치할 때만)→STRENGTHENED/WEAKENED/INVALIDATED. INVALIDATED→DETECTED 재활성화 시 과거 기록/근거 SHA·상태 버전 삭제 금지.
- 출처가 확인되지 않은 뉴스, AI 주장/임의 TRUE로 CONFIRMED 전이 금지. 보도 없음=자동 만료 아님. 합성 signed witness 시험은 실제 외부 공식 공개시각 공증이 아니라 코드 경계 검증임.

## 6_2 — 기본 기능 완료
- analysis_cache.py: event SHA + source revision SHA + 모델 공급자/모델 + prompt version + 메타 SHA 묶음이 완전히 일치할 때만 캐시를 사용한다. 동일 결과 중복 AI 호출 경계/재실행 보존. 출처 수정·새 금액·prompt 교체 시 새 분석키.
- owner-only SQLite에 작은 정규화 AI 결과만 SHA와 함께 저장; 뉴스 원문/유료 기사/키 없음. 캐시 삭제/변조/과거 재생 요청 차단. 실제 AI provider 비용은 4_1/4_6 실연동 게이트 미완료.

## 6_3 — 기본 기능 완료
- catalyst_audit.py: 이벤트 SHA, 증빙 SHA, lifecycle 전이 SHA, 분석·모델·prompt SHA 및 처음 수신/실제 기록시각을 append-only 원장에 저장. 이후 정정은 같은 이벤트의 이전 감사 SHA를 참조. 기록시각 이전에 미래 원장 보이지 않음.
- 외부 공시 최초 대외 공개시각 인증 미획득 자료는 UNKNOWN, 독립 검증된 역사적 증거라고 주장하지 않음.

## 6_4 — 기본 계약 테스트 완료, EraLeader 실제 소비 검증 대기
- standard_delivery.py: CatalystEvent/BeneficiaryGraph/EventHistory 버전 JSON과 선택적 pyarrow Parquet. 서로 다른 이벤트 ID 섞기·미래 버전/근거·불법 원문 본문 포함·변조된 소비자 SHA 차단. Parquet 포맷은 동일 버전 메타 3개 JSON 문서를 한 파일의 3행으로 전송하는 계약이다.
- 실제 V1.0 EraLeader 소비자 연동은 수행하지 않음. 엄격한 최종 V1 출시 게이트에는 여전히 실제 read-only 소비 검증 필요.

## 6_5 — 기술 백업·복원 구현 완료, 장기 운영 인수 미완료
- backup_recovery.py: SQLite 온라인 일관성 백업 API로 NewsCatalystOS owner-only SQLite 원장을 백업 디렉터리 내 별도 버전으로 보관, 원본/매니페스트 SHA 기록. 원장 덮어쓰기 금지, 독립 비공개 **새** 디렉터리에서 원본 무변경 복원·SQLite integrity_check·SHA 검증 후 성공. `eraleader` 경로를 백업/복원 대상에서 제외한다.
- **실제 Mac 검사:** 뉴스OS의 private incremental_feeds.sqlite3 45,056 bytes를 사용자 Mac 내부 분리 디렉터리에 일관성 백업 후 owner-only 다른 폴더로 복원 PASS. 서로 다른 물리 디스크/클라우드에 복구 가능한 백업이 있는지는 검증하지 않았으며 해당 검증 결과 **FAIL 아닌 NOT_VERIFIED**. 5거래일 연속 기술 운영은 아직 시작/검증하지 않았음. `launchd` 템플릿만 이전 단계에서 생성됐고 자동 시작하지 않음.

## 6_6 — 릴리스 체크 함수 구현, 릴리스 인수 미완료
- release_readiness.py와 scripts/check_v1_release.py: 36개 작업 완료상태, 중복 정밀도 ≥95%, 중요 탐지 recall ≥90%, 추출 95%, 반도체 수혜 95%, 주요 숫자 근거 100%, 실 API 호출·실비용 월 5만원 이하, 검수 라벨 500, 5 실제 거래세션, 별도 물리 장치 복원, EraLeader read-only 실소비, P0/P1=0, 전체 회귀 시험 종료코드 0 등을 필수로 표시.
- 사용자 스스로 임의로 숫자/TRUE를 넣은 경우 모든 정량식이 맞아도 `independently_release_certified=False`, `permitted_to_tag_v1=False`를 유지하고 실제 증거/운영자 서명 검토 후에만 릴리스 결정을 별도 진행한다. 이번에 v1.0 태그/기능 동결을 수행하지 않는다.

## 검증 원칙 및 상태
- 테스트는 합성 시험·실제 로컬 SQLite 원장 1개 복원. 2026-10-13 전체 테스트 숫자와 Git SHA는 PROJECT_STATE.md 최신 기록 참조. Public GitHub에 원본 운영 DB, 지문 영수증 값/비공개 키, 기사 유료 본문, 백업, 사용자 개인자료를 올리지 않음.
- 6_1·6_2·6_3과 6_4 버전 출력 기본 기능은 완료로 판정 가능. 그러나 6_4 실제 EraLeader 소비 검증은 미완료로 별도 표시한다. 6_5 실제 5거래일·독립장치 복원, 6_6 통합 릴리스는 명백히 미완료. 2_6·3_6 실라벨, 4_1·4_2·4_5·4_6 실AI/검수, 5_2~5_6 반도체 실증도 미완료 유지.
