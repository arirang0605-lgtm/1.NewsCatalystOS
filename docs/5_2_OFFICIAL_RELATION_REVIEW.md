# 5_2 — 공식 문서에 근거한 반도체 관계 검토 (증분 개발)

## 이번에 연결한 경계
- 기존 `OperationalObservationSet`의 **원자 게시 완료 및 SHA/PIT 검증된 v2 공식 공시 메타**에서 특정 DART/SEC 문서 ID가 실제로 있었는지 확인한다.
- 해당 공시의 본문은 기존 5개 EraLeader 최초 수신 캡처/3,866개 연구 메타에 **포함되지 않는다**. 문서 ID나 회사명만으로 공급자·고객·공정·직접 계약을 자동 생성하지 않는다.
- 별도 허가·입수한 공식 문서 **UTF-8 추출 텍스트의 외부 보관 SHA**, 최초 확인 시각, 관계가 실제 명시된 문장, 두 회사의 명시적 검토 ID와 운영자 검토시각이 있을 때만 `review_official_supply_relation`이 관계 **후보**를 만든다.
- 본문은 함수 호출 중에만 검사하고 저장/JSON 게시하지 않는다. 기사 원문·유료 원문, 인증정보, 투자정보를 Git에 올리지 않는다.
- `SupplyChainEdge`에 `document_sha256`, `review_proof_sha256`를 별도로 보존한다. 기존 미검토 피드 관계와 달리, 검토된 문서에서 나온 결과만 `BeneficiaryGraph`의 추가 선택 메타에 출처 SHA/검토 SHA를 실어 내보낸다. 기존 피드 엣지 JSON 구조는 변경하지 않았다.
- 문서 내용 확인과 역할 판단은 **사람의 검토**이며 실계약 이행·매출발생의 외부 감사 증거는 아니다. `verified_real_transaction=False`, `verified_real_benefit=False`, 매출 비중 `N/A`을 강제한다.

## 5_2 실제 수락 이전 필요한 자료
1. 운영자가 기존 SHA/PIT 확인된 EraLeader DART·SEC 공개 스냅샷의 *특정 수신 문서 ID*를 선택한다.
2. 접근권한이 허용된 실제 공시 원문 또는 해당 부분의 공식 제출 본문을 검토한다. 별도 디스크/승인 경로에서 문서 ID와 SHA를 관리하고 사용한 본문 텍스트의 신뢰 해시 및 최초 확보시각을 독립 기록한다. 기존 DART/SEC/KRX 재수집·EraLeader 코드/DB/Git 변경 금지.
3. 공급사·고객사 공식 식별자와 역할·제품/공정, 명시적 관계 문장을 함께 운영자가 검토한다. 정보 없음이면 `UNKNOWN`; 본문 속 일반적 동시 언급과 직접거래를 혼동하지 않는다.
4. 5_2 오프라인 검토 기능으로 PIT·원본 SHA·실제 문서 내용·관계 증거를 확인 후에만 공급망 관계 **후보**를 승인한다. 이를 바탕으로 5_3~5_5 실제 파급/소비 시험과 5_6 독립 라벨 평가를 진행한다.

## 현재 합격 경계
- 합성 문서에 대한 SHAs·역할·시점·부정 테스트와 그래프 JSON 호환 검증은 완료했다.
- **실제 독립 검수된 반도체 고객/공급 관계는 아직 0건**. SEC 접수시각/DART 접수일과 검토자 주장은 공식 공개시각 공증 또는 거래 이행 증명이 아니다.
- 따라서 **5_2 최종 실증/완료 판정은 보류**, V1.0 완료 수는 23/36 그대로다.

## 2026-10-14 | 실제 별도 문서 도착 시 오프라인 5_2 입력 경로
- `official_relation_intake.read_official_relation_intake`가 **기존 비공개 완료된 v2 관측 배치**를 사용자 별도 보관 SHA로 재검증하고, 별도 보관 중인 승인 공식문서 UTF-8 텍스트(최대 1 MiB)와 사람 검토 JSON을 읽는다. API 네트워크/원문 복제/EraLeader 쓰기 없음. 문서·JSON은 소유자 전용 디렉터리(0700)와 파일(0600)에 두어야 한다.
- JSON은 `schema: "newscatalyst.official_relation_intake.v1"` + `review`, `supplier`, `customer` 세 객체. `review`는 `OfficialRelationReview` 필드 전체(기존 공시 source ID, 문서 ID, 증거 SHA, 수신영수증 SHA, 본문 SHA, 최초 확보/pin/인적검토 시각, 검토자 코드, 양사 이름, 문서 안의 원문 일치 관계 문장, 반도체 product_stage), 양사 객체는 `CompanyBinding` 필드 전체를 반드시 포함한다. 일시는 UTC offset 포함 ISO 문자열.
- 실행: `PYTHONPATH=src python3 scripts/review_supply_relation.py --publication <비공개-v2-게시-폴더> --publication-root <비공개-게시-상위폴더> --payload-sha256 <별도-보관-배치SHA> --review-json <private-review.json> --document-text <허가받은-공식문서.txt> --document-sha256 <별도-보관-문서SHA>`. 두 SHA를 입력 파일/게시 마커에서 방금 계산해 독립 증거로 둔갑시키지 말 것.
- 실제 입력 완료시각을 PIT 최초 사용 가능시각으로 강제한다. 이미 과거 날짜의 인적 검토가 있더라도 **현 시점 증거 소비보다 앞선 과거 시점에 소급 표시 금지**. 성공 시 `OFFICIAL_DOCUMENT_REVIEW_CANDIDATE_ONLY` + 관계 SHA/검토 SHA/현재 사용 가능시각만 화면에 표시(원문/회사명/민감정보 출력·Git 저장 0). 실패 시 `DATA_UNAVAILABLE` / exit 4.
- 반환된 `SupplyChainEdge`는 기존 `classify_semiconductor_beneficiary` 및 `build_beneficiary_graph`에 타입 그대로 연결 가능하지만, 여전히 **상업적 거래 실행 확인 0/매출수혜 확정 0**. 기존 공개 메타에 공식 문서 본문이 없으므로 외부 승인 문서·사람 검토가 없으면 실물 통과/5_2 완료 판정 금지.
