# 5_2 기존 공시 스냅샷 기반 실제 문서 검토 작업목록

> 현재 기준은 D-060/D-059이다. 사람 검수 절차와 관련 도구는 삭제했다. 아래 실행 기록은 당시 기록이며 현재 완료 상태는 PROJECT_STATE.md를 따른다.

## Mac 단발 실행 (운영자만)
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/build_official_review_queue.py \
  --publication "/Volumes/T5DATA/1.NewsCatalystOS/output/<기존-완료-게시폴더>" \
  --publication-root "/Volumes/T5DATA/1.NewsCatalystOS/output" \
  --payload-sha256 "<별도-보관한-기존-게시-PAYLOAD-SHA256>" \
  --source-id ALL --limit 1500 \
  --output-root "/Volumes/T5DATA/1.NewsCatalystOS/output"
```
특정 문서만 재검토할 경우 `--source-id dart-disclosures --document-id <기존-DART-ID> --limit 1`처럼 좁힌다. SEC는 `--source-id sec-submissions` 사용.

**실 데이터 스모크 검증 시 주의:** 원 게시 파일에서 *지금* 계산한 SHA를 입력하면 같은 로컬 파일에 대한 일관성 검증일 뿐 과거 공시 공개시각·독립 출처 공증은 아니다. 운영에서는 이전에 독립 보관한 payload pin을 제공해야 한다. 작업목록에 공식 문서 **본문은 저장하지 않는다**.

## 자동 처리 대기 상태
공시 메타의 `UNKNOWN_UNSCREENED`는 본문이 아직 처리되지 않은 상태다. 확보한 본문에서 관계 문장·회사 식별자를 자동 추출해 근거 검사에 전달한다.
