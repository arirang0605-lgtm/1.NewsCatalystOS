# NEXT_TASK — 다음에 수행할 단 하나의 작업
작업 ID: 5_2 (실물 반도체 공급망 증빙 검증; 6_1~6_4 기본 구현 완료)
제목: 검증된 EraLeader 읽기 전용 공시에서 반도체 고객·공급자 관계 근거 연결
상태: 기본 기능 23/36(63.9%) 완료. 6_5 내부 DB 백업·별도 폴더 복원 성공했으나 5거래일·독립 물리 장치 복구 미검증, 6_6 릴리스 판정 NOT_READY. 전체 테스트 611 PASS/0 FAIL, 기능 SHA 648806f.
선행 조건: EraLeader DART·SEC·KRX/PIT/SHA 고정 스냅샷 read-only, 반도체 1개 산업만 검증. EraLeader 코드·DB·Git·운영키 변경/중복 공식 API 호출 금지. 해당 원본에 직접거래 근거가 없으면 UNKNOWN.
목표: 5_2 공식 source SHA·문서 ID·고객/공급사 기업ID·PIT 출처를 실제 연결하고 직접거래/테마 주장 구분. 외부 확인 없는 직접 거래 verified_real_transaction=False 유지.
시작 시: 공식 출처의 실제 공유 가능 필드만 최소 조회하고, 검증 가능한 관계가 있을 때만 기존 supply_chain_graph.py/beneficiary_graph_contract.py에 연결. 대량 재수집·무근거 기업 추정·REWRITE 금지.
완료 조건: 관계 근거와 PIT/정정 검증 및 음성 사례 합격. 독립 증거 없으면 합성 그래프 구현만으로 완료 처리하지 않는다.
그다음 작업: 2_6·3_6 실제 검수 라벨, 4_1 실 AI, 5_6 관계 평가, 6_5 5거래일/독립백업, 6_6 릴리스 최종 인수.
V1.0 신규 기능 자동 추가 금지. 사용자가 다른 순서로 명시하면 DECISIONS 갱신 후 변경한다.


1_1 추가 안전 조건 (NC-PARALLEL-2026-10-13): EraLeader 개발이 진행 중이므로 **게시 완료된 SHA·PIT 검증 스냅샷만 읽기 전용 소비**, 원본 코드/DB/Git/키 변경 0건, 미완성 자료 읽기 차단 및 장애 격리 테스트 필수. 동일 Mac의 고부하 작업과 겹쳐 테스트하지 않는다. 현재 NEXT_TASK=1_1 유지.

## 1_1 선행 작업 추가 — GitHub Public 초기 연결 (NC-PUBLIC-REPO-2026-10-13)
- 확인된 GitHub 원격: https://github.com/arirang0605-lgtm/1.NewsCatalystOS.git (Public, main).
- 현 확인 상태: 이 폴더에 로컬 Git 미초기화; GitHub 공개 원격은 비어 있었음. 최초 개발 시 두 상태 재검증.
- 사용자 기존 폴더/문서·이미지 보호 백업 확인 후 **기존 SSD 폴더에서 안전하게 로컬 Git 생성·origin 연결**한다. 별도 클론 덮어쓰기 금지.
- 첫 stage 전에 .gitignore 및 공개 대상 허용 목록 작성; .env/인증키/유료 기사·원본 데이터/운영 DB·로그/백업/계좌정보/._* 제외. staged 파일과 실제 내용·출처 사용권 검수 후 작은 첫 커밋/푸시를 수행한다. 원격 인증이 막히면 허위 성공 보고 금지.
- Git 설정은 **새 단계가 아니라 1_1의 선행 작업**이다. 1_1 본작업(완료된 EraLeader DART·SEC·KRX 스냅샷 읽기 전용 공유 계약·PIT·SHA 검증)은 그대로 유지한다.
- 상세 지시: GITHUB_PUBLIC_POLICY.md 와 NewsCatalystOS_V1.0_CHAT_개발마스터프롬프트.md.

## 2026-10-13 | 1_1의 남은 실제 작업 (최신)
- 구현 위치: `src/newscatalystos/source_share.py` 및 `docs/1_1_SOURCE_SHARE_CONTRACT.md`; 테스트: `tests/test_source_share.py` (23개 합성 PASS).
- 현 소비자는 EraLeader의 **정식 완료된 게시 export + 독립적 SHA pin**을 요구한다. 실제 EraLeader의 `official_api_capture`에는 비공개 `first_receipt.json`/원본이 있고, 그 캡처가 본 소비자 규격으로 게시·등록되었다는 증거는 없다. 기존 API를 재호출하거나 원본 파일을 수정해 문제를 해결하지 말 것.
- 다음에는 **읽기 전용**으로 기존 EraLeader 공식 캡처 포맷(수신 영수증 SHA/원본 SHA/first_local_received_at_utc/quality)을 검증하는 공유 경계를 확정하고, 이미 원자 발행된 snapshot인지 증거를 확보한다. 필요하다면 NewsCatalystOS 소유의 **합성 테스트/변환 코드**만 추가한다. EraLeader의 Git/DB/코드/비밀을 수정하지 않는다.
- 당일 원본/영수증의 독립 SHA pin, 공개/최초 수신 시각, 게시 완료 상태, DART 날짜 정밀도 제한 및 부분 페이지 품질 확인이 불가능하면 `DATA_UNAVAILABLE` 유지. 합성 시험 PASS를 운영 성공으로 표시하지 않는다.
- 실제 게시 표본에서 각 provider 데이터 1회 이상 read-only 결과 검증·원본 SHA 사전/사후 동일·PIT 미래차단/품질실패/미완성 게시물 격리 재확인 후에만 1_1을 **1/36 완료**로 전환하고 `NEXT_TASK=1_2`로 이동.

## 2026-10-13 | 1_1 다음 미완료 게이트
- 2026-10-13 실제 오프라인 검증은 `505b073d31418713b56cc791c1d5b9257e7e2d63`에서 완료. 더 이상 존재하는 캡처를 반복 탐색하지 말 것.
- **남은 하나의 작업:** 최초 수신시각 `first_seen_at`과 원천 공개시각 `published_at`을 혼동하지 않는 공시/원천별 메타데이터 정규화 완성. 증명되지 않은 release_at은 `None/UNKNOWN`, DART 첫 페이지만 `PARTIAL`, SEC facts taxonomy는 신고 이벤트 0건 유지.
- 증거를 실제로 수집 가능한 범위에서 서로 다른 보관소에 리포트 SHA pin 보관, 과거 확정 시각이 없는 원본의 `RawEvent` 승격 차단 테스트, 기존 코드/원본 무변경 증빙, 실제 DART/SEC/KRX 승인된 event evidence 내역 검증을 완료한 뒤에만 1_1 종료.
- 외부 권한/자료가 계속 불가하면 정확히 DATA_UNAVAILABLE으로 기록하고 1_2 작업으로 완료 숫자를 부풀리지 말 것. V1.0 다른 산업 확대 금지, 전체 회귀는 단계 게이트까지 보류.

## 2026-10-13 | 실제 최신 재개점 — 1_1 남은 출처 공개시각 검증 게이트
- **직전 구현 푸시:** `73a87949c938cf01ba436b0cf82ab17845bbcd4f`; 합성 변경 영향 시험 **78 PASS / 0 FAIL**. 별도 Mac 내부 디스크 local-TOFU 핀과 EraLeader 5개 실제 캡처 재검증 PASS, 연구용 메타후보 3,866개. 원본 변경 없음.
- **중복 구현 금지:** `era_capture_share.py`의 SEC acceptance timestamp, `official_normalization.py`의 후보/승격 차단, `pin_anchor.py`의 재작성 불가능한 로컬 별도 디스크 pin은 이미 작성·실증. 같은 확인을 매번 전체 반복하지 말 것.
- **남은 핵심 한 작업:** 공식 출처별 독립적으로 검증 가능한 **대외 공개시각·정정 버전·발행자 provenance** 자료가 있는지 확인하고, 자료가 확인된 개별 기록에 한해 검증 증거에 묶인 `RawEvent` 전환 계약 구현/음성 테스트. SEC `acceptanceDateTime`은 독립된 공개시각 확증이 아니며 DART `rcept_dt`은 날짜 정밀도뿐임. 외부 증거 없으면 `DATA_UNAVAILABLE` 유지.
- **추가 제약:** 외부 신뢰 시각공증/제3자 서명은 현재 없음. 로컬 별도 디스크 핀은 생성 이후 변조 탐지용 TOFU이지 과거 PIT 인증이 아님. EraLeader 원본·Git·수집 코드를 절대 수정하지 않는다.
- **완료 전환 금지:** 정식 `RawEvent` 실물 하나 이상의 검증/명시된 범위·PIT·SHA/원본무변경 게이트 미충족. **NEXT_TASK=1_1, 완료 0/36** 유지. 외부 접근 제한이면 데이터 부족 상태를 기록하고 1_2 완료로 세지 않는다.

## 2026-10-13 | 최신 미완료 1_1 — 인증된 실제 공개시각 증거 확보
- 직전 기능 푸시: `8233fe499a5a19e8f7d9f5d13a6451d37072de24`, 1_1 관련 **105 PASS / 0 FAIL**. `release_claim.py`는 이미 별도 SHA로 묶인 정정/공개시각 주장 메타를 검사하나, 외부 진위 확인이 없어 의도적으로 `RawEvent`를 차단한다.
- **다음 한 작업:** 실제 DART 또는 SEC 공시 한 건 이상에 대해 발행기관이 대외 공개한 검증 가능한 공개시각·issuer 신원·공시 버전/정정 연결을 **외부 독립 증거**로 확보하고, 원본 최초 수신 SHA 및 결정 당시 가용 시점과 대조한다. 증빙이 없는 `SEC acceptanceDateTime`/DART 날짜·링크 문자만으로 사실 확정 금지.
- 독립 증거의 출처/검증자/실제 확보시각/저장 위치/신뢰수준 기록 후에만 별도 공식 proof 검증을 구현하여 합격 실물 `RawEvent`를 만들 것. 증거가 확보되지 않으면 `DATA_UNAVAILABLE` 유지, 1_1=미완료. 신규 DART·SEC·KRX 수집기 작성 및 EraLeader 코드/DB/운영자료 수정 금지.
- 1_1의 마지막 완료 판단은 기존 수신본 원본불변, 시간 역행·정정 오류 방어, issuer/공개시각 인증이 모두 충족될 때만 1/36으로 전환하고 1_2를 시작. V1.0 진행률 **0/36(0.0%)**.

## 2026-10-13 | 최신 1_1 실제 완료 전 마지막 외부 증거 조건
- `c744909bf4f3ead33babc9788f77e9de480ae69b` 기능 푸시/관련 **127 PASS, 0 FAIL**. `release_claim.py`는 후보 SHA·시각·정정·SEC issuer 경로 검사, `signed_publication.py`는 사전 승인된 독립 검증자의 Ed25519 서명·PIT 검사·시점별 RawEvent 접근을 이미 구현.
- **현 유일 핵심 장애:** EraLeader 기존 DART/SEC 공시 중 적어도 1건에 대해 외부 진위 검증된 공개시각·issuer·정정 연결의 **실제 독립 서명/원천 증명** 및 별도 신뢰키 지문이 없다. SEC acceptance 시각, DART 날짜, 공개 웹페이지의 사후 조회시각 또는 로컬 TOFU는 그 증거를 대체하지 않는다.
- 실제 신뢰 검증자/공식 증명 자료가 생기면 EraLeader 5개 공식 캡처의 이전 SHA anchor와 원본 불변을 다시 확인하고 `inspect_release_claim → authenticate_publication → proof.as_of(decision_at)` 실물 1건 이상 실행, PIT 과거 결정 누출/정정/중복/장애 격리 및 연동 시험을 거쳐 **1/36 완료**로 전환. 없으면 `DATA_UNAVAILABLE`, 1_1 미완료 유지. EraLeader 코드·원본·Git 및 중복 API 수집 금지.
- 다음 작업 번호를 성급히 1_2로 넘기거나 V1.0 완료율을 올리지 않는다. 이번에 완료한 것은 **서명 검증 코드/합성 테스트**이며 실제 공시 인증은 아니다.

