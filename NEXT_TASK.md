# NEXT_TASK — 다음에 수행할 단 하나의 작업
작업 ID: 1_1
제목: EraLeader DART·SEC·KRX 공식 자료를 읽기 전용으로 가져오는 표준 계약 구현
상태: 1_1 연구용 실제 수신본 5종 read-only 검증 성공·57개 단위 테스트 PASS. 정확한 공시 release_at, 독립 신뢰 PIN 장기 보관, 실 RawEvent 정상화/검증은 미완료.
선행 조건: NewsCatalystOS 기존 폴더·정상 파일 백업 계획 확인, EraLeader 데이터 API 이용약관 및 원본 위치 확인.
목표: 신규 수집기 재작성 없이 EraLeader 검증 자료의 출처·원본 SHA·published_at/first_seen_at을 보존한 SourceManifest/RawEvent 인터페이스 확정.
시작 시: 현재 로컬 소스/Git/권한 확인→최소 어댑터 구현→가짜 출처/미래 시각/원본 불변 테스트→결과 기록. EraLeader 코드 변경 금지.
완료 조건: 지정 샘플 입력 정규화·PIT 차단·읽기 전용 검증 및 테스트 종료 0, 변경·Git SHA/미완료를 STATE에 기록.
그다음 작업: 1_2 허용된 신규 뉴스 수집원 목록 및 라이선스 계약 정의.
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
