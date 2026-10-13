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

## 2026-10-13 | API 데이터 공유 표현·경계 확정 (NC-READONLY-DATA-SHARE-2026-10-13)
- 사용자 첨부 5개 원칙을 AGENTS.md 및 Chat 개발 마스터 프롬프트에 추가, DECISIONS.md D-017 기록. EraLeader 공식 DART·SEC·KRX API는 기존 수집 기능을 유지하고, NewsCatalystOS는 수집·검증·게시된 결과를 읽기 전용 공유한다. NewsCatalystOS 자체 수집 범위는 EraLeader가 수집하지 않는 경제뉴스·기업 IR·정부 정책 등으로 제한. 독립 실행·공유 장애 격리·원본/분석 이력 보호·EraLeader 코드/중복 수집기 금지.
- **문서·정책 반영만 수행**: 코드 기능·API 연결·테스트 결과 새 완료 주장 없음, 1_1 여전히 미완료/0/36. 기존 36개 단계·반도체 산업 범위·PIT 및 V1.0 검증 조건 변경 없음.

## 2026-10-13 | 1_1 비공개 연구 배치 읽기 검증 및 PIT 게이트 (NC-1_1-READ-PUBLISHED)
- **구현:** `src/newscatalystos/published_observations.py`에 원자 게시된 NewsCatalystOS 자체 `output/` 연구 배치의 안전한 **읽기 전용 소비자** 추가. 별도 전달 SHA256 pin·원본/마커 SHA·크기·스키마·출처별 품질·처음 수신/앵커/로컬 게시시각의 PIT·원본/영수증 SHA·중복 차단, 심볼릭 링크·경로 탈출·미완성 게시 거절. `published_at=null`, `issuer_verified=false`, 연구 전용 유지.
- **기존 코드 최소 변경:** `inspect_official_observations.py` 로컬 게시 마커에 `first_local_published_at` 기록 추가; 과거 이 필드 없는 결과는 기존 그대로 보존하고 **소비 단계에서 보류**(소급 판단 금지). `__init__.py` 공개 API/문서/합성 테스트 추가. EraLeader 수집기·API 키·DB·Git·운영자료 변경 및 재수집 0건.
- **실데이터 검증:** 이미 별도 로컬 SHA로 고정된 EraLeader 공식 캡처 **5개**를 읽어 연구용 메타 **3,866행**을 NewsCatalystOS private `output/`에 새 원자 게시 → 소비자 재개방 PASS. 재게시된 배치 로컬 SHA256 `5573ce9abe6a7bc63d50a85a96fcbdb809b00f42e54015e9b13142b94f491a2e`. 이것은 **동일 컴퓨터 로컬 무결성 테스트**이며 독립 외부 공개시각 공증이 아님. 실제 RawEvent 0건.
- **테스트:** 1_1 관련 9파일 **170 PASS / 0 FAIL**, compileall PASS. staged 파일 5개 명시 허용목록·비밀/바이너리/크기·diff 검증 PASS. 기능 커밋 `801db132bbb0ea0b429f5916da174966d0db34f2` `origin/main` push 및 원격 SHA 일치.
- **여전히 미완료:** 신뢰할 만한 외부 발행기관의 실제 공개시각·issuer·정정 연결 시점 인증 증거 부재; SEC acceptance와 DART 날짜는 발표 시각 인증 아님. 실제 인증 이벤트 0, AI API 0회, 운영 0거래일. 현 `NEXT_TASK=1_1`, 엄격 완료 **0/36(0.0%)**, `DATA_UNAVAILABLE` 유지. 기존 36개 개발계획/공식 API 공유 정책 불변.

## 2026-10-13 | 1_1 공식 공유 연구 배치 v2 출처완결 검증 (NC-1_1-COVERAGE-V2)
- **실제 구현:** `observed_batch.py`의 `newscatalyst.observed_official_batch.v2`는 `source_coverage`에 모든 캡처의 원본/영수증 SHA, 제공자, 최초 수신, 품질, 원천 관측수, 정규화 메타수 기록. `published_observations.py` 소비자는 요약/행/문서ID/수신시각/품질/건수 교차검증 및 없는 출처·0행 소스 확인. 이전 v1 연구 배치는 삭제·변경 없이 하위호환으로 읽되 `coverage_verified=False` 명시.
- **실데이터:** 기존 EraLeader DART/SEC/KRX 완료 스냅샷 5개 읽기 전용→NewsCatalystOS 비공개 v2 원자 게시→재읽기 **PASS**. 원천 관측 총 **3,868건**, 연구용 메타 **3,866행**, SEC companyfacts 원천 **2건/뉴스 메타 0행**, 인증된 RawEvent **0건**. 이 실증은 로컬 PIT/무결성 검사이며 외부 독립 공시 공개시각 인증 아님.
- **검증:** 변경범위 9파일 **183 PASS / 0 FAIL**, Python compileall PASS. Public 명시 6파일 stage+비밀/텍스트/크기/공백 검사 PASS, `output/` ignore 확인. 기존 EraLeader 코드/원본/DB/Git 쓰기 및 중복 API 수집 0.
- **GitHub:** 기능 commit `e46b2619b337cd09fb8eec9131a5b121c9fd51ac` `origin/main` push 및 원격 SHA 일치.
- **아직 미완료:** 기존 정식 1_1 게이트인 공식 대외 공개시각·issuer·정정의 신뢰 가능한 독립 과거시점 증빙 부재, 실제 공시 RawEvent 검증 0. API 직접 수집·AI API 0회, 5거래일 운영 0일. `NEXT_TASK=1_1`, 엄격 완료 **0/36(0.0%)**, `DATA_UNAVAILABLE` 유지. 기존 36개 개발계획과 EraLeader 데이터 공유 정책 불변.

