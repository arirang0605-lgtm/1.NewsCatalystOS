# PROJECT_STATE — NewsCatalystOS 단일 작업 상태 기록
기준일: 2026-10-13
상태: 1_1 부분 구현. EraLeader 공식 API 첫 원자 게시 수신본 5종 실제 읽기 전용 검증 성공. 독립 시점공증/정확한 공시 공개시각 및 실운영 API 직접 연동은 미검증.
완료된 산출물: 1_1~6_6 상세 설계 SVG 6장, 루트 재개·개발 원칙 문서.
기존 공유 의존성: /Volumes/T5DATA/eraleader 의 DART/SEC/KRX 수집 결과는 향후 읽기 전용 연결 예정. 연결 성공/권한 검증/실시간 동작을 여기서는 주장하지 않음.
현재 단계: 1_1 기존 수신본 5종/연구용 외부 SHA 리포트 대조 완료; 검증된 공시 발행시각 기반 RawEvent 승격 및 독립 핀 보관 게이트 미완료.
CURRENT_NEXT_TASK: 1_1 EraLeader 공식 데이터 읽기 전용 공유 어댑터 계약·샘플 정리.
완료된 구현: newscatalystos SourceManifest/RawEvent, fail-closed publication/SHA/PIT/원본 불변 검증 모듈 (1_1의 일부).
마지막 검증: 1_1 관련 단위시험 57 PASS / 0 FAIL; Python compileall PASS; 기존 EraLeader 로컬 수신본 5종 실제 read-only SHA/품질/시점 점검 PASS. 직접 신규 API 호출/운영 증명 아님.
Git 저장소: 기존 폴더 내 main 안전 초기화·origin 연결, 기능 커밋 445b6ae553c43afc864324630a6bc110c99cd125 공개 원격 푸시 및 ls-remote SHA 대조 성공.
남은 조건: 1_1~6_6 구현+500건 평가 데이터+반도체 집중 검증+5거래일 안정운영+전체 회귀+복원+V1.0 태그.
금지: 새로운 산업을 필수 범위에 추가, 기존 EraLeader 코드/원본 변경, 성과 인증 허위 주장.
작업 재개 시 가장 마지막 갱신일·Git SHA·검증 결과를 여기에 덧붙이며 오래된 상태를 현재 상태로 오인하지 않는다.


