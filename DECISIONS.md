# DECISIONS — 확정된 프로젝트 경계
D-001: NewsCatalystOS는 뉴스 분석 전용 독립 프로젝트. 투자전략, 자동주문, 홈페이지는 다른 프로젝트.
D-002: EraLeader의 DART/SEC/KRX 및 PIT 증빙은 읽기 전용 데이터 공유. 수집기 중복 개발 금지.
D-003: V1.0 단계: 뉴스 수집(1), 필터(2), 경제적 변화 탐지(3), AI 분석(4), 공급망(5), 생명주기·공유(6); 세부번호 각 1~6.
D-004: 공급망 V1.0 실증 산업은 반도체 1개. 완료 뒤 후속 산업 추가는 별도 승인/V1.1.
D-005: 미확인 SNS/중복 재보도는 확인된 사실로 판단하지 않음. 공식 발표·공시 근거 우선.
D-006: AI는 실제 구조화 분석에 사용하되 저비용·적은 호출을 우선한다. 최종 공급자는 정확도/비용 비교 후 1곳 결정.
D-007: 월 AI 분석비 3만원 목표/5만원 상한(수집데이터 이용료·서버 비용 별도).
D-008: 분석 근거와 최초 공개·수집·판단 시각을 PIT로 보존. 허가되지 않은 기사 원문은 장기 저장하지 않음.
D-009: P0/P1 오류 0, 정답셋 정확도, 반도체 검증, 5거래일 자동운영, 백업·복원, 전체 테스트로 V1.0 완료.
D-010: 개인화 알림·실거래·유료 SNS·홈페이지 개발은 V1.0 범위 밖. 신규 아이디어는 V1.1 백로그에만 기록.
D-011: 새 채팅에서 '개발계속하자'로 프로젝트 내부 상태 문서를 읽고 다음 작업부터 재개한다. 같은 프로젝트에서 Remote Desktop Commander가 연결된 경우에 한함.


D-012 (NC-PARALLEL-2026-10-13): EraLeader와 NewsCatalystOS는 **동시에 독립 개발 가능**. 각자 소스·DB·테스트·Git을 분리하고, EraLeader 공식 DART/SEC/KRX 결과는 검증·게시 완료된 스냅샷만 NewsCatalystOS가 읽기 전용 소비한다. 원본/코드 변경 및 API 중복 호출 금지. 같은 Mac에서 고부하 전체 테스트·백업은 시간 분리. 기존 V1.0 36개 개발 범위는 그대로 유지한다.

D-013 (NC-PUBLIC-REPO-2026-10-13): 사용자가 GitHub **Public** 저장소 arirang0605-lgtm/1.NewsCatalystOS 를 직접 생성했고 공개 소스·허용 문서의 단계별 푸시를 승인했다. GitHub 주소 https://github.com/arirang0605-lgtm/1.NewsCatalystOS.git, 기본 브랜치 main (실행 시 재확인).
D-014: 공개는 API 비밀키·유료 뉴스 원문·원본 운영 DB·백업·사용자 투자정보·개인정보의 공개를 허용하지 않는다. 첫 스테이징 전 .gitignore 및 스테이지 대상 비밀정보/저작권 검사를 필수 수행한다. Public 여부만으로 오픈소스 라이선스를 자동 선정하지 않는다.
D-015: 최초 확인 당시 NewsCatalystOS SSD 폴더는 Git 미초기화이며 원격 Public 저장소는 빈 상태였다. 1_1 시작 시 기존 폴더·사용자 자료 보존을 전제로 안전한 Git 연결(최초 사용자 승인된 범위의 공개)을 선행한다. 동일 폴더를 새 클론으로 덮어쓰거나 기존 EraLeader Git을 변경하지 않는다.
D-016: Public Git 설정은 1_1의 선행 작업이며 새 V1.0 개발 단계나 확대 기능이 아니다. 개발 범위 1_1~6_6, 반도체 1개 산업 우선 검증, 5거래일 인수시험 등 기존 조건을 유지한다.

