# NEXT_TASK — 발견 원인 연결의 후속 정정·취소 표시

## 현재 기준
기능 **7a3a0074ed2989dd2dbd62b4777df32e14fbf1bc**. 수요와 명시 정책 원인→제품→기업 행동 연결은 개발/선택 조회 경로에서 완료. DEV170PASS, SSD 고정판28PASS. 기존36/36 구현 기록 유지. 운영 dashboard=5a7ada1dd2a5a369f54d9308cd4a87d7bf853376, 새 기능 미활성화.

## 다음 핵심 작업 하나
기존 발견 원인 연결의 **이전 가용 판본→현재 정정/취소→연결 약화·해제 이유/근거 출력**을 잇는다. 현재 _observations가 반증/무효 사건을 제외해 유효 연결에서 제거하는 것은 정상이다. 그러나 두 제품 연결 중 한 행동이 철회되면 공통 그룹이 목록에서 사라져 사용자가 무엇이 바뀌었는지 볼 수 없다. 이 기존 경로의 후속 변화 설명(NC-05/06)을 보완한다.

기존 ThemeStore 판본/정정·취소 근거와 원인 group_id를 재사용한다. 취소로 사라진 연결을 현재 유효 테마·확정 손실로 복구하지 않는다. 과거 as_of·기본 export bytes·원 사건/점수/ID/SHA/PIT 보존, 선택 비교 조회/화면까지 연결한다. 합성 수요·정책 연결→원 행동 철회→이전/현재 비교의 정상 양성 경로와 과거 조회 불변을 먼저 확인한다. 별도 관리 도구·새 필수 인수조건은 만들지 않는다.

정책 실자료는 저장384제목 중 명시원인0·연결0으로 확인했다. 새 증거 없이 같은 실자료 양성0 점검을 반복하지 않는다. 새 수집·유료AI·운영DB replay·전체 회귀 반복·자동화 설정·Era 변경·Public push 금지. 운영 새 기능 활성화는 별도 실행 범위로 구분한다.

DEV=/Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, branch=codex/real-data-path. SSD 고정판=/Volumes/T5DATA/1.NewsCatalystOS/output/discovery_policy_20261018/code/. SSD 기존 소스/미커밋·사용자dirty3 보존, BASE=~/Library/Application Support/NewsCatalystOS. 기존 자료·예산·비밀·PIT·무인운영·무주문 기준을 유지한다.
