# 1_1 — EraLeader 실제 수신본의 안전한 읽기 전용 소비 (2026-10-13)

## 실제 구현

- `src/newscatalystos/era_capture_share.py`: EraLeader의 기존 공식 API **첫 수신본** `output/official_api_capture/first_<uuid>/`를 새 수집/쓰기 없이 열어 원본 SHA·수신 영수증 SHA·출처·행수·품질을 재검증. EraLeader `official_api_capture.py`의 기존 원자적 디렉터리 rename 게시 정책을 확인했으며, 소스 코드를 import하거나 수정하지 않는다.
- `src/newscatalystos/verified_reference.py`: EraLeader의 기존 `official_api_pit_research.json`을 독립적으로 전달받은 **리포트 SHA 핀**으로 검증한 후 그 안에 기존에 기재된 5개 source 영수증 SHA를 실제 캡처의 증빙과 대조. 위변조·누락·미확인 source 차단.
- `scripts/verify_era_captures.py`: 실제 SSD에서 **읽기만** 수행하는 명시 CLI. 수집/자동승격/원본 DB 변경 없음. 출력은 공용 수집원/건수/품질 합계만.
- `src/newscatalystos/source_share.py`: 앞서 구현한 독립 게시 export용 SourceManifest/RawEvent/COMPLETE 검증 계약을 변경 없이 보존. 실제 첫 수신본(별도 공식 계약)의 보수적 `OfficialCapture/OfficialRecord`와 구별한다.

## 독립 SHA 핀 준비 및 실행

미리 **신뢰할 수 있는 다른 저장 위치/경로에서 별도 확인·보관한** 기존 EraLeader 리서치 기록 SHA256이 있어야 한다. **호출 시 파일 자체를 계산한 SHA로 자동 신뢰 승인하지 않는다.** 최초 bootstrap의 신뢰 수준, 누가 언제 기록했는지 별도 보존해야 한다. 로컬의 기존 리서치 기록은 암호학적 외부 타임스탬프 공증/제3자 인증이 아니다.

```bash
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_era_captures.py \
  --era-root /Volumes/T5DATA/eraleader \
  --reference /Volumes/T5DATA/eraleader/output/official_api_integrated_20261012/official_api_pit_research.json \
  --reference-sha256 '<separately-anchored-64-hex-reference-sha256>' \
  --decision-at '2026-10-13T05:00:00+00:00'
```

명령의 decision 시각은 실제 검증 시점의 현재 시각 이하로 선택해야 하며, 최초 수신보다 과거면 거절한다. 비밀키/기사 원문/실사용 DB를 GitHub에 포함하거나 stdout에 표시하지 않는다.

## 2026-10-13 실제 테스트 증거

이미 별도로 기록된 EraLeader 연구용 `official_api_pit_research.json`의 SHA를 명시해 **실제 저장된 캡처 5개**의 독립 재검증을 실행했고 결과:

| Provider | source_id | 관측 수 | 정규화 메타 record | 결과 |
|---|---|---:|---:|---|
| KRX | krx-kospi | 942 | 942 | ROWS_RECEIVED_NOT_PIT_CERTIFIED |
| KRX | krx-kosdaq | 1823 | 1823 | ROWS_RECEIVED_NOT_PIT_CERTIFIED |
| DART | dart-disclosures | 100 | 100 | INCOMPLETE_FIRST_PAGE_NOT_FULL_DAY |
| SEC | sec-submissions | 1001 | 1001 | RECENT_SUBMISSIONS_NOT_FULL_HISTORY |
| SEC | sec-companyfacts | 2 | 0 | FINANCIAL_FACT_TAXONOMIES_NOT_PIT_CERTIFIED |

원본/영수증 사전·사후 SHA 동일 확인. 총 3,868개의 **원천 관측 항목**이며, SEC taxonomy 2건은 뉴스 이벤트로 간주하지 않으므로 메타 record는 0건이다. DART 100건은 해당 하루 전체가 아닌 첫 페이지다. KRX 거래 일봉 수치는 소급 주도주 발견 실적이 아니다.

현재 최초 수신시각만 검증되었고, 원천 발행/공개시각·합법적 share class·역사 유니버스 PIT는 독립 확정되지 않았다. 따라서 `OfficialRecord.release_at=None`, `issuer_attested=False`, `historical_pit_certified=False`, `completeness_certified=False`를 유지한다. 관측 가능시각 `available_at`을 원본 발행시각 `published_at`으로 속이지 않는다.

모의/음성 테스트: `python3 -m pytest -q tests/test_source_share.py tests/test_era_capture_share.py tests/test_verified_reference.py` → **57 PASS / 0 FAIL**. 실제 API 네트워크 인증 호출 0회, AI API 0회, 운영자동화 0거래일. 외부 공증/시점 독립 인증은 여전히 미완료.

## 완료까지 남은 1_1 게이트