D-017 (NC-READONLY-DATA-SHARE-2026-10-13): EraLeader는 DART·SEC·KRX 공식 데이터 수집을 유지하며 NewsCatalystOS에는 **검증·게시 완료 데이터만 표준 읽기 전용 인터페이스로 공유**한다. NewsCatalystOS는 EraLeader가 수집하지 않는 경제뉴스·기업 IR·정부 정책 등만 독립적으로 수집한다. 양 프로젝트는 독립 실행·장애 격리·원본/분석 이력 보호 원칙을 지키며 EraLeader 코드 변경·중복 수집기를 금지한다. 기존 36개 작업/완료 조건은 불변.

D-018 (NC-OBSERVED-PIT-MODERATE-2026-10-13, 사용자 승인): **1_1 운영 완료 기준 재정의.** D-002/D-008 보존. EraLeader가 원자 게시한 공식 수신본의 SHA/영수증/출처 품질을 검증한 후, NewsCatalystOS에서 실제 확인한 `verified_at` 이후의 신규 분석에만 관측 메타데이터를 사용한다. 공시 `published_at` 불명은 `None/UNKNOWN` 유지하고 `OperationalObservation`은 `RawEvent(공개시각 인증)`와 별도 유형으로 명시한다. 정식 issuer/공개시각·정정 이력 외부 인증 및 과거 역사 PIT는 **선택적 고정밀/후속 게이트**이며 운영 관측형 `1_1`의 필수 선행조건이 아니다. 다만 수신/게시 전 과거 사용·누락 출처 완전성 가장·KRX 가격데이터 뉴스 이벤트 혼동·증빙 위조는 계속 금지. 36개 단계/반도체 1개 산업/V1.0 운영·보안·PIT 원칙은 불변.

D-019 (NC-1_2-MODERATE-ACCEPT-2026-10-13): 1_2 기본 인수 기준은 **신규 공식 정부 RSS와 공개 배포 RSS 2종 실제 1회 성공, 사전 권한 확인·기본 거부·라이선스 범위/원문 금지·PIT/문서ID/오류 차단 합격**으로 정한다. 활성 소스: 중소벤처기업부 공식 RSS와 뉴스와이어 IT 보도자료 RSS(기사 본문 저장/재배포 0, 자체 fact-certification 0). 기업 IR은 소스별 접속 및 사용권 확인 전 `COMPANY_IR` 인터페이스를 제공하지만 자동 활성화하지 않는다. 삼성물산 공식 뉴스 RSS는 HTTP 403으로 비활성화, 삼성전자 뉴스룸은 제한적 이용약관으로 자동 재사용 보류. 미허가·접속 제한된 제공자 수집을 억지로 통과시키지 않아도 **1_2 모듈의 기본 완료**는 가능하다. 실제 기업 IR·언론사의 추가 이용권 확보 시 소스 설정으로 증설하되 V1.0 범위 외 기능을 추가하지 않는다. 1_3에서 워터마크·재시도·호출량 제한을 구현한다. V1.0 36단계·1개 반도체 산업 범위와 전체 완료 조건 불변.

D-020 (NC-1_3-INCREMENTAL-ACCEPT-2026-10-13): 기존 1_2 승인 RSS의 **SQLite 기반 증분 수집 / 소스별 watermark / SHA ID 멱등성 / 시간당 호출 제한 / 429·5xx 다음 주기 백오프 / 401·403 중단 및 실제 권한 재검토 후 복구**를 1_3 V1.0 기본 합격조건으로 확정. 15분 간격 `launchd` 실행 예약 템플릿을 실제 Mac owner-only 디렉터리에 생성하고 `plutil`로 검증했지만 **백그라운드 작업은 설치·활성화하지 않았다**. 테스트 및 단발 실소스 수집·반복 요청 차단으로 기능 1_3 합격 가능, V1.0 최종 5거래일 자동운영은 운영 승인을 받아 별도 판정. EraLeader 공식 수집기/코드/DB/Git 변경 금지, 반도체 1개 산업·36개 개발 작업 유지.

