# 산업통상부 공식 산업정책 RSS — 기존 1_2/1_3~3_5 기능 재사용 (2026-10-14)

## 실제 공개 출처·권한 확인
- **정부 공식 게시판:** https://www.motir.go.kr/kor/article/ATCL3f49a5a8c
- 위 페이지는 RSS 제공과 보도자료의 **공공누리 제1유형(출처표시)** 이용 조건을 게시한다. 특정 첨부 파일/제3자 권리는 개별 확인하며 기사 본문·이미지·첨부 파일은 저장하지 않는다. 2026-10-14에 공식 페이지를 직접 확인했다. 해당 안내 자체가 공식 기관 발행시각에 대한 독립 시간인증은 아니다.
- **공식 RSS:** `https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/rss`. 게시판의 `rssForm`이 **본문 없는 HTTP POST**를 전송한다. 최초 수동 확인: GET→HTTP 405, 빈 POST→HTTP 200 `text/xml`, XML RSS2.0 `item` 10개, HTTPS 링크 및 제목. 뉴스 원문 저장 금지.
- 별도 프로젝트: SK hynix Newsroom `https://news.skhynix.com/en/terms-of-use/`에서는 무단 자동화 접근을 제한한다. 별도 서면 허가 없는 SK hynix 자동 RSS/페이지 수집 **차단**. 삼성 글로벌 뉴스룸 등 민간 사이트도 개인·비상업적 이용 조건과 모델 목적이 다를 수 있으므로 임의 활성화 금지.

## 최소 기능 구현
- 기존 `provider_registry.py`에 **RSS_POST** 허용 유형을 추가하되 오직 기관 유형 `GOVERNMENT_POLICY`이고 URL이 위 MOTIR 공식 RSS와 **완전히 동일한** 경우만 가능하다. 그 외 임의 URL/도메인으로 POST가 전송될 가능성을 차단한다. 기존 RSS/JSON_API의 GET 동작 변경 없음.
- 기존 `feed_transport.fetch_authorized_once`가 한 번만 POST하고 HTTP 200·동일 최종 URL·XML MIME·128KiB·10초 제한·TLS 확인·무리다이렉트·무재시도 등 기존 가드를 재사용한다. `new_source_adapter.parse_authorized_feed`가 XML RSS의 ID(없으면 공식 HTTPS 링크)/제목/출처 링크만 추출; XML DTD·entity·기사 본문/설명은 버린다. 최초 이용가능 시각은 POST 요청 전/응답 검증시각을 사용하며 이전 RSS 게시시각으로 소급하지 않는다.
- 실제 운영은 **별도의 owner-only 등록부** `~/Library/Application Support/NewsCatalystOS/providers/motir_authorized_sources.json`, 별도 Mac `state/motir_incremental_feeds.sqlite3`·`motir_triage_exact_index.sqlite3`, `inbox/motir_feed_triage`, SSD private `output/motir_policy`를 쓴다. 기존 2소스 `authorized_sources.json`와 `com.newscatalystos.triage` 코드/plist/운영 DB는 변경하지 않는다. 권한 확인/활성화는 `scripts/prepare_motir_source.py --write --operator-reviewed-official-terms`를 통해 운영자가 명시적으로 수행하고 기존 파일에 덮어쓰지 않는다.
- 기존 `run_feed_triage.py`의 1_3 예약·호출예산(시간당 최대 **1회**)→retry checkpoint→2~3단계 보수적인 메타 triage→실 ACK를 그대로 활용한다. 이어 **기존** `run_gold_capture_once.py --motir-policy-only`를 새 격리 inbox/SSD `output/motir_gold_review`/Mac `pins/motir_gold`와 `motir_gold_review_workspace`에 적용해 민간/이전 일반 RSS 후보와 혼합하지 않고 PIN과 **빈 인적 검수 시트**를 만든다. 인간답안·경제적 거래·반도체 공급망 관계는 자동 생성·인증하지 않는다.
- `scripts/run_motir_policy_once.py`는 위 두 기존 기능을 한 번 순서대로 호출한다. 소스가 아직 호출제한으로 `NOT_DUE`여도 기수집 완료 ACK의 Gold PIN 검증/동결은 진행한다. 실제 문제 발생 시 `DATA_UNAVAILABLE`로 보고하고 원본/기존 완료 checkpoint를 삭제하지 않는다.

## Mac 실증
- 2026-10-14 외부 정부 RSS의 실제 검증된 첫 metadata POST: **10건 실제 신규 고유 관측**, 그중 제목 기준 반도체 검토 힌트 **1건**, 정상 triage SHA+원자 ACK 기록 성공, AI/기사 본문/기타 공식 EraLeader API **0회**.
- 전용 MOTIR 후속 기존 파이프라인 연결: `NOT_DUE`(예약 준수) 상태에서 이전 완료 ACK 10건을 새 T5DATA 사설 동결 GoldBatch / Mac 별도 물리장치 SHA PIN / **2개의 빈** 검토자 양식으로 게시. 산업부 후보 **10건은 다른 승인 RSS 70건과 별도 집합**이므로 검토자 중복제거 확인 전 '80개 독립 정답'으로 합산하지 않는다.
- 전용 macOS 사용자 LaunchAgent `com.newscatalystos.motir`를 3,600초 간격으로 **독립** 설치·활성화. 실 `launchctl kickstart` 첫 실행 결과 **runs=1/last exit code=0**, Mac 개인 stdout 정상, stderr 0바이트. 기존 RSS triage **runs=10/last exit0**, Gold 일반 동결 **runs=2/last exit0** 그대로 운영된다. 이 1회 실증은 향후 5거래일/반도체 독립 Gold의 인증이 아니다.

## 사용·중지
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
# 사설 MOTIR 수집과 gold snapshot 자동 한번 검증(기존 1시간 호출 한도 적용)
PYTHONPATH=src python3 scripts/run_motir_policy_once.py
launchctl print gui/$(id -u)/com.newscatalystos.motir
# 필요 시 이 전용 산업통상부 서비스만 중지. 기존 triage/gold는 계속 운영.
launchctl bootout gui/$(id -u)/com.newscatalystos.motir
```
- 산업통상부 Gold 템플릿의 전체 검수 목록/정답 계산은:
```sh
PYTHONPATH=src python3 scripts/run_gold_review.py \
  --out-root "$PWD/output/motir_gold_review" \
  --pin-root "$HOME/Library/Application Support/NewsCatalystOS/pins/motir_gold" \
  aggregate --workspace-root "$HOME/Library/Application Support/NewsCatalystOS/motir_gold_review_workspace"
```
- **V1 개발 완료조건은 그대로 23/36**: 출처 저작권·공공누리 표시/정보의 정확한 사건성·계약 관계·실매매 판정·2인 독립 500건 검수/실AI/5거래일 운영 미완료. 독립 기관으로부터 별도 SHA/PIT 공개시각 보증을 받았다고 주장하지 않는다.
