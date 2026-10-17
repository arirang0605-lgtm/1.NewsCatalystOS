# START HERE — NewsCatalystOS: 재료 판단 → 대장 후보 → 전략

기준 2026-10-17T23:39:34+09:00. 사용자 첨부 목적표와 **“바로 잡자”** 지시가 최우선이다. [역할·개발 우선순위](docs/ROLE_ALIGNMENT_20261017.md)를 적용한다. 재개 시 이 문서 → AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md의 최신 내용과 실제 Git 상태만 확인한다.

## 바로잡은 목표
**NewsCatalystOS: 무엇이 새로 달라졌나/반복인가/어느 기업에 왜 영향을 주나 → EraLeader: 독립 전시장 발굴과 가격·거래대금·수급·경쟁력/뉴스를 종합한 후보 판단 → 독립 매매전략: 매수·매도·손절.** Era 재무를 News 화면에 보여주는 기존 역방향 조회는 보존하되 후순위다. 새 RSS 수/재무표·관리도구 확장으로 본 흐름 완성을 대신하지 않는다. News는 대장주 점수·선정/매매신호를 만들지 않는다.

## 최신 작동
- News 재료 판정 기능 e735107767cdb51eaf55a49a97f5f3168c4bfbcf 및 문구보정·운영 SHA **bed8e9dd5e878509d1a4563e1b88a6861d6cb2b9**. 기존 ThemeStore 판본/사건·계획→개시/집행 연결·theme_changes·economic_path를 재사용해 로컬첫관측/이전자료분석/반복/원문판본변경미확정/단계진전/상충/철회/유지를 구분. source first_seen은 시장신규 재료 인증이 아니다.
- 기존 /api/themes에 optional catalyst_material과 기업별 조건부 경제 경로·반증을 포함. search_themes.py --materials --export-root로 같은 입력을 불변 SHA 파일로 발행 가능. 기존 원본 사건/회사/테마점수 변경0. 첫 관측·발행시각/시장선반영 미확인은 해당 항목만 UNKNOWN/null, 독립 Era 발굴을 차단하는 새 조건 아님.
- 실제 저장 SK 투자계획의 최근30분 비교: NO_NEW_MATERIAL → Era 입력 NO_NEW_CATALYST. 기업 영향은 SK 자신의 CAPEX부담/향후 공급 확대 가설과 집행·수요·가동률 반증. 미확인 장비수혜자 추가0. 운영 기사 상세/일간에서 재료판정을 재무조회보다 먼저 표시. 기존 금융연결 유지.
- 관련 **61 PASS/0 FAIL**, 문구보정 UI1건 재시험 통과. 운영 HTTP200/배포 JS SHA 확인, 실제 API17테마를 기존 Era 수신 함수로 읽어 extension 포함 호환 확인. 이것은 **Era 실제 후보순위 반영 완료가 아님**. Era 코드·DB·Git·예약 변경0, 유료AI/재수집/공식API0.

## 운영과 보존
개발 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, branch codex/real-data-path. dashboard만 /Users/shmoon/Library/Application Support/NewsCatalystOS/releases/bed8e9dd5e878509d1a4563e1b88a6861d6cb2b9 고정코드로 교체. 기존 연구수집/core/MOTIR 예약과 데이터/비용원장은 그대로. 운영 http://127.0.0.1:8766/ . 운영 source는 /Users/shmoon/Library/Application Support/NewsCatalystOS/research_workspaces, dev output/*_live_dev는 보관본이므로 재수집 금지. 원본 SSD/EraLeader, 사용자 미커밋 AGENTS·DECISIONS·비전3 보존, Public GitHub push 없음. 증거/롤백은 ignored output/role_alignment_20261017/.
다음 핵심은 NEXT_TASK.md. 36/36은 과거 코드구현 기록이고 전체 대장선정·전략인수 완료를 뜻하지 않는다.