D-021 (NC-1_4-EVENT-IDENTITY-2026-10-13): 1_4 `NormalizedEvent v1`은 `first_seen_at/collected_at/verified_at/available_at/decision_at`을 **분리 저장**하고 `published_at`은 외부 공개 확인 없으면 `None/UNKNOWN`으로 유지한다. 공식/허용 RSS 관측치는 기업을 자동 추론하지 않는다. SEC_CIK·DART_CORP·KRX_STOCK은 별도의 운영자 검토 evidence SHA/실제 최초 관측 시각에 연결하며 이 검토는 법적 issuer 공증이 아니다. 정정 `RevisionEvidence`는 독립 reference/SHA/관측 시각을 요구하고 원본 이벤트를 덮어쓰지 않는다. 서명된 최초 공개시각은 `AnchoredOfficialPublication`을 이미 검증한 경우에만 공통 정규화에 반영하며 원천 공증과 합성 시험을 구분한다. 1_4 관측형 기능·PIT/실물 배치 검증 통과 후 1_5를 시작한다. 전체 36단계·반도체 1산업/PIT/다른 프로젝트 쓰기 금지 불변.

D-022 (NC-1_5-2_2-CONTINUATION-2026-10-13): 1_5~1_6·2_1~2_2는 정상 EraLeader 파일을 건드리지 않는 **현실적 기본 검증**을 합격조건으로 삼는다. 1_5는 허가된 메타/명시 라이선스 원본만 개인 소유 디스크에 append-only SHA/영수증/수신·archive 시각 보존, 원문 무허가 비저장. 1_6은 공백/403/429/신선도 이상을 미완료/PENDING으로 표기하고 복구 후 해결기록 보존. 2_1은 실제 허가된 RSS 헤더의 안전한 정규화 계약·원본 불변, 2_2는 출처별 정확 ID·URL·내용해시 멱등성 및 내용 변경은 REVISED로 보존. 전체 36작업과 정답셋 95%·반도체 실증·5거래일 자동운영 기준은 낮추지 않는다.

D-023 (NC-2_3-3_6-2026-10-13): 2_3 사건 그룹(수치/정정 변형 보존), 2_4 광고/루머 차단, 2_5 단일 원천 재인용의 독립 증거 과장 방지, 3_1 PIT 과거사실, 3_2 NEW_FACT 후보, 3_3 장애 해소 후보, 3_4 후속 실현/훼손, 3_5 검토 중요도는 합성/영향범위 기본기능 시험으로 완료 판정한다. 2_6 라벨 중복 precision 95%와 3_6 중요 사건 탐지 recall 90%는 실제 독립 검수 gold set 미확보로 **미완료** 유지. 계산기·탐지 이력만으로 목표 달성/법적 공시 공증/반도체 실증/5거래일 운영 완료를 주장하지 않는다. 기존 36단계/단일 산업/PIT/ EraLeader 읽기 전용·비밀 보호 조건 불변.

D-024 (NC-4_1-5_5-CONTINUE-2026-10-13): 4_1~4_6의 AI 프로토콜/메타 수치 증거/안전검증/비용원장은 실제 API 키·실비용·정답셋 이전에 **코드 구현과 실연동 인수를 구분**한다. 4_3 공식·독립보도·보도자료·SNS·AI 추론 구분과 4_4 수요/공급/CAPEX/실적/경쟁 반례 포함 분석경로는 V1.0 기본 계약 테스트 충족으로 기능 완료 인정. 5_1 반도체 9부문·7 영향경로 SemiconductorProfile v1 완성 인정. 4_1/4_2/4_5/4_6 실제 모델·라벨·원문 100% 검증 및 실비용 검증 전 미완료. 5_2~5_5 그래프·파급·후보·JSON 인터페이스는 합성 근거만 있으므로 실물 공급망·EraLeader 소비 연동 인수 전 **미완료**, 5_6 공급망 95% 평가 미완료. 누락 임의 사실·매출 생성/PIT 소급 금지, 36단계·반도체 산업 한 개·5거래일 릴리스 게이트 유지.

