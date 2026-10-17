# NewsCatalystOS ↔ EraLeader: completed daily publication connection

## User-visible flow

The exact news article and its economic event remain in the original ThemeStore.
The news company card also shows the matched, completed EraLeader daily snapshot:
DART issuer/stock identity, annual CFS observations, completed KRX session close,
producer support/weakening reasons and missing valuation evidence. This is not a
new financial evaluator, order instruction, live quote or certification of benefit.

## Interfaces and persistence

- Existing `/api/themes` now includes configured additional news scopes. Original
  base theme IDs remain unchanged. Additional stores have stable source-qualified
  theme IDs and retain `export_origin` with the original ID, SHA and decision time.
  `/api/themes?scope=base` retains the old restricted view; `scope=company`,
  `scope=nist`, or `scope=all` selects explicit independent stores. The normal
  v1/v2 envelope remains accepted by the existing EraLeader reader.
- `/api/era-assessment?entity_id=...` returns only the received, time-available
  producer assessment. The existing article and daily theme cards use the same
  data. Unsupported/missing/ambiguous identities remain N/A.
- `import_era_daily_snapshot.py` and the optional `--era-daily-config` /
  `--era-daily-root` arguments of the existing approved RSS runner read one
  completed publication referenced by EraLeader's operations home. They copy it
  into NewsCatalystOS's owner-only, content-addressed receipt store. An identical
  source preserves its first import time; a changed source creates a new receipt.
  An unavailable producer does not stop news collection.
- Configuration contains only `era_root` and
  `source: OPERATIONS_CURRENT_KR_DAILY`; it is private, not committed.

## Evidence boundaries

A name must match exactly after Unicode/whitespace/case normalization, and the
same published daily row must bind its security code to an official annual DART
issuer and receipt. Duplicate names/share classes are not arbitrarily selected.
The producer's candidate-browser SHA and same-company order are checked. Financial,
price and review data are copied as attributed producer observations, not rebuilt.

Local import time is content-addressed and gates all reads. An identity-enriched
export advances its derived decision/identity-recording time while retaining the
original event, original source times and original theme SHA. It never rewrites a
news source, turns a plan into execution, or backdates imported corporate context.
Signed supply-chain graphs are not rewritten for convenience.

## Scope

Only NewsCatalystOS code, its private received snapshots and its own dashboard /
existing hourly research runner are changed. EraLeader source, DB, Git, schedules,
original published reports, and official DART/KRX/SEC collectors remain untouched.
The existing EraLeader reader/matcher is exercised read-only against the export;
no new EraLeader-side persistent import or ranking scheduler is installed here.

Verification: focused normal/duplicate/corruption/PIT/company mismatch cases and
actual SK hynix article → exact DART issuer → producer annual CFS/dated quote →
news card and daily view. US/absent company assessment is explicitly separate.