## 2026-10-13 | 최신 1_1 진행 및 남은 최종 인증 게이트
- 신규 기능 `e5150be753323d610b1f265a93781eb662b226ab` GitHub push 검증; 합성/실데이터 연구용 경계 관련 **145 PASS / 0 FAIL**. `observed_batch.py`+ `scripts/inspect_official_observations.py`가 기존 완료 캡처 5개를 읽어 비공개 메타 3,866건을 원자 게시하고 SHA 대조 성공. 신규 재수집 0, 공식 `RawEvent` 0.
- **여전히 미완료인 1_1 게이트:** 실제 공시의 대외 공개시각·정정/발행자 진위를 외부 독립적으로 인증할 만한 신뢰된 출처 증거/서명 및 당시 가용시각 확보. `SEC acceptance` 또는 DART 접수일을 공개시각으로 변조하지 말 것. 신뢰 가능한 실물 증빙 1건 이상 획득 시 기존 `inspect_release_claim → authenticate_publication → proof.as_of` 경계에 연결하고 원본불변·PIT·정정 음성시험 통과 후에만 1_1 완료/1_2 전환.
- 외부 인증증거가 없다면 **DATA_UNAVAILABLE, 미완료 1_1, 0/36**. 반복 API 수집·EraLeader 코드/DB/Git 변경·이미 통과한 전체 테스트 중복 실행 금지. 이후 동일 SHA/상태는 `PROJECT_STATE.md` 최신 아래 기록에서 이어간다.

## 2026-10-13 | 최신 1_1 미완료 게이트 (검증된 연구 배치 소비 구현 이후)
- 직전 기능 `801db132bbb0ea0b429f5916da174966d0db34f2`: NewsCatalystOS 내 비공개 원자 게시 결과의 read-only 소비/PIT·SHA 품질 게이트 구현, **170 PASS / 0 FAIL**, 실제 EraLeader 5개 공식 캡처 기반 연구 메타 3,866건 end-to-end 로컬 재검증 PASS. 신규 API 재호출/중복 수집/다른 프로젝트 변경 없음. 기존 메타 연구 배치 및 로컬 검증 반복은 불필요.
- **남은 단일 핵심:** 기존 DART/SEC 수신본 최소 1건의 실제 대외 공개시각·발행자 신원·정정 계보를 **외부 독립 증거**로 확인하고 그 증거의 최초 가용시각·신뢰 인증 자료를 확보하여 `inspect_release_claim → authenticate_publication → proof.as_of` 실물 검증 수행. 검증된 시각 자료를 소급 생성하거나 SEC 수리시각/DART 접수일로 대신하지 않는다.
- 외부 증명이 확보되지 않는 동안 실제 인증 `RawEvent=0`·`DATA_UNAVAILABLE`, `1_1` 완료 판정 유예, `NEXT_TASK=1_1`, **0/36(0.0%)** 유지. EraLeader 공식 수집 공유 경계를 유지하며 다른 35개 단계의 순서·V1.0 완료 조건 변경 금지.

## 2026-10-13 | 최신 인계 — 1_1 실제 공개시각 증빙 미확보
- 기능 `e46b2619b337cd09fb8eec9131a5b121c9fd51ac`: 공식 공유 연구 배치 v2에 출처별 관측수·메타수·품질·원본/영수증 SHA 장부 추가. **183 PASS/0 FAIL**, 기존 공식 캡처 5종 원천 관측 3,868/메타 3,866, SEC facts 2/0 실데이터 오프라인 게시·재읽기 PASS. 이전 v1 하위호환 구현. 이미 정상인 이 경계를 중복 작성/점검하지 말 것.
- **다음 단일 핵심:** EraLeader 기존 DART 또는 SEC 수신본의 **실제 발행기관 공개시각·정정 연결·발행자 진위**를 독립적으로 검증할 증거와 실제 최초 입수시각/사전 신뢰키를 확보해 기존 `inspect_release_claim → authenticate_publication → proof.as_of`에 연결. SEC acceptance나 DART 날짜, 로컬 자체 SHA/TOFU는 외부 공개시각 인증을 대신하지 않는다.
- 외부 증거 없으면 `DATA_UNAVAILABLE`과 인증 `RawEvent=0` 유지, 단계 1_1의 엄격 완료 전환 및 1_2로 이동 금지. 현재 **0/36 = 0.0%**, EraLeader 공식 수집기 재개발·중복 수집·원본/DB/Git 변경 금지.

## 2026-10-13 | 최신 1_1 미완료 핵심 — 실제 독립 공개시각·발행자 증거
- 직전 기능 `ca804cd4aeafe717c909e90c0b56dbd7d2122a93`: EraLeader 별도 SHA anchor·실제 공식 수신본·원천 CIK→독립 Ed25519 `attestation.v2`의 raw SHA/영수증 SHA/first_seen을 결합하는 읽기 전용 계약 구현. 관련 **199 PASS / 0 FAIL**, 실제 EraLeader 캡처 5종 read-only 확인. 기존 정상 코드 재구현/중복 점검 금지.
- **실제 다음 한 작업:** 검증 가능한 외부 독립 기관/공식 발행기관의 DART·SEC 공시 최소 1건에 대한 공개시각·issuer·정정/버전 증빙, 서명 검증자 독립 신뢰키 및 증거의 최초 실제 가용시각 확보. 확보 시 `authenticate_from_era_readonly`를 통해 실제 공식 원본 SHA/CIK/PIT와 신뢰 증빙을 결합, 원본 무변경·음성/장애 시험 통과 후 1_1 최종 완료 여부 판단.
- 증거 없으면 `DATA_UNAVAILABLE`과 인증 `RawEvent=0` 유지, `NEXT_TASK=1_1`, 엄격 0/36. SEC 접수시각/DART 접수일 및 로컬 SHA/TOFU를 역사적 외부 공개 인증으로 대신하지 말 것. EraLeader의 공식 API 수집기는 그대로 두고 검증된 게시 결과만 읽기 전용 공유, 전체 36개 개발계획 불변.

## 2026-10-13 | 최신 1_1 미완료 — 외부 공식 공개 증명 확보
- 직전 보완 `78a53132ed87bb37ca6e5677348954dc002b7f53`: 서명 증빙/독립 pin의 지연 취득을 `RawEvent.first_seen_at` 사용 가용시각에 반영하도록 PIT 누출 경계 수정. 원본 receipt first_seen은 `source_capture_first_seen_at`로 별도 보존. **200 PASS/0 FAIL**, origin/main push 검증. 이미 작동하는 계약/합성 서명 검증 재구현 금지.
- **남은 단일 핵심:** 기존 EraLeader 공식 수신 캡처에 대응하는 DART 또는 SEC 공시 최소 1건의 대외 공개시각·issuer·정정 버전의 **독립 검증 가능한 신뢰 증거**와 실제 당시 가용시각 및 승인된 검증자 신뢰키 확보. 확보 이후 `authenticate_from_era_readonly`로 진짜 증거만 연결해 원본불변/음성·PIT 검증 후 1_1 완료 게이트 평가.
- 외부 증빙이 없으면 `DATA_UNAVAILABLE`, 실 인증 RawEvent 0, `NEXT_TASK=1_1`, **0/36** 유지. SEC 접수시각·DART 날짜·동일 Mac 로컬 SHA/TOFU를 공식 발표시각으로 가장하지 않는다. EraLeader 코드·DB·Git 변경 및 DART/SEC/KRX 중복 수집 금지.

## 2026-10-13 | 최신 1_1 단일 차단조건 — 실제 독립 공시 증빙 입수
- 기능 commit `72cfb61abf37a07250568a7952df05b6bc77e042`: 최종 `scripts/check_official_proof.py` 게이트 준비/실행; 관련 **207 PASS/0 FAIL**. 기존 공식 캡처 5개로 실물 read-only 검증 PASS, 서명 증거 부재에 대해 `DATA_UNAVAILABLE` / 종료코드 4 / 실제 인증 `RawEvent=0` 명확히 확인. 정상 경계 재구현이나 무한 반복 검사 금지.
- **다음 실제 필요 작업:** DART·SEC 기존 공식 수신본 최소 1건과 일치하는 외부 독립 발행기관의 대외 공개시각·issuer·정정 계보, 실제 최초 증거 확보시각 및 사전 독립 신뢰 등록된 검증자 키/서명 증거를 확보한다. 확보한 신뢰 증빙만 `check_official_proof.py`의 전체 옵션으로 검사하고 원본 불변·PIT·음성/장애·실제 정식 `RawEvent` 평가 이후 1_1 완료 여부 판정.
- 증빙을 확보할 수 없으면 `DATA_UNAVAILABLE`·1_1 미완료·**0/36** 유지. SEC 접수시각/DART 접수일/같은 Mac TOFU를 과거 대외 공개시각의 공식 인증으로 변환 금지. 기존 EraLeader 공식 API 수집기는 유지하고 NewsCatalystOS는 검증·게시 결과만 읽기 전용 공유.

## 2026-10-13 | 최신 실제 장애 — 외부 공시 발표·issuer 인증 증거
- 최신 기능 `dac46e90bd96ff15563040f54161fa56e5c31d4f`: 임의 키+자기 SHA 동시제출을 막고 독립 디스크 owner-only 검증자 신뢰 등록부를 사전 확인하도록 강화. 관련 **222 PASS / 0 FAIL**, 기존 EraLeader 공식 캡처 5종 재수집 없는 읽기 전용 확인 PASS. 실제 외부 신뢰 검증자 등록부는 자동 생성하지 않았고 신뢰키/서명/공식 공개시각 증거는 미제공.
- **다음 단 하나의 작업:** 실제 사전 독립 검증기관/발행기관에서 검토·입증 가능한 DART/SEC 1건의 공개시각·issuer·정정 연결, 검증자 실제 승인일·신뢰키 SHA 및 서명 증빙을 획득. 비공개 owner-only 독립 디스크 등록부로 진위/시점 확보 후 `check_official_proof.py`의 기존 최종 검증을 수행해 정식 `RawEvent`를 판단. 외부 증거 없으면 `DATA_UNAVAILABLE`/RawEvent 0/1_1 미완료 유지.
- SEC 접수시각, DART 접수일, 로컬 TOFU/자가 생성 서명을 과거 대외 공개 인증으로 가장하거나 EraLeader API/원본/DB/Git을 변경하지 않는다. **0/36(0.0%)**, 1_1~6_6 개발계획 변경 금지.


## 2026-10-13 | 최신 1_1 인계 — 등록 시점 PIT 보완 완료, 실물 외부 증거 대기
- 기능 `ba7f9583b056cd0c1c18e639c66e0e68b2ee9399` 원격 검증: 지연 검증자 신뢰 등록 시각까지 정식 이벤트의 최초 사용 가능 시각에 반영. **224 PASS/0 FAIL**, Public 7파일 보안검수 PASS. 이미 작성된 공식 read-only 공유/서명/등록부/게이트 재구현하지 말 것.
- **유일 실제 미완료 핵심:** EraLeader 기존 공식 수신 DART 또는 SEC 공시 최소 1건의 발행기관 공개시각·issuer·정정 계보를 실제 입증하는 독립 신뢰 증거, 공신력 있는 검증자 사전 신뢰 등록 및 서명·최초 확보 시각 확보. 등록 후 실제 `scripts/check_official_proof.py`로 전체 검증하고 원본 SHA/PIT/정정·장애 음성 시험으로 1_1 게이트 판정. SEC는 공개시각 독립 타임스탬프를 제공하지 않으므로 접수시각으로 대신하지 말 것.
- 증빙을 확보하지 못하면 `DATA_UNAVAILABLE`, 정식 `RawEvent=0`, `NEXT_TASK=1_1`, **0/36** 유지. EraLeader 변경·공식 API 중복 수집·연구용 후보의 정식 승격·무근거 완료 판정 금지. 1_2로 변경하지 말 것.

## 2026-10-13 | 다음 실제 작업 — 발행기관/독립 검증자 증거 확보
- 최신 기능 `afb9bf61d84d26782ed2f8823a6b5b3241fdf383`: EraLeader 기존 SEC 문서 `0001140361-26-039158`의 SHA·접수ID·최초 수신/앵커에 결합된 `external_proof_request.v1` 연구용 요청서 **실물 생성 성공**, 관련 **234 PASS / 0 FAIL**. 외부로 자동 발송/키 등록/공식 API 재수집 없음.
- **유일 핵심 차단:** 이 요청서를 근거로 실제 권한을 확인한 **별도 발행기관 또는 승인된 독립 검증자**가 SEC/DART 최초 대외 공개시각, issuer, 정정/버전 계보를 입증하고, 최초 증거 획득시각과 사전 검증자 신뢰 등록/서명 이력을 제공해야 한다. 실제 인수 증거는 사용자 또는 승인된 신뢰 채널에서 확보, 비밀 키/원본 Git 공개 금지.
- 실물 증빙을 제공받은 경우에만 기존 `scripts/check_official_proof.py`로 인증 + PIT/as-of/원본 무변경/정정 음성 검증 후 1_1 완료를 평가. SEC `acceptanceDateTime` 및 연구 요청서 SHA는 공개시각 독립 인증이 아님. 더 이상 동일 수신본/연구 배치 탐색, 증빙 없는 모의 완료, 추가 인증 추측 기능을 반복하지 말 것.
- 현재 `NEXT_TASK=1_1`, `DATA_UNAVAILABLE`, 실제 인증 RawEvent=0, 완료 **0/36 (0.0%)**. 다른 35개 단계 또는 반도체 산업 범위 변경 금지.

