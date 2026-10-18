# 뉴스 실질 변화 → 기업 경제 영향 → 기존 EraLeader 후보 평가

사용자 요청: 기존 기능을 유지하고 프로젝트 목적에 맞는 이 핵심 연결부터 완성한다.
EraLeader의 뉴스 재료 반영 선정기(12a6d9c)는 이미 존재한다. 이번에는 새 점수를
만들지 않고 누락된 공통 발견·최근 회사 뉴스 읽기 분석을 그 입력에 연결한다.

## 연결한 경로

1. 기존 승인 저장 제목·원문에 결속된 public_demand/recent_followups 분석을 읽는다.
   기존 사건에 연결된 회사와 정확한 기사 판본·SHA·최초 가용시각을 보존한다.
2. `company_economic_changes.v1`은 회사별 최근 경제 변화, 출처별 조건, 기존
   경제경로의 기회·반증을 전달한다. 원문 기사 분석과 독립 확인 사실을 구별하고,
   새 사건을 꾸며 ThemeStore에 쓰거나 계약 상한액을 매출로 변환하지 않는다.
3. 기존 material publisher에 선택적인 discovery 저장영역을 연결한다. 기존
   base/company/msit/nist 판본과 새 영역을 하나의 고정 게시에 포함하며, 입력이
   같으면 같은 bytes·SHA·최초 게시시각을 재사용한다. 새 일일 시세만 바뀌어도
   같은 DART 식별 근거는 재사용하므로 뉴스가 다시 신규화되지 않는다.
4. EraLeader는 정확한 DART 기업과 KRX 종목/회사명·기존 원 사건을 대조한다.
   회사가 현재 평가 목록에 없으면 미연결로 남기고 임의 재무·가격을 만들지 않는다.
   연결 오류는 해당 회사 분석만 격리하고 기존 재료 판정은 유지한다.
5. 기존 같은 비교군·같은 Pareto 단계의 강화/유지/약화 반영을 재사용한다.
   첫 로컬 관측·기본계약·계획은 유지와 조건을 표시한다. 명시적으로 같은
   프로젝트의 발주/납품 진전은 강화, 관련 회사의 실제 위험 보도는 약화 근거로
   연결한다. 관련 사업의 과거 실적·다른 지역 증설·논평을 개별 계약 이행으로
   승격하지 않는다. 100점 배점·정식 상태·매매 권한은 변경하지 않는다.
6. 이미 완료된 Era 가격·재무·사업 평가를 재수집/재계산하지 않고 새 뉴스만
   다시 적용하는 refresh 경로를 추가했다. 기존 보고서 저장기·변화 추적·digest·
   중립 JSON 발행기를 재사용해 화면과 출력이 같은 판단을 제공한다. 원 보고서,
   시장 세션·원 평가시각·재무·시세를 보존하고 뉴스 평가시각을 따로 표시한다.

## 코드와 실행

News: `company_economic_changes.py`, `material_publication.publish_material`의
`economic_discovery_root`/`recent_workspaces`. 기존 approved research runner는
설정된 discovery를 게시에 포함하며, `--material-news-workspace SCOPE=ABSOLUTE_ROOT`로
기존 수동 승인 출처의 제목 결속을 읽는다. 이 선택 인수는 해당 출처를 수집하지 않는다.

Era: `news_company_economic_changes.py` → `kr_news_candidate_priority.evaluate`.
`news_material_refresh.refresh`와 `scripts/refresh_news_candidate_assessment.py --project <ERA>`는
기존 연결 설정과 운영 홈의 완료 보고서를 사용한다. 기존 일일 실행의 material
수신 경로도 그대로 사용한다. 새 수집기·Era 재무평가기·주문 경로·스케줄러는 없다.

## 검증과 판정 범위

`tests/test_company_economic_changes.py`는 합성 승인 제목→저장 분석→고정 게시→
실제 Era 수신기·기존 선정기까지 연결한다. `ERALEADER_SOURCE_ROOT`를 현재 Era
개발 폴더로 지정해 실행한다. 정상 회사·공식ID·조건부 경제경로·PIT·반복·stale·
잘못된 기업/해시·미래정보·진전/약화/관련사업 구별·기존 동급 후보 순서 변화를
확인한다. Era의 `test_news_material_refresh.py`는 원 재무·시세와 원 보고서 보존,
화면/digest/중립 JSON의 동일 판단 및 재실행 재사용을 검증한다.

이 기능은 기존 평가 후보로 정확히 연결되는 뉴스의 연구 판단 경로다. 현재
평가에 없는 기업의 자동 재무 수집, 모든 뉴스 본문의 자동 읽기/사실 검증,
수익성·시장 신규성 확정, 매매 엔진 주문 실행까지 완료했다는 뜻은 아니다.
기존 V1 36/36은 유지하고 이 연결의 구현·실자료·운영 증거를 구분한다.
