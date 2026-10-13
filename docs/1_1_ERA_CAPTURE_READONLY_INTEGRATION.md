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