## 2026-10-13 | 1_1 최신 재개 — 실제 증빙 파일 도착시각 게이트 강화 완료
- 기능 `8f24d48cf8abd0af782962cfd5ef0dd10a306e46` `main` push 검증; `proof_observed_at`을 실제 증빙 파일 입수 완료 후에 찍어 원래 서명 확인시각으로 과거 결정을 소급 승인하지 못하도록 수정. **236 PASS / 0 FAIL**. 기존 정상 모듈/요청서 재구현·동일 EraLeader 캡처 반복 검사 금지.
- **다음 실제 한 작업은 외부 자료 확보:** 별도 승인 기관의 SEC/DART 실제 공개시각·issuer·정정 계보, 검증자 신원·사전 등록/서명 및 최초 입수시각에 대한 진짜 독립 증거를 확보한다. 승인 검증이 완료된 실물 증빙을 기존 `scripts/check_official_proof.py`로 처리하고 원본/PIT/정정·장애 시험 후 1_1 완료 판정.
- 외부 자료가 없으면 `DATA_UNAVAILABLE`, 인증 RawEvent 0, `NEXT_TASK=1_1`, **0/36(0%)** 유지; 인증 문서/시각/서명 자체 생성·중복 공식 수집·EraLeader 소스/DB/Git 변경 금지.

## 2026-10-13 | External proof still unavailable (NC-1_1-EXTERNAL-BLOCKER-CHECK)
- The Mac has no enrolled independent external witness registry and no dedicated proof inbox. Existing request_official_proof.py and check_official_proof.py are implemented; do not recreate or repeat synthetic tests without changed inputs.
- One required external action: obtain authentic issuer/publication time/correction evidence for one DART or SEC document previously captured by EraLeader, plus time-of-acquisition and independently approved witness key/signature. Then run the existing proof gate and PIT/nonmutation tests. If absent: DATA_UNAVAILABLE, NEXT_TASK=1_1, 0/36.

## 2026-10-13 | 최신 1_1 외부 독립 공시 증빙 차단 상태
- 기능 SHA `6f2ae882c2f0f5c8e1db033c49fd7da75e15a3af` origin/main 반영 검증: 직접 호출 가능한 파일 기반 인증 함수가 별도 디스크 신뢰 등록부 자체를 검사하도록 수정. 등록 누락/자가 PIN/임의 등록시각 경계 차단, **238 PASS / 0 FAIL**. 기존 서명·PIT·원본 read-only·요청서 구현 재작성 금지.
- **다음 한 작업:** 실제 사전 승인된 별도 검증기관/발행기관이 기존 EraLeader DART 또는 SEC 공시 1건의 외부 공개시각·issuer·정정 연쇄를 독립 증명하고, 최초 증빙 확보시각·신뢰 검증자 사전 등록/서명 자료를 제공해야 한다. 그때 비공개 owner-only 신뢰 등록부를 적법하게 등록하고 기존 `scripts/check_official_proof.py`로 실물 시험/PIT/원본불변·정정·장애 검사 후 1_1 완료 판정.
- 현재 신뢰 등록부·외부 증거 미확보이므로 `DATA_UNAVAILABLE`, 실제 인증 `RawEvent=0`, `NEXT_TASK=1_1`, **0/36** 유지. 자료 없는데 과거 공식 발표시각/서명/외부 신뢰키 자가 생성하지 말 것. 다른 V1.0 35단계 순서 및 반도체 검증 범위는 변경 없음.

## 2026-10-13 | **현재 유효 NEXT_TASK = 1_2** (이전 1_1 외부증빙 대기 기록은 과거 이력)
- 사용자 승인 D-018에 따라 1_1 실시간·운영 관측형 공식 공유 완료: **1/36(2.8%)**, 테스트 `281 PASS / 0 FAIL`. 공시 공식 발표시각 외부 서명은 선택적 고정밀 검증, 여전히 `RawEvent=0`, `published_at=None`; 뒤늦게 관측한 자료를 소급 사용하지 않음.
- 1_2 부분 구현 `abf396d99fea418f0d6adb2c0211964fed8b99ff`: 제공자 권한 기본 비활성화 등록부와 허가된 RSS/JSON 메타 어댑터 합성 검사 완료; 외부 허가 소스 실시간 연결/운영 데이터 검증은 아직 안 됨.
- **다음 한 작업:** EraLeader 기존 DART/SEC/KRX 외 신규 공식 정부 정책·기업 IR 또는 권한이 명확한 RSS/API 자료원 중 소스별 이용약관/보관권한을 확인하고 최소 1개 실제 라이브 메타데이터만 수집하여 새 어댑터와 결합. 과도한 법적 공증 요구 금지; 이용약관 확인 및 수집 허용 범위 내에서만 수행. 권한 확인 실패 시 무허가 호출 금지. 1_2 품질·장애 테스트 후 2/36 판정.
- 전체 개발계획 1_1~6_6, V1.0 반도체 산업 1개 검증/실 AI/5거래일 최종 운용 게이트 불변.

## 2026-10-13 | 1_2 신규 정부 RSS 1회 실제 검증 이후 남은 작업
- 중기부 공식 보도자료 RSS 실 URL, 라이선스 제공 안내 확인→로컬 맥 **1회 GET + 20개 메타 파싱** 성공. 기사 원문 저장 없이 헤더/URL/최초 관측만; 관련 전체 **282 PASS/0 FAIL**. 정책브리핑 `korea.kr` RSS는 2026-07-01 종료돼 사용 금지.
- 다음에는 기존 회사 IR 공식 RSS/공시 설명자료 및 허용된 언론 RSS/API 등 **서로 다른 신규 공급자 유형**의 실제 이용조건을 확인한 뒤, 적법한 최소 1개 라이브 검증과 신선도/오류·권한 만료 검사를 수행한다. 실제 원문 보관·API 자격증명 공개/유료 기사 크롤링 금지. 운영 스케줄러는 1_3에서 완성.
- 현재 `NEXT_TASK=1_2`, 단계완료 `1/36(2.8%)`. D-018의 외부 공개시각 공증은 선택적 고정밀 단계. 자동매매·홈페이지/추가 산업 개발 금지.

## 2026-10-13 | **최신 유효 NEXT_TASK=1_3** — 1_2 기본 운영 인수 통과
- 사용자 요청 '너무 엄격하지 않게' + D-018/D-019 적용: 1_1 SHA/PIT 관측형 + 1_2 제공자 권한·단발 RSS 메타 연계 **2/36(5.6%)**. 신규 중기부 20건·뉴스와이어 RSS 15건 실연동, 본문 저장/공시 최초 공개 인증 0. 관련 **297 PASS/0 FAIL**. 기능 `e3a28b4c0eb3669d2972daef14dc6be897b9cfe1` 원격 푸시 확인.
- 삼성물산 공식 RSS HTTP 403 및 삼성전자 뉴스룸 비상업적 이용약관은 우회 금지, **기업 IR 자동수집 비활성** 유지. 미확인 소스가 일부 있어도 허가받은 두 종류만 활성화할 수 있다는 점이 1_2의 정책 목적. RSS 보도자료와 독립 언론 확인 사실을 혼동하지 말 것.
- **다음 실제 작업 1_3:** 기존 `feed_transport.py`, `provider_registry.py`, `new_source_adapter.py` 유지하면서 소스별 별도 상태 원장/워터마크, 호출량 제한/재시도 백오프, 중복 증분 처리, 실패 시 구버전 원장 보존, PIT 음성 테스트. EraLeader 수정·중복 DART/SEC/KRX 호출 금지. 실제 운영 자동매매·홈페이지 구현 제외.

## 2026-10-13 | 1_3 기능 완료, 다음 1_4 개발 인계
- `664b30c3da9563bc07cf16cb94cb8991baf5d802`: 추가 1_3 증분 엔진 원자 상태·watermark·SHA ID 중복방지/HTTP429·5xx 백오프/403 차단·권한 재검토 복원 구현. **323 PASS / 0 FAIL**, Mac 내부 private DB 및 예약 launchd plist owner-only 검증 PASS. 중기부 20/뉴스와이어 15건 신규 메타 첫 실행 SUCCESS, 직후 두 소스 `NOT_DUE` 추가 GET 0. 백그라운드 스케줄 미활성.
- **현재 완료 3/36 (8.3%), NEXT_TASK=1_4.** 1_4에서 `published_at` 미확인/수신·검증 완료시각·판단시각의 분리, 기업 ID/심볼/공시 정정 매핑의 신뢰 수준, 기존 SourceManifest/OperationalObservation/FeedObservation 공통 스키마와 PIT를 구현. 가짜 issuer 확정·공시 공식 발표시각 추정/소급 사용·EraLeader 수집기 중복개발 금지.
- 1_2 제공자/1_3 원장 재작성·증명 없던 공시 외부 서명 강제화·추가산업 도입 금지. V1.0 최종 5거래일 운영/복원은 별도 추후 인수 게이트이며, 실제 수집 launchd는 아직 활성화되지 않았음.

## 2026-10-13 | 최신 유효 NEXT_TASK=1_5 — 1_4 운영형 정규화 완료
- `c6406375654928e7fc380bccb9f729cc6d9f79cc` GitHub 기능 푸시 검증. 기존 공식/신규 RSS 공통 `NormalizedEvent`, UTC/PIT 시점·기업ID namespace/검토 증빙 SHA 및 명시 정정 참조 구현. 실제 공식 스냅샷 5종/3,866 메타 read-only 정규화, **345 PASS/0 FAIL**, 사용 불가 발표시각·매핑·정정 추정 0. 전체 기본 **4/36(11.1%)**, 정식 서명된 RawEvent 실물 0.
- 다음 한 작업 **1_5**: 이미 허가된 신규 RSS/API 메타와 수신 영수증의 원본/메타 SHA를 NewsCatalystOS 전용 private 디스크에 안전 원자 게시·이력 불변 검증. 원문 저장은 명시 권한이 있는 소스만; 보도기사/유료 원문 자동 보관 금지. 정정본은 새 버전 ID·SHA와 `supersedes`로 별도 추적. 기존 EraLeader 공식 첫 수신본은 외부 원본으로 그대로 두고 재수집/수정 금지.
- 정상 동작 중인 1_1~1_4 재작성, 허가되지 않은 뉴스 본문 저장, 장기 자동실행/회사 ID 추측/미검증 공개시각 인증·다른 산업 확대 금지. 전체 V1.0 개발 계획 36개와 단일 반도체 산업 검증 기준 유지.

## 2026-10-13 | **현재 유효 NEXT_TASK=2_3** — 36단계 연속 개발 요청 중 마지막 실제 체크포인트
- 기능 `e88351664aabc7e49ec18469ca757b06f87f06c7` 원격 GitHub main 푸시·SHA 일치 확인. 1_5 원본·영수증 SHA 원자 private 버전/정정, 1_6 새로 수집할 소스의 누락·오류 PENDING/회복 확인, 2_1 텍스트·URL 정규화, 2_2 SHA 인덱스 NEW/DUPLICATE/REVISED 처리. 기존 포함 전체 **396 PASS / 0 FAIL**.
- **엄격 진행상태:** 1_1~1_6 + 2_1/2_2 총 **8/36(22.2%)** 완료; 2_3부터 **28단계** 남음. 다음 작업은 같은 사건의 제목·숫자·기간/정정 업데이트를 유실 없이 묶는 2_3 그룹핑, 다음 2_4 루머, 2_5 출처 독립성, 2_6 라벨 평가. 유료원문/비밀/API 중복 수집 금지.
- 이 채팅에서 백그라운드 자동개발을 개시하거나 36/36 완료를 약속한 사실 없음. 실 데이터 라벨셋·반도체 공급망 검증·외부 API/5거래일 운용이 필요하면 해당 게이트를 PASS 하지 않는 한 완료를 주장하지 않는다.