D-025 (NC-6_1-6_6-INCREMENTAL-2026-10-13): 6_1의 사건 생명주기 불변 전이·서명된 CONFIRMED 게이트, 6_2 사건/모델/prompt/변경분 SHA 캐시, 6_3 사실/모델/상태 SHA 및 당시 판단 감사원장, 6_4 CatalystEvent/BeneficiaryGraph/EventHistory JSON+Parquet 계약은 기본 기능 테스트 합격으로 완료 처리한다. 6_4 EraLeader 실제 소비/최종 계약은 V1 운영 인수에서 별도 실증한다. 6_5는 owner-only SQLite 일관성 백업·별도 폴더 복원·SHA 통과했으나 **독립 물리 장치·연속 5거래일 운영 미검증**이므로 미완료. 6_6은 모든 출시조건의 부족/실증을 차단하는 검증 도구만 구현하고 V1.0 tag/기능 동결 금지. 19+4=23/36(63.9%) 진행, 나머지 13은 실제 정답셋·AI 공급자·공식 반도체 관계·5거래일·DR·출시 판단에 달려 있다. EraLeader 코드/DB/Git·공식 API 중복 수집 금지, 정상 코드 CONTINUE.

D-026 (NC-5_2-OFFLINE-CONSUMER-ASOF-2026-10-14): 별도 공시문서 인적 검토가 과거 시점에 기록됐어도 NewsCatalystOS 소비자가 해당 공식 원문/별도 SHA/완료된 v2 메타를 **이번에 처음 검증한 시각** 이후만 PIT 관계 후보로 사용할 수 있다. `consumer_observed_at`은 실제 입수완료 이후 운영 경로에서 찍는다. 기존 검토 원문·사업상 거래 완료를 자가 공증하지 않고 `OFFICIAL_DOCUMENT_REVIEW_CANDIDATE_ONLY`로 유지하며, 실제 공식 공급거래 실증은 자료 확보 후 별도로 평가한다. 5_2 완료 미승격, **23/36**, 반도체 단일산업/보안/EraLeader 읽기전용/다른 단계 합격 기준 변경 없음.

D-027 (NC-5_2-REAL-REVIEW-QUEUE-2026-10-14): 기존 원자 게시된 실 DART/SEC 메타를 재수집 없이 비공개 작업목록으로 추출하는 것은 5_2 실제 데이터 접근/운영 기능으로 인정한다. 단, DART·SEC 공시 ID/접수 영수증과 SHA만으로 산업 관련성·공급계약·상업 거래·수혜기업을 확정할 수 없으므로 모든 건의 `industry_relevance=UNKNOWN_UNSCREENED`, `supply_relation_status=UNREVIEWED`를 유지한다. 동일 로컬 파일에서 즉시 얻은 payload SHA는 로컬 무결성 검사이며 독립 공시 공증이 아니다. 실제 공식 문서 본문/사람 검수 관계가 없으므로 5_2 완료 승격 없이 **23/36**, 이후 유효 관계에만 5_3~5_5 분석·출력을 연결한다. 원본 보존·PIT·EraLeader 읽기전용·공개보안/단일 반도체 산업 규칙 불변.

D-028 (NC-RSS-LIVE-TRIAGE-2026-10-14): 기존 1_3 승인 RSS 1회 수신 응답을 메모리에서 2_1/2_2/2_3/2_4/3_5로 전달해 데이터 재호출을 피하고, 제목 키워드 일치를 사실·신규 경제사건·확정 공급계약·투자추천으로 승격하지 않는다. 뉴스와이어 배포원은 독립 언론 대신 보수적 PRESS_RELEASE, 미확인 영향은 UNKNOWN/AI 미호출. 별도 2_2 SHA 색인 최초 등록(BOOTSTRAP)은 기존 1_3 신규 수신 이벤트와 다르다. 개인 output에 허가된 헤더/URL과 SHA만 게시, 기사 본문/비밀·EraLeader 원본 Git 노출 금지. 단발 35건 실테스트는 5거래일 운영 검증이 아니므로 완료 23/36 유지. 다음은 5_2 공식 거래 실증 또는 독립 6_5 장애복구/운영실증이며 36단계·단일 반도체·PIT 기본 계약 불변.

