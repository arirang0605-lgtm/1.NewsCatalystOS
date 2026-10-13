# 1_2 — 신규 뉴스 제공자 권한 확인 및 안전한 메타데이터 어댑터

## 범위와 현재 상태
- 신규 자원 범위: 정부 정책 발표 `GOVERNMENT_POLICY`, 기업 IR `COMPANY_IR`, 적법하게 허가된 언론 RSS/API `LICENSED_NEWS`. SNS 제보 `SNS_TIP`은 공식 사실·자동수집으로 활성화 금지.
- **EraLeader 기존 DART·SEC·KRX와 중복 수집 금지**. `provider_registry.py`에서 관련 source_id 및 접두사를 차단.
- `ProviderRegistry`는 HTTPS(자격증명 없는 URL), 공급자별 유형·형식 RSS/JSON_API, 권리 근거·검토시각/만료시각, 호출량 상한, 본문 저장 권한을 기록한다. **기본 비활성화**; 승인되지 않은 소스와 기간이 만료된 소스는 `active()` 호출에서 실패.
- `new_source_adapter.py`는 **외부에서 제공된** 허용된 RSS/JSON 메타데이터 바이트만 검증·정규화한다. 원문 기사·description/body를 보관하지 않고 source-provided headline·고유 ID·URL 및 자체 최초 관측 시각만 보존. 기사 공개시각·발행기관 실제 주장·issuer는 인증하지 않는다.
- 이번 테스트에서 쓰는 `example.org` 및 권한 문구는 모두 **합성 fixture**다. 실제 언론/정부/기업과 라이선스를 체결하거나 생산 API에 접속한 것이 아니다.
- 실제 제공자 활성화 전에 운영자가 이용약관·수집 방식·분당/시간당 호출량·기사 본문 보관/재게시·개별 소스 도메인을 확인하고, 적법한 권리 증빙을 별도 비공개 경로에 보존해야 한다. JSON의 문자열 하나가 법적 권한을 입증하지 않으므로 자동으로 원본 사이트를 호출하지 않는다.

## 1_2 단계의 남은 합격 게이트
1. 실제 신규 정부/IR/RSS 공급원의 이용조건·권한 자료 확인 및 사전 승인.
2. 승인된 소스에 한해 안전한 라이브 수집과 장애·권한 만료·호출 제한 테스트.
3. 신규 관측 이력의 출처·최초 수신·PIT/원문 보관 금지 확인.

운영 연결 전까지 **1_2 부분 구현**으로만 기록한다. 기존 1_1 완료 1/36과 별개로 1_2 완료 숫자를 올리지 않는다.