## 2026-10-13 | 최신: 16/36(44.4%), NEXT CODE=4_1, 2_6·3_6 GOLD 대기
- 완료 기능: 2_3~2_5 및 3_1~3_5 기본 코드. 기능 SHA `3bcdbc7990bca606ba1bad93bb965d3b03c4246c` / `f3d8230bf1a32256ae8b6509deef81af04bb53b5`; 전체 관련 **481 PASS / 0 FAIL**, 컴파일/공개보안 PASS.
- 미완료 평가: 2_6은 독립 검수 뉴스 라벨 precision >=95%, 3_6은 중요 사건 gold recall >=90% **실제 데이터로 재검증 필요**. 현재 점수 계산기와 SHA 이력은 작성됐지만 실증 PASS 아님.
- **다음 구현 가능 작업 4_1:** 외부 AI 공급자간 공통 JSON·비용·시점 계약/오류 fail-closed 인터페이스 구현 후 실제 승인 모델/비공개 API 키/호출비용 연동. 승인되지 않은 유료 호출·출처 본문 전송 금지. 4_1~6_6 18개 기능과 미완료 평가 2개, 총 잔여 20/36.
- EraLeader 읽기전용/중복 DART/SEC/KRX 수집 금지, V1.0 단일 반도체 산업, 5거래일 운영·복원/P0·P1 미해결 0/릴리스 태그 조건 유지. 백그라운드 자동 코딩/36완료를 주장하지 않음.

## 2026-10-13 | 최신 정확한 완료 19/36(52.8%), 다음 독립 코드 작업 6_1
- 기능 SHA `80f8c838445c4954b703242415a8eb5ab5cf196f` main 푸시 검증. 4_1~4_6 AI 메타/예산 경계, 5_1~5_5 반도체 taxonomy·공급망 후보/JSON 코드 구현. 전체 pytest **566 PASS/0 FAIL**·compile/공개보안 PASS. **4_3·4_4·5_1 기본 기능 3개만 완료 카운트 추가**, 나머지 실호출/골드/실사례/소비 연동은 미완료.
- **미완료 17개:** 2_6 정밀도 95%·3_6 탐지율 90% 실제 골드셋, 4_1 API 실제 키/모델, 4_2 95% 라벨, 4_5 실제 원문·출처 100% 사실 검증, 4_6 실제 비용/500건 라벨, 5_2~5_5 실제 공급망 거래·EraLeader 소비, 5_6 실제 반도체 사례 95%, 6_1~6_6 기능·실운영/복원/태그. 실 데이터 없는 단위 테스트로 완료 카운트 추가 금지.
- **다음 구현 가능 작업 6_1:** DETECTED→CONFIRMED→STRENGTHENED/WEAKENED→INVALIDATED·재활성화의 검토 기반 불변 상태전이와 PIT/근거 SHA, 재활성화 시 과거 이벤트 보존. 기존 detection_history.py/claim_boundaries.py 재사용, 미확인 보도자료를 자동 CONFIRMED로 승격시키지 않는다. 그 다음 6_2 캐시, 6_3 변경 원장, 6_4 출력 연동 코드. 실제 5거래일 자동 운영은 별도 게이트.
- 비공개 API 키/Git 공개·운영DB 공개/유료 원문 저장·EraLeader 수정·중복 공시 수집·추가 산업·자동매매/홈페이지 금지.

## 2026-10-13 | 최신 6_1~6_6 체크포인트 — 다음 실제 작업 5_2
- 기능 SHA 648806f6984e3ef6a1d7bf25114cbc49d6f334db origin/main push 확인. 6_1 사건 불변 상태 전이/재활성화, 6_2 변경감지 AI 캐시, 6_3 감사 SHA·PIT 원장, 6_4 버전 JSON/Parquet 소비 계약 기본 구현 완료. **611 PASS/0 FAIL**, 컴파일 및 공개보안 검사 PASS. 6_5 Mac 내부 private 실 원장 45,056 bytes의 독립 경로 백업/복원 SHA 시험 통과(별도 물리 저장장치 아님). 6_6 release readiness 23/36 입력 결과 NOT_READY/missing 13/exit 4, 정식 v1.0 태그 생성 안 함.
- **현재 엄격 완료 23/36(63.9%).** 미완료 13: 2_6·3_6 실측 gold, 4_1/4_2/4_5/4_6 실제 모델·정확도·청구, 5_2~5_6 공식 반도체 공급망 관계 실증·정확도·EraLeader 연동, 6_5 독립장치 DR·5거래일, 6_6 릴리스 인수. 합성 테스트로 이 13개를 완료 판정하지 않는다.
- **다음 5_2:** 기존 EraLeader DART/SEC/KRX SHA/PIT 검증 스냅샷의 데이터 범위 안에서 반도체 고객·공급자/제품·거래 증거를 읽기 전용으로 확인하고, 실제 문서·기업 식별자가 확인된 관계만 supply_chain_graph에 반영. 공식 자료에 관계 근거가 없으면 UNKNOWN 유지; 새 공식 DART/SEC/KRX 수집·EraLeader 데이터 수정 금지.
- 뒤이어 검증 가능한 반도체 관계에 한해 5_3~5_5 실제 경로·외부 소비, 5_6 독립 라벨, 2_6·3_6 사람 라벨, AI 실공급자/비용, 6_5 운영·DR을 진행한 뒤 6_6 전체 릴리스 최종 확인. 백그라운드 자동 개발 시작/365일 학습/사용자 몰래 유료 API 호출 금지.

## 2026-10-13 | 5_2 문서 검토 경계·2_6/3_6 골드 검토 입력 통합
- 5_2 공식 메타 관측→별도 SHA 고정 공시 본문/사람 검토 관계 후보 경계 추가. 기능 `f10e167c7dc6246afbf3533489f25473936ed70a` origin/main 푸시. 관련 29 PASS/0 FAIL, Python compile 및 staged 공개 보안 검사 PASS. 실제 공급망 독립 검증 관계 0건으로 5_2 실증은 미완료.
- 기존 GitHub 독립 브랜치 `feature/gold-review-intake-20261013`의 2_6/3_6 이중 라벨·PIT 정답셋 입력 모듈을 SSD main에 안전 통합, `bdd50c119b45bbd7bcf73f0be05fc9f542d8e6fe` origin/main 푸시. 관련 기존 테스트 29 PASS/0 FAIL. 새 모듈 전용 실라벨 테스트 및 500건 독립 평가 미실시, 2_6·3_6 완료 아님.
- **현재 완료 23/36(63.9%), NEXT_TASK=5_2 실자료 독립 검증**. 실 AI 공급자/500건 gold/반도체 계약 관계/5거래일 운영·독립 물리 복원/릴리스 태그 미완료. 사용자 기존 미추적 도면·문서 보존, EraLeader 코드·DB·Git/공식 API 중복 수집 없음.

## 2026-10-13 | 2_6·3_6 골드 검토 입력 자동 테스트 보완
- `tests/test_gold_review_intake.py` 9개 신규 시나리오 추가: 2인 합의/불일치·누락, source SHA/예측 SHA, 검토/PIT 미래 차단, 중요 사건 제외, 500건 합성 라벨과 인증 구분. 최초 테스트 2건의 fixture 기대 조건 수정 후 관련 26 PASS/0 FAIL, Git diff --check PASS.
- 기능 커밋 `5bf22318efcf9a5d22a45a5fd9826596a5ba82c8` origin/main 푸시 성공. 실제 독립 검수 gold 500건은 0건, 반도체 공식 공급망 실거래 검증 0건. 2_6/3_6/5_2 완료 승격 없음.
- **엄격 완료 23/36(63.9%), NEXT_TASK=5_2** 실제 허가 공식 공시 본문·회사 역할 증빙 확보 후 읽기전용 검증. EraLeader 원본/수집기·DB·Git 무변경. 실제 AI/5거래일 운영·별도 물리 복원은 미완료.

## 2026-10-13 | 5_2 공식 공급망 관계 기업 식별자 안전성 보완
- `official_relation_review.py`에서 DART→DART_CORP, SEC→SEC_CIK로 공급자·고객자 모두 동일 공식 네임스페이스를 요구. 교차/잘못된 네임스페이스 합성 음성 테스트 추가, 영향범위 **24 PASS/0 FAIL**, git diff --check PASS.
- 기능 Git SHA `d920008651089483662e6e61f605353a477274d5` origin/main push 검증. 실제 문서 본문 독립 SHA/공급망 계약 실증은 여전히 0건. **완료 23/36(63.9%), NEXT_TASK=5_2 실물 공식 반도체 관계 검증**. EraLeader 쓰기/중복 공식 수집 0.

## 2026-10-13 | 5_2 공식 관계 문장 오탐 억제
- `official_relation_review.py`에서 기업명 안의 supplier 단어를 관계 동사로 오인하지 않게 분리, 계약 부정·무관계 문구 거절, 광범위 제조/테마 단어 축소. 관련 합성 음성 검증 포함 **25 PASS/0 FAIL**, Git diff --check PASS.
- 기능 `22fa470fce0024d49b8702dd97210391e7be8546` origin/main push. 관계 증빙 본문·외부 pin/독립 검토 실사례는 미확보. **완료 23/36(63.9%), NEXT_TASK=5_2 실제 공식 공급망 문서 관계 검증**. EraLeader 원본·DB·Git/공식 API 중복 수집 0.

## 2026-10-13 | 5_2 추가 부정형 관계 오탐 차단
- 공급하지 않음/계약 없음 등 한·영 부정 문구가 직접 공급관계 후보로 승격되지 않도록 5_2 검토 경계 보완. 신규 음성 테스트 포함 관련 **26 PASS/0 FAIL**, Git diff --check PASS.
- 기능 Git SHA `99fe9e97aed7ed191e59d2cd96922e22e834d654` origin/main 확인. 실제 반도체 공식 공급계약 본문 독립 검수 0건, **완료 23/36(63.9%), NEXT_TASK=5_2 실제 증빙 수집·검증**. EraLeader 코드·DB·Git 및 중복 API 호출 없음.

## 2026-10-13 | 5_5 수혜 그래프 관계 검토/PIT 무결성 강화
- `beneficiary_graph_contract.py`에서 미래 관계 검토시각, available_at > last_reviewed_at, 잘못된 관계 종류, 공식 문서 검토 상태의 문서 SHA/검토 SHA 누락을 거부. 관련 테스트 **29 PASS/0 FAIL**, git diff --check PASS.
- 기능 Git SHA `be2f2806a40870ad8e5d27a3b80bf8b830d2d067` origin/main 반영 확인. 5_5 실제 EraLeader 소비 연동/5_2 실거래 관계 증빙은 미완료. **23/36(63.9%), NEXT_TASK=5_2 실제 공식 반도체 공급망 관계 실증**. EraLeader 소스·DB·Git·공식 API 중복 수집 0.

## 2026-10-14 | 5_5 테마 관계의 공식 거래 증거 가장 차단
- 공식 문서 검토 상태(`RELATION_STATUS`)가 단순 테마 관계(`THEMATIC_ASSOCIATION`)에 결합되면 BeneficiaryGraph 생성을 거부. 관련 테스트 **30 PASS/0 FAIL**, git diff --check PASS.
- 기능 Git SHA `4d658973948fa793c02f8cf63f0fc9b9d5cbcd71` origin/main 확인. 실제 공급망 관계 본문·독립 검토 및 EraLeader 실소비 미완료. **23/36(63.9%), NEXT_TASK=5_2 실제 공식 반도체 공급망 관계 실증**. EraLeader 원본·Git/공식 API 중복 수집 변경 0.

## 2026-10-14 | **현재 유효 NEXT_TASK=5_2 공식 반도체 관계 실물 확인** (신규 파일 입력 경로 준비)
- 기능 `c189f632b9f7178629dfb7e53d5dc37f1650e2a1` origin/main 반영 검증: 완결 v2 공식 관측 메타 + 운영자 개인 폴더의 인적 검토 JSON + 접근 허용된 공식 텍스트 + 별도 SHA PIN을 오프라인으로 결합하는 `official_relation_intake`/CLI 신규 구현. 첫 로컬 검증 완료 전 PIT 소급 금지. 6개 관련 테스트 **81 PASS/0 FAIL**, 컴파일·Public 보안 검사 PASS.
- **다음 실제 작업:** 기존 EraLeader 완료된 DART/SEC 공시 메타에서 공시 ID 1개를 선택하고, 외부 승인 경로로 해당 **실제 공식 제출 본문/명시 공급사·고객사 관계 문장/양사 공식 식별자**를 권한 있게 확보하여 별도 SHA·첫 관측·사람 검토 영수증을 만든다. 실제 자료가 확보되면 `docs/5_2_OFFICIAL_RELATION_REVIEW.md`의 신규 `scripts/review_supply_relation.py`로 SHA/PIT/부정 검증하고, 5_3→5_5 기존 그래프·표준출력 소비를 시험한다.
- 현재 완료 **23/36(63.9%)**, 실제 독립 반도체 공급계약 검토 0건. 공개시각 공증/실거래 수행/수혜 확정은 계속 별도. 실물 자료 부재 시 `DATA_UNAVAILABLE`를 유지하고 **동일 형태 합성 가드 반복 구현보다 실제 허가 자료 확인·5_6 독립 라벨/4단계 실 AI/6_5 운영**에 집중. 기존 EraLeader 코드·DB·Git·중복 공식 API 수집 절대 금지. 실제 5거래일 운영 및 릴리스 36/36 주장 금지.

