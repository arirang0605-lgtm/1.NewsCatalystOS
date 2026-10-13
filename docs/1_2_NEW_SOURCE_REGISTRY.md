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