D-029 (NC-6_5-FEED-RETRY-2026-10-14): 승인 RSS 수집이 성공했으나 후속 2~3단계 분석이 실패한 경우를 대비해 1_3 선택적 `before_commit`에서 허용된 짧은 메타만 private SHA 원자 checkpoint로 보존하고, checkpoint 실패 시 seen/watermark 성공도 금지한다. 복구는 기존 SQLite 커밋 증거와 파일 SHA/출처·PIT 검증 뒤에만 허용하고 HTTP 재요청 없이 새 결정시각으로 평가한다. 성공 ACK는 triage 원자출력 검증 뒤 기록하며 5거래일 자료는 실제 승인 RSS/날짜·휴장/독립 물리복원 실증 전 승격하지 않는다. `NOT_DUE`를 장애로 오분류하지 않으며 승인 없는 자동 예약/원문/AI 호출·EraLeader 쓰기는 금지한다. 합성 테스트 및 단발 `NO_PENDING_REPLAY`만으로 6_5 완료 승격 금지: **23/36** 유지.

D-030 (NC-6_5-CROSS-DEVICE-DR-2026-10-14): 기존 백업 SQL 원자 코드는 보존하고 운영 NewsCatalystOS 두 SQLite만 내부 Mac `disk3`와 외장 T5DATA `disk6`의 서로 다른 `ParentWholeDisk`를 확인한 뒤 복구한다. 백업 및 SHA pin은 서로 다른 장치·private root에 별도 보관하며 PIN 기반 재복원을 실제 시험하되, 이는 **로컬 장치 분리 및 검증**이지 오프사이트·외부 서명 공증은 아님. 기존 DB 덮어쓰기/개인정보·원문·EraLeader 쓰기/Git 공개금지. 허가 RSS 2소스 하루 실운영 성공 ACK는 5거래일 인수 전체를 대신하지 않으므로 6_5 미완료·**23/36 유지**. PIN 신뢰 시각을 과거 공시시각으로 소급 사용하지 않으며 릴리스 태그는 최종 완결 후 승인.

D-031 (NC-6_5-DR-OPERATING-STATUS-2026-10-14): 실제 별도 물리장치 DR가 완료된 NewsCatalystOS 승인 SQLite 2개에 한해 Mac 로컬 SHA PIN과 T5DATA snapshot/manifest의 지속 무결성을 검증한 뒤 `check_feed_operations.independent_physical_recovery_verified=true`를 표시한다. 이 플래그는 오프사이트 백업·5거래일·V1.0 릴리스 인수와 절대 동일하지 않다(`offsite_backup_verified=false`, `five_trading_day_operation_certified=false`). 권한·SHA 불일치 시 실패, 운영 DB 재작성·EraLeader 쓰기 금지. 실증 지표가 보강되었어도 **완료 23/36** 유지.

D-032 (NC-6_5-USER-AGENT-2026-10-14): V1.0 실제 5거래일 운영 인수에 필요한 한정된 RSS 자동화는 Mac 사용자의 `launchd`로 설치해 기존 승인 RSS `mss-official-press`, `newswire-public-rss-it` 2개만 고정 호출한다. 실행 3,600초 간격·기존 1_3 사전 승인/호출 예산/백오프/PIT/분석 실패 복구를 변경 없이 재사용하고, 외부 API 공식 수집/유료 AI/자동매매는 금지한다. Mac/SSD 연결 실패나 실제 거래소 일정 미검증 시 운영 완료를 자동 선언하지 않는다. 사용자에게 중지/상태 점검 안내를 남기고 5거래일 및 실증 요구 때문에 **23/36 유지**, V1.0 tag 보류.