## 2026-10-14 | **NEXT_TASK=5_2 실제 공식 문서 검토** — 1,101건 실데이터 검토 큐 구축
- 신규 `official_review_queue.py`/`scripts/build_official_review_queue.py`가 SHA/PIT 검증된 완결 게시본 v2에서 **DART 100·SEC 1,001 공시 메타** 작업목록을 Mac 개인 `output/`에 원자 게시, SHA 재검증·단일 공시 ID 선택 PASS. 정렬은 문서ID 순, 반도체/공급거래 관련성은 모두 `UNKNOWN_UNSCREENED`; 본문, 계약·매출 증거 없음.
- 변경 코드 SHA `070a8688020e4d1876b3b28f4ed8de0110ca540a`, `origin/main` push 확인. **93 PASS/0 FAIL**, 컴파일·Public 보안검사 PASS. 사용법: `docs/5_2_OFFICIAL_REVIEW_QUEUE.md`; 입력 및 증거 연결: `docs/5_2_OFFICIAL_RELATION_REVIEW.md`. 큐 private 데이터는 Git에 올라가지 않음.
- **다음 실질 작업:** 큐에서 반도체 관련 가능성이 있는 실제 공식 문서 ID를 운영자 검토로 고르고, 접근권한 확인 후 해당 공시의 공식 본문과 양사 DART_CORP/SEC_CIK 매핑·관계 문장·독립 PIN/첫확보 시각을 별도 비공개 경로로 준비. `scripts/review_supply_relation.py`에서 실물 1건을 검토하고 기존 `SupplyChainEdge`→5_3/5_4/`BeneficiaryGraph` 소비 및 5_6 평가 입력으로 연결. 소스 본문에 없다면 UNKNOWN, 새 DART/SEC/KRX API 수집 금지.
- 실제 인적 검수 계약·AI API 키/호출·500건 gold·5거래일/물리 복원 미완료. **23/36(63.9%)**, 5_2/36 승격 보류. 원천 부재 시 동일 합성 경계 테스트/부정어 추가보다 합법적 실증 데이터 또는 다른 미완료 기능 구현을 우선. V1.0 완료/릴리스 태그 무근거 보고 금지.

## 2026-10-14 | 현재 유효 NEXT_TASK=5_2 실관계 증거; 병행 가능 다음 개발=6_5 운영 인계
- 기능 `871c34721e6f4ec85b262ec8f4a5f8d8e87297b8` origin/main 반영·대조 성공: 수집된 허가 RSS 응답을 **추가 GET 없이** 기존 2_1/2_2/2_3/2_4/3_5 모듈에 연결, 개인 output SHA 게시. 실수집 중기부 20건/뉴스와이어 IT 15건, 신규 문서 ID 0, 제목상 반도체 키워드 0, AI 0, 실제 수혜/공시 거래 확정 0. 변경 영향 **65 PASS/0 FAIL**, compile/Public 검사 PASS. 최초 2_2 색인 등록은 신규 경제사건과 혼동 금지. 1_3 SQLite 제목·기사 본문 비저장 유지.
- 5_2 실제 원본 점검: 이전 EraLeader 공식 DART 완료 캡처 표본 100건 제목에 명시 공급계약/수주/증설 항목 없음(이 범위를 넘어선 부재를 뜻하지 않음). 5_2 실제 공식 공시 본문+계약 양사 기업식별자·관계문장·최초확보시각을 허가 경로로 확보하면 **기존** `review_supply_relation.py`를 호출해 5_3~5_5와 연결. 신규 DART/SEC/KRX 직접 수집 금지, 원천 없으면 UNKNOWN 유지.
- **다음 가능한 기능 개발:** 6_5 승인 RSS의 실행 결과를 지속 운영 인수 증거로 별도 기록하고, 1_3 수집 성공 후 2~3단계 분석이 실패해도 후속 수동 재처리 가능한 안전한 로컬 복구 경계 개선. 기존 기능/테스트를 재작성하거나 동일 인공 공급계약 가드만 반복하지 말 것. 5거래일 자동 운영 실제 달성·실모델 연동·독립 물리 복원·500건 gold는 미완료. 완료 **23/36(63.9%)**, tag 보류.

## 2026-10-14 | **NEXT_TASK=6_5 실제 운영 영수증 누적/DR; 5_2 공식 계약 증빙 별도 대기**
- 신규 운영복구 기능 SHA `6b2255d3e0207e93afc93ba819ba498576e61cdb` origin/main 검증: 승인 RSS 후속 triage용 메타 원자 checkpoint **수집 성공 커밋 이전** 기록, SQLite 원장에 반영된 checkpoint만 재처리(추가 HTTP=0), triage SHA 원자출력 뒤 별도 ACK 및 실행 일자 현황 조회. 연결 변경 영향 **76 PASS/0 FAIL**, compile/Public 보안 PASS. `run_feed_triage.py --replay-only`/ `check_feed_operations.py` 사용법은 `docs/6_5_FEED_RECOVERY_RUNBOOK.md`.
- 실제 Mac에서 중기부 추가 요청은 **`NOT_DUE`** (1_3 제한 정상 적용), 무네트워크 복구 조회 `NO_PENDING_REPLAY` (기존 미처리 없음), 승인 소스 2/신규 성공 ACK 0/미처리 0; 이번 호출로 5일 기록을 발급하지 않았다. 도입 이전 35 RSS 메타를 과거 성공 ACK로 소급 변조하지 말 것.
- **다음 실제 동작:** 기존 허가된 제공자의 정상 호출 가능 시각 이후 1회 실행하여 신규 6_5 checkpoint→수집 watermark→triage SHA→ACK 완성, 실패 시 `--replay-only`를 우선 사용하고 제어된 장애주입/실복구 기록 점검. 장기 예약 자동 활성화·5거래일 완료 주장은 실제 관측 전 불가. 내부 Mac와 별도 물리 장치 간 백업·실복원/휴장 구분/일간 보류율도 최종 6_5 인수에서 시험. 5_2는 실제 공식 반도체 공급관계 문서·검토 기업 ID가 확보되기 전 UNKNOWN.
- **완료 23/36 (63.9%) 유지**, 13 미완료 단계 기존 판정 불변. 다음 독립 작업은 6_5 실운영/DR 또는 실 AI 공급자 승인/4단계, 골드 평가 자료 확보. EraLeader 코드/DB/Git·공식 API 중복 수집·자동매매/홈페이지 금지.

## 2026-10-14 | 최신 NEXT_TASK=6_5 남은 실제 운영일 누적; 5_2 실공시 계약증거 별도 대기
- 기능 `31a1ba7d3702f2efbed32beccd3886a376b76a3a` origin/main 반영 확인: Mac 내부 `disk3` ↔ T5DATA `disk6` 실제 물리적으로 다른 저장장치 간 RSS 원장/중복 인덱스 SQLite **2개 온라인 백업→SHA/SQLite 새 폴더 복원 PASS**, 별도 Mac owner-only PIN 저장 **2개→나중 PIN cold restore 2개 PASS**. 영향범위 **52 PASS/0 FAIL**, 컴파일/Public 보안검사 PASS, 비공개 `.local_backups/`의 DB·백업 Git 게시 0.
- **현실 운영 증빙 2026-10-14:** 승인된 중기부 RSS 20건+뉴스와이어 IT RSS 15건 단발 처리 후 원장 ACK 2, 모든 승인 소스가 동일 날짜 완료 1일치. **신규 경제사건/AI/확정 수혜 0**, 남은 미처리 0. 자동 launchd 실행은 아직 시작하지 않음. `check_feed_operations.py`은 실제 거래소 세션 검증 전 `verified_exchange_trading_days=0` 및 `five_trading_day_operation_certified=false` 고정. 이 결과를 5일 성공으로 소급하지 말 것.
- **다음 실질 작업:** 기존 허가 RSS의 정상 호출 시각 이후 중복 요청하지 않고 6_5 분석/완료 영수증을 추가 실제 일자에 누적하고 출처 신선도·오류·재생/중복·복원 상태를 점검한다. 5개 실제 거래일의 결측 없는 검증 완료 시에만 최종 인수를 평가. 별도 Mac+SSD 동시 장애 대비 오프사이트 보관은 미검증. 범위 확장·인증 없는 사실 승격·EraLeader 코드/DB/Git 수정 금지. 5_2 허가 공식 공급계약 본문/양사 기업 ID가 준비되면 기존 5_2 review CLI로 검토; 실자료 없으면 UNKNOWN. 2_6/3_6/4_1~4_6/5_6·6_6 인수 증거도 미완료.
- 사용법 `docs/6_5_FEED_RECOVERY_RUNBOOK.md`. 복구 확인 `scripts/check_physical_recovery.py` 기본 2개 DB; `--verify-pin`은 신규 API·수집 없이 저장된 Mac 개인 SHA PIN에서 복원. **완료 23/36(63.9%)**, v1.0 출시 tag 보류.

## 2026-10-14 | 최신 NEXT_TASK=6_5 실제 운영일 누적 및 5_2 공식 계약 증빙
- 기능 Git SHA `dd8f9facf6f10466f8882e7deb215d2816c5a332` origin/main 확인. 맥북/T5DATA 서로 다른 저장장치의 SQLite 2개 독립 백업 SHA PIN을 기존 `check_feed_operations.py` 운영 상태에 연결, `independent_physical_recovery_verified=true` 실제 관측. 오프사이트 백업/연속 5거래일·출시 조건은 별도 미검증.
- 2026-10-14 승인 RSS 2종 각각 실관측 완료 ACK 1건씩, 모든 승인소스 성공 날짜 **1일**; 과거 데이터 소급 완료 처리 금지. 변경 영향 테스트 55 PASS/0 FAIL. **전체 23/36 (63.9%)**.
- 다음: 승인 RSS의 기존 호출/권한·백오프를 그대로 쓰는 가벼운 **실사용 정기 실행 경로** 연결, 5거래일 실제 ACK 누적/오류 기록·중단·복구 및 원본 보존 검증. 단발 기능 완성 반복보다 실운영 우선. 동시에 실제 반도체 공식 공급관계 원본 확보 때만 기존 5_2 검토 함수로 연결, 확인 못한 사실은 UNKNOWN 유지.

## 2026-10-14 | 최신 NEXT_TASK=6_5 실제 정기 운영 누적; 5_2 실물 공식 공시 증거
- **실사용 기능 Git SHA `d154a280065a531cc54017663ac8f51af24be644` origin/main 반영:** Mac 사용자 launchd `com.newscatalystos.triage`로 명시 기승인 RSS 2종만 매 3,600초 `run_scheduled_triage.py --once` 실행. 실물 `plutil lint OK` + `bootstrap` + `kickstart` 1회 `last exit code=0`, 로그 양쪽 정상 처리/실패0. 코드 변경영향 **75 PASS/0 FAIL**, Python 컴파일/Public 검사 PASS. 기존 `com.newscatalystos.incremental` 중복 스케줄러 활성화 금지.
- **다음 운영:** 5개 실제 거래일 중 **2026-10-14 단일 날짜만 증거 확보**. 이후 `PYTHONPATH=src python3 scripts/check_feed_operations.py` 로 ACK/양 소스/미처리/상태/실제 PIN 확인하고 stderr 및 Mac·T5DATA 마운트 상태 관찰; 필요하면 기존 `--replay-only`로 무네트워크 장애 복구. Mac sleep/SSD 분리·제공자 권한 오류는 자동 완성으로 보고하지 않음. 다른 프로젝트 API 중복 수집 및 자동매매/홈페이지 없음.
- 다른 미완료 5_2 실공식 반도체 계약 본문/양사 공식 ID는 실제 증거가 확보될 때 기존 offline `review_supply_relation.py`로 검토. AI 실제 모델/독립 검수 gold 및 6_6 최종 인수 조건 대기. **완료 23/36(63.9%)**, 6_5/36 릴리스 완료 판정 금지. 현황/안전 중단 문서 `docs/6_5_SCHEDULED_TRIAGE_OPERATIONS.md`.

