# 1_4 — 공통 시간 · 기업 식별자 · 정정 연결 (2026-10-13)

## 목적과 형식
- 기존 `OperationalObservation`(DART/SEC/KRX 읽기 전용)과 `FeedObservation`(1_2 허가된 신규 RSS/API)을 기존 코드 변경 없이 `NormalizedEvent v1`로 변환한다.
- **분리 필드:** `first_seen_at`(원본 최초 로컬 관측), `collected_at`(이번 V1 소스가 보유한 수신 완료 근거; 별도 수집시각이 없으면 first_seen과 동일), `verified_at`(현재 신뢰 경계 검사), `available_at`(소비 가능 최초 시점), `decision_at`(정규화 시의 판단 시점), `published_at`(발행기관 공개시각 독립 확인 때만 설정). 시각은 모두 timezone-aware UTC로 정규화.
- **PIT 규칙:** `available_at >= max(first_seen_at, 소스별 local verified/atomic published, 이번 verification, 기업 매핑 및 정정 증거 실제 관측 시각)`. 이전 결정에 미래 수신·매핑·정정을 소급하지 않는다. `normalized.as_of(at)`는 `max(available_at, decision_at) <= at <= now`만 허용한다.
- 공시 `published_at`가 없는 경우 **None / UNKNOWN**이며 SEC `acceptanceDateTime`, DART 접수 날짜, RSS `pubDate`를 정확한 대외 최초 공개 시각으로 대체하지 않는다. 아무런 외부 issuer 근거가 없는 경우 `company_id/company_namespace/mapped_ticker=None`, 상태 UNKNOWN.
- 증빙이 있는 경우 `CompanyBinding(source_id,source_document_id,id_namespace,company_id,mapped_ticker,evidence_sha256,observed_at)`를 별도 전달한다. SEC_CIK(1~10자리 숫자), DART_CORP(8자리 숫자), KRX_STOCK(6자리 숫자)를 구분하고 실제 공식 공급자에 잘못된 네임스페이스를 연결하지 않는다. 출처 연결 바인딩은 **법적 발행기관 외부 공증이 아니므로** 상태 `SOURCE_LINKED_MAPPING_NOT_ISSUER_ATTESTED` 유지.
- 정정 참조는 `RevisionEvidence(..., revision_id, supersedes_document_id, evidence_sha256, observed_at)`가 있어야 연결되며, 자기참조/타 공급자/미래 자료는 거부. 기존 자료를 덮어쓰거나 처음 관측 시간으로 정정 소급 불가. 이 단계는 연쇄의 형식·PIT만 확인; 실제 정정 사실의 독립 법적 인증은 선택 고정밀 게이트.
- 이미 사전 승인 검증자·별도 앵커를 통과한 `AnchoredOfficialPublication` 객체만 `normalize_attested_publication`으로 변환하여 witness-signed published_at을 보존할 수 있다. **RawEvent나 임의 JSON만 넘겨도 인증으로 승격하는 경로는 없음**. 테스트의 합성 서명은 실증 발행기관 공증이 아니라 기능 회귀 예시.
- `KRX` 가격 참고 메타는 `MARKET_CONTEXT_NOT_NEWS`로 계속 구분하며, RSS 보도자료도 `FEED_METADATA_UNVERIFIED`로 남긴다. 시장 재료 사실 판정/실제 기업 재무 근거는 후속 2~5단계.

## 실제 관측 데이터 점검
- EraLeader의 기존 공식 수신을 재수집하지 않고 NewsCatalystOS 비공개 v2 원자 게시 배치를 read-only 오프라인 소비. **5개 소스 / 3,866 메타행** → 새 정규화 성공: 공시 관측 1,101 / KRX 시장 참고 2,765, 확인된 실제 발행시각 0, 임의 매핑 issuer 0, 임의 정정 0, 과거 가용시각 소급 0.
- SHA pin을 이번 테스트에서 같은 Mac이 계산한 것은 **같은 기기 로컬 일관성 검사**이며 제3자 역사적 웹 공개 인증 또는 과거 시점 독립 공증이 아님. 실제 외부 증거 없는 기존 데이터의 원래 공개시각은 계속 UNKNOWN.
- 새 합성 테스트는 수신/검증/판단 UTC, 미래 시점 차단, 기업 ID 네임스페이스, 타 문서 잘못된 매핑·SHA, 정정 자기참조/미래 참조, signed witness claim 게이트·원본 불변을 확인한다.

## V1.0 완료 기준과 후속
- 1_4 기본 인수: 두 수집 경계 공통 타입 + 실제 메타 배치 정규화/PIT/기업 매핑 근거·정정 테스트 PASS.
- `RawEvent` 공식 공개시각을 모든 실데이터에 채우는 것, 실제 기업 식별자를 원천 없이 추론하는 것, 5거래일 자동운영 증명은 1_4 완료 조건이 아니다.
- 다음 1_5는 허가된 원문·영수증 SHA 증빙의 안전 보관/정정 버전 이력. EraLeader 수집기/DB/Git 변경 금지.
