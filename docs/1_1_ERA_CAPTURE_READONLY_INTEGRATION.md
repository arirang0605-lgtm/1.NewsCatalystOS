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
