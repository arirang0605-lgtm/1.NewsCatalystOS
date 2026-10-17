# PROJECT_STATE — 사용자 목적에 맞춘 재료 판단 우선

2026-10-17T23:39:34+09:00. News dashboard 배포 SHA **bed8e9dd5e878509d1a4563e1b88a6861d6cb2b9**. 역할은 docs/ROLE_ALIGNMENT_20261017.md. V1 반도체 1산업·정상코드 CONTINUE·무주문, 기존 코드작업36/36 기록과 실제 전체 연동은 구별.

## 이번 변경
- 기존 뉴스 사건 이력·중복 그룹·단계 후속 연결을 실제 **재료 판단 출력**에 연결. 로컬첫관측과 시장신규성 분리, 반복 보도·기업ID 보완·시간 경과만으로 신규 강화 근거 생성하지 않음. 같은 문서 제목변경은 실질변경 미확정, 계획후 개시/집행은 출처보고 진전, 상충/철회는 해당 사건의 재평가 입력. 무뉴스는 무효화 아님.
- 각 출처에 직접 명시된 기업의 CAPEX/공급/수요/손익/경쟁여건 영향을 조건부로 설명하며 반증·결측을 함께 제공. 원본에 같은 사건/기업으로 묶인 공급관계가 없는 기업은 추가하지 않음. 기존 economic_path 재사용, 임의 매출/수혜/주가·리더점수0.
- 실제 기존 SK하이닉스 투자 발표: PLANNED 유지, 최근30분 NO_NEW_MATERIAL/NO_NEW_CATALYST, 원래 기사 기준 첫 관측은 시장신규 UNCONFIRMED. 자본지출 및 공급능력 확대 가설·집행/수요/가동률 위험을 출력. 공식기업 DART_CORP:00164779 연결 유지. 기존 /api/themes17테마의 확장 입력이 Era 기존 decoder/validator에서 읽힘; News가 Era 순위/후보상태를 대신 바꾸지 않음.
- 기존 기사/테마 카드에서 **재료 판단 → 기업별 조건부 영향/반증 → 선택적 Era 재무** 순서로 표시. CLI --materials 불변 내보내기 지원. 기존 데이터 수집/뉴스 권리/문서·시간/PIT·비밀·예산은 그대로.

## 검증·운영
변경 영향61PASS/FAIL0, 최종 UI 문구1건 재시험. 실제 운영 API/기사 HTTP200, JS 배포 SHA 확인. News dashboard만 고정snapshot으로 교체했고 원본테마/사용자dirty3·출처 DB와 나머지 예약은 변경 없음. Era 원본 코드/DB/Git/예약 쓰기0, 타 담당자 정상 작업 불간섭. 뉴스재수집/유료AI/공식API0, Public GitHub push0.
현재 성과는 **News 재료판정과 전달을 바로잡은 것**이다. EraLeader 내부 가격·거래대금·수급·기업경쟁력과 결합해 후보 강화/약화/유지/우선순위를 실제 산출하는 작업은 아직 남아 있다. 독립 전략의 매매 조건 적용도 전체 완료로 주장하지 않는다.
증거: output/role_alignment_20261017/operating_material_proof.json·material_activation.json·outbox/; 현재 UI http://127.0.0.1:8766/.
