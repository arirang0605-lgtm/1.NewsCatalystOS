# 산업부 보도자료 원문과 RSS 영수증 연결 — 2026-10-15

## 기능

`motir_article_binding.py`는 이미 SHA 확인된 산업부 RSS 수집 결과와 별도 공공누리 제1유형 본문 아카이브를 오프라인으로 결합한다. RSS의 `event_id`·제목 SHA·기사 URL·체크포인트·triage SHA와 아카이브의 제공자·문서 ID·본문 SHA·영수증 SHA를 모두 맞춘다. URL이 같아 보여도 다른 사건·제목 버전이면 결합하지 않는다. 기사 본문은 RSS 관측시각으로 소급하지 않고, 결합 영수증에 실제 아카이브·결합시각을 기록한다.

별도 뉴스 인적 검수는 없다. 결합 결과는 **출처가 보도한 자료에 대한 연결**이며, 신규 경제 사건·실제 계약·수혜를 검증했다고 표시하지 않는다. 본문·HTML·첨부물은 공개 Git에 넣지 않는다. 이용 범위는 [산업통상부 보도자료 게시판](https://www.motir.go.kr/kor/article/ATCL3f49a5a8c)의 공공누리 제1유형 안내와 부처 작성 본문 텍스트로 한정한다.

## 실제 자료 검증

- 기사: [2026-10-15 산업부 충청권 메가프로젝트 투자 이행 점검](https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172295/view). 본문은 이전에 발표된 투자계획의 **이행 점검**을 다루며, 오늘 신규 투자 확정으로 재분류하지 않았다.
- RSS 관측시각: `2026-10-15T02:10:53.192736+00:00`, RSS ACK: `2026-10-15T02:10:53.468625+00:00`.
- 허가 본문 아카이브: `private/motir_press_172295/archive`; 문서 SHA `a2644b1c9f8bbfc873c2f6f84d445292d5e587afeb3e3557cb854971898d13ba`; 아카이브시각 `2026-10-15T05:20:16.849855+00:00`.
- 결합 영수증: `private/motir_press_172295/rss_bindings/motir_article_binding_23e58e58d579fb6d2116fc31d3ccb131e8e85ec1b309a53fb8c680fe2a22301f.json`. 별도 프로세스에서 SHA `23e58e58d579fb6d2116fc31d3ccb131e8e85ec1b309a53fb8c680fe2a22301f`로 읽기 성공. `new_economic_event_verified=false`, `verified_real_transaction=false`.
- RSS 기반 분석의 실제 기초 입력은 기사 제목뿐이었으므로 이 결합으로 과거 제목 분석 결과를 몰래 수정하지 않는다. 이후 본문 사건 추출은 별도의 명시적 단계로 추가한다.

## 호출

`scripts/archive_motir_press_document.py`는 한 번 받은 공식 HTML 파일에서 본문만 추출·아카이브한다. `scripts/bind_motir_article.py`는 기존 RSS 자료와 그 아카이브의 고정 SHA를 결합한다. `scripts/consume_motir_article_binding.py`는 별도로 전달받은 payload SHA와 시각·미확정 상태를 검사한다. 세 명령 모두 외부 뉴스 검수자를 요구하지 않는다.