D-033 (NC-RSS-FTS5-SEARCH-2026-10-14): NewsCatalystOS 운영 실사용을 위해 **기승인 1_3 수집 및 2_1~3_5 분석 완료된 RSS 메타**만 SHA 체크포인트/ACK/원장 검증 후 전용 NewsCatalystOS 파생 FTS5 검색 캐시에 구축한다. 제목/링크/상태는 private `output/`에만 두고 검색 시 공급자 현재 승인 여부 및 최초 실제 색인시점을 확인한다. 2글자 한글 검색은 literal LIKE; 반도체 전용 추천은 키워드+광고/루머 차단 통과의 인적 검토후보이며 실제 경제사건·계약·수혜 인증이 아니다. 기사 원문·비밀·재수집·AI·EraLeader 쓰기 금지. 신규 자체 개발 기능은 36개 단계의 진도 가중치를 임의 올리는 근거가 아니므로 **23/36** 유지.

D-034 (NC-5_2-5_5-READONLY-DELIVERY-2026-10-14): 실제 허가된 공식 DART/SEC 관계 원문/독립 SHA/PIT·운영자 공식 회사 ID 2개와 문장 검토가 완료된 `SupplyChainEdge` **후보**만 기존 5_3~5_5 반도체 전달·수혜 그래프에 투입하고 비공개 JSON outbox를 원자 발행한다. 후속 소비자는 자신이 독립 수령한 SHA와 소비시점을 확인해 **읽기 전용**으로 공식 기업ID/공정/관계 SHA/가설 분류를 받는다. 거래 이행·수혜/매출/실매매는 자동 인증할 수 없으며 후속 프로젝트 자동 수정도 금지. 현재 공개 메타는 실제 관계 원문을 포함하지 않아 **실공급관계 실증0**, 합성 별도 프로세스 검증을 완료단계로 과장하지 않으며 **23/36**을 유지한다. EraLeader DB/Git/공식 API 재수집·자동매매 금지, 반도체 1개 산업/PIT 규칙 불변.

D-035 (NC-5_2-PINNED-ISSUER-2026-10-14): 공식 문서ID만 있는 5_2 검토목록의 실사용 선택 편의를 위해 **기존 EraLeader 완료 first-capture DART/SEC raw의 제공자 보고 기업명·식별자·보고서 제목·SEC Form**만 NewsCatalystOS에서 읽기 전용 공유한다. 원본/first receipt SHA와 기존 완료 v2 문서별 source/raw SHA 및 Mac 별도 TOFU 연구 앵커를 검증한 메타 선별 큐는 v2, 기존 IDs-only 큐 v1 스키마 불변. 회사명·제출 유형·`계약` 같은 제목 단어만으로 **공급사/고객사 실거래·매출/수혜·발행기관 인증/공시 공개시각·반도체 업종을 확인하지 않음**. DART 실제 키워드 1건은 주식 양수도 계약으로 5_2 실제 공급관계 증거 0건. 코드 변경은 새 공식 API 수집 없이 수행, **23/36 유지**.

D-036 (NC-2_6-3_6-REAL-RSS-GOLD-FREEZE-2026-10-14): 2_6 중복 precision·3_6 중요 신규 사건 recall의 목표 500건 실측을 위해 **기존 승인된 RSS 1_3/2~3단계 완료 ACK 메타**에서 공급자+source event SHA+제목 버전 SHA로 실제 사례를 중복 제거하고 판정 상태를 **현재 동결 시각**에 Mac↔T5DATA 별도 SHA 핀으로 고정한다. 리뷰 목록에는 예측/중복 판정 플래그를 숨기고 실제 독립 2인 리뷰자가 별도 입력한 boolean/인적 SHA/PIT을 기존 gold intake로 평가한다. 기존 수집시각으로 소급해 실시간 예측 성능 주장 금지, 사람 답안지 빈 상태 39건은 gold 라벨 0건이며 precision/recall N/A, 최소 500/출처·내용 독립성을 증명하지 못한 경우 출시 판정 false. 추가 공식 API 수집·EraLeader 쓰기/유료 원문 공개·자동매매 불허. **완료 23/36 유지.**