## 2026-10-13 | 신규 정부 RSS 1개 실제 오프라인 헤더 검증
- 공적 출처 우선 확인: **중소벤처기업부 RSS 안내**(https://www.mss.go.kr/site/smba/contents/view.do?menuCd=20905000000002024122902&siteCd=smba)는 정책/보도자료 RSS 이용 제공을 명시하며 **보도자료** 링크 `https://www.mss.go.kr/rss/smba/board/86.do`를 게시한다. 이것은 RSS 헤더 내부 소비 근거이지 기사의 전체 본문 재배포/상업적 라이선스는 아님.
- 실제 Mac에서 공식 **www.mss.go.kr** RSS 1회 GET (응답 XML 6,760 bytes, RSS 항목 20개) 후 이번 `ProviderRegistry` + `parse_authorized_feed`로 **신규 메타 20행 파싱 PASS**, 고유ID 20, 본문 0, 발표시각 독립 인증 0, 관측시각 현재 UTC. 네트워크 응답 원문/제목은 Git에 올리지 않음. 테스트 URL은 공개 공식 공지에 기재된 경로이며 Meta만 사용.
- 공개된 다른 정책브리핑(https://www.korea.kr/etc/noticeView.do?newsId=132038885&pWise=main&pWiseSub=O1)은 **2026-07-01 RSS 서비스 중단**을 공지하므로 해당 구독 경로는 제공자 목록에서 제외해야 함.
- 일부 정부 게시물은 문서 링크에 비밀이 아닌 `?cbIdx=...&bcIdx=...` 같은 쿼리를 사용하므로, HTTPS URL 검증은 비밀 쿼리 키(token/api_key/serviceKey/auth 등)는 거부하면서 일반 문서 식별 쿼리는 허용하도록 수정.
- 아직 기업 IR 및 라이선스 확인된 언론 소스 실수집 연동은 없으며 호출량 제한/스케줄링 1_3 단계까지는 **1_2 부분 구현**. `1/36` 유지; 원문 라이선스 확대/비공개 전송 금지.

## 2026-10-13 | 1_2 수집 경계 통합·실물 소스 2종 인수 (NC-1_2-LIVE-RSS-GATE)
- `feed_transport.py`: 사전 권한이 확인된 `ProviderRegistry.active`로만 **HTTPS GET 1회** 수행. 표준 TLS, 리다이렉트 차단, 비밀정보 포함 URL 차단, 지정된 제한시간·128KiB/콘텐츠 타입·HTTP 상태 확인. 403/리다이렉트/응답 5xx/과대 응답/권한 만료는 재시도나 원문 보존 없이 `SourceShareError`로 보류. 주기 스케줄·watermark는 1_3 예정.
- `scripts/check_new_feed.py`: 로컬 Mac `~/Library/Application Support/NewsCatalystOS/providers/authorized_sources.json` owner-only 0600을 읽어 승인된 소스의 최신 메타데이터 수만 출력. 실제 URL, 제목, 본문, 인증정보·원문은 Public에 올리지 않음. 이 등록 파일은 이번 세션에 **없음을 확인한 뒤 신규 생성**했고 기존 파일은 덮어쓰지 않았다. 호출 상한 필드는 등록돼 있지만 지속적인 호출 계수·재시도 스케줄은 아직 1_3 범위.
- 실제 Mac 단발 실행 검증: 중소벤처기업부 공식 보도자료 RSS `https://www.mss.go.kr/rss/smba/board/86.do` **20건**, RSS 이용근거 `https://www.mss.go.kr/site/smba/contents/view.do?menuCd=20905000000002024122902&siteCd=smba`. 뉴스와이어 공개 RSS의 IT 분야 `https://api.newswire.co.kr/rss/industry/600` **15건**, 구독/사이트 표시 안내 `https://www.newswire.co.kr/?nd=31`. 두 소스의 제목·문서링크·원본 ID만 1회 파싱, `first_seen_at`은 수신/검증 완료시각, `reported_published_at=None`, 실제 공식 사건 인증 0, 유료 원문·본문 보관 0. 뉴스와이어는 **보도자료 배포/미검증 주장**이며 독립 사실 확인 기사로 인정하지 않음.
- 기업 직접 제공 RSS 후보 삼성물산 건설부문 `https://rnc.samsungcnt.com/pr/news/rss.xml`은 공식 RSS 안내 `https://rnc.samsungcnt.com/customer/rss.html`가 있지만 실제 Mac GET에서 **HTTP 403** 반환되어 추가 접근·우회 시도 없이 **비활성화**. 삼성전자 뉴스룸은 `https://news.samsung.com/global/terms`에서 비상업적 이용 제한을 밝히므로 별도 허가 전 미승인으로 유지. 행정안전부 RSS는 128KiB 수신 상한 초과로 안전 차단(원문 대용량 저장·한도 해제 안 함).
- 이번 1_2 목표인 ProviderRegistry 허용/거부·공식 정책 RSS/배포 RSS·권리 범위별 기본 거부·실제 메타만 수신·문제 소스 장애 격리는 **보통 수준 인수 통과**. 직접 기업 IR은 이용가능한 허가 확인된 소스가 없어 지원 인터페이스만 유지하고 자동 수집은 시작하지 않음. 이는 전체 소스망 커버리지나 뉴스 사실 판정 완료가 아니다.
- 전체 기존/신규 관련 **297 PASS, 0 FAIL**, Python compileall PASS. `1_2` 운영 가능 베이스 완료로 `2/36` 처리, 신규 1_3 단계에서 스케줄·증분 수집·watermark·요청량 관리를 시작한다.
