# 1_1 — EraLeader 공식자료 읽기 전용 공유 계약 (실제 연결 전)

## 현재 구현과 한계

`src/newscatalystos/source_share.py`는 EraLeader의 공식 수집기를 import/실행하지 않는 순수 Python 읽기 전용 소비자입니다. V1.0 산업 검증 범위는 반도체 한 산업만 유지합니다.

**실제 연결 상태: DATA_UNAVAILABLE.** 2026-10-13 현재 EraLeader의 공식 API private `first_receipt.json`과 `official_api_pit_bridge.py` 존재는 확인했지만, 아래 계약 형태의 독립 SHA 핀을 가진 **게시 완료된 소비자용 export가 실제 존재한다는 증명은 확보하지 않았습니다.** 이 모듈을 작성/모의 검증한 것과 실제 DART·SEC·KRX 자료 성공 연동은 다릅니다. 기존 EraLeader 코드를 수정하지 않으며 원본 운영 DB, raw API bytes, 사용권 미확인 자료를 외부에 복제하지 않습니다.

## 생산자/소비자 경계

- 생산자는 EraLeader 측에서 **명시적인 별도 합의 후** `<eraleader>/output/<게시된 상대 경로>/`에 불변 형태로 export합니다. 작성/검증 중에는 이 경로에 COMPLETE를 공개하지 않아야 하며, 스테이징 폴더를 완료된 이름으로 원자적으로 바꾸고 마지막에 `publication.json`을 게시하거나, 완결된 디렉터리 전체를 원자적으로 publish해야 합니다.
- 소비자는 `read_verified_bundle(bundle_dir, era_root, expected_manifest_sha256, decision_at, now=...)`를 호출합니다. `expected_manifest_sha256`는 **manifest나 publication.json 자체에서 복사하지 않은**, 독립적으로 신뢰·기록된 SHA pin이어야 합니다.
- 모든 검사는 실패 시 `SourceShareError`로 중단하고 원본 데이터를 변경하지 않습니다. 허용 범위는 EraLeader의 `output/` 하위 절대 경로에 있는 일반 파일이며 심볼릭 링크·의도하지 않은 경로 이탈을 차단합니다.
- 원본은 변화하지 않아야 하고 신규 데이터가 필요하면 별도 snapshot ID로 publish합니다. 네트워크 재수집·SQLite 열기/쓰기·키 조회를 하지 않습니다.

## 파일 계약 (세 파일을 같은 게시된 snapshot 폴더에 위치)

**`manifest.json`** (UTF-8 JSON, 중복 키 금지)

```json
{
  "schema": "newscatalyst.source_manifest.v1",
  "status": "COMPLETE",
  "quality_status": "PASS",
  "publisher_id": "eraleader",
  "snapshot_id": "synth001",
  "provider_id": "DART",
  "source_id": "dart-disclosures",
  "source_schema_version": "eraleader.receipt.v1",
  "published_at": "2026-10-12T10:02:00Z",
  "first_seen_at": "2026-10-12T10:01:00Z",
  "first_receipt_sha256": "<64 lowercase hex>",
  "events_file": "events.jsonl",
  "events_sha256": "<64 lowercase hex>",
  "events_size_bytes": 0,
  "event_count": 0
}
```

`provider_id`는 `DART | SEC | KRX`만 인정합니다. `first_receipt_sha256`는 EraLeader의 별도 검증된 최초 수신 영수증의 SHA이자 각 이벤트의 원천 영수증 바인딩 값입니다. provider-specific timestamp precision은 원본 PIT 제한을 준수해야 합니다(예: DART 접수 **날짜**를 임의로 최초 발표 분시각으로 간주하지 않음).

**`events.jsonl`** — 각 줄에 메타데이터 객체 하나, 기사 본문·유료 원문·인증키 포함 금지.

```json
{"schema":"newscatalyst.raw_event.v1","event_id":"ev001","source_id":"dart-disclosures","provider_id":"DART","source_document_id":"doc001","company_id":null,"published_at":"2026-10-12T10:00:00Z","first_seen_at":"2026-10-12T10:01:00Z","source_sha256":"<64 lowercase hex>","source_receipt_sha256":"<manifest.first_receipt_sha256>"}
```

**`publication.json`** — 게시 완료 표식. manifest SHA와 구체적 게시 시각이 있어야 하며 pinned SHA와 일치해야 합니다.

```json
{"schema":"newscatalyst.publication.v1","status":"COMPLETE","publisher_id":"eraleader","published_at":"2026-10-12T10:02:00Z","manifest_sha256":"<external trust pinned manifest SHA>"}
```

## 거부 규칙

- 마커 없거나 `status != COMPLETE`, quality 미합격, manifest SHA pin 불일치, 원본 크기/이벤트 SHA/개수 불일치.
- 미래 `published_at`/`first_seen_at`, timezone 없는 시각, `decision_at`보다 늦게 게시·수신된 이벤트, 실제 `now`보다 미래 `decision_at`.
- 출처 위조/허용되지 않은 provider, 이벤트별 수신 SHA 불일치, 중복 event_id, 경로 탈출·심볼릭 링크.
- 허용 범위를 벗어나는 JSON/JSONL 크기(이벤트 최대 10,000개/16 MiB). 제한은 처음부터 페일클로즈이며 향후 승인된 배치 단위로 조정.

## 테스트 및 실제 연결 조건

```bash
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 -m pytest -q tests/test_source_share.py
```

현재 테스트는 **100% 합성 데이터**, 외부 HTTP/운영 DB 미접근. 다음 실제 연결에는 EraLeader 측 정식 게시 경로·별도 SHA 핀·출처별 시각 의미를 먼저 확정하고, 원본 파일 사전/사후 SHA 동일성을 각각 독립 비교해야 합니다. 본 소비자 구현만으로 EraLeader API 연동 완료, 실시간 운영, 1_1 종료 합격으로 표시할 수 없습니다.
