# START HERE — NewsCatalystOS

AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md와 실제 Git 상태를 확인한다. 최신 사용자 지시가 우선한다.

운영: `/Volumes/T5DATA/1.NewsCatalystOS`
작업 체크아웃: `/Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project`

**2026-10-16 목적 확인:** 경제·산업 변화를 자동 정리하고 **투자 가치가 있는 기업 후보를 찾는다**. 뉴스 의미 추출→기사 연결→공통 원인/테마→기업 수혜 경로→재무·가격 평가로 연결한다. 대시보드는 추후 이 목적에 맞춰 개편한다. 자동매매 추가 아님.

이번 구현은 기존 허가 본문 의미 추출/본문 인용/제목 binding 연결과 예약 실행 적용이다. 139 PASS. 실제 정책 본문 1건·AI 2회·추정 4.9056원. 회사명이 없는 정책 사건 추출 수정, 기존 의결/시행 전 상태와 사건 수 유지. 캐시 재처리 추가 호출·테마 버전 0. 투자 후보 평가와 실자료 다기업 테마 성과는 아직 미완료다.

다음은 NEXT_TASK의 기존 테마/공급망/공시 명부를 이용한 기업 후보 포함 이유·수혜 경로 연결. 원본·사용자 변경·무인 운영·SHA/PIT·비밀·기존 월 예산·EraLeader 읽기 전용을 유지한다.