D-037 (NC-6_5-RSS-LAUNCHD-HEALTH-2026-10-14): 승인 RSS Mac 1시간 launchd 운영 인수 보조 지표는 읽기전용 별도 검사기로 점검한다. owner-only 원본 plist/실제 launchctl label/간격/last exit/runs/최근 stdout JSON·승인 제공자 2개·다른 중복 agent를 대조하고, 로그가 2시간15분 이상 갱신되지 않으면 경고한다. 서비스가 시간 사이 `not running`인 것은 정상. 검사기는 새 GET/수집·API·AI/DB쓰기·launchctl 동작 변경 없이 status/사유만 반환하며 `AGENT_HEALTHY_OBSERVED`는 5거래일/데이터 정확도/최종 릴리스 인증이 아니다. **23/36 유지**.


D-038 (NC-6_5-REVIEWED-KRX-SESSION-2026-10-14): 6_5 운영 인수에서 단순 월~금 후보와 실제 거래소 날짜를 구별한다. 운영자가 별도 허가 경로로 취득·보관한 KRX 공식 일정의 사유화된 source_snapshot + SHA256과 owner-only 검토파일(reviewed_at/reviewer_id/session_dates)을 read-only로 확인하고 실제 승인 RSS 양소스 ACK 완료 날짜에 한해서 `operator_reviewed_calendar_days`를 보고한다. 사람이 입력한 거래일 목록·자체 SHA는 외부 기관의 독립 검증이 아니므로 `verified_exchange_trading_days=0`, `five_trading_day_operation_certified=false`, `v1_release_ready=false` 유지. 수집/매매/공식 DART·SEC·KRX API 호출/ EraLeader 변경 금지. 실제 일정 증빙 없이 과거 성공일을 소급 생성 금지. **23/36 유지**.


D-039 (NC-2_6-3_6-APPEND-REAL-GOLD-2026-10-14): 실뉴스 gold 인수는 기존 비공개 `gold_batch_<SHA>` 및 2인 검수 답안지를 **절대 덮어쓰지 않고** 증분 배치를 별도 고정한다. `run_gold_review.py freeze --new-only`는 모든 종전 배치의 Mac 독립 SHA PIN/예측/검토표/게시 증명을 확인하고 승인 RSS 완료 ACK의 공급자+문서사건 ID+제목버전 SHA가 이전과 중복되지 않는 것만 새 원자 배치로 게시한다. 기존 배치 중 변조/독립 pin 누락/상호 중복 발견 시 fail-closed. `progress`는 기존 골드와 현재 승인 RSS를 **네트워크 호출·상태 쓰기 없이** 대조하며, 사람이 라벨하지 않은 제목은 정답셋으로 계산하지 않는다. 금번 실제 새 17건/기존 39건 = 고유 후보 56건, **인적 검수 0건**, 전체 500건/품질·독립성 게이트 미완료. 실서비스·EraLeader API/DB/Git 미변경, 전체 23/36 유지.


D-040 (NC-4_1-RESPONSES-ADAPTER-2026-10-14): 4_1의 첫 실 HTTP 연결은 기존 `AIModel/AIRequest/run_ai_analysis` 공통 계약을 그대로 재사용하는 OpenAI Responses JSON Schema 어댑터로 제한한다. 유료 호출은 실제 운영자의 별도 `allow_paid=True`·Mac 내부 환경변수 자격증명·PIT 중요 신규 공식/허가 메타 입력·기존 4_6 월 예약 원장 선행 성공을 모두 요구한다. 본문 업로드·응답 서버 저장(store=false)·리다이렉트/자동 재시도/중복 청구 금지, usage 토큰 검증 후에만 결과 정산하며, 실패한 예약은 보수적으로 보류한다. AI 판단의 `available_at`은 호출 시작 전이 아니라 응답 검증 완료 이후로 기록한다. API 키/라이브 테스트 승인·실청구 검증 없으면 **4_1 미완료, 23/36 유지**. 다른 Gemini/Anthropic 코드를 대체하지 않으며 EraLeader 공시/API/DB/Git 공유 경계 변경 없음.


