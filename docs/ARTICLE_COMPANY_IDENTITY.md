# 기존 공시 명부 → 기사 속 기업 식별

## 실제 기능

`official_filing_context.read_pinned_filing_context`로 기존 완료 DART/SEC 원본·영수증·독립 pin을 읽고, 기사 원문 이름을 해당 명부의 기업명/법인코드에 연결한다. 원본 수집 API, EraLeader 코드/DB/설정은 변경하지 않는다.

- 같은 정규화 이름에 법인 식별자가 하나일 때만 연결한다. 여러 공시는 중복 기업으로 세지 않는다.
- 동일 이름에 서로 다른 식별자가 있으면 `AMBIGUOUS`, 명부에 없으면 `NOT_IN_SNAPSHOT`이다. 법인명 접미사 제거·약칭 추측·이름 부분 일치로 매핑하지 않는다.
- 회사 식별 근거에는 공시 번호, 원본/영수증 SHA, 조회 완료시각을 남긴다. 이는 출처가 보고한 기업 식별 정보이며 계약·납품·매출·수혜 증명이 아니다.
- 공개 원문을 다시 받지 않고 이미 허가된 본문 아카이브의 SHA/현재 권리를 확인한다. 본문은 결과 JSON에 포함하지 않는다.
- 비공개 결과는 `document_analysis/company_identity/article_company_identity_SHA.json`에 불변 저장한다. 동일 기사 버전은 조회 시 최신 결과 한 건으로 묶고 과거 시점 조회를 지원한다.

## 실행과 소비

```sh
python3 scripts/resolve_article_companies.py \
  --era-root /기존/EraLeader \
  --era-report /기존/official_api_pit_research.json \
  --independent-anchor /비공개/official_api_pit_research.pin.json \
  --archive-root /허가본문/archive --archive-version ARCHIVE_SHA \
  --receipt-sha256 RECEIPT_SHA --document-sha256 DOCUMENT_SHA \
  --registry /허가본문/registry.json
```

기존 대시보드의 **기사 속 기업 식별** 영역에서 회사명·기업 ID·공시 번호·시각·원문 링크·미확인 이름을 검색할 수 있다. 기사 집계나 신생 테마 수를 늘리는 기록으로 취급하지 않는다.

`search_news.py --company-identity-root /비공개/문서분석/company_identity --query 삼성전자`는 기존 뉴스 검색에 기업 식별 결과를 함께 제공한다. Python의 `search_article_identities(root, query=..., as_of=...)`는 읽기 전용이다.

기존 본문 예약 분석은 같은 분석 루트 아래의 식별 결과를 자동 읽어 원문 버전·본문 SHA·URL이 일치하는 경우 보고서에 결합한다. 경제 사건의 원문 회사명에만 ID를 연결하며 과거 사건 식별자는 보존한다. 식별 결과가 없거나 손상돼도 기존 뉴스·AI 분석은 계속한다. **새 기사마다 명부 조회 결과를 생성하는 예약 단계는 다음 작업**이다. 현재 명령과 저장 결과 자동 소비를 구분한다.

## 이번 실자료 결과

기존 고정 스냅샷 1,101개 공시 기록, 중복 제거 51개 기업을 읽었다. 산업부 보관 기사 171178에서 삼성전자 → `DART_CORP:00126380` 연결 성공. 근거 공시 번호는 `20261008000706`이다. ASML·SK하이닉스·TSMC는 현재 명부에 없어 미확인 유지. ‘노광장비·첨단장비’를 기업 후보로 잡은 오탐을 수정했다.

최종 비공개 결과 SHA `70460ea99a1c6457a89b5122610e7dab257195fb979cc6d2be0eba87567d3a23`. 직접 수혜·실거래 확인 0, 유료 AI/새 네트워크 호출 0. 2025년 기존 관계 기사를 신규 사건으로 등록하지 않았다.

변경 영향 125개 테스트 통과, JS 구문 검사 통과. 명부 중복/동명/미래/권리/원문 SHA, 원문→ID→기존 테마, 읽기 전용 검색·HTTP, 손상 시 다른 경로 유지가 포함된다. 복수 기업 공급망 정상 경로는 기존 합성 시험이며 실제 자료에서는 삼성전자 식별만 확인했다.