## 2026-10-13 | 1_1 EraLeader 원본–공개시각 독립서명 결합 구현 (NC-1_1-PROOF-JOIN)
- **실제 구현:** `official_promotion.py`에서 로컬 별도 디스크 독립 pin → 검증된 기존 EraLeader 공식 수신본 → 원문 ID/원본·영수증 SHA/최초 수신시각 → 신뢰 검증자 서명·PIT as-of를 하나의 읽기 전용 계약으로 연결. `OfficialCapture.source_request_value`에 기존 SEC 공식 수신 영수증 CIK를 보존하고 서명된 issuer/EDGAR URL CIK와 교차검사. `signed_publication.py` 필수 서명 스키마를 `publication_attestation.v2`로 올려 source/raw SHA·영수증 SHA·first_seen을 **서명 본문에 필수 결합**하며 구 v1 서명은 거절. 출처/원본 혼선·서명 재사용·미래정보 소급 방지. 기존 정상 코드 전체 재작성·API 중복 호출 없음.
- **검증:** 변경영향 10파일 `199 passed, 0 failed`, Python compileall PASS, Public 허용목록 7파일·키/원문/바이너리·diff check PASS. 합성 Ed25519 증빙의 유효·무효·틀린 issuer·다른 문서·anchor 이후 가용시각·변조 검증 통과. **실제 EraLeader** 기존 연구 인덱스/별도 로컬 pin 기반 공식 캡처 5종 재검증 PASS, SEC source_request_value CIK 수신 메타 확인. 실제 독립 검증자 서명은 여전히 **0건**.
- **GitHub 기능 커밋:** `ca804cd4aeafe717c909e90c0b56dbd7d2122a93` 원격 origin/main 푸시·SHA 확인. EraLeader 코드·원본·DB·Git 변경 0, 새 공식 API 호출/중복 수집 0, 민감정보 Public 미업로드.
- **1_1 완료 게이트:** 외부 독립 검증자의 신뢰키, 실제 DART/SEC 발표시각·발행기관/정정 증거와 그 최초 확인시각이 아직 없어 실물 인증 RawEvent **0건**. LOCAL_TOFU는 외부 공증이 아니며 합성 서명 테스트로 완료를 속이지 않음. `NEXT_TASK=1_1`, `DATA_UNAVAILABLE`, 엄격 V1.0 완료율 **0/36(0.0%)**. 직접 AI API 0회, 5거래일 운영 0일.

## 2026-10-13 | 1_1 지연 인증 증빙 PIT 누출 차단 수정 (NC-1_1-RAW-EVENT-ASOF-FIX)
- **실제 수정:** `SignedPublication.as_of`가 반환하는 `RawEvent.first_seen_at`에 `max(원본 첫 수신, 서명 검증 시각)`을 적용, `AnchoredOfficialPublication.as_of`는 별도 로컬 SHA pin 최초 관측 시각까지 적용. 이로써 서명/앵커를 뒤늦게 확보한 과거 수신본을 외부 소비자가 원래 수신 시각부터 인증됐다고 오인하지 못하도록 제한. 원본 최초 수신시각은 `source_capture_first_seen_at`에 별도 보존하며 `ObservedOfficialBatch` 연구 계약은 불변.
- **변경 영향 검증:** 1_1 관련 10파일 **200 passed, 0 failed**, Python compileall PASS. 새 지연-앵커 직렬화/PIT 회귀 시험 포함; 관련 코드와 doc 총 5개 파일만 명시 stage, 키/바이너리·diff 검사 PASS. EraLeader API/수집기·원본/운영DB/Git 변경 없음.
- **기능 GitHub SHA:** `78a53132ed87bb37ca6e5677348954dc002b7f53`, origin/main push 및 ls-remote 일치.
- **남은 완료 게이트:** 실제 DART/SEC 공시 발표시각·issuer·정정의 외부 독립 증명/승인된 서명 키가 없음. 합성 증빙 외 **실제 인증 RawEvent 0건**, 정식 1_1 단계 **미완료**, `NEXT_TASK=1_1`, 전체 완료율 **0/36(0.0%)**. 실제 AI API 0회·자동운영 0거래일, `DATA_UNAVAILABLE` 유지. 36개 계획 및 EraLeader 공식 API 데이터 읽기 전용 공유 범위 변경 없음.

## 2026-10-13 | 1_1 실제 외부 증빙 준비상태 CLI 구현 (NC-1_1-PROOF-CLI)
- **기능 구현:** `scripts/check_official_proof.py` 실행 도구를 추가하여 EraLeader의 기존 게시 완료 공식 수신본/별도 로컬 SHA 핀을 읽기 전용으로 검증하고 외부 증빙 유무를 fail-closed로 판정. 신뢰 자료가 없을 때 `DATA_UNAVAILABLE` / `certified_raw_event_count=0` / **exit 4** 출력. 독립 증빙(개별 공시 문서ID, 승인된 검증자 서명/키 지문/시각 등)이 제공되면 기존 `authenticate_from_era_readonly` 계약을 단일 검증 경로로 호출. 키·증빙 내용 stdout 노출 금지, 미완성 입력/미래시각/경로 심볼릭링크/크기 제한 방어. 기존 EraLeader API 직접 재호출/운영DB 쓰기 없음.
- **실물 오프라인 게이트 실행:** 기존 Mac 별도 pin과 EraLeader 2026-10-12 공식 연구 인덱스 사용. **수신 캡처 5/5 검증**, 증빙 미설정으로 `DATA_UNAVAILABLE`, **exit 4** 예상대로 반환(정상 종료 아님). 독립 공개시각·발행자·정정 외부 증거 여전히 없음; 정식 `RawEvent=0`.
- **테스트/공개:** 1_1 관련 11개 파일 **207 PASS / 0 FAIL**, compileall PASS. 보안 검수한 실행 코드·합성 테스트·허용 문서 **3개만** 선택적 stage; Public secret/바이너리 검사, diff --check PASS. 기능 commit `72cfb61abf37a07250568a7952df05b6bc77e042` `origin/main` 비강제 push 및 원격 SHA 동일.
- **완료 판정:** 현재 `1_1` **미완료**, 전체 **0/36(0.0%)**, `NEXT_TASK=1_1`, 외부 인증 증빙 없으므로 `DATA_UNAVAILABLE` 유지. EraLeader 정상 코드·DB·Git·원본 변경 및 공식 API 중복 수집 0. 실제 AI API 0회, 연속 운영 0거래일. 36개 개발 계획·반도체 한 산업 검증·완료 조건 불변.