## 2026-10-14 | 최신 NEXT_TASK=5_2 실제 공급사·고객사 증거; 6_5 실운용 날짜 누적
- 기능 Git SHA `692850de780e0e0af2032371854f7bd307f280f3` origin/main 검증. 기존 승인 RSS 1_3→3_5 완료 ACK 메타를 SHA/원장/PIT 재검증해 **FTS5 제목 검색** 가능. 실제 승인 RSS **35개 고유 제목/완료 ACK 4건** 색인, `기업` 조회 상위 5건, `반도체` 검토 후보0; 네트워크/AI/공식 API 중복 호출0. 영향 pytest **66 PASS/0 FAIL**, 컴파일·Public 검사 PASS. `docs/2_1-6_4_NEWS_TITLE_SEARCH.md` 참조.
- **다음 구현 우선순위:** 이미 가동된 1시간 launchd는 유지하되 실 실제 **5개의 거래소 세션**에 대한 ACK/오류/복구 실증을 누적한다. 병행하여 **반도체 한 산업의 실제 공급사–고객사 공식 관계 문장·두 기업 ID·독립 SHA/최초 입수 시각**을 승인 경로로 확보한 뒤 기존 `review_supply_relation.py`로 5_2 실증하고 5_3~5_5 소비 계약에 연결한다. 데이터 없으면 UNKNOWN이며 동형 가드/합성 점검만 반복하지 말고 공급망 분석 기능 구현에 집중한다.
- 실제 공식 문서 검토 관계 0, 제공자 AI 실제 비용·500 독립 gold/수혜 정확도·오프사이트 및 6_6 릴리스 미완료. `23/36(63.9%)` 유지, 사용자 미추적 도면·EraLeader 원본 코드/DB/Git·DART/SEC/KRX 재수집 금지.

## 2026-10-14 | 최신 NEXT_TASK=5_2 실제 공식 거래관계 1건 인수; 6_5 실제 운용일 누적
- **기능 SHA `0e95762c4a12fdfdfa804292df775a86e6fa5abe`** 원격 main 검증. 완료된 DART/SEC v2 공시 메타 + 운영자 별도 공식원문 SHA/PIT 및 양사 공식 식별자 검토가 있으면, 5_2→5_3→5_4→5_5를 하나의 CLI로 실행해 비공개 outbox에 결과를 SHA 원자 게시하고 미지정 후속 프로젝트가 별도 SHA로 읽을 수 있는 기계판독 `candidate_edges` 전달 기능 준비. 테스트 **115 PASS/0 FAIL**/컴파일/공개 보안 PASS, 합성 fixture 별도 소비 프로세스 성공.
- **실제 5_2 공식 실물 증거는 아직 0건**(기존 공시 메타 1101건은 본문 미보유)이라 운영용 관계 후보 발행/실프로젝트 소비/매출·주가 수혜 확정은 미완료. 다음: 합법적으로 확보된 해당 공식문서의 원문·출처/최초 확보·별도 SHA·공급사/고객사 ID·검토 문장을 비공개 저장한 후 `scripts/publish_reviewed_beneficiaries.py`로 **실물 1건** 접속; 기존 `consume_reviewed_beneficiaries.py`로 사실성/오류/출력 인수. 증빙 없으면 UNKNOWN, 새 DART/SEC/KRX 수집 절대 금지.
- Mac 승인 RSS 1시간 launchd/뉴스 검색 기능 유지, 6_5 실제 **5개 거래일** 기록/복원 점검 병행. 현재 **23/36(63.9%)**, 6_6 태그 금지. 상세 `docs/5_2-5_5_REVIEWED_BENEFICIARY_DELIVERY.md`; 다른 프로젝트 연결 대상 정해지기 전 자동 수정·Git 푸시 금지.

## 2026-10-14 | 최신 NEXT_TASK=5_2 실반도체 공식 관계 원문 확보; 6_5 실운영 병행
- 기능 `18144a5fa77fcfd6e1b5824956f1a7e0ca134e90` origin/main 확인: 검증된 v2 + **EraLeader 기존 DART/SEC raw 첫 수신본의 Mac 별도 SHA 앵커**를 읽기 전용 병합하여 `build_official_review_queue.py --with-pinned-issuer-context` 추가. 기업명/기업코드·공시 제목/제출 Form 필터로 **실제로 SEC Apple 10-Q 33건**, DART `계약` 제목 1건 선별 성공. 후자는 주식 양수도 계약으로 **반도체 공급 계약이 아님**. `109 PASS/0 FAIL`, 컴파일/Public 검사 PASS, 공식 API 새 요청/EraLeader 쓰기0. 기존 IDs-only v1 큐 변경 없음, 원본 메타 확장 v2는 `docs/5_2_PINNED_FILING_SCREENING.md` 참고.
- **다음 실무:** 실제 반도체 고객·공급관계 문장이 포함된 **허가된 공식 DART/SEC 문서 본문 1건** 및 공식 양사 식별자·별도 독립 SHA/최초 관측·사람 검토를 승인된 소스에서 확보한다. 원본이 실제 완료 스냅샷 목록에 없으면 EraLeader 중복 공식 수집을 NewsCatalystOS에서 하지 않고 거짓 관계를 만들지 않는다. 해당 본문이 확보된 이후에만 기존 `scripts/review_supply_relation.py`→`scripts/publish_reviewed_beneficiaries.py`→읽기 전용 소비를 수행하고 사람 gold 5_6 인수를 추진한다.
- 자동 1시간 승인 RSS `launchd`/6_5는 별도 Mac에서 지속; 누적된 **5개 실제 거래일**과 장애 복구·소스 신선도/오프사이트 보관 미완료. V1.0 **23/36(63.9%)**, 6_6 태그/허위 실거래 확정 금지. 실 AI 제공자 미승인/500 gold 및 실수혜 정확도 측정 보류.

## 2026-10-14 | 최신 NEXT_TASK=2_6/3_6 실제 2인 정답 작업 시작; 5_2 공식 실증·6_5 운영 병행
- 기능 Git SHA `06316752f700deafa0eeaeadcbcf5a10d6073968` origin/main 확인. 1_3 승인 RSS 완료 영수증 **6건/고유 실제 제목 39건**을 검증해 비공개 정답 선행예측 파일과 블라인드 제목·링크 검토목록을 원자 저장하고, **서로 다른 디스크 Mac 독립 SHA PIN**을 보관하는 `run_gold_review.py freeze` 구현. Mac 실제 `draft`로 검수자 빈 답안지 2개 작성; **정답 입력 0건**, `evaluate` 결과 39 pending, 500 요구대비 461 부족, precision/recall N/A, gate false. 영향 **78 pytest PASS/0 FAIL**, compile/Public 검사 PASS. 문서 `docs/2_6-3_6_LIVE_GOLD_REVIEW.md`.
- **다음 실질 작업:** 사용자 승인된 독립 검수자 2명이 실제 원본/메타 접근권한 범위에서 39개 사례를 각자 판정해 회사/소스와 독립된 근거 SHA 및 완료시각을 입력한다. 예약/자동 생성한 정답은 실제 인적 gold로 세지 않는다. 코드는 reviewer placeholder `UNASSIGNED`에 판정이 입력되면 거부한다. 500 케이스까지 추가 461건도 실제 허가/관측한 신규 헤드라인·공식 사례로 추후 채운다(39건 모두 라벨링되어도 해석상 소스·제목-only 편향과 독립성은 별도 검토).
- 기존 5_2 실반도체 거래관계 공식 본문+양사 ID 확보 전 공급망 5_2~5_5 실출력0, 4단계 실제 AI API/유료 원문·500 정답 연구는 외부 승인 없으면 미완료. 6_5 launchd 1시간 승인 RSS 운영·실제 5개 거래일 누적은 계속, 6_6 릴리스 태그 금지. **23/36(63.9%)** 유지. EraLeader 원본·DB·Git 및 DART/SEC/KRX 수집기 쓰기/중복 호출 금지.


## 2026-10-14 | 최신 NEXT_TASK=6_5 실제 5거래일 누적/5_2 공식 실관계·2_6/3_6 독립 검수
- 기존 `check_feed_operations.py` 운영 인수 지표에 승인 제공자별 **날짜별 완료/누락**을 추가해 일부 제공자 실패를 5일 성공으로 오인하지 않도록 함. 기능 `6c62ac38ee3f4ec28245c509d1b198c8f2f08ee6`; 변경 영향 **22 PASS/0 FAIL**, 컴파일·Git diff PASS. 실제 Mac approved=2, ACK=8, `2026-10-14` 한 날짜에 승인 2소스 완료, partial0/pending0, 별도 SSD DR true, **5거래일 false/verified_exchange_trading_days=0**. 무단 새 공식 API/모델 호출 없음.
- **다음 필수 외부 실증:** 예약된 기존 1시간 launchd 운용으로 **추가 4개 실제 거래일**을 기다려 각 날짜의 양소스 ACK·예외 로그/PIT·원장/물리 복원을 검증하며, 공휴일/휴장 구분은 독립적으로 점검. 5_2는 공식 반도체 고객–공급 계약의 허가 본문+공식 회사 ID 두 개+별도 SHA/관측시각+사람 검토 없이는 UNKNOWN. 2_6·3_6 현재 실 RSS 39건 리뷰어 2명 빈 양식·실답변0/500 부족 461. 인증·실 AI/골드·반도체 매출/5거래일 완료를 선언하지 말 것.
- **완료 23/36 (63.9%)**. 6_6 릴리스 태그 보류, EraLeader 소스·DB·Git/수집기 수정 금지, 사용자 미추적 자료 보존. 운영 명령 `PYTHONPATH=src python3 scripts/check_feed_operations.py`.


## 2026-10-14 | 최신: 6_5 실제 운영일 누적, 5_2 실공식 반도체 관계·2_6/3_6 골드 실제 입력
- 기능 `422622130871db7589766109c0119aad0d81de30`: `PYTHONPATH=src python3 scripts/check_triage_agent_health.py`를 통한 Mac RSS launchd 실사용 안전 진단. 승인 소스/설정/실서비스/최근 stdout 비교·설정변조·간격오류·중복 schedule/노후 로그 fail-closed. 변경 영향 **59 PASS/0 FAIL**, compile/Public 검사 PASS. 실제 runs4/exit0/승인 2/최근 로그/건강상태 exit0; 이는 5거래일 완료를 의미하지 않음.
- **다음:** Mac 운영 `scripts/check_feed_operations.py`(날짜별 양 소스 실제 ACK, pending/물리 SHA 복원) 및 신규 건강진단을 후속 실제 거래일에 점검. 실거래소 휴장 일정 증빙 확인 후에만 실제 5거래일 인수. 현재 관측일 2026-10-14 단 1개, 출처 정상 2개, 추가 4개 실제 날짜 미도래. 인공 생성으로 날짜/수혜 실증 대체 금지.
- 5_2 공식 반도체 고객·공급 계약본문/양사 공식 ID+별도 SHA/PIT·독립 사람검수가 확보되면 **기존** 5_2→5_5 CLI로 실물 1건 소비; 자료 없으면 UNKNOWN. 2_6/3_6 기존 RSS 39건 검수자 2명 실제 답변0(500까지 461부족), 4단계 AI 실모델 승인 없음, 최종 출시 6_6 보류. **23/36(63.9%)**, 전체 기획 범위와 비공개/EraLeader 안전 준수.


## 2026-10-14 | 최신 NEXT_TASK=6_5 실제 거래일 5개 누적, 공식 반도체 5_2 원문/2_6·3_6 인적 검토
- `f2b454b7fdb4e8527224da1c20f42b9b0db26db3`: KRX 거래일 operator-reviewed 일정 폴더를 `scripts/check_feed_operations.py --calendar-review-dir <Mac-private-folder>`로 *선택적으로* 대조, 실제 양승인 제공자 완료 ACK를 소급하거나 기존 RSS 워터마크에 쓰지 않음. 잘못된 원본·SHA/미검토 일정 오류 차단. **46 PASS/0 FAIL**, compile/Public 검사 PASS. 현재 사설 실제 공식 일정 리뷰 **입수0** → 검토된 거래일0/출시 false. 승인 RSS 2/실분석 ACK10, 실제 모든소스 완료 날짜 2026-10-14 한 날짜, 별도 물리 복원 true.
- **다음 핵심 외부 실증:** 실제 KRX 공식 2026 거래일 일정의 합법적 개인 근거 파일/운영 검토가 있을 때 SHA·시각을 입력해 기존 승인 RSS ACK 날짜와 대조. Mac 기존 1시간 RSS launchd로 **추가 4개의 실제 거래일** 관측이 필요, 달력상 날짜/공휴·휴장·소스 정상/오류·DR을 확인. 과거 날짜/데이터 임의 생성 금지. `verified_exchange_trading_days`와 5일 완료 플래그는 독립 실증 전 0/false.
- 5_2 실제 공식 반도체 고객사·공급사 본문+양사 공식 식별자·SHA/PIT/사람 검수 미확보 → UNKNOWN. 2_6/3_6 독립 인적 gold 0(39건 블라인드 대기), AI 실공급자/반도체 수혜 정확도/6_6 최종 출시 인수 미완료. **23/36(63.9%)**. EraLeader Git·코드·DB/API 수집 변경 절대 금지, 기존 사설 자료 보존.