## 2026-10-13 | 병행 개발 문서 개정 (NC-PARALLEL-2026-10-13)
- EraLeader와 동시 개발해도 서로 다른 소스/DB/Git/백업·테스트를 사용하고, EraLeader 수집 완료·검증된 결과만 읽기 전용으로 소비하도록 지침 개정.
- 기존 \`1_1~6_6\` 개발 범위/반도체 1개 산업 검증/V1.0 종료 조건 변경 없음.
- 본 항목은 **문서 작업만** 기록한 것으로 애플리케이션 구현·AI API 연동·테스트 완료 아님. CURRENT_NEXT_TASK는 계속 \`1_1\`.

## 2026-10-13 | GitHub Public 확정 및 개발 프롬프트 개정 (NC-PUBLIC-REPO-2026-10-13)
- **확인된 GitHub:** arirang0605-lgtm/1.NewsCatalystOS (Public), https://github.com/arirang0605-lgtm/1.NewsCatalystOS.git, 기본 브랜치 main. 원격 저장소 크기 0으로 표시됨(검증 시점 기준, 후속 재확인 필수).
- **로컬 확인:** /Volumes/T5DATA/1.NewsCatalystOS 는 현재 Git 저장소가 아님. 기존 MD/다이어그램은 보호. 원격과 연결/첫 커밋·푸시는 아직 수행하지 않음.
- **신규 기획 산출물:** NewsCatalystOS_V1.0_CHAT_개발마스터프롬프트.md, GITHUB_PUBLIC_POLICY.md.
- **개정 기록:** 기존 AGENTS/DECISIONS/START_HERE/NEXT_TASK/PROJECT_STATE/상세명세/상시지침/프로젝트 TXT에 Public 보안 정책 반영. 원문 보존 사본은 .local_backups 에 생성.
- **현재 실제 기능 구현:** 아직 미착수. 실제 AI API·수집/테스트·Git 릴리스 성공을 주장하지 않음. CURRENT_NEXT_TASK = 1_1.
- **1_1의 초기 확인:** 기존 폴더 안전 Git 연결과 .gitignore·비밀검사, EraLeader 완료 스냅샷의 읽기 전용 표준 데이터 어댑터 설계·구현/관련 테스트.
- **범위 그대로:** 36개 작업, 공급망은 반도체 1개 산업만 V1.0 실제 검증. 전체 5거래일/정답셋/복원 및 공개 릴리스 조건은 미충족.

## 2026-10-13 | 최초 실제 코드·GitHub Public 체크포인트 (NC-1_1-INPROGRESS)
- 사용자 승인된 공개 GitHub 저장소로 기존 SSD 폴더 그대로 `main` 초기화·origin 연결(빈 원격에 정상 푸시). 기존 설계 문서/이미지 삭제·덮어쓰기 없음. .local_backups 내부에 상태 문서 복사 보관.
- 첫 커밋 **445b6ae553c43afc864324630a6bc110c99cd125**, `git ls-remote origin refs/heads/main`로 동일 SHA 확인. `git push --force`/타 프로젝트 Git 접근 없음.
- 공개 커밋은 검수된 6개 파일만 명시적으로 stage: `.gitignore`, `pyproject.toml`, `src/newscatalystos/{__init__,source_share}.py`, `tests/test_source_share.py`, `docs/1_1_SOURCE_SHARE_CONTRACT.md`. 비밀 접두사 패턴/바이너리/대용량 파일 검사 PASS; `.local_backups` 등 ignore 확인.
- 1_1 **일부 구현**: SourceManifest/RawEvent 구조, DART/SEC/KRX 발행 메타 읽기 전용 계약; 원자 게시 COMPLETE·독립 신뢰 SHA 핀·이벤트 SHA/크기·증빙 영수증 바인딩·PIT·중복 ID·심볼릭 링크/원본 불변 방어. HTTP 호출·원본 SQLite 쓰기·EraLeader 코드 재사용 구현 없음.
- **검증:** `python3 -m pytest -q tests/test_source_share.py` → **23 passed, 0 failed, exit 0**. `python3 -m compileall -q src/newscatalystos` → PASS. 모든 test fixture 합성. 단일 변경범위 검사로 전체 회귀는 아직 실행하지 않음.
- **운영/실데이터:** EraLeader 공식 API 캡처 코드 및 수신 원본 존재 확인. 다만 NewsCatalystOS 소비자 계약의 **독립 SHA 신뢰핀을 보유한 게시 완료 export**를 아직 확인하지 못함. 실제 DART/SEC/KRX 배치 소비 0회, AI API 0회, 자동운영 0거래일, 복원 실증 없음. 실사용 상태 **DATA_UNAVAILABLE**.
- **완료 판정:** 1_1의 실제 게시 자료 원본불변 실증 게이트 미충족으로 **검증 완료 0/36 = 0.0%**. 부분 개발 구현과 완료된 세부작업 수를 혼동하지 않는다. 다음 작업은 1_1 실물 export/receipt 연결 및 음성 실패검증 지속.

## 2026-10-13 | 1_1 공식 첫 수신본 read-only 실제 소비 (NC-1_1-CAPTURE-READ)
- **구현:** `src/newscatalystos/era_capture_share.py`(기존 원자 게시 `first_<uuid>` 검증 및 제공자별 안전 metadata records), `verified_reference.py`(별도 SHA pin 연구 리포트 대조), `scripts/verify_era_captures.py`(읽기 전용 smoke), `tests/test_era_capture_share.py` / `test_verified_reference.py`, 개발/제약 문서.
- **실제 EraLeader 데이터 연구 검증 5/5 PASS:** KRX KOSPI 942, KOSDAQ 1823, DART 100(첫 페이지 한정), SEC submissions 1001, SEC companyfacts taxonomy 2 (뉴스 record 0). 총 관측 항목 **3868**; KRX/SEC 실 수신 스냅샷을 NewsCatalystOS로 새로 생성/재수집하지 않음. 원본 SHA·영수증 SHA·수신시각·출처 품질 및 원본 불변 읽기 통과. 참고 리포트의 SHA는 그때 보유한 실제 연구 보고서 자체의 SHA를 명시해 PIN으로 사용했으며 **외부 시각공증/제3자 인증은 아님**.
- **테스트:** 새 관련 합성 fixture 포함 `python3 -m pytest -q tests/test_source_share.py tests/test_era_capture_share.py tests/test_verified_reference.py` → **57 PASS, 0 FAIL, exit 0**. `compileall` PASS. 원래 EraLeader 수집기/DB/Git/비밀 설정 쓰기 0, 신규 외부 API 호출 0.
- **Public 검수:** 새 코드/테스트/문서 7개 파일만 명시적으로 stage; secret 패턴·바이너리·diff whitespace 검사 PASS. 기능 commit `505b073d31418713b56cc791c1d5b9257e7e2d63` GitHub `origin/main` 푸시 및 원격 SHA 동일 확인.
- **실사용 한계:** 공식 문서 실제 공개 시각, DART 하루 전체, SEC 전체/법적 share-class, 외부 독립 PIN 보관 및 RawEvent 승격은 미완료. `OfficialRecord.release_at=None`, `historical_pit_certified=False`, 5거래일 자동운영 0회. 운영 이벤트로 자동 승격/확정 투자분석 금지. NEXT_TASK 1_1 유지, 36개 중 엄격 완료 **0/36(0.0%)**.

## 2026-10-13 | 1_1 시각 분리 + 로컬 별도 디스크 SHA 핀 (NC-1_1-TIMESTAMP-PIN)
- **실제 구현:** SEC `acceptanceDateTime`을 `provider_acceptance_at`으로 UTC 정규화하며 잘못된 시각·최초 수신 후의 미래 시각 거절. DART `rcept_dt`은 날짜만. `official_normalization.py`로 공식 메타후보 정규화, `published_at` 증명 없으면 `RawEvent` 승격 차단.
- **독립 보관(한계 포함):** Mac 내부 디스크의 `~/Library/Application Support/NewsCatalystOS/pins/official_api_pit_research.pin.json`에 별도 디바이스 SHA 핀을 최초 관측 시각으로 **한 번만 생성(O_EXCL)**, owner-only 보관. EraLeader SSD와 다른 디바이스 ID 확인. `LOCAL_TOFU_NOT_EXTERNAL_ATTESTATION`: 제3자 공증도 과거 publication time 증명도 아님. GitHub로 핀 파일을 올리지 않음.
- **실데이터 오프라인 검사:** 기존 EraLeader DART 1/SEC 2/KRX 2 총 **5개 캡처** 별도 pin 연동 및 읽기 전용 연구 재검증 PASS, 메타후보 **3,866개**, 이벤트 승격 0개. 원본 캡처/리포트 SHA 사전·사후 동일 PASS. 신규 직접 API 호출/재수집 0.
- **검증:** 변경 영향 관련 **78 passed, 0 failed**, compileall exit 0. 스테이지 7개 명시적 파일 allowlist + 비밀 패턴/바이너리 크기/공백 검사 PASS; 사용자 미추적 원본/도면/설정 파일 미스테이지.
- **기능 commit:** `73a87949c938cf01ba436b0cf82ab17845bbcd4f`, `origin/main` 정상 push, `ls-remote` SHA 일치.
- **남은 1_1 차단요인:** 신뢰 가능한 원천 실제 대외 공개시각+정정/버전+발행자 증빙을 갖춘 공식 `RawEvent` 실물 0건, DART 첫 페이지 한계, SEC 전체 이력/issuer 미검증. 실제 AI API 0회, 연속 자동운영 0거래일. 외부 증거 전 무검증 자료를 정식 이벤트로 승격하지 않음.
- **엄격 V1.0 검증 완료율:** **0/36 (0.0%)**. 1_1 부분 기능 구현은 정상이나 1_1 전체 게이트 미충족. **NEXT_TASK=1_1** 유지.

## 2026-10-13 | 1_1 공개시각 주장·정정본 검증 후보 계약 (NC-1_1-CLAIM-GATE)
- **이번 실제 구현:** `src/newscatalystos/release_claim.py` + `tests/test_release_claim.py` + 패키지 공개 API + `docs/1_1_ERA_CAPTURE_READONLY_INTEGRATION.md` 갱신. DART/SEC 제공자·개별 접수번호와 HTTPS 공식 URL 구조, 별도 전달된 SHA256 pin, claim 시각·PIT, issuer 문자열/정정 버전·원본 ID 참조를 검사. 8KiB 제한 및 JSON 중복 키 거절.
- **안전한 거절:** 입력된 URL 문자열·로컬 digest는 독립 공개시각/발행자 진위 증명 아님. 결과 `PINNED_CLAIM_UNAUTHENTICATED` 유지, `RawEvent` 자동 전환 항상 거절. 기존 EraLeader 수집 코드·Git·DB/원본 및 별도 디스크 TOFU pin 쓰기 0; 직접 신규 API/AI 호출 0.
- **관련 검사:** 신규+기존 1_1 연결 테스트 6파일 **105 passed / 0 failed / exit 0**. 최초 신규 테스트 1건에서 예외 메시지 기대값 수정 후 영향 테스트 42 passed. Python compileall PASS.
- **보안 검수:** 코드/테스트/허용 문서 4개만 명시적 stage, staged allowlist 일치, 키/토큰/인증서 패턴·비텍스트·대용량 파일 검사 PASS, `git diff --cached --check` PASS. 사용자 미추적 문서/도면·로컬 백업 stage하지 않음.
- **기능 GitHub push:** `8233fe499a5a19e8f7d9f5d13a6451d37072de24` → `origin/main`; `git ls-remote` SHA 동일 검증.
- **남은 핵심 차단:** 공신력 있는 외부 원문/발행기관의 독립 공개시각 증빙, 실제 issuer/정정 이력 인증, 실제 공식 `RawEvent` 1건의 PIT 재현이 없어 `1_1` 완료 전환 금지. EraLeader 5개 기존 공식 캡처 연구용 read-only 실증은 직전 기록과 동일. 500건 평가/반도체 산업 통합/실 AI API/5거래일 운영은 미완료.
- **엄격 완료율:** **0/36 = 0.0%** (1_1 부분 구현). `CURRENT_NEXT_TASK=1_1`, 외부 증거 미확보 시 `DATA_UNAVAILABLE` 유지.

## 2026-10-13 | 1_1 외부 서명 증거 검증 경계 구현, 실제 완료 게이트 보류 (NC-1_1-SIGNED-PROOF)
- **실제 코드:** `signed_publication.py`에서 별도 신뢰 등록된 Ed25519 검증자의 공개키 SHA 및 원본 64바이트 서명 검증(OpenSSL 3), 공시 issuer/accession/정정/발행시각 주장/증빙 ID 상호 바인딩, `witness_verified_at`와 최초 수신 간 PIT 차단, `SignedPublication.as_of()` 제한 구현. `release_claim.py`는 `source_id` 보존과 SEC URL의 CIK 일치 검사를 강화. `__init__.py` 및 1_1 문서 갱신.
- **테스트:** 전체 1_1 관련 파일 7개에서 **127 passed, 0 failed**, `compileall` PASS, staged allowlist/공개 키·토큰/바이너리 검사 PASS, diff whitespace PASS. 합성 외부 서명 검증(긍정·위조·PIT·정정)은 **실제 공증이 아님**.
- **실제 EraLeader 재검증:** Mac 내부 별도 디스크 이전 TOFU pin 이용, 공식 캡처 5/5 오프라인 읽기 전용 SHA/PIT 확인 PASS, 연구 메타후보 3,866건, **실제 독립 발행 인증 RawEvent 0건**. 원본·설정·운영 DB·EraLeader 코드/Git 변경 0, 공식 신규 수집/API 재호출 0.
- **공식/독립 근거 조사:** SEC EDGAR 공시 `0001140361-26-039158`의 issuer·accepted 시각을 확인했으나 EDGAR 수리시각과 최초 외부 공개시각은 동일하지 않을 수 있음. 웹사이트의 제3자 사후 조회/수집시각 주장은 서명 또는 독립 역사 시점공증이 아니므로 자동 승격 차단.
- **기능 commit/push:** `c744909bf4f3ead33babc9788f77e9de480ae69b` `origin/main` 원격 SHA 일치. Public에는 허용 코드/합성 테스트/문서 6개 파일만 stage.
- **명확한 차단 조건:** 실제 독립 검증자의 사전 승인된 신뢰키 및 출처 공개시각·발행기관·정정 연쇄에 대한 독립 서명/시점 감사 증거가 없음. 직접 AI API 0회, 운영 0거래일. `1_1=미완료, DATA_UNAVAILABLE`; 엄격 완료 **0/36 = 0.0%**, 다음 작업 **1_1**. 신뢰 증거 없이는 가짜 완료/가짜 공시 시각 생성 금지.

## 2026-10-13 | 1_1 연구용 공식 관측 배치 실제 게시 (NC-1_1-OBSERVED-BATCH)
- **구현:** `src/newscatalystos/observed_batch.py`는 독립 로컬 핀으로 검증된 EraLeader 공식 완료 수신본을 구조화된 `ObservedOfficialBatch`로 정규화. `first_seen_at` / `usable_from=max(first_seen,pin 첫관측)` / 공급자 접수시각 / 품질 / 원본·영수증 SHA만 사용하고 `published_at=null`, `issuer_verified=false`, `research_only=true` 고정. 정식 `RawEvent` 승격 없음.
- **실행 가능 진입점:** `scripts/inspect_official_observations.py` 원격 실제 실행 PASS. 프로젝트 `output/`(Public GitHub ignore)에서 private staging → 원자 디렉터리 rename 게시, 동일 이름 기존 결과 비파괴. SSD 하드링크 미지원 오류를 실제 발견·수정.
- **실제 결과:** EraLeader의 게시 완료된 캡처 **5종**, 관측 메타행 **3,866개**, `RawEvent=0`; private JSON `2,513,011 bytes`, SHA256 `a7b572e395ce7ec8c8825fbe87c9aea49f19c1a165882523756ffc6ed1ae9328`; 게시 marker SHA/크기·모든 항목 release_at null 검사 PASS. 신규 공식 API 호출, 운영 DB/원본 데이터 쓰기 및 비밀 Git 업로드 0.
- **검증:** 1_1 관련 자동 테스트 **145 passed / 0 failed / exit 0**, compileall PASS, Git staged 허용목록 5개·키 패턴·바이너리/대용량·diff 검사 PASS. 기능 SHA `e5150be753323d610b1f265a93781eb662b226ab` `origin/main` 비강제 push/remote SHA 일치.
- **미완료:** SEC 접수와 공식 공개시각 인증은 다름. DART 기존 첫 페이지 자료는 하루 전체가 아님. 외부 신뢰 검증자/공식 공개시각·issuer/정정 실물 증빙 없음, 인증된 `RawEvent` 0, AI API·실운영 0. 따라서 `NEXT_TASK=1_1`, 엄격 완료수 **0/36=0.0%**, 상태 `DATA_UNAVAILABLE` 유지. 1_2로 진행한 것으로 보고하지 않음.
