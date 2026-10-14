# PROJECT_STATE — NewsCatalystOS 현재 상태

기준일: 2026-10-14. 사용자 원칙 D-052는 AGENTS.md에 보존.

## 기능 구현·테스트
- **5_5 기업발표 v2 게시→별도 읽기전용 소비 연결 완료.** 기능 커밋 `b8dadb97be67669e859120dccdb10a14b73d574e`, origin/main push와 원격 SHA 일치 확인.
- 기존 publisher 입력→공급망/파급/분류/graph v2→원자 게시→별도 consumer를 재사용. 제공자·문서 ID·IR/정부 출처·양사 식별체계·공급계획·영향 불확실성이 payload SHA에 묶여 전달된다.
- 기존 official/v1 기본 경로 유지. v2는 `publish_reviewed_beneficiaries.py --input-kind publisher`와 `consume_reviewed_beneficiaries.py --graph-version v2`로 명시. 원문/인용/답안은 결과에 포함하지 않는다.
- 반복 게시 시 빈 임시폴더가 남던 실행 오류를 수정하고 재검증. 변경 영향 **8파일 124 PASS/0 FAIL**, 컴파일·diff·Public 검사 PASS. 기존 v1 경로도 포함; 전체 프로젝트 회귀는 이번에 수행하지 않았다.
- Mac 격리 테스트 디렉터리에서 합성 입력으로 producer/consumer **별도 Python 프로세스 exit0/exit0**. 동일 SHA·계획/출처/불확실성 보존, 입력4파일·소비 outbox 불변 확인.
- 증거: `logs/publisher_v2_delivery_regression.log`, `logs/publisher_v2_delivery_smoke.json`. 합성 허가·답안은 실제 권한이나 인적 정답이 아니다.
- **다음 미완료 기능:** 실제 RSS의 신규성·중요도 판단 결과→기존 AI/캐시·분석 결과 연결. 기본 수집/검색/Gold를 다시 만들지 않는다.

## 실자료 검증
- 기존 승인 RSS3 출처와 공개 공급관계 참고1건의 증거는 보존. 이번 작업에서 재수집·실자료 검수·운영 DB 접근은 하지 않았다.
- 최신 기존 기록의 publisher 실제 원문 인수0/인적 라벨0은 이번 합성 시험으로 변경하지 않는다. 원문 권한·실검수·실AI 사용 승인 대기는 해당 실증에만 적용한다.
- EraLeader 코드/DB/Git·공식 API·다른 프로젝트·사용자 미추적 자료 변경 없음. 기존 서비스 재설치/새 출처/유료 AI 호출 없음.

## 운영·출시 인수
- 기존 단계 인수 집계 **23/36 유지**. 전체 코드 구현률이 아니다. 위 5_5 v2 연결은 기능 완료이며 실회사 자료 인수와 구분한다.
- 원래 500건 인적 평가·정확도·반도체 관계 평가·실AI 비용·실제5거래일·전체 회귀/릴리스 조건은 별도 미완료. 새로운 필수 검증을 추가하지 않는다.
- 다음 작업은 NEXT_TASK.md. 과거 기록을 이 파일에 계속 누적하지 않는다.