## 2026-10-13 | 1_1 외부 증빙 검증자 사전 등록부 보안 강화 (NC-1_1-WITNESS-TRUST)
- **실제 구현:** `witness_registry.py`는 Mac 내부의 프로젝트 전용 owner-only 신뢰 등록부를 원본 SSD와 별개 디바이스에서 읽어 사전 등록된 검증자 고유 ID/허용 공식 제공자/등록시각/공개키 SHA256을 확인한다. 실제 등록부·키는 이번 작업에서 자동 생성하지 않음. `scripts/check_official_proof.py`의 `--witness-key-sha256` 동시 자가신뢰 옵션을 제거하고 이전에 신뢰 등록된 SHA만 서명 검증에 전달. 누락·위조·중복·이른 과거 판단·허용되지 않은 제공자는 실패 처리. 다른 프로젝트 파일/DB/Git/API 설정은 변경하지 않음.
- **검증:** 기존 1_1 관련 **222 passed / 0 failed / exit 0**, Python compileall PASS. 기존 EraLeader 공식 완료 캡처 5종 실제 읽기 전용 검사 PASS, 신뢰 증빙 미제공 상태 `DATA_UNAVAILABLE` / CLI 종료코드 **4** / 실제 인증 `RawEvent=0` 재현. Public 공개 대상 5파일 명시 stage/키·바이너리·크기/공백 검사 PASS.
- **GitHub 기능 SHA:** `dac46e90bd96ff15563040f54161fa56e5c31d4f`, `origin/main` 비강제 push 및 원격 SHA 일치. 기존 원본 수신본 5개/연구 관측 3,868·메타 3,866 수치는 이전 검증에 따른 기록이며 새 수집/성공 이벤트 발생 아님.
- **실제 잔여 조건:** 사전에 승인된 **진짜 독립 기관 검증자**와 DART/SEC 공시 공개시각·issuer·정정 이력·최초 증거 확보 시각의 외부 증거는 미확보. 등록부의 로컬 파일만으로 법적 공증을 주장하지 않음. `NEXT_TASK=1_1`, `DATA_UNAVAILABLE`, 엄격 완료 **0/36(0.0%)**. 실제 AI API 0회, 자동운영 0거래일. 기존 36개 계획/반도체 범위/EraLeader 데이터 공유 규칙 불변.