## 2026-10-14 | 최신 NEXT_TASK=2_6/3_6 실제 2인 리뷰·신규 444건 누적; 5_2 계약증거·6_5 5거래일
- 기능 **`98dd4a662c745c0d6c840872c25c4f206c09188e`** (공개 원격 push 확인 필요): `PYTHONPATH=src python3 scripts/run_gold_review.py progress` 읽기전용 SHA/PIT 중복 없는 실제 검수 후보 현황, `freeze --new-only`는 기존 39건·새 17건 pinned batch 및 검수자 답변을 그대로 두고 이후 실제 승인 뉴스만 별도 인수한다. 현재 총 **56건 고유 검토 후보/2배치**, 실제 인적 gold **0**, 목표까지 **444건 부족**, 검증 precision/recall N/A. 빈 신규 리뷰 시트 2개 Mac 내부 보관. 변경 영향 **45 PASS/0 FAIL**, compile/Public 검사 PASS.
- **다음 실질 작업:** 실제 독립 검토자 2명이 승인된 제목/공식 근거를 판정하고 출처 SHA·리뷰 종료시각을 답안지에 입력. 더 많은 합법적 신뢰 가능한 승인 RSS/공식 기존 읽기전용 스냅샷 뉴스 사건을 중복 없이 누적하고 검수·분모 편향 점검; 내부 코드로 '사람 정답' 대체 금지. 5_2 공급사–고객사 공식 본문/양사 IDs/별도 SHA·검토 원천은 아직 0건(없으면 UNKNOWN), Mac 자동 RSS 6_5 실제 5거래일·독립 거래일 확인 및 4단계 실 AI 모델/비용 인수도 미완료.
- **현재 엄격 23/36(63.9%)**, 6_6 출시 태그 보류, 실모델·가짜 정답/수혜 승격·EraLeader 원본/DB/Git·DART/SEC/KRX 신규 중복 수집 금지. 문서 `docs/2_6-3_6_LIVE_GOLD_REVIEW.md` 참고.


## 2026-10-14 | 최신 NEXT_TASK=4_1 실호출 승인 대기, 5_2 실반도체 관계·2_6/3_6 독립 골드·6_5 5일
- 기능 `9c0e5b9462e2c9870ca0f7a17c8875588c99d0a3`: `ai_openai_transport.py`가 기존 AI 공통 스키마/월 예산 4_6 결합, OpenAI Responses API `store=false`/무리다이렉트/무재시도/strict JSON+토큰 검증, 결과 종료 후 PIT 시각 처리. **44 PASS/0 FAIL**, 컴파일·Public 검수 PASS. `OPENAI_API_KEY` 미설정, 유료 실호출 0, 실공급자/요금·정답 측정 전 **4_1 미완료**. 실제 API 연결은 운영자가 유료 사용·모델/키를 승인하고 비공개 환경키가 준비된 경우에만 명시적 실행; 임의 유료 호출 금지.
- 다른 선행 병목: 기존 2_6/3_6 검증된 RSS 후보 **56건**/2배치, 인간 2인 독립 정답 **0건**, 목표까지 444건·품질 검증 필요. 5_2 실제 반도체 계약 본문/양사 공식 기업 ID/독립 SHA·사람 검토 0건 → UNKNOWN; 새 DART/SEC/KRX 수집·EraLeader 변경 없이 기존 공유 완료 캡처 검토. 6_5 Mac 1시간 승인 RSS 실제 5거래일·거래소 일정 독립 검수 미완료. 6_6 tag 불가.
- **진행 23/36(63.9%) 유지**. 다음은 유료 API 승인 없는 범위에서 5_2 실수집 공식문서 증거 확보 가능 여부 및 사람 gold 검토자료·원장 운영 확인. 재작성·동일 방어 테스트 반복보다 실제 실증과 정확도 평가를 우선.


## 2026-10-14 | 최신 NEXT_TASK=2_6/3_6 실제 두 사람 검수·444 뉴스 후보 확보; 5_2 공급 관계 증빙
- 커밋 `9fcfe7ab237348518edf4b69e0f27b9d044f5848`: `PYTHONPATH=src python3 scripts/run_gold_review.py aggregate` 전체 frozen 2배치 SHA/PIT/2인 리뷰파일 read-only 검사 및 합산 precision/recall. 44 PASS/0 FAIL, 컴파일/Public 검사 PASS. 실제 56 뉴스 제목 후보/인적 2인 합의 **0건**, 중복 정밀도/중요 탐지 재현율 N/A, 각 배치 리뷰 정답 파일 빈 상태·500건 중 444개 신규 고유 후보 부족. 완료 **23/36(63.9%)**.
- **다음 실질 작업:** 공식 뉴스 메타·허가 원문을 확인할 권한이 있는 서로 다른 2명이 현 56건을 블라인드 독립 판정해 evidence SHA·reviewed_at과 함께 answer 파일에 직접 입력. 새로 승인받은 RSS 신규 사건이 들어오면 `progress` → `freeze --new-only`로만 기존 실 데이터를 보존하며 500개까지 점진 축적. 초기 2개 공급자/제목-only 편향 점검과 500건 규모에서 실제 결과 분모/홀드아웃 별도 인수 필요. **AI는 인간 리뷰어를 가장하여 정답을 입력하면 안 됨.**
- 5_2는 확인된 공시 본문·양사 법인ID/관계 문장을 받은 경우만 기존 `review_supply_relation.py`→`publish_reviewed_beneficiaries.py`로 실제 전파; DART 100/SEC 1001 메타만으로 실거래 확정 불가. 4_1 실 OpenAI 키·사용자 유료 승인 없음, 6_5 실제 5거래일 및 공식 일정 독립 확인 미완료. EraLeader 원본·코드·DB/Git 수정 및 DART/SEC/KRX 직접 중복 수집 금지. 출시 tag 보류.


## 2026-10-14 | 최신 NEXT_TASK=실제 2인 인적 리뷰 수행; 공식 반도체 원문/5거래일·AI 승인 별도 대기
- 기능 `77a8cc8639dfc68d8dfe1f71ae57e625a8b6ffaa` Mac 독립 PIN 고정 GoldBatch의 블라인드 제목만 조회하는 `PYTHONPATH=src python3 scripts/run_gold_review.py review-list --expected-sha256 <SHA> --reviewer-slot UNASSIGNED_A` 및 명시적 인간 검토 `review-one` 입력 구현. reviewer 슬롯 owner-only `evidence_<case>.txt`를 사용자가 **스스로 작성**한 경우에만 판단을 입력, 기록시점/PIT·이전 답안 백업/SHA 이력 보존·덮어쓰기 차단. 실제 새 배치 17건 실목록 조회 성공, 기존 56건 검수 합의 0 유지. 영향 **45 PASS/0 FAIL**, 컴파일·공개보안 PASS.
- **다음 실제 필수:** 승인된 뉴스 메타에 접근 가능한 독립 인간 2인이 Mac private A/B 검수 공간에서 공식 근거를 열어보고 자기 판단과 사유 SHA를 직접 기록. ChatGPT가 임의 라벨/검수시각/검토자 신원 생성하면 안 된다. 작업 후 `run_gold_review.py aggregate`로 실검수 현황·정밀도·재현율 확인. 실뉴스 신규 고유 사례 **444건**(기존 56) 및 500건 정답 인수 필요. `docs/2_6-3_6_LIVE_GOLD_REVIEW.md`의 새 검수 CLI 사용법 참조.
- 5_2 공식 반도체 공급사·고객사 본문/회사 ID·거래 문장 인수 전 UNKNOWN, 실제 OpenAI 호출은 승인·환경키 미준비 0회, 6_5 5거래일/공식 거래소 일정 독립 확인 미완료. **23/36(63.9%)** 유지, EraLeader 자료 읽기전용, Git Public 정보검수, 6_6 tag 보류.


## 2026-10-14 | 최신 NEXT_TASK=실제 2인 검수/반도체 5_2 증거·6_5 5거래일
- 기능 `329fc01f10f387beb5526fa8b45dfd40fdd7e47f`(기능 커밋): 실제 승인 RSS **9개 신규** 동결으로 **65개**(3 SHA PIN 배치), 소스별 중기부23/뉴스와이어IT42, 반도체 제목 키워드 힌트1(사실 승인 아님). Mac A/B 빈 검수자 공간 생성. `review_news_interactive.py --batch-sha256 <SHA> --slot UNASSIGNED_A --reviewer-code REVIEWER_A`는 검수자 **본인이** 출처·중복·중요 여부·근거·확정을 입력할 때만 기존 `record_review_once`에 개별 판정 제출. 55 PASS/0 FAIL·컴파일/Public 검사 PASS. 실제 두 사람 정답 **0**, 500 후보까지 **435건 부족**, 완료 **23/36(63.9%)**.
- **다음 실제 필수:** 독립된 뉴스 검수자 두 명이 허가 출처를 직접 열어보고 이 CLI를 각각 운용한 뒤 `run_gold_review.py aggregate`에서 2인 합의·의견충돌·precision/recall을 계측. AI가 사람을 가장하거나 임의 근거를 자동 작성 금지. 초기 2개 출처 편중을 해소하려면 새 제공자의 적법한 이용허가 확인 후 등록; DART/SEC/KRX는 EraLeader 검증 완료 스냅샷만 읽기전용 공유. 5_2 실반도체 고객사·공급사 공시 원문/공식 기업식별자 2개 없으면 실거래 UNKNOWN 유지. 6_5 추가 4개 실제 거래일 관찰/공식 일정, 4_1 실제 키·승인 AI 비용 검증 대기. 인수조건 미충족이므로 6_6 V1 릴리스 tag 금지.


## 2026-10-14 | 최신 NEXT_TASK=실인적 gold 검수/5_2 공식 관계/6_5 운영일 실증
- 기능 `9bc3564944d8f336c787844e06fb5a65a253a3c0`: 실제 2인 검수 저장이 장애로 중단돼도 인간이 이미 확정한 답안 원본·제안·SHA 영수증을 개인 `review_history`에서 검증하여 **명시적 복구만** 허용. `PYTHONPATH=src python3 scripts/run_gold_review.py review-recover --expected-sha256 <기존SHA> --reviewer-slot UNASSIGNED_A --case-sha256 <기존 사건SHA>`는 특정 케이스만 복구; 답안 없음/영수증 없음/근거·SHA 변경 시 거절. 62 PASS/0 FAIL, 컴파일/Public 검사 PASS. 새 인간 정답을 만들지 않으며 실제 라벨 0/65, 현재 정밀도·재현율 N/A, 500까지 고유 435건 부족. 6_5 RSS 운영 10월14일 한 날짜만 증명, 출시 불가.
- **다음 작업 우선순위**: 실제 승인·독립 인간 2인의 65건 블라인드 검토 입력 및 `aggregate` 실측; 허가된 새 데이터 출처의 진짜 신규 사건 축적과 5_2 반도체 고객–공급사 문서 원문+양사 공식 기업 ID/PIT/운영자 증거; Mac 1시간 RSS 5개 실제 거래일 ACK와 공식 휴장 대조. AI 실호출은 사용자 승인/비공개 키·정식 요율 확인 전 금지. EraLeader DART·SEC·KRX/PIT/SHA 스냅샷 읽기전용, EraLeader Git·코드·DB 변경 금지. **23/36(63.9%)**, 6_6 태그 보류.