실제 첫 수신본을 메타데이터 연구용으로 공유하는 경계는 동작한다. 그러나 출처별 자료의 **정확한 provider release time**이 불명확하고 완전 공시 본문/정정 관계가 미연결이므로 이를 완전한 `RawEvent` 확정으로 판정해서는 안 된다. 별도 신뢰 저장소에 리포트 SHA를 지속 보존하는 운영 절차를 인수하고, 공식 timestamp가 입증된 공시만 원본 PIT를 보존해 downstream 정규화해야 한다. 그 전에는 V1.0 `1_1`의 전체 합격 선언 및 `1_2`로 NEXT_TASK 이동을 보류한다.

## 2026-10-13 | SEC 시각 정규화·로컬 별도 디스크 SHA pin 실증

- `src/newscatalystos/era_capture_share.py`: SEC submissions 각 기록의 `acceptanceDateTime`을 UTC 유효 시각으로 파싱하고 `provider_acceptance_at`에 별도로 보존. 최초 수신 시각보다 미래·형식 오류/타임존 없음은 차단. SEC 접수시각은 **독립적으로 입증된 대외 공개시각이 아님**. DART의 `rcept_dt`은 날짜만 유지.
- `official_normalization.py`: 공식 수신본의 각 기록을 연구용 `OfficialEvidenceCandidate`로 정규화. `first_seen_at`, `provider_day`, `provider_acceptance_at`, 원본/영수증 SHA를 각각 유지하고 `verified_published_at=None` 및 `RELEASE_UNVERIFIED_RESEARCH_ONLY`를 강제. `RawEvent` 자동 승격은 예외로 차단.
- `pin_anchor.py` / `scripts/anchor_era_reference.py`: Mac 내부 디스크의 **NewsCatalystOS 전용 비공개 디렉터리** (`~/Library/Application Support/NewsCatalystOS/pins/`)에 별도-device SHA 핀을 최초 관측 시점 기준으로 한 번만 기록. `O_EXCL`로 재작성 금지, 소유자 전용 디렉터리/파일·다른 디바이스 ID 검증, 과거 결정 시점 이전으로 pin 소급 금지. 공개 GitHub에 앵커 기록/원본 파일 미업로드.
- **핀의 증거력 제한:** 로컬 SHA 앵커는 `LOCAL_TOFU_NOT_EXTERNAL_ATTESTATION`이며 생성 당시 현재 파일의 **최초 로컬 관측**에 불과하다. 이전 시각에 그 문서가 존재했다는 제3자 공증이나 법적 공시 발표시각 확인은 아니다. 동일 Mac 디스크 변경 위험을 제거하지 않는다.
- 실제 EraLeader 기존 연구용 보고서 SHA pin 별도 저장 및 재검증 PASS; KRX 2개·DART 1개·SEC 2개 **5/5**와 연구용 메타후보 **3,866개**, 자동 승격 0개. 핀 저장소 디바이스 ID와 EraLeader SSD 디바이스 ID 구분 확인. EraLeader 기존 캡처·보고서 SHA 사전/사후 동일.
- 합성/영향범위 단위시험 **78 PASS / 0 FAIL**, 실제 기존 공식 캡처 오프라인 검증 PASS. 신규 외부 API 호출 0회, 실운영 0거래일, 공식 정확 발표시각 증명 0건.
- **1_1 미완료:** 외부 검증 가능한 발표/공개시각 자료, 정식 출처별 전체 범위·정정 버전·기업 매핑 등 검증된 `RawEvent` 생산이 미완료. 완료 기준 **0/36** 유지. 다음 개발은 신뢰할 수 있는 공개시각 증빙을 가진 공식 이벤트 정상화 경계 보강.

## 2026-10-13 | 공개시각·정정본 증빙 후보 계약 (RawEvent 승격 아님)

- `src/newscatalystos/release_claim.py`: 이미 수신·SHA 검증된 DART/SEC 메타후보에 대해, **외부에서 별도로 고정한 SHA256**을 입력받아 공개시각 주장 JSON의 출처 문서ID·발행자 ID 문자열·정정 버전·정정 전 문서ID·관측시각을 대조한다. 원본/기사본문을 복사하지 않고 새 HTTP/API 수집기를 호출하지 않는다.
- 출처 URL은 HTTPS 공식 도메인과 개별 접수번호/SEC accession 경로 모양을 검증한다. URL 문자열 및 로컬 SHA만으로 실제 발행자 신원·공개시각을 증명할 수 없으므로 결과는 **PINNED_CLAIM_UNAUTHENTICATED**이고 `to_raw_event()`는 항상 거절한다.
- DART `rcept_dt` 당일(한국시간) 경계, SEC 접수시각 이후 공개주장, 최초 원본 수신·증빙 관측·판단시각 순서를 검사한다. 정정 공시는 기존 문서를 덮어쓰지 않고 참조 ID를 요구한다. 영수증 SHA/원본 SHA 바인딩을 유지한다.
- 검증 입력은 필수 필드만 허용하고 8KiB 초과·중복 JSON 키·미래시각·허위 URL/출처·자기참조 정정은 실패 처리한다. `tests/test_release_claim.py`는 **합성 입력 전용**이다.
- **남은 외부 게이트**: 실제 공식 출처 페이지를 독립 조회/진위 확인하고, 공신력 있는 최초 대외 공개시각·정정 연쇄·기업 ID를 인증한 증빙을 별도 시점에 확보해야 한다. 단순 링크/SHA pin·SEC acceptance·DART 접수일만으로는 `RawEvent` 실물 1건을 인증하지 않는다.
- 기존 EraLeader 수집/DB/Git·별도 Mac 내부디스크 local-TOFU pin 수정 없음. 전체 1_1 완료 및 실운영 성공을 선언하지 않는다.

