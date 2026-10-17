# PROJECT_STATE — NewsCatalystOS 운영 개시

기준 2026-10-17T20:58:49+09:00. V1 반도체 1산업. 사용자 승인 배포 완료. 실제 운영 코드 SHA **c56059ab4b9b422fd687f3c8775b1d527fe49052**. 기존 1_1~6_6 코드구현 기록 **36/36** 유지; 운영 시작과 장기 관찰·EraLeader 공동 인수는 별개.

| 이번 요청 | 판정 | 실제 근거 |
|---|---|---|
| 전체회귀 | 완료 | 7140 PASS/0 FAIL, 875.88초. 첫 3개의 오래된 기대값을 현행 provenance/시점·기능 정책과 맞추되 무근거/미래/고유이름 오인 거부 유지. 런타임 코드 변경 없음. |
| 산업부 운영 오류 수정 적용 | 완료 | com.newscatalystos.motir 고정 snapshot 실행. 실제 launchd RunAtLoad 자동실행1회 exit0, 기존 수집 원장은 NOT_DUE를 지킴, 18기사 분석 성공. 선택적 과거 AI1건 보류·requested_ai_complete=false를 숨기지 않고 유지. 중요한 AI실패는 기존 fail 보호. |
| 신규5개 RSS 정기실행 | 완료 | com.newscatalystos.research-approved 설치·활성, 3600초/RunAtLoad. 등록 직후 실제 5개 모두 exit0, 새 고유기사0·경제후보9. 출처별 호출예산·동일기관 교대·중복/PIT 유지. |
| 사용자 실제 운영화면 | 완료 | com.newscatalystos.dashboard 상주/자동시작, 127.0.0.1:8766 HTTP200. 5영역8제공자372제목판본·일간199·중요후보9. SK하이닉스 투자계획/테마/기업 원문근거 READY, 실제수혜 비인증. |

## 운영 경로와 원본 보호
배포 버전 /Users/shmoon/Library/Application Support/NewsCatalystOS/releases/c56059ab4b9b422fd687f3c8775b1d527fe49052. 새 출처 데이터는 /Users/shmoon/Library/Application Support/NewsCatalystOS/research_workspaces. Mac 무인 실행에서 Documents의 원본 개발 경로 읽기가 멈추는 현상을 확인해, 정상 Application Support 운영 데이터 경로로 이전 후 실제 launchd 읽기5/5 확인. 개발 원본은 전부 보존, SQLite 일관성·원본 행 검증, 원 기사/분석 hash와 PIT 유지, 복사 ACK의 파일저장주소만 이전. 새 운영 원장과 보관된 dev 원장을 동시에 수집하지 않는다.
기존 core 서비스 정상 그대로(마지막exit0). 원본 SSD src/scripts 코드 SHA 235개와 기존 core plist 보존. 기존 5종 운영 DB의 백업→별도복원 SHA/무결성 성공 근거 유효. Gemini 실제 정산86회/71.286원·미정산예약2/15.1552원, 월50000원 이내. 키·기존AI설정·미정산 예약 삭제/재과금·유료본문 공개 없음. 사용자 dirty3, EraLeader 코드/DB/Git, Public GitHub push 불변.

## 남은 후속 범위
설치 직후 RunAtLoad 자동 실행을 확인했다. **자연 hourly 실행을 기다려 확인한 것은 아니며 24시간/5거래일 안정성은 운영 후 관찰**이다. 기존 설정대로 다음 실행이 이어지도록 활성화되어 있음. 동시 수집·일괄 재시험·새 출처 확대를 이유 없이 추가하지 않는다. EraLeader 실제 공동 소비·기업평가 연동은 별도 인수, 뉴스만으로 자동매매/수혜확정하지 않음.
증거: output/release_20261017/activation.json·operational_verification.json·full_regression_final_result.json. 롤백 후보/원 plist도 동일 ignored 비공개 폴더에 보존.