## 2026-10-14 | 최신 NEXT_TASK=gold 자동동결 1시간 운영 관찰 및 인적 2인 검수/5_2 실원문
- 기능 **`806d40b79f9d24a0d27b529240152ba166f17ac5`**: 실 Mac 승인 RSS 정상 1시간 `com.newscatalystos.triage`와 독립적인 `com.newscatalystos.gold`를 설치/등록(3,600초 주기)해 **이미 승인·분석 완료한 RSS ACK에서만** SHA 동결/빈 검수자 시트 자동 누적. 실제 launchctl gold **runs1/exit0**, RSS triage **runs9/exit0**; 신규 실제 뉴스 제목 후보 **+5건**, 총 **70건/4개 독립 Mac PIN SHA 배치**, 중기부23/뉴스와이어IT47, 500까지 **430건 부족**, 2인 인적 합의 **0**. 자동 잠금·중단 후 완전 미존재 빈 양식만 복원, 기존 answer/원본 불변, 테스트 **66 PASS/0 FAIL**, compile/Public 검사 PASS. 시작 후 첫 시간·맥북 절전/SSD 분리에 따른 장기 정상운영은 미검증, 실제 이틀 이상 운영실적이 생겨야 추가 평가.
- **다음 실제 업무:** 독립 실제 2인 검수자가 각자 검증된 RSS/공식 근거를 확인하고 owner-only A/B 시트에 직접 라벨 제출. 자동 동결은 human gold 판정 없음; 진짜 라벨 500/실제 출처 다양성/정확도 평가 전에 2_6·3_6 미완료. 추가 430건은 승인 RSS future 관측으로만 확보, 과거 날짜 소급 금지. 5_2 실제 승인 공식 반도체 공급고객 관계 문서 원문/2개 회사 공식 ID/PIT SHA 확보 시 기존 인수 파이프라인 사용, 자료 없으면 UNKNOWN. 6_5 실제 5거래일 및 KRX 휴장 독립확인/오프사이트 미완료, 4_1 유료 실모델/비용 사용자 미승인. **진도 23/36(63.9%)**, 최종 6_6 태그 금지. 운영 중지는 `launchctl bootout gui/$(id -u)/com.newscatalystos.gold`로 새 Gold agent만 별도 중지, 기존 승인 RSS는 별도 유지.


## 2026-10-14 | 최신 NEXT_TASK=반도체 실표본 대표성 확보/실 2인 gold/5_2 계약 증거
- 기능 `ee2c0997a4896df01448f3d7a8ca385e9dc38f23`: `PYTHONPATH=src python3 scripts/run_gold_review.py scope-audit`의 실 RSS 골드 표본 QA. 영향 **59 PASS/0 FAIL**, 컴파일/Public 검사 PASS. 현재 **70개 고유 PIN 후보**, 공식 정부기관 23/배포 보도자료47, 반도체 관련 제목 키워드 **1개(1.4%, 실제 사건 검증 아님)**, 2인 독립 실제 골드 **0**, 500 표본 후보까지 **430개** 부족. 보도자료는 독립 언론으로 간주 금지. 기존 `triage`와 `gold` 사용자 1시간 launchd는 유지, RSS 추가 HTTP/AI·EraLeader 쓰기 없음.
- **다음 실질 작업:** 기존 뉴스 후보를 실제 서로 다른 검수자 두 명이 자신의 승인 출처에서 직접 확인하고 `review_news_interactive.py`에 라벨·근거를 입력. 반도체 평가를 위해 **기업 IR/공공정책/독립 기사 등 신규 자료원의 이용권한·RSS 공개조건**부터 확인한 후 관련성 있는 실제 후보를 확보; 승인 없는 RSS 신규 활성화 금지. 기존 EraLeader DART/SEC/KRX 검증 스냅샷은 읽기전용만 활용. 5_2 실반도체 공식 관계 원문·양사 공식 ID가 없으면 UNKNOWN, 6_5 실제 5거래일/공식 휴장표, 4_1 실제 유료 키·모델 승인 없이는 실출시 거절. **23/36(63.9%)**, 6_6 tag 보류.


## 2026-10-14 | 최신 NEXT_TASK=공식 산업통상부 RSS 실 10건 인수 이후 반도체 실검증
- 기능 `f513999b32d7733993839636c9742880df8af6a9`: 기존 RSS GET·EraLeader 불변, 공공누리1유형 및 RSS를 명시한 산업통상부 `motir.go.kr` 정부 공보를 정확한 폼 **빈 POST**로만 추가. 자체 Mac owner-only registry·전용 SQLite/inbox/Gold SHA PIN, 별도 `com.newscatalystos.motir` 1시간 자동 작업 실설치/기동 정상 exit0. 실제 정부 RSS 최초 `10` 건 메타/완료 ACK/실 SHA Gold 검증, 반도체 키워드 **후보1**(공급 관계 증명 아님), 기존 일반 Gold70과 **별도**. 변경 영향 **118 PASS/0 FAIL** 및 Public 검사 PASS. `docs/1_2_MOTIR_SEMICONDUCTOR_POLICY_RSS.md` 절차·운영 명령.
- **다음 실제 필수:** 독립 사람 검수자 2명이 신규 MOTIR 반도체 키워드 후보와 기존 PIN Gold 제목·공식 링크를 검토하여 진짜 사건 여부/2_6·3_6 정답을 직접 기록한다. 기존 두 RSS 후보70과 MOTIR 후보10의 교차출처 중복·반도체 대표성은 별도 실증 전 합산 독립 Gold/성능 지표로 주장하지 않는다. MOTIR 실제 후속 1시간 운용·공개시각/PIT·원장복구/출처표시 확인. SK하이닉스 뉴스룸 등 로봇제한 민간 출처는 별도 서면 허락 전 자동수집 금지. 5_2 실공식 반도체 공급계약 본문·2개 회사 공식 ID+사람 검토 확보 전 UNKNOWN; 4_1 실 승인 유료 모델 없고 6_5 실제 거래소 5거래일/오프사이트 검증 안 됨. **23/36(63.9%)**, 6_6 tag 보류, EraLeader 원본/DB/Git·기존 두 RSS 서비스 변조 금지.


## 2026-10-14 | 최신 NEXT_TASK=반도체 교차출처 후보를 기존 PIN Gold 검수 흐름에 연결
- 직전 기능 `67b2bb28ccbdc2d0ffc9b438357e1c0df7b7372d`는 **원격 main 동일 SHA까지 검증 완료**. `PYTHONPATH=src python3 scripts/search_news.py --scope all --query 반도체 --semiconductor-only`로 격리된 기존 2소스와 산업통상부를 함께 조회한다. 실제 제목 버전83/반도체 검토 힌트2/독립 인적 정답 판정 없음. 영향 **100 PASS/0 FAIL**, 코드 컴파일·Public 검사 PASS. 읽기전용 검색 중 등록부2/운영 DB4의 SHA 동일. 기존 기본 검색/자동수집/Gold/사용자 자료 보존. 완료 **23/36(63.9%)**.
- **다음 하나의 구현 대상:** 통합 검색 결과의 `provider_id/event_id/title_sha256`를 이미 검증된 기존 PIN Gold 사례에 연결해 반도체 후보의 교차출처 비교·공식 링크 확인과 기존 인간 검수 CLI 진입을 지원한다. 기존 답안지/검수 이력·각 작업공간 분리/불변 PIN을 재사용하고 새 평가 프레임워크로 재작성하지 않는다. 검색에 존재하나 아직 Gold로 동결되지 않은 버전은 명시적으로 대기하며 가짜 PIN/사람 라벨 생성 금지. 블라인드 A/B 검토 전 자동 중복 힌트나 모델 예측을 정답처럼 주입하지 않는다.
- 출처 중복 힌트0은 독립 경제사건0/검증 합격이 아니다. 실제 두 사람의 근거·판정이 들어온 경우에만 기존 aggregate 평가를 수행한다. 5_2 실공급고객 관계를 확정하려면 공식 본문과 양사 공식 ID가 필요하고 제목만으로 승격하지 않는다. 4_1 사용자 유료 승인·키/실요금, 6_5 실제 5거래일·공식 일정, 6_6 인수는 별도. EraLeader 공식 API 신규 중복 수집·DB/Git/코드 변경, 이미 정상인 서비스 재설치 및 동일 전체 테스트 반복 금지.


## 2026-10-14 | 최신 NEXT_TASK=5_2 실제 반도체 관계 근거 확보·기존 파이프라인 실증
- 직전 기능 `411d6118c0ef95e024e730ed0be66c1469ab4c07` origin/main SHA 확인 완료. 검색 반도체 후보→기존 PIN Gold→정확한 `--case-sha256` 인적 검수 진입 구현/실조회 완료, **119 PASS/0 FAIL**, Mac 제목89/반도체2건 A·B 각각 정확한 사례 연결, 입력55파일 SHA 불변. `search_news.py --scope all --query 반도체 --semiconductor-only --review-links --reviewer-slot UNASSIGNED_A` 사용. 정상 연결을 다시 개발하거나 새로운 검수 프레임워크/동형 가드를 추가하지 않는다.
- **다음 실제 한 작업:** 허가된 공식 반도체 공급사–고객사 관계 본문과 두 회사의 공식 식별자·최초 확보시각/근거 SHA가 존재하는지 확인하고, 확보된 실제 증거만 기존 `review_supply_relation.py`→`publish_reviewed_beneficiaries.py`→읽기전용 소비 경로로 연결한다. EraLeader는 완료·검증 스냅샷만 공유하며 공식 API 중복 수집/코드·DB·Git 변경 금지. 기존 1,101개 공시 메타에 본문이 없다는 사실은 기확인됐으므로 동일 목록 반복 점검 금지. 본문/관계 증거 부재 시 UNKNOWN을 유지하고 사실·매출/수혜를 창작하지 않는다.
- 2_6/3_6은 이제 기존 검색 연결·직접 검수 CLI가 준비돼 있으므로 실제 사람의 독립 답안을 받은 경우에만 기존 aggregate로 평가한다. AI가 검수자를 가장하거나 임의 라벨/답안을 생성하지 않는다. 검색된 제목89/후보2는 인적 골드/독립 사건 수가 아니다. 4_1 유료 AI 호출은 실제 승인·비공개 키/요금 조건 전 금지, 6_5 실제 5거래일 및 6_6 최종 인수 미완료. **23/36(63.9%)**, 무근거 릴리스 태그 금지.


## 2026-10-14 | 최신 NEXT_TASK=5_2 확보한 실제 관계의 운영 입력·검수 인수 연결
- 기능 `00b2549631d7a3a1daa12e6bb5c4fcd2b5efe5fd` origin/main 동일 SHA 확인. 실제 공개 기업 발표 관계 참고 **1건/양사 공식 CIK 참조2건**을 별도 SSD 파일·Mac PIN으로 보관하고 기존 5_2~5_5 코드 시범 처리 exit0. 8개 테스트 파일 **87 PASS/0 FAIL**, 입력8파일 SHA 불변. 기존 1,101 공시 메타/검색 검수 도구를 반복 탐색·재개발하지 않는다. 전체 **23/36**.
- **이미 확보한 실제 자료 위치:** `logs/public_relation_reference_live_check.json`의 reference_file/pin_file을 읽고, 필요 시 `scripts/inspect_public_relation_reference.py`로 해당 한 건만 재개한다. SSD `output/public_relation_references`의 짧은 인용은 전체 기사/공시 원문이 아니며 `source_reported_date=2023-11-30`, 현재 수혜/새로운 경제사건 아님. 문서 `docs/5_2_PUBLIC_RELATION_REFERENCE.md` 참고. 더 이상 '실제 관계 참고자료를 아직 찾지 못했다'고 보고하지 않는다.
- **남은 실제 인수:** 허용된 운영 입력 출처와 실제 운영자 검토를 확보해 기존 공식 relation intake/게시 조건을 충족하는 경로로 연결한다. 지금 자료는 ASSISTANT_SOURCE_RESEARCH_NOT_HUMAN_REVIEW·SHORT_CITATION_ONLY_NOT_COLLECTION_PERMISSION이며 자동 수집원 등록/인적 정답/공식 게시/외부 소비 인수에 사용하지 않는다. 해당 기업 발표를 기존 다른 SEC 공시의 본문으로 위장하거나 원문 SHA·사람 검수시각을 생성하지 않는다. 증빙이 추가되기 전 참고 어댑터·SHA 방어·검수 편의 기능 반복 확장 금지.
- 2_6/3_6은 기존 실제 사람 답안이 있을 때만 평가, 4_1 실유료키/모델 승인은 별도, 6_5 실제 운영일 누적/6_6 최종 인수 보류. EraLeader 원본/코드/DB/Git 및 공식 수집기 불변, 미추적 사용자 자료 보존. 다음 실제 증거 없는 완료 수/릴리스 태그 승격 금지.