## 2026-10-13 | 1_1 독립 검증자 지연 등록 PIT 보완 (NC-1_1-WITNESS-ENROLLMENT-ASOF)
- **기능 수정:** 검증자 서명 검증시각보다 `witness_registry.enrolled_at`이 늦은 경우 `SignedPublication.usable_from` 및 외부 `RawEvent.first_seen_at`을 `max(원본 수신, 외부 서명 확인, 신뢰 등록, 별도 핀 관측)` 이전으로 소급하지 않음. 미래/시간대 미지정 등록시각 거절. `signed_publication.py → official_promotion.py → check_official_proof.py` 단계별 바인딩, 합성 음성 테스트 2건 추가.
- **검증:** 1_1 관련 전체 12개 테스트 파일 **224 passed / 0 failed (exit 0)**, compileall PASS, git diff --check PASS. Public 명시 7파일 allowlist/개인키·토큰·비텍스트/용량 검사 PASS. 원래 사용자 미추적 파일·비공개 운영데이터 공개/스테이징 안 함.
- **GitHub 기능 커밋:** `ba7f9583b056cd0c1c18e639c66e0e68b2ee9399` -> `origin/main` 비강제 push, 원격 SHA 동일 확인. 기존 EraLeader 코드/수집/운영 DB/Git 변경·공식 API 중복 호출 0.
- **증빙 한계:** SEC 공식 FAQ는 EDGAR 접수와 최초 웹 공개 사이 1~3분 이상 차이가 날 수 있으며 해당 최초 웹 공개시각을 나타내는 시각 필드가 없다고 밝힘(https://www.sec.gov/files/about/webmaster-faq.htm). 이 사실을 토대로 SEC 접수시각을 실제 공개시각으로 가장하지 않음. 외부 기관의 승인된 검증자/발행기관·정정/실제 독립 공개시각 서명 증빙 미확보: **실제 인증 RawEvent=0, DATA_UNAVAILABLE**. `NEXT_TASK=1_1`, 엄격 완료 **0/36(0.0%)**. AI API 0회/운영 0거래일 유지.

## 2026-10-13 | 1_1 실물 SEC 수신본 외부 증빙 요청 계약 (NC-1_1-PROOF-REQUEST)
- **기능:** `src/newscatalystos/proof_request.py` + `scripts/request_official_proof.py` 신설. 기존 EraLeader 공식 수신본/별도 Mac 디스크 SHA 핀을 오프라인 read-only로 검증한 뒤 지정 DART·SEC 문서 한 건에 대한 신뢰 검증자용 **비공개 메타데이터 요청서**를 생성. 원본/영수증 SHA·문서ID·수신/앵커 시각·provider acceptance만 담고, publisher 공개시각·issuer·정정 계보는 미입증 값 `null` 유지. 수집/쓰기/인증키 등록/외부 발송 없음.
- **실증:** 기존 SEC `0001140361-26-039158` 수신본을 대상으로 CLI 실행하여 `newscatalyst.external_proof_request.v1` 생성 PASS. 로컬 최초 수신/앵커 SHA 바인딩 성공, 결과 `EXTERNAL_EVIDENCE_REQUIRED_NOT_CERTIFIED`, `certified_raw_event_count=0`. 접수시각은 증명되지 않은 공개시각으로 승격하지 않음.
- **검증:** 합성 positive/negative/변조/미래·PIT·개별문서·공급자·실패시 비밀 경로 숨김 시험 포함 1_1 연계 13개 파일 **234 PASS / 0 FAIL (exit 0)**, compileall PASS. Public 4개 파일 명시 스테이징/개인키·키패턴·바이너리·용량·diff 검사 PASS. 사용자 미추적 파일/비공개 운영 자료 업로드 안 함.
- **GitHub 기능 커밋:** `afb9bf61d84d26782ed2f8823a6b5b3241fdf383` 원격 origin/main 푸시, 원격 SHA 동일 확인. EraLeader 원본·DB·수집기·키·Git 변경/중복 공식 API 호출 0건.
- **엄격 완료 조건:** 실제 승인된 독립 서명 검증자 및 발행기관의 공개시각/발행자/정정 연쇄와 독립 최초 증거 입수시점 미확보. 요청서는 실제 증빙이 아니므로 정식 RawEvent=0, `DATA_UNAVAILABLE`, `NEXT_TASK=1_1`, **0/36 (0.0%)** 유지. AI API 0회, 5거래일 운영 0일.

## 2026-10-13 | 1_1 외부 증빙 실제 도착시각 PIT 차단 (NC-1_1-PROOF-ARRIVAL)
- **수정:** 신뢰된 검증자 서명에 표시된 `witness_verified_at`만으로 과거 자료 사용 가능 시점을 소급할 수 없으므로, 실제 `check_official_proof.py`가 **증빙 파일 4개를 읽은 뒤** 확보한 UTC `proof_observed_at`을 필수로 `authenticate_from_era_readonly`에 전달. 결과 `usable_from=max(원본 첫 수신, 별도 pin 관측, 외부 검증자 등록·서명 확인, 실제 증빙 로컬 입수)`를 반영. `--decision-at` 이전에 도착하지 않은 증거는 파일 기반 원본 조회 전에 거절. 정식 이벤트 `RawEvent.first_seen_at`도 실제 증빙 사용 가능 시각 이상만 허용.
- **검증:** 새 합성 음성 시험 2개 추가; 1_1 관련 전체 **236 PASS / 0 FAIL (exit 0)**, Python compileall / git diff --check / Public 5파일 명시 allowlist·비밀 패턴·비텍스트·용량·gitignore 검사 PASS. 증빙·서명키·운영 DB 공개/중복 수집 없음. EraLeader 파일/코드/Git 쓰기 수행하지 않음.
- **GitHub 기능 SHA:** `8f24d48cf8abd0af782962cfd5ef0dd10a306e46` `origin/main` 정상 push, remote SHA 일치 확인. 사용자 미추적 문서·도면 미스테이징.
- **외부 조건 미충족:** 실제 승인 검증자 서명과 공식 외부 공개시각·issuer/정정 증거는 계속 없음. CLI에 실제 인증 증빙이 제공되지 않았으므로 `RawEvent=0`, `DATA_UNAVAILABLE`, `NEXT_TASK=1_1`, **0/36(0.0%)** 유지. 이 수정은 로컬 관측 PIT 가드이지 공시 공개시각 인증이 아님.

## 2026-10-13 | External evidence check (NC-1_1-EXTERNAL-BLOCKER-CHECK)
- Current verified Git HEAD before this checkpoint: 6c9a54c3ea53b3f29489ba15d4febc2f72986573. Separate-disk local PIT SHA anchor exists, but owner-approved independent witness trust registry and private proof inbox were NOT_FOUND. No new official external publication-time, issuer, correction-chain or trusted signed evidence was received.
- This session added no application code and ran no new tests. The previously recorded 236 PASS is a prior checkpoint, not a new test outcome. No EraLeader code/data/DB/Git changes or duplicate API calls. Official RawEvent 0; DATA_UNAVAILABLE, NEXT_TASK=1_1, strict 0/36.

## 2026-10-13 | 1_1 운영 인증 진입점 신뢰 등록부 우회 차단 (NC-1_1-ENTRY-TRUST)
- **발견/수정:** 이전에는 `scripts/check_official_proof.py`가 외부 검증자 신뢰 등록부를 먼저 확인했지만, 운영 파일 기반 `authenticate_from_era_readonly()`를 직접 호출하면 self-supplied 검증자 공개키 SHA/등록시각으로 진입하는 우회 가능성이 있었다. 이제 이 함수가 owner-only 별도 디스크 `load_operator_witness()`를 **직접 재확인**하고 사전 등록된 SHA와 사용자가 전달한 SHA·enrolled_at이 일치하지 않으면 EraLeader 원본을 열기 전에 실패. 내부 검증에는 등록부에서 직접 얻은 등록시각만 전달.
- **검증:** 직접 진입점의 등록부 누락/허위 SHA/등록시각 회귀 시험 2개 추가. 1_1 전체 관련 **238 PASS / 0 FAIL**, compileall PASS, git diff --check PASS. Public 3파일 explicit stage·비밀키/토큰/바이너리/크기·.gitignore 검사 PASS. EraLeader 코드/운영DB/원본/Git 변경 및 직접 API 중복 수집 0.
- **기능 GitHub:** `6f2ae882c2f0f5c8e1db033c49fd7da75e15a3af` `origin/main` 비강제 push, 원격 SHA 일치 확인. 기존 미추적 사용자 자료·도면 무변경/스테이지 제외.
- **완료 제약:** Mac 외부 검증자 owner-approved 등록부·실물 독립 검증자 증거/원천 최초 웹 공개시각·issuer·정정 계보가 아직 존재하지 않음. 코드 안전 경계 보완 ≠ 실증 인증. 공식 `RawEvent=0`, `DATA_UNAVAILABLE`, `NEXT_TASK=1_1`, **엄격 완료 0/36(0.0%)** 유지. AI API 0회, 5거래일 운영 0일.

## 2026-10-13 | 1_1 관측형 운영 게이트 합격 · 1_2 권한 등록부 개발 착수 (NC-OBSERVED-PIT-MODERATE)
- **사용자 직접 승인 D-018:** 과거 웹 최초 공개시각 외부 공증은 고정밀 검증용으로 유지하되 1_1 필수 완료조건에서 제외. NewsCatalystOS가 검증한 **실제 로컬 시점 이후만** 데이터를 사용할 수 있는 `OperationalObservation`을 별도 이벤트 타입으로 채택. `published_at=null`, issuer 검증 FALSE, `RawEvent` 자동 승격 금지 유지.
- **1_1 실제 관측형 공유:** 기존 EraLeader DART·SEC·KRX 원자 게시·SHA/영수증/PIT/품질 기반 private v2 5소스, 관측 메타 **3,866**(공시 1,101 / KRX 시장 참고 2,765), 최초 웹 공개 인증 `RawEvent=0`. `available_at=max(원본 수신, 앵커, 로컬 원자 게시, **새 소비 검증 시각**)`으로 과거 정보 누출 차단; 과거 백테스트 인증과 다르게 운영 관측형 합격. 새 코드 `operational_observations.py` 및 9개 합성/오류 회귀 시험.
- **1_1 판정:** 조정된 관측형 1_1 인수기준(5개 출처 read-only, SHA/PIT·원자 게시·부분범위 경고, 원본/다른 프로젝트 코드 불변, 오류 주입, 관련 테스트) PASS. **단계 완료 1/36(2.8%)**, `NEXT_TASK=1_2`. 외부 최초 대외 공개시각·신원/정정 서명 공증은 선택 모듈로 계속 미완료이며 과거 PIT 인증을 주장하지 않음.
- **1_2 기능 구현 착수:** `provider_registry.py`에서 정부 정책·기업 IR·허용된 언론 RSS/API의 권리검토/만료/요청 상한/원문 저장 허가를 **기본 거부**로 처리; EraLeader DART/SEC/KRX 중복 수집 금지. `new_source_adapter.py`는 허가된 입력 바이트의 RSS/JSON 헤드라인·문서 ID·URL·관측시각만 정규화, 원문·비밀·API 직접 호출 없음. 테스트 source URL/권한은 합성. 실제 신규 소스 이용권한 확인/라이브 수집이 없어 **1_2는 부분 구현 미완료**.
- **실제 검증:** 1_1~1_2 코드 포함 영향 범위 전체 `281 passed / 0 failed`, compileall PASS, staged 명시 allowlist/비밀패턴·바이너리·크기/공백·.gitignore 검사 PASS. 기존 EraLeader DART·SEC·KRX 코드/DB/Git 변경과 중복 API 호출 없음; 사용자 미추적 파일 무변경.
- **GitHub 기능 SHA:** 1_1 `d8d0b45139ef5429303fb5bc28da483a94a454f0`, 1_2 `abf396d99fea418f0d6adb2c0211964fed8b99ff`; 각각 origin/main 정상 push 및 원격 SHA 대조 성공. 상태 문서 최종 커밋 별도 기록.

## 2026-10-13 | 1_2 중소벤처기업부 공식 RSS 실제 헤더 검증 (NC-1_2-MSS-RSS-SMOKE)
- **검증된 신규 공식 출처:** 중소벤처기업부 `https://www.mss.go.kr/rss/smba/board/86.do`, 공식 RSS 제공 안내 `https://www.mss.go.kr/site/smba/contents/view.do?menuCd=20905000000002024122902&siteCd=smba`. 실제 Mac HTTPS GET 1회, RSS XML **6,760 bytes**, 항목 20개. 새 권한 게이트/헤더 어댑터에서 **관측 20 메타/고유 ID 20/원문 본문 보관 0/공개시각 외부인증 0** 정상 파싱. 기존 EraLeader 중복 공식 API 호출 아님.
- **표준 소스 경계 보완:** 일반 정부 문서 링크 쿼리 `cbIdx/bcIdx` 허용, API 비밀키/토큰 쿼리는 거절. 중단된 `korea.kr` RSS는 2026-07-01 공식 서비스 제공 종료 공지로 인해 활성 제공자에서 제외; 본문 라이선스 확대·자동 재게시 안 함.
- **테스트:** 관련 총 **282 passed/0 failed**, compileall PASS. 이번 1_2 라이브 1회는 매시간 자동 운영/스케줄/리트라이 통합 완료가 아님. 기업 IR 및 허용된 언론 소스 별도 실연동·권한 범위 검증 필요, **1_2 부분 구현**, 전체 **1/36(2.8%)** 유지.

## 2026-10-13 | 1_2 공식 신규 RSS 2개 실연동·단발 실행 완료 (NC-1_2-LIVE-GATE)
- **이번 구현:** `feed_transport.py`(허가된 ProviderRegistry → TLS HTTPS 단발 GET → 리다이렉트·403·5xx·크기/Content-Type/시간초과 거절 → metadata-only 파싱), `scripts/check_new_feed.py`(owner-only 0600 제공자 등록부 읽고 이름/관측수/가용시각만 출력), 합성 장애·권한 테스트. 네트워크 호출 시도는 해당 신규 승인 공급원에만 한정; EraLeader DART/SEC/KRX 추가 수집 0.
- **실제 승인 공개 RSS:** 중기부 `https://www.mss.go.kr/rss/smba/board/86.do` 20건, 뉴스와이어 IT 보도자료 `https://api.newswire.co.kr/rss/industry/600` 15건. 각각 공식 RSS 이용 안내 링크 확인, Mac 보안 연결 CLI에서 1회 성공. **35 메타/고유 관측**, 기사 본문·원문 파일/인증정보 저장 0, 최초 웹 공개시각 독립 인증 0, 주장 미확인 유지. URL/권한 참조만 별도 Mac 내부 디스크 `~/Library/Application Support/NewsCatalystOS/providers/authorized_sources.json` owner-only 0600/폴더0700 신규 생성, 기존 파일 덮어쓰기 없음; Public 업로드 금지.
- **안전 비활성:** 삼성물산 건설 공식 RSS GET HTTP 403, 우회 금지·미활성화. 삼성전자 뉴스룸 콘텐츠 이용약관은 비상업적 개인 이용 중심이라 별도 허가 전 미활성. 행안부 RSS는 기존 설정한 128KiB 한도 초과 시 거절. 뉴스와이어는 보도자료 유통 플랫폼이므로 독립 언론 보도/사실 인증으로 간주하지 않음. 기타 IR 허가 미확인 소스는 `ProviderRegistry`에서 disabled.
- **검증:** 기존 282개 + 신규 15개 = **297 passed / 0 failed**, compileall PASS, 403/redirect/5xx/과대/만료/미승인/본문 금지·속임수 음성 시험 PASS. Public 6개 파일 allowlist·비밀/원문/바이너리/용량·.gitignore 검사 PASS.
- **기능 Git SHA:** `e3a28b4c0eb3669d2972daef14dc6be897b9cfe1` origin/main push SHA 일치. D-019 승인된 운영 기본 게이트에 따라 **1_2 완료, 전체 2/36 (5.6%)**. 비활성 회사 IR은 권한 확인 후 설정 추가 가능; V1.0 타 단계/반도체 한 산업 계획 변경 없음. 다음 `NEXT_TASK=1_3`.

## 2026-10-13 | 1_3 증분 RSS 수집/워터마크·백오프 구현 및 실제 검증 (NC-1_3-INCREMENTAL)
- **기능:** `src/newscatalystos/incremental_ingest.py`에서 Mac 내부 독립 NewsCatalystOS owner-only `state/incremental_feeds.sqlite3` SQLite 원장에 제공자별 요청시각·마지막 성공 watermark·SHA 이벤트ID/처음 검증 시점만 보관. 기사 제목/URL/본문/원본/키 저장 안 함. `BEGIN IMMEDIATE` 요청 예약/중복방지·원자 커밋, 실패 시 기존 성공 watermark·이력 보호. 429/5xx 실패지수 백오프(최대 1시간), 401/403 자동 요청 중단·추가 운영자 권한 재검토 후 수동 복구. 기존 `feed_transport.py`에 오류 유형만 추가, 정상 기존 코드 보존.
- **실행 도구:** `scripts/run_incremental_feed.py`의 `--all-approved` 또는 개별 승인 provider, 실패 소스 장애 격리/NOT_DUE 노출. `scripts/launchd_incremental.py`는 **15분 템플릿**을 Mac 내부 owner-only `launchd/`에 생성하고 `plutil -lint` PASS, 파일 권한 0600, **launchctl bootstrap 호출/백그라운드 자동 실행 시작 없음**.
- **실데이터 1_3 통합:** 사용자 승인된 중기부 공식 RSS **최초 신규 메타 20**, 뉴스와이어 IT RSS **최초 신규 15** `SUCCESS_NEW`, 소스별 원장 저장/확인 PASS. 직후 같은 명령 재실행 두 소스 모두 `NOT_DUE`; 다음 가능시각은 약 30분 이후, 추가 네트워크 GET **0**. 로컬 상태 `seen_count=20/15`, 실패 수 0, SQLite 퍼미션 0600, 본문 저장·공개시각 독립 인증/실물 `RawEvent=0`.
- **검증:** 기존 포함 변경 영향 관련 전체 **323 PASSED / 0 FAILED**(exit 0), Python compileall PASS, `plutil -lint` PASS. 신규 커버리지: 멱등/신규 증분/워터마크/시간 예산·동시 예약/실패 보존/429·403/권한 재검토/DB 경로 모의 공격/PIT 미래/launchd 설정. Public 9파일 허용목록·민감 키/바이너리·크기·diff 및 .gitignore 검사 PASS. EraLeader 코드/수집기·DB·Git/키 쓰기·중복 공식 API 호출 없음.
- **GitHub 기능 커밋:** `664b30c3da9563bc07cf16cb94cb8991baf5d802` `origin/main` 비강제 push 및 SHA 일치. `1_3` 기본 기능 완료, **3/36 (8.3%)**, 다음 `1_4` 공통 시각/기업 ID 정규화. 아직 활성화되지 않은 자동운영/5거래일/릴리스 완료를 주장하지 않음.

## 2026-10-13 | 1_4 공통 시각·기업ID·정정 PIT 정규화 구현 (NC-1_4-EVENT-IDENTITY)
- **신규 기능:** `src/newscatalystos/event_identity.py`에서 기존 `OperationalObservation`·`FeedObservation`를 `NormalizedEvent v1`로 변환. `first_seen_at`·`collected_at`(별도 원시 수집시각 없을 때 first_seen 기반)·`verified_at`·`available_at`·`decision_at`을 별도로 기록하며 UTC/조회 시각 이후 정보 소급 방지. `published_at` 미확인 `None` 유지. SEC_CIK/DART_CORP/KRX_STOCK 운영자 검토 바인딩과 정정 RevisionEvidence는 출처ID/문서ID·SHA·최초 실제 증빙 관측/PIT·네임스페이스 검사. 운영자 검토 ≠ 공식 issuer 외부 인증; 자동 기업ID·종목코드 추측 없음.
- **서명 경계 보존:** 유효한 기존 `AnchoredOfficialPublication` 객체만 `normalize_attested_publication`에서 witness-signed 주장으로 처리(합성 서명 테스트). 임의 JSON/RawEvent를 외부 공개인증으로 승격하지 않음. DART 회사코드 형식이 불분명하면 네임스페이스 검증되지 않은 신원으로 분리.
- **실제 기존 데이터:** EraLeader의 기존 공식 5개 게시 완료 스냅샷에서 구축된 NewsCatalystOS private v2 연구 배치 **3,866개**를 새 모듈로 오프라인 읽기 정규화 PASS. 공시 관측 1,101/KRX 시장자료 2,765. 원천 발표 공개시각 임의 확정 0, 임의 issuer 및 정정 0, `available_at < 검증 시각` 0. 같은 Mac 로컬 SHA 검증은 독립 역사 시각공증이 아님. 신규 DART/SEC/KRX 네트워크 재수집·EraLeader 코드/DB/Git 쓰기 없음.
- **검증:** 신·구 연결 전체 1_1~1_4 관련 `345 passed/0 failed`(exit 0), Python compileall PASS. 합성 UTC/소급/매핑 문서·증거SHA/정정 자기참조/서명 경계/원본 불변 테스트 및 실제 3,866건 정규화. Public 명시 stage 4파일 허용목록·비밀키 패턴/바이너리·크기·diff·.gitignore 검사 PASS. 기존 사용자 미추적 파일/도면/비공개 데이터 stage하지 않음.
- **기능 SHA:** `c6406375654928e7fc380bccb9f729cc6d9f79cc` → `origin/main` 푸시, 원격 SHA 동일 확인. **기본 작업 1_4 완료, 4/36 (11.1%)**, 다음 `NEXT_TASK=1_5` 원본/영수증 SHA 안전 보관·정정 버전. 실제 외부 발표시각 서명 증거·AI API·5거래일 자동운영은 아직 미검증.

## 2026-10-13 | 요청된 36단계 연속 개발 — 1_5,1_6,2_1,2_2 기본 구현 (NC-1_5-2_2-BATCH)
- **사용자 지시:** 기존 4/36에서 36/36까지 완료 희망. 현재 Chat/원격 연결 안에서 실제 코드를 계속 구현했으나 5거래일 운영 등 실제 시간·검증이 필수인 조건은 완료로 가장하지 않는다.
- **1_5:** `evidence_archive.py` owner-only private 원자 게이트에서 허가된 RSS 메타데이터·명시 글자수/보관권한을 통제, 원본 SHA/영수증 SHA·버전/정정 불변 보존. 원본 최초 확인과 실제 아카이브 완성시각을 분리하고 역사 소급 불가. 기존 private source registry 기반 **실제 Mac 개인 디스크 합성 메타 225B 원자 보관/재검증 PASS**, 기사 유료 원문 0, EraLeader 변경 0.
- **1_6:** `quality_watch.py` 및 `scripts/check_feed_quality.py`: 첫 수집 누락, 빈 응답, 403·429, 품질 저하/신선도 및 미수집 범위를 PENDING으로 기록, 성공 복구 시 해결 완료시각 남김. **실제 private 상태** 중기부/뉴스와이어 2소스 HEALTHY·CLEAR, pending=0, raw source 보관 0. 기존 1_3에 빈 피드가 성공 watermark를 기록하던 결함 수정.
- **2_1:** `text_normalization.py` 허가된 헤드라인 UTF-8/NFKC/HTML 안전 정규화, source URL 파라미터 추적키 제거·문서 식별 키 보존, 입력 SHA와 검증·결정시각 분리 및 원본 무변경. 합성 RSS HTML/URL/PIT 테스트 PASS.
- **2_2:** `exact_dedup.py` 개인용 SQLite SHA index에 제공자별 ID·정규화 URL·원문으로 허가된 제목의 SHA를 저장하여 NEW/DUPLICATE/REVISED 구분, 똑같은 재수집은 AI 호출대상 제외, 변경된 제목/수치/정정은 새 버전으로 추적, 독립 출처는 강제 하나로 병합하지 않음. 공개 아카이브/뉴스 본문 또는 사용자 개인정보 기록 없음.
- **변경 영향 검증:** 기존 + 신규 pytest **396 PASS / 0 FAIL**, Python compileall PASS, 명시 stage 허용목록 13파일·Public 비밀/바이너리·크기/.env·운영 DB·output 제외 검사 PASS. Code SHA `e88351664aabc7e49ec18469ca757b06f87f06c7` origin/main push·SHA 동일 확인.
- **보통 수준 기본 개발 완료:** 1_1~1_6, 2_1~2_2 **8/36 (22.2%)**. 2_3~6_6 **28단계 미완료**, 실제 5거래일 운영 및 반도체 공급망·중요 뉴스 정답셋 95% 검증·AI API 정식 검증·릴리스 태그 미완료. 다음 `NEXT_TASK=2_3`. 작업환경은 장기 자율 백그라운드 코딩 서비스를 시작하지 않음.

## 2026-10-13 | 2_3~3_6 연속 코딩 체크포인트
- **기본 구현 완료:** 2_3 `event_cluster.py`(수치·금액·정정 정보 보존, 검토된 동일 원천만 묶기), 2_4 `claim_filter.py`(광고/SNS·익명 루머 차단), 2_5 `origin_provenance.py`(다중 재배포 독립 증거 과대계산 방지, 공식 반박 HOLD), 3_1 `prior_fact_state.py`(SQLite owner-only PIT 과거조회), 3_2 `novelty_detection.py`(제목 변경과 신규 경제주장 구분), 3_3 `barrier_changes.py`(이전 장애 이력 없는 자동 해소 금지), 3_4 `change_followup.py`(기존 사건의 실현/지연/취소·정정 버전 유지), 3_5 `impact_triage.py`(검토 우선순위/UNKNOWN, 매출 추론 금지).
- **부분 구현·실증 미완료:** 2_6 `filter_evaluation.py`는 confusion matrix/정밀도/recall·중요 누락 목록·제외 표본, 3_6 `detection_history.py`는 최초 관측시각·변경버전 SHA 불변 이력과 recall 평가 함수를 구현. 각각 실제 검수 gold set **중복 precision 95% / 중요 신규 탐지 recall 90%** 미확보로 완료 판정 보류.
- **검증/보안:** 이전 396 PASS에서 신규 2_3~2_6 테스트 41, 3_1 8, 3_2~3_6 테스트 36 추가해 **481 PASS / 0 FAIL**, compileall PASS. Public 허용목록/민감 패턴/바이너리/크기/.gitignore 검사 PASS. 비공개 키·유료 뉴스원문·운영 DB 공개 0; EraLeader 코드/DB/Git 수정·공식 API 중복 수집 0.
- **기능 Git SHA:** `3bcdbc7990bca606ba1bad93bb965d3b03c4246c`, `f3d8230bf1a32256ae8b6509deef81af04bb53b5` origin/main 푸시 성공·원격 SHA 동일 검증.
- **정확한 완료 현황:** 기존 8 + 2_3~2_5의 3 + 3_1~3_5의 5 = **16/36 (44.4%) 기본 구현 완료**. 2_6·3_6 인수 미완료, 4_1~6_6 18작업 미완료 = 20단계 잔여. 반도체 실제 공급망/AI 공급자 실호출/라벨셋/5거래일 운영·V1.0 출시 태그 미완료.

## 2026-10-13 | 4_1~5_5 신규 구현·통합 (NC-4_1-5_5)
- **4단계:** `ai_provider.py` OpenAI/Gemini/Anthropic 공통 JSON·토큰/가정단가 계약, 중요 신규·PIT 메타만 요청, transport 주입 없으면 DATA_UNAVAILABLE. `fact_extraction.py` 원문 조각 금액/날짜 exact match 외 hallucination 거절, `claim_boundaries.py` 공식 채널/언론/배포/SNS/AI 가설 분리(issuer는 신뢰 AnchoredOfficialPublication 필요), `economic_path.py` 수요/공급/CAPEX/실적/경쟁의 반대 근거 필수, `analysis_validation.py` AI-금액·인용-파급 SHA 연결·불일치 UNKNOWN_HOLD, `ai_cost_ledger.py` 사건·모델·prompt 중복 재요청 차단·월 3만원 소프트·5만원 하드·예약/정산 SQLite.
- Mac shell에서 OPENAI_API_KEY/GEMINI_API_KEY/ANTHROPIC_API_KEY **환경변수 존재 여부**만 조회(모두 false), 키 읽기·실 유료 AI 전송/요금 결제 0. 모델 가격은 운영자 가정치. **4_1·4_2·4_5·4_6** 실통합/4_2 95%/4_6 라벨 500·실비용 등 완료 미충족. **4_3·4_4**는 출처분리/반례포함 기본 기능 테스트 PASS로 완료.
- **5단계:** `semiconductor_profile.py` SemiconductorProfile v1 9부문(메모리 DRAM/NAND/HBM+웨이퍼/장비/소재/기판/패키징/테스트), 7 영향 경로. **5_1 기본 기능 완료.** `supply_chain_graph.py` 공급자·고객 별도 기업 바인딩 및 원문 SHA·PIT·direct-vs-thematic, `semiconductor_impact.py` HBM/CAPEX/패키징/테스트 경로, `beneficiary_classification.py` 잠재수혜/잠재손해/테마 구분, `beneficiary_graph_contract.py` 버전형 후보 JSON·출처SHA. 공급망 실계약·증빙 검증 및 EraLeader 소비 연동 없으므로 **5_2~5_5 인수 미완료, 5_6 실제 사례 평가도 미완료**. 확인된 실제 수혜기업/매출 기여/정식 법인 인증 생성 0.
- 기존 원본·EraLeader 코드/DB/Git/PIT/SHA 수정·DART/SEC/KRX 재수집 0, 자동매매/홈페이지/다른 산업 구현 0. 신규 총 24코드·테스트·문서 파일 Public 명시 staged/토큰·키 패턴/바이너리/크기/.gitignore 검사 PASS.
- **검증:** 신·구 합계 `566 PASS / 0 FAIL`, Python compileall 및 Git diff check PASS. 신규 `docs/4_1-5_5_IMPLEMENTATION.md`에 완료/미완료 세부 구분. 기능 Git SHA `80f8c838445c4954b703242415a8eb5ab5cf196f` origin/main 푸시·원격 SHA 일치.
- **완료 카운트:** 이전 16 + 4_3/4_4(2) + 5_1(1) = **19/36 (52.8%)**. 미완료 2_6·3_6(2), 4_1/4_2/4_5/4_6(4), 5_2~5_6(5), 6_1~6_6(6) = **17개**. 실제 독립 라벨·반도체 공급망 증거·5거래일 운영·P0/P1·V1.0 release tag 없음. 다음 구현 가능한 6_1 이벤트 생명주기, 동시에 앞 단계 실검증 게이트는 별도 보류.

## 2026-10-13 | 6_1~6_6 신규 기능/출시 게이트 구현 — V1.0 출시 미완료 (NC-6_1-6_6-CODE)
- **6_1:** event_lifecycle.py — DETECTED→CONFIRMED→STRENGTHENED/WEAKENED→INVALIDATED + INVALIDATED→DETECTED 재활성화; 기존 SQLite 원본 보존·PIT/근거 SHA. 아무 자료나 CONFIRMED로 승격 금지, 기존 AnchoredOfficialPublication 타입과 해당 event ID가 일치해야 공식 확인 주장 가능. 재활성화 이전 이력 삭제/무뉴스 자동 만료 금지.
- **6_2:** analysis_cache.py — event/version/model/prompt/metadata SHA 바뀌지 않으면 별도 AI 재분석 방지. SHA 검증된 bounded 응답만 private SQLite에 저장하며 AI 가설 사실 승격 금지.
- **6_3:** catalyst_audit.py — 사건별 근거 SHA/첫 관측·실제 등록시각/상태 변경/AI 모델·프롬프트 해시를 append-only, PIT 당시 원장 조회 및 변경 이력 보존.
- **6_4:** standard_delivery.py — 동일 사건 ID·시점 근거 묶음 CatalystEvent/BeneficiaryGraph/EventHistory를 JSON/Parquet로 버전화, SHA 확인·잘못된 source/cross-event/과거 누출/미확인 수혜 확정 거부. 실제 EraLeader 수신 환경 소비와 법적 공개 증거는 미검증이나 계약 기본 구현 통과.
- **6_5:** backup_recovery.py — 활성 NewsCatalystOS private SQLite의 일관성 백업/매니페스트 SHA 및 별도 복원 디렉터리 신규 0600·0700/SQLite PRAGMA integrity_check 검증. 실제 Mac incremental_feeds.sqlite3 45,056 bytes를 private Mac 백업 폴더에 SHA 고정한 뒤 다른 owner-only 디렉터리에서 복원 PASS. **다른 물리 장치의 독립백업·연속 5거래일 실제 자동운영은 하지 않았으므로 6_5 미완료**, 기존 launchd 예약 템플릿은 미활성.
- **6_6:** release_readiness.py + scripts/check_v1_release.py — 36개 단계, 실제 사람검수 라벨 500·정밀도/중요 탐지·수혜 정확도/숫자 증거, 실 AI 요금, 5거래일/독립복원/타 프로젝트 소비/P0-P1/전체 회귀 입증 부족을 명시. 23개 완료를 입력한 실제 Mac 실행 결과 **NOT_READY, missing 13 tasks, exit 4(의도된 출시 차단)**. 합성 모든 조건 True여도 독립 출시 인증 FALSE, V1.0 tag 생성/푸시 안 함.
- **기능 검증:** 전체 관련 테스트 **611 PASS / 0 FAIL**(exit 0), Python compileall PASS, Public 허용목록 staging 18파일·민감 패턴·바이너리/용량·.env/DB/원본 제외 및 git diff --check PASS. EraLeader 코드/DB/Git·공식 수집 API 호출/변경 0. 기능 Git SHA **648806f6984e3ef6a1d7bf25114cbc49d6f334db**, GitHub origin/main 정상 비강제 push 및 remote SHA 일치.
- **엄격 개발 합격 23/36(63.9%)**: 기존 19/36 + 6_1~6_4 네 기본 기능. 아직 13개 미완료: 2_6,3_6,4_1,4_2,4_5,4_6,5_2,5_3,5_4,5_5,5_6,6_5,6_6. 실제 경제뉴스 정답셋/AI 키·비용/공식 고객·공급자 거래·EraLeader 소비/별도 물리복원·5거래일/출시 태그 증명 없음. 다음은 5_2 공식 공급망 관계 read-only 실증 시도; 증거 없으면 UNKNOWN, 허위 수혜 확정 금지.

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

## 2026-10-14 | 5_2 실제 문서 도착 대비 독립 PIN + PIT 오프라인 입력 연결
- **기능 Git SHA:** `c189f632b9f7178629dfb7e53d5dc37f1650e2a1` 원격 `origin/main` non-force 푸시/동일 SHA 확인. `official_relation_intake.py`가 완료된 v2 공개 메타를 별도 payload SHA로 소비하고 owner-only 사람 검토 JSON·공식 문서 UTF-8 텍스트·별도 문서 SHA를 결합하도록 구현. `scripts/review_supply_relation.py`는 계약/매출이 확정되지 않은 관계 후보의 SHA·검토시점만 출력, 원문 미저장·네트워크/재수집 0.
- 기존 `review_official_supply_relation`에 `consumer_observed_at` 선택 계약을 추가해 검토자 과거 날짜·새 소비시점의 PIT 혼동 수정. 첫 완전 검증 시점 전에는 관계 후보를 소급 노출하지 않음. 기존 타입·함수 기본 호출 유지.
- **변경 영향:** 공식 리뷰/그래프/관측 게시 6개 테스트 파일 **81 PASS / 0 FAIL**, compileall PASS, Git diff --check PASS, staged 파일 5개 explicit/Public 비밀 패턴 검사 및 ignore 검사 PASS. 기존 사용자 미추적 도면·문서 원형 유지, EraLeader 코드·DB·Git·DART/SEC/KRX API 호출/변경 0.
- **실증 미완료:** 실제 승인된 공식 반도체 거래문서 본문/사람 검토 관계 0건, 500건 사람이 검수한 gold 0, AI 공급자 실호출 및 5거래일/독립 물리 DR 미진행. 5_2는 도구 준비 기능만 통과했으며 **완료 23/36(63.9%), NEXT_TASK=5_2 실문서/관계 실증** 유지. 미확인 거래·매출·투자확정 주장 금지.