## 2026-10-13 | 1_1 외부 검증자 서명 게이트 (실물 증빙 대기)

- `signed_publication.py`는 **이미 `inspect_release_claim`을 통과한 DART/SEC 공시 후보만** 추가 인증한다. 독립적으로 등록·신뢰한 검증자의 **Ed25519 공개키 PEM + 미리 별도 기록한 SHA256**이 필요하며, 동일 증빙 묶음의 키/핀을 자체 신뢰하지 않는다. 검증은 Mac OpenSSL 3 로컬 명령으로 수행하며 키·서명·증빙 파일은 EraLeader에 기록하지 않는다.
- 증빙 JSON `newscatalyst.publication_attestation.v1` 필수 필드: `schema`, `claim_sha256`, `provider_id`, `source_id`, `source_document_id`, `issuer_id`, `revision_id`, `revision_kind`, `supersedes_document_id`, `official_url`, `publisher_released_at`, `witness_id`, `witness_verified_at`. 이 JSON **원본 바이트에 서명한 64바이트 Ed25519 서명**을 별도 전달한다. 검증자 확인·출처 확인 절차는 신뢰 등록 전에 별도로 감사해야 한다.
- 서명자의 신뢰 계정·공개키를 독립적으로 승인하지 않으면, 키를 임의 생성하여 '공증'으로 속이거나 `trusted_public_key_sha256`을 동일 입력에서 자동 계산해 실데이터 완료를 주장하는 것을 금지한다. 서명은 **누가 주장했는지**를 인증할 뿐 실제 발행자의 사실 여부/서명자 시계 정확도까지 독립 증명하지 않으므로 신뢰 정책·증거 감사가 별도로 필요하다.
- 서명된 발표시각·issuer·정정 메타·원본 영수증을 묶어 `SignedPublication`으로 반환한다. 실제 `RawEvent`는 `proof.as_of(decision_at)` 호출 시점이 `max(first_seen_at, witness_verified_at)` **이후**일 때만 제공된다. 과거 최초 수신 시각에 늦게 획득한 서명 증거를 소급 적용하지 않는다. DART 날짜/SEC acceptance는 공개시각이 아니며, 근거 없는 정확한 시간 생성은 여전히 금지한다.
- OpenSSL로 생성한 **합성 서명** 및 오류/변조/PIT 차단 테스트만 현재 성공했다. **외부 승인 서명자/공식 공개시각 증빙/독립 timestamp**는 확보되지 않았다. 검증 신뢰수준 불충분이므로 실제 EraLeader 기존 캡처를 `RawEvent`로 승격하지 않으며, `1_1 = DATA_UNAVAILABLE`/0/36을 유지한다.
- 실제 참조 가능한 SEC 예시: [EDGAR 공식 Form 4 접수·발행자](https://www.sec.gov/Archives/edgar/data/320193/000114036126039158/0001140361-26-039158-index.htm). 해당 접근번호는 기존 EraLeader 읽기 전용 캡처에 존재한다. 공식 SEC `Accepted` 2026-10-08 18:30:32 EDT는 **접수시각**, 공개 시각의 독립 증명은 아님. 제3자 웹사이트가 표기한 수집시각도 과거로 소급 가능한 공증으로 취급하지 않는다.

## 2026-10-13 | 실데이터 연구용 관측 배치 생성·비공개 원자 게시 (NC-1_1-OBSERVED-BATCH)

- `src/newscatalystos/observed_batch.py`에서 **독립 로컬 TOFU SHA pin으로 확인한 `VerifiedOfficialSources`**의 기존 공식 캡처를 `ObservedOfficialBatch`로 정규화한다. 모든 행에 출처·공급자·문서 ID·최초 수신시각·SHA256·품질·(있는 경우) SEC acceptance/DART 날짜를 기록하며 **`published_at=null`, `issuer_verified=false`, `research_only=true`**를 고정한다. 사용 가능 시각은 `max(first_seen_at, 별도 pin 첫 관측 시각)`. 미래 또는 소급 판단을 거절한다.
- `scripts/inspect_official_observations.py`는 이미 저장된 EraLeader 완료 수신본을 **읽기 전용**으로 소비하며 API 수집기나 EraLeader 코드를 호출하지 않는다. `--output-name` 지정 시 NewsCatalystOS 전용 `output/`(GitHub 제외)에 유일한 랜덤 디렉터리를 만들고, JSON과 digest/bytes/status 포함 `publication.json`을 staging 뒤 디렉터리 **원자적 rename**으로 게시한다. 기존 게시물을 덮어쓰지 않으며 비밀키·기사 원문·운영 DB를 포함하지 않는다. 하드링크 불가 SSD(exFAT 등)에서 기존 기능 실패를 실제 수정했다.
- 로컬 재현: `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 scripts/inspect_official_observations.py --era-root /Volumes/T5DATA/eraleader --reference /Volumes/T5DATA/eraleader/output/official_api_integrated_20261012/official_api_pit_research.json --anchor "$HOME/Library/Application Support/NewsCatalystOS/pins/official_api_pit_research.pin.json" --output-name official_observations_20261013_v1.json`
- 실제 오프라인 실증: **5개 캡처, 메타행 3,866개, 인증된 RawEvent 0개**. `observations.json` **2,513,011 bytes** SHA256 **`a7b572e395ce7ec8c8825fbe87c9aea49f19c1a165882523756ffc6ed1ae9328`**, `publication.json`의 해시/크기 재대조 PASS; 모든 기록의 `published_at=null`, 사용자 자료 외부 업로드/신규 공식 API 재수집 없음.
- 이 배치는 실운영 투자 신호·`RawEvent`가 **아니며** 발행 원문 공개시각/issuer 독립 인증·정정 증거가 확보되지 않은 상태. 1_1 최종 인증 게이트는 계속 보류. 안전한 신규 소비 기능을 개발한 것과 1_1 전체 검증 통과를 혼동하지 않는다.

## 2026-10-13 | 연구용 게시 결과 소비자·역사 PIT 경계 (NC-1_1-READ-PUBLISHED)

- `src/newscatalystos/published_observations.py`: NewsCatalystOS 소유 `output/<원자적 게시 디렉터리>/`의 `observations.json` 및 `publication.json`을 **읽기 전용**으로 재검증하는 소비자. 별도로 신뢰된 `expected_payload_sha256`를 호출자가 입력해야 한다. 게시 마커 안의 자기 SHA를 자동 신뢰 승인하지 않는다.
- 게시 마커에 `first_local_published_at`(프로젝트 로컬 실제 게시 시작 시각)을 추가했다. 파일을 나중에 발견했다고 옛 거래 시점으로 소급하지 않도록 `decision_at >= first_local_published_at` 차단한다. 예전 게시물의 시각 필드가 없으면 명확히 **차단**하고 새 버전으로 원자 게시한다(기존 결과 보존).
- 파일/디렉터리 owner-only, 심볼릭 링크·상대경로/탈출 거부, MAX 16MiB/20,000행/공급자 5개, 원본 SHA와 독립 핀/게시 마커 무결성, JSON 중복 필드, 출처별 품질·SEC acceptance·DART 날짜·`first_seen_at`/독립 pin·사용가능 시각·문서 중복 검사. `published_at`은 **항상 null**, `issuer_verified`는 **false**, `certified_raw_event_count=0`만 허용. 변경·미게시/부분게시·미래자료는 실패 처리한다.
- 실데이터 오프라인 end-to-end 재검증: 기존 EraLeader **공식 캡처 5종**, NewsCatalystOS 비공개 연구 메타 **3,866행**, 인증된 `RawEvent` **0건**. 새 원자 게시·소비자 재개방 SHA/시간/품질 PASS. 기존 EraLeader 코드/원본/Git/API 인증정보 변경 및 신규 공식 API 호출 **0건**. private `output/` 디렉터리는 공개 GitHub에서 제외.
- **신뢰수준 경고:** 이번 실증에서 게시된 파일의 SHA를 같은 Mac에서 직접 계산해 넣은 것은 **로컬 데이터 무결성 연동 테스트**다. 제3자 원천 공개시각 인증/독립 신뢰 핀이 아니다. 운영용 독립 PIN은 사전에 별도 신뢰 보관소·최초 관측시각으로 관리해야 한다. 1_1 공식 발표시각 게이트는 계속 `DATA_UNAVAILABLE`이며 완료 단계/36 수를 올리지 않는다.

## 2026-10-13 | 1_1 연구 공유 계약 v2: 이벤트 0행 출처까지 명시

- 신규 게시물은 `newscatalyst.observed_official_batch.v2`를 발행한다. `source_coverage` 배열로 **각 공식 캡처**의 `source_id`, `provider_id`, 원본/영수증 SHA256, `first_seen_at`, 품질, `observed_count`(공식 API 원천 관측수), `metadata_count`(뉴스 정규화 후보수)를 보존한다. 정규화된 개별 `rows` 수와 이 배열의 합계를 일치시키며, 각 행의 SHA·품질·최초 관측시각·안정적 문서 ID를 원천별 요약에 다시 결합한다.
- 이 변경으로 **SEC companyfacts taxonomy 2건·뉴스 이벤트 0행**처럼 행이 없는 공식 출처도 출처 장부에 남는다. `source_count`로 행 개수만 추정하는 문제를 제거한다. 품질상 `NO_DAILY_ROWS` 등 0건은 0건으로 기록하고, 개별 공식 출처의 포맷별 건수 무결성을 검사한다.
- 기존 `v1` 연구용 게시 파일은 **삭제·덮어쓰기 없이** `read_published_observations()`에서 하위호환으로 읽되 `coverage_verified=False`를 명시한다. v2는 원천 요약이 완결·정합할 때만 `coverage_verified=True`; v1 결과를 v2 출처 완결로 자동 승격하지 않는다. 이 필드는 원본 스냅샷의 전체 역사·정식 공개시각 공증을 의미하지 않는다.
- 기존 DART·SEC·KRX EraLeader 공식 5개 캡처로 v2 배치 실제 비공개 게시·재읽기 PASS: 원천 관측 **3,868**, 메타행 **3,866**, SEC companyfacts 원천 관측 **2/뉴스 0**, `RawEvent` **0**. 결과는 여전히 `RESEARCH_ONLY_RELEASE_UNVERIFIED`이며 공개시각 `null`/발행기관 독립 신원 미확정. 공식 신규 API 중복 수집·EraLeader 원본/DB/Git 변경 **0**.

## 2026-10-13 | 1_1 실물 공식 수신본–독립 서명–PIT 연결 게이트 (NC-1_1-PROOF-JOIN)

- `src/newscatalystos/official_promotion.py`는 세 개의 검증 경계를 연결한다. ① 별도 디스크에 고정된 EraLeader 연구 인덱스 SHA pin을 검증하고 기존 **공식 완료 수신본**만 읽음(`read_local_reference_anchor` → `verify_official_research_reference`). ② 지정한 DART/SEC 제공자·문서ID가 실제 수신본에 유일하게 존재하고 원본 SHA/영수증 SHA·최초 수신시각과 일치하는 메타후보만 `inspect_release_claim`에 전달. ③ 사전에 승인된 **독립 서명 검증자**의 Ed25519 증빙을 `authenticate_publication`에서 확인한 뒤 `AnchoredOfficialPublication.as_of`로 판단 당시 자료 가용성을 검사. EraLeader 수집기·API·코드·DB·Git 쓰기 **0**.
- 증거 재사용 방지: 실제 데이터 수신본을 특정하려면 서명 명세 **`newscatalyst.publication_attestation.v2`**의 서명 대상 JSON에 `source_sha256`, `source_receipt_sha256`, `first_seen_at`을 필수 포함한다. 종전 v1(수신 원본 SHA 미결합) 서명은 **유효한 생산 증빙으로 간주하지 않으며 거절**한다. 이전 실증 중 실제 독립 서명 자료는 없으므로 기존 운영 공시 자료를 덮어쓰지 않는다.
- 역사 PIT 강제: `usable_from=max(EraLeader 첫 수신, 독립 pin 최초 관측, 증빙 검증자 시점)`. 이후 조회라도 위 시각보다 이전 결정에 증거를 소급 사용할 수 없다. 발행기관·서명 신뢰키·실제 공개시각을 발급한 독립 증빙이 없을 경우 `RawEvent`로 승격하지 않는다.
- 합성 Ed25519 키로만 정상/실패 경로를 테스트한다. 실제 독립 검증자 키 또는 법적 공식 게시시각 증거를 생성하거나 추정하지 않으며 `1_1` 완료율은 기존 조건에 따라 계속 미완료 처리한다.

- **원본 issuer 교차 검증 추가:** `OfficialCapture.source_request_value`로 기존 검증된 수신 영수증의 SEC 요청 CIK를 보존하고, 서명된 claim issuer/EDGAR 경로 CIK와 일치하는지 확인한다. URL 자기 일치만으로 다른 기업의 공시를 승인하지 않는다. 기존 EraLeader 수신 파일을 수정하거나 API를 재호출하지 않는다. v1 서명은 합성 구형 시험에만 해당하며 인증 대상에서 명시적으로 거절한다.

## 2026-10-13 | 서명 증빙 이후 PIT 소급 노출 차단 (NC-1_1-RAW-EVENT-ASOF-FIX)

- **수정 이유:** 과거 수신본에 대한 서명 증빙을 며칠 뒤 취득해도 `RawEvent.first_seen_at`이 원본 수신시각만 표시되면, 이벤트만 소비하는 외부 컴포넌트가 그 증빙을 과거 판단에 잘못 사용하게 될 위험이 있었다.
- `SignedPublication.as_of()`에서 발행 이벤트의 `first_seen_at`을 `max(원본 수신, 서명 검증자 확인시각)`으로 보수적으로 정규화한다. `AnchoredOfficialPublication.as_of()`는 여기에 **별도 로컬 독립 핀의 최초 관측시각**까지 합쳐 `max(원본 수신, 검증자 확인, 독립 pin 관측)` 이후로만 `RawEvent`를 반환한다. 호출 시점이 사용 가능 시각보다 이르면 실패한다.
- 원본 수신시각은 바꾸지 않고 `SignedPublication.source_capture_first_seen_at`에 보존하여 최초 관측과 독립 확인을 구분한다. 따라서 반환된 정식 `RawEvent.first_seen_at`은 **증빙까지 사용 가능한 시각**, 원본 수신 영수증의 실제 최초 관측은 별도 필드다. 연구용 `ObservedOfficialBatch`의 원본 `first_seen_at` 계약은 변경하지 않는다.
- 합성 서명/독립 핀의 지연 상황에서 역사 의사결정 소급 차단, JSON/데이터클래스 직렬화 시각, 원본 receipt SHA 결합 회귀 테스트를 수행했다. 실제 제3자 서명·공시 공개시각을 확보한 것은 아니므로 실제 공시 인증 완료를 주장하지 않는다.

## 2026-10-13 | 1_1 실제 증빙 최종 검증 CLI — 외부 증거 누락 시 중단

- `scripts/check_official_proof.py`를 추가했습니다. 기존 `pin_anchor → verified_reference → official_promotion` 코드를 **재사용**하며, EraLeader 공식 API 직접 호출·EraLeader 원본/코드/DB/Git 쓰기는 하지 않습니다. 기본 명령은 기존 SHA 핀·공식 수신본 5종을 검증하고, 외부 독립 서명 증빙 미제공 시 JSON 상태 `DATA_UNAVAILABLE`, `certified_raw_event_count=0`, **exit code 4**를 출력합니다. 상태가 불명확해도 성공(exit 0)으로 처리하지 않습니다.
- 사용 예: `PYTHONPATH=src python3 scripts/check_official_proof.py --era-root /Volumes/T5DATA/eraleader --reference /Volumes/T5DATA/eraleader/output/official_api_integrated_20261012/official_api_pit_research.json --anchor "$HOME/Library/Application Support/NewsCatalystOS/pins/official_api_pit_research.pin.json"`.
- 실제 증거 확보 이후에는 `--source-id`, `--document-id`, `--claim`, `--claim-sha256`, `--attestation`, `--signature`, `--witness-key`, `--witness-key-sha256`, `--witness-id`를 **한꺼번에** 별도로 승인된 신뢰 채널에서 제공해야 합니다. 일부만 제공하면 실패(exit 4). 필드는 크기 제한 및 심볼릭 링크 차단 읽기로 처리되며 내용을 stdout에 노출하지 않습니다. 검증 성공 메시지는 실제 발행기관·독립 검증자 권한/정확도에 대한 추가 인간 감사 없이 과거 최초 공개시각의 완전한 공증을 의미하지 않습니다.
- **주의:** 서명키 파일과 그 SHA를 동일 입력 자료에서 스스로 추출해 공급하면 독립 신뢰 검증이 아닙니다. 이전 외부 신뢰 등록/출처·입수시각의 감사 증거가 없는 경우 운영 이벤트로 확정하지 않습니다. 현재 실데이터에는 해당 신뢰 자료가 없으므로 1_1 전체 완료를 선언하지 않습니다.

## 2026-10-13 | 외부 서명 검증자 사전 신뢰 등록부 의무화 (NC-1_1-WITNESS-REGISTRY)
- 발견된 허점: 이전 CLI는 `--witness-key`와 `--witness-key-sha256`를 **동일 실행에서 함께 공급**할 수 있어 임의 생성한 키의 SHA를 '독립 검증자 핀'처럼 주장할 위험이 있었다.
- `witness_registry.py`는 Mac 내부 디스크의 `~/Library/Application Support/NewsCatalystOS/trust/official_witness_registry.json`을 읽기 전용으로만 확인한다. 폴더·파일 소유자 전용 권한, 소스 SSD와 다른 디바이스, 신뢰 스키마·검증자 고유 ID·허용된 SEC/DART 원천 범위·등록 시점·키 SHA를 검증한다. 신규 등록 파일/검증자 키를 **자동 생성하지 않는다**.
- 사용자 CLI의 `--witness-key-sha256` 옵션을 **삭제**했다. 검증에 사용할 fingerprint는 반드시 이전에 운영자가 승인·별도 보관한 등록부에서 로드한다. 등록 누락, 출처 범위 불일치, 등록 전 판단시점, 위조·중복·미래시각은 fail-closed. `--witness-key` 파일은 실제 서명 확인용 공개키이며 신뢰지문 출처가 아니다.
- 등록부 형식은 `{"schema":"newscatalyst.official_witness_registry.v1","trust_level":"OPERATOR_APPROVED_EXTERNAL_WITNESS","witnesses":[{"witness_id":"externally-reviewed-witness","public_key_sha256":"<independently-enrolled-64hex>","enrolled_at":"<actual-observed-UTC-ISO>","allowed_sources":["sec-submissions"]}]}` 이며, **예시값은 절대 실제 신뢰로 등록하지 않는다**.
- **증거력 제한:** 별도 디스크의 로컬 등록부만으로 외부 기관 실재·승인·서명 역사시점이 암호학적으로 공증되는 것은 아니다. 실제 운영자는 검증자 신원/발행기관·공개시각·실제 승인일을 독립 감사해야 한다. 해당 증빙이 없으므로 `RawEvent=0`, 1_1은 아직 미완료.


## 2026-10-13 | 외부 검증자 신뢰 등록 지연에 따른 PIT 차단 (NC-1_1-WITNESS-ENROLLMENT-ASOF)
- 발견한 위험: 증빙 서명시각·원본 수신·로컬 SHA 핀을 확인했더라도 **외부 검증자의 신뢰 등록이 그보다 늦으면** 등록 이전 시점에 인증 이벤트를 소급 사용할 수 없음.
- `signed_publication.authenticate_publication(..., witness_enrolled_at=...)`는 별도 독립 신뢰 등록시각을 전달받았을 때 `usable_from=max(원본 first_seen, 서명 검증시각, 신뢰 등록시각)`로 제한하고, 등록시각이 의사결정 시점보다 미래거나 시각에 시간대가 없으면 거부.
- `official_promotion` 연결 계층 및 `check_official_proof.py` 운영 CLI에서 owner-only 검증자 등록부의 `enrolled_at`을 누락 없이 전달. 나중에 등록한 키로 이전 시점의 인증 `RawEvent.first_seen_at`을 생성하지 않음.
- 변경사항은 **합성 서명/가짜 fixture에 대한 PIT 음성 회귀**이며 실제 공식 대외 공개시각이나 공신력 있는 검증자 서명을 확보한 것이 아님. 실물 `RawEvent=0`, 외부 증빙 부족 시 `DATA_UNAVAILABLE` 및 `NEXT_TASK=1_1` 유지.

## 2026-10-13 | 외부 공시 증빙 요청서 생성 (NC-1_1-PROOF-REQUEST)
- `proof_request.py`와 `scripts/request_official_proof.py`를 추가했다. 기존 독립 Mac 디스크 SHA 앵커 → EraLeader 완료된 공식 수신본 5종의 읽기 전용 검증 → **지정 공시 1건**의 공급자 ID/접수번호/원본 SHA/영수증 SHA/최초 관측시각만 추려 신뢰 검증자 확인용 JSON 요청으로 출력한다.
- `publisher_released_at`, `issuer_id`, `revision_id`, `supersedes_document_id`는 **항상 null**이고 필수 외부 증거 5종을 열거한다. 상태는 `EXTERNAL_EVIDENCE_REQUIRED_NOT_CERTIFIED`, `certified_raw_event_count=0`. 요청서는 서명/시각 공증/공식 발표 증명이 아니라 요청을 위한 메타데이터이다. 외부 발송은 자동으로 하지 않는다. 출력 JSON에도 SHA/ID 등 내부 메타데이터가 있으므로 공유 전 권한 확인.
- 실제 읽기 전용 실행 예:
  `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 scripts/request_official_proof.py --era-root /Volumes/T5DATA/eraleader --reference /Volumes/T5DATA/eraleader/output/official_api_integrated_20261012/official_api_pit_research.json --anchor "$HOME/Library/Application Support/NewsCatalystOS/pins/official_api_pit_research.pin.json" --source-id sec-submissions --document-id 0001140361-26-039158`
- SEC 실제 첫 수신본의 해당 공시와 SHA/anchor를 대조해 요청서 생성 PASS. `provider_acceptance_at=2026-10-09T02:30:32+00:00`은 **접수시각**이며 공개시각 증명이 아님. SEC 공식 설명: https://www.sec.gov/about/webmaster-frequently-asked-questions (SEC 접수 후 공개까지 지연, 정확한 최초 웹 공개시각 표시 없음).
- 이후 외부 기관/검증자가 사전 승인·서명한 진짜 증빙이 제공된 경우에만 **기존** `check_official_proof.py`에 입력하여 인증·정정/PIT 시험을 수행한다. EraLeader 수집기/키/DB/원본 및 Git 변경 금지. V1.0 1_1 승인 게이트 자체는 불변.

## 2026-10-13 | 증빙 파일 실제 입수시점 PIT 누출 방어 (NC-1_1-PROOF-ARRIVAL)
- 발견·수정: 외부 서명이 주장하는 `witness_verified_at`이 과거여도, 그 서명 파일을 NewsCatalystOS가 뒤늦게 처음 **읽은 시점**보다 이른 판단에서는 해당 증빙을 사용할 수 없다. 기존 `max(원본 수신, 로컬 SHA 핀, 서명 확인, 검증자 등록)` 사용 가능 시각에 **실제 로컬 증빙 읽기 완료시점 `proof_observed_at`**을 추가.
- `authenticate_from_era_readonly(..., proof_observed_at=...)`는 실제 파일 기반 진입점에서 시점을 필수 입력으로 요구하고, 결정시각보다 늦으면 원본 읽기 전에 거부. `authenticate_anchored_official_record`는 `usable_from`에 이 시각을 합쳐 `RawEvent.first_seen_at`도 소급되지 않도록 한다.
- 운영 `scripts/check_official_proof.py`는 증빙 파일들을 읽은 직후 현재 UTC를 로컬 최초 관측으로 찍고, `--decision-at` 미지정 시 실제 읽기 완료 시각으로 결정시각을 맞춘다. 과거 `--decision-at`이 지정되면 이후에 처음 도착한 증빙을 과거에 사용할 수 없다. 테스트용 합성 API는 기존 호출을 유지하며 실사용 래퍼만 fail-closed.
- 범위 테스트 236 PASS/0 FAIL, Python 컴파일 PASS. **로컬 시각은 외부 공시 공개시각의 인증이 아니며**, 이전부터 증빙이 존재했음을 역사적으로 공증하지 않는다. 실제 외부 발행기관 검증 증거/사전 승인 서명자는 아직 확보되지 않아 `DATA_UNAVAILABLE`, 인증 `RawEvent=0`, 1_1 미완료를 유지한다.

## 2026-10-13 | 실사용 인증 함수 직접 호출 시 신뢰 등록부 우회 차단 (NC-1_1-ENTRY-TRUST)
- 이전에는 `scripts/check_official_proof.py`가 외부 검증자 신뢰 등록부를 확인했지만, 다른 코드가 `authenticate_from_era_readonly()`를 직접 호출하면 스스로 제공한 키 SHA/등록 시각을 전달할 수 있었다.
- **실사용 파일 진입점 자체**가 owner-only 별도 디스크 `load_operator_witness(era_root, witness_id, source_id, decision_at)`를 재확인하고, 사전 등록된 검증자 공개키 SHA와 호출자 제공 SHA가 다르면 거절한다. 별도 전달된 등록 시각이 실제 등록부와 다르면 거절하고, 아래 인증 경로에는 조회된 `trusted.enrolled_at`만 전달한다. 신뢰가 확인되기 전 EraLeader 데이터 파일은 열지 않는다.
- 합성 내부 함수는 기존 API를 유지해 저수준 정합성 테스트를 보존한다. 공개된 실사용 함수의 외부 등록부 강제 검사는 누락·임의 SHA·허위 등록 시각을 원본 조회 전 차단한다. 단, 운영자 로컬 등록부 자체로 검증기관의 실제 권한이나 공식 공개시각이 공증되지는 않는다.
- 외부 독립 진짜 증거가 아직 없으므로 `RawEvent=0`, `DATA_UNAVAILABLE`, 엄격 `NEXT_TASK=1_1` 유지. EraLeader 수집기·DB·Git/원본 변경이나 공식 중복 API 호출 없음.

## 2026-10-13 | 사용자 승인: 운영 관측 PIT 우선, 독립 공개시각 인증은 선택 (NC-OBSERVED-PIT-MODERATE)
- **완료 조건 조정(D-018):** 관측된 공식 수신본의 원본·영수증 SHA 및 게시 완료/출처별 건수·품질/원본 불변을 검증하고, 실제 NewsCatalystOS 로컬 `verified_at` **이후**에만 신규 분석에 사용하면 1_1의 관측형 공유를 합격 판정할 수 있다. 과거 수신/접수시각만으로 발행기관의 최초 대외 공개시각을 인증했다고 주장하지 않는다. 기존 외부 Ed25519/검증자 신뢰 등록부/공개시각 정확 인증 모듈은 보존하되 필수 1_1 운영 게이트에서 분리한다.
- 신규 `operational_observations.py`는 기존 `read_published_observations`의 출처 완결성 확인된 **v2** 원자 게시물을 재사용한다. `available_at=max(원본 first_seen, 로컬 SHA anchor, 뉴스OS 원자 게시, **이번 소비 검증시각**)` 이후에만 `OperationalObservation`으로 노출한다. `published_at=None`, `issuer_verified=False`, `release_certified=False`, `RawEvent` 직접 승격 거절. V1 데이터와 변조/미완성 게시물은 거부. 외부 시각공증·원문 공개확인 없이 과거 백테스트에 소급하는 것은 계속 금지.
- SEC/DART 공시 메타는 `DISCLOSURE_OBSERVED` (분석 후보)로, KRX 시장데이터는 `MARKET_CONTEXT_NOT_NEWS`로 분리. DART 첫 페이지만 수신했으면 `INCOMPLETE_FIRST_PAGE_NOT_FULL_DAY`, SEC 최근 제출분만 있으면 `RECENT_SUBMISSIONS_NOT_FULL_HISTORY`를 그대로 노출한다. SEC facts taxonomy는 뉴스 행 0개이며 출처 장부에는 남는다.
- 실제 **기존 EraLeader 스냅샷 5개** 기반 NewsCatalystOS 기존 private v2 원자 게시물을 새로운 Python 소비자에서 읽어 **3,866개의 관측 메타**를 검증: `DISCLOSURE_OBSERVED=1,101`, `MARKET_CONTEXT_NOT_NEWS=2,765`, 정식 인증 RawEvent **0**, 공개시각 알려진 행 **0**, v2 출처 count **5**. 이는 실시간 5거래일 운용이나 최초 웹 공개시각 검증 실증이 아니라 로컬 SHA/PIT·읽기 전용 공유 경계 실증이다.
- 비공개 증빙/원본 SHA를 GitHub Public에 올리지 않는다. `load_operational_observations(publication, root, independently_supplied_payload_sha256)` 호출의 SHA가 같은 컴퓨터에서 즉석 생성된 경우 **로컬 일관성 검사**일 뿐 과거 시점 공증으로 보지 않는다.
