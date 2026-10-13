# NEXT_TASK — 다음에 수행할 단 하나의 작업
작업 ID: 1_5
제목: 원본 증빙·영수증 SHA 안전 저장 및 정정 이력
상태: 1_1~1_4 네 단계 기본 구현·변경 영향 테스트 완료, 4/36 (11.1%). 1_4 관련 전체 345 PASS/0 FAIL, 공식 관측 메타 3,866개 실물 정규화 확인.
선행 조건: source_share.py/operational_observations.py/event_identity.py의 SHA·PIT·정정 계약을 재사용하고 EraLeader 원본/운영 DB는 읽기 전용으로 유지. 허가되지 않은 기사 원문 장기 보관 금지.
목표: 저장이 허가된 신규 자료·수신 영수증의 SHA256/출처/최초 수신/버전 기록을 NewsCatalystOS 전용 안전 영역에 원자 게시. 원본 변조/정정 시 이전 증빙 보존.
시작 시: 1_5 보관권한/파일 크기/비밀정보 예외와 로컬 경로를 정한 뒤 독립 소형 보관 모듈·변조/경로탈출·PIT/중복/정정 음성 시험.
완료 조건: 허가된 메타·원문 SHA와 영수증 SHA 대조, 원자 게시/재실행/복원 검사 통과; 무허가 기사 원문 0건 저장, Public Git 파일 허용목록 검사.
그다음 작업: 1_6 수집 장애·품질 감시.
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