D-041 (NC-2_6-3_6-CROSS-BATCH-AGGREGATE-2026-10-14): 2_6/3_6의 독립 정답셋은 단일 RSS 동결 배치가 아니라 기간 중 누적된 **여러 PIN 고정 배치 전체**를 대상으로 평가한다. 기존 `run_gold_review.py aggregate`는 Mac 독립 SHA pin·T5DATA 동결 예측/블라인드 검토표·두 검수 답안지를 모두 재검증하고, 중복 사례/유실 자료를 차단한 상태에서 TP/FP/FN/TN·실중요사건 수·정상탐지 수를 각각 합산해 95% precision/90% recall을 계산한다. 묶음별 백분율 평균이나 빈 라벨을 정답으로 취급하지 않는다. 실 인간 독립성·출처 다양성·과거 실시간 판정 인증/출시 태그는 별도 인수 전 false. 기존 56 실제 제목 후보의 2인 정답 0건, 부족 후보 444건이므로 **완료 23/36 유지**. 기존 EraLeader 데이터 및 API는 쓰지 않는다.


D-042 (NC-2_6-3_6-HUMAN-ENTRY-2026-10-14): 실제 2인 독립 뉴스 검수는 기존 동결 GoldBatch/로컬 독립 SHA PIN을 보존한 상태에서 운영자가 직접 입력할 수 있는 Mac 로컬 명령 `run_gold_review.py review-list`, `review-one`으로 수행한다. 블라인드 목록은 제목·출처·사건 SHA만 표시하며 모델 사전 예측을 검수자에게 노출하지 않는다. 검수자는 자신이 승인된 출처를 확인해 별도 owner-only 근거 메모를 작성하고 true_duplicate/important_event 두 판정을 **직접** 선택한 경우에만 개별 기록한다. 이전 답안지/검수 증거 SHA를 개인 이력에 불변 저장 후 답안지를 원자 갱신하며 완료된 건은 자동 덮어쓰기·수정 불가. 사용자 데이터/원문/비밀·API 접속·AI 자동 인적라벨 생성 금지. 검수자 독립성은 별도 실제 검증 필요하며 합성 테스트로 real human gold 승격 금지. 완료 **23/36 유지**.


D-043 (NC-2_6-3_6-GUIDED-HUMAN-REVIEW-2026-10-14): 기존 실제 뉴스 PIN 동결·Mac 개인 검수자 A/B 슬롯·`record_review_once`을 보존하며, 직접 출처를 확인한 **실제 사람만** 터미널에서 뉴스 1건의 중복/중요 사건 여부와 근거를 입력할 수 있도록 `review_news_interactive.py` 단발 대화형 흐름을 추가한다. 답변 기본값/자동 정답/AI 판정 금지, 직접 확인·최종 작성 확인 없이는 답안지 변경 없음. 개인 근거파일은 0600으로 새로 생성 후 기존 SHA/PIT/불변 리뷰 이력을 사용한다. 골드 후보 출처별 비중은 기존 승인 RSS SHA 관측 자료로만 산출하고 키워드 힌트를 검증된 경제사건/계약/수혜로 인증하지 않는다. 사용자 미추적 자료·EraLeader 원본/DB/Git/공식 API 수집기 무변경. 완료 **23/36** 유지.


D-044 (NC-2_6-3_6-REVIEW-CRASH-RECOVERY-2026-10-14): 실사용 2인 검수 제출 시 기존 원자적 답안 교체 직전 Mac/SSD 장애가 발생해 로컬 SHA 영수증만 남고 답안이 갱신되지 않는 상태를 복구한다. 사용자가 이미 직접 작성·확정한 제출만 `review_history/<case>.before.json`, `<case>.proposed.json`, `<case>.receipt.json` 및 owner-only 근거 메모·Mac 별도 SHA PIN 고정 배치를 검증한 후 `run_gold_review.py review-recover` 명시 실행으로 잔여 교체한다. 원래/제안 SHA가 정확히 일치해야 하며 다른 케이스·검수자 변경·검토시각 소급·재입력 자동 생성 금지. 로컬 SHA 영수증은 외부 서명 공증이 아니며 두 사람 독립성/정답 정확도 인증도 아니다. 완료 단계 **23/36 유지**; 기존 프로젝트·EraLeader 원본 불변.
